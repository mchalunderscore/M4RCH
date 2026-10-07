import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sdboot'))
import enrollment
spec=importlib.util.spec_from_file_location('stub_transaction',ROOT/'sdboot/stub_upgrade.py')
transaction=importlib.util.module_from_spec(spec);spec.loader.exec_module(transaction)


class StubTransactionTests(unittest.TestCase):
    def test_replacements_leave_owner_and_loader_alone(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            files={'System': ['System/Library/CoreServices/SystemVersion.plist',
                    '.IAPhysicalMedia','Finish Installation.app/Contents/Info.plist'],
                   'Preboot': ['restore/Firmware/agx/gpu.im4p'],
                   'Recovery': ['usr/standalone/firmware/arm64eBaseSystem.dmg'],
                   'Data': ['private/var/db/dslocal/file']}
            for role,names in files.items():
                for name in names:
                    p=root/role/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('test')
            result=transaction.replacement_paths(root)
            self.assertEqual(result['System'],['System/Library/CoreServices/SystemVersion.plist'])
            self.assertNotIn('Data',result)
            self.assertEqual(result['Preboot'],['restore/Firmware/agx/gpu.im4p'])

    def test_inventory_never_follows_external_link(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'restore').symlink_to('/Volumes/Preboot/UUID/restore')
            value=transaction.inventory(root)
            self.assertEqual(value['restore']['kind'],'link')
            self.assertEqual(set(value),{'restore'})

    def test_rollback_skips_identical_immutable_objects(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'owner').write_text('untouched')
            expected=transaction.inventory(root)
            with patch.object(transaction,'run') as run:
                transaction.restore_tree(root,root,expected)
            run.assert_not_called()

    def test_changed_backup_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'roles/System/file';p.parent.mkdir(parents=True);p.write_text('old')
            value=transaction.inventory(p.parent)
            p.write_text('modified')
            with self.assertRaisesRegex(ValueError,'Rollback copy changed'):
                transaction.validate_backup(root,{'backup_inventory':{'System':value},'host_inventory':{}})

    @unittest.skipUnless(sys.platform == 'darwin', 'Requires native macOS ditto')
    def test_rollback_restores_changed_file_and_preserves_other_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'backup';destination=root/'installed'
            source.mkdir();destination.mkdir()
            (source/'firmware').write_bytes(b'old firmware')
            (source/'owner').write_bytes(b'original owner')
            (destination/'firmware').write_bytes(b'new firmware')
            (destination/'owner').write_bytes(b'original owner')
            expected=transaction.inventory(source)
            transaction.restore_tree(source,destination,expected)
            self.assertEqual(transaction.inventory(destination),expected)

    @unittest.skipUnless(sys.platform == 'darwin', 'Requires native copyfile')
    def test_backup_keeps_immutable_source_and_records_flags_separately(self):
        import os
        import stat
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';source.mkdir()
            (source/'db').mkdir()
            owner=source/'db/owner';owner.write_bytes(b'owner metadata')
            (source/'link').symlink_to('db/owner')
            os.chflags(owner,stat.UF_IMMUTABLE)
            try:
                expected=transaction.inventory(source)
                actual=transaction.copy_backup_tree(source,root/'backup',expected)
                self.assertEqual(transaction.inventory(source),expected)
                self.assertEqual((root/'backup/db/owner').read_bytes(),b'owner metadata')
                self.assertEqual((root/'backup/link').readlink(),Path('db/owner'))
                self.assertEqual(actual['db/owner']['flags'] & stat.UF_IMMUTABLE,0)
                record={'backup_inventory':{'System':expected},
                        'backup_storage_inventory':{'System':actual},'host_inventory':{}}
                (root/'roles').mkdir();(root/'backup').rename(root/'roles/System')
                transaction.validate_backup(root,record)
                (root/'roles/System/db/owner').write_bytes(b'tampered')
                with self.assertRaisesRegex(ValueError,'Rollback copy changed'):
                    transaction.validate_backup(root,record)
            finally:
                os.chflags(owner,0)

    @unittest.skipUnless(sys.platform == 'darwin', 'Requires native flags and ditto')
    def test_rollback_reapplies_recorded_flags_from_writable_backup(self):
        import os
        import stat
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'backup';destination=root/'installed'
            source.mkdir();destination.mkdir()
            (source/'owner').write_bytes(b'original')
            (destination/'owner').write_bytes(b'changed')
            expected=transaction.inventory(source)
            expected['owner']['flags']=stat.UF_IMMUTABLE
            try:
                transaction.restore_tree(source,destination,expected)
                self.assertEqual(transaction.inventory(destination),expected)
            finally:
                os.chflags(destination/'owner',0)

    def test_upgrade_accepts_legacy_receipt_and_preserves_existing_inputs(self):
        record={'candidate_manifest_sha256':'target hash','backup':'saved backup'}
        legacy={'identity':{'apple_build':'25F84'},'partition':{'unchanged':True}}
        updated=transaction.upgraded_state(legacy,record)
        self.assertEqual(updated['identity']['apple_build'],'25G83')
        self.assertEqual(updated['bootstrap_inputs'],{'stub_manifest_sha256':'target hash'})
        self.assertEqual(updated['partition'],legacy['partition'])
        self.assertNotIn('bootstrap_inputs',legacy)
        modern={**legacy,'bootstrap_inputs':{'owner_sha256':'owner hash'}}
        self.assertEqual(transaction.upgraded_state(modern,record)['bootstrap_inputs']['owner_sha256'],'owner hash')

    def test_resume_allows_declared_payload_but_rejects_owner_or_loader_change(self):
        from common import sha256
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);mounts={role:root/role for role in ('System','Data','Preboot','Recovery')}
            for mount in mounts.values():mount.mkdir()
            resources=mounts['System']/transaction.card.RESOURCES;resources.mkdir(parents=True)
            boot=resources/'boot.bin';boot.write_bytes(b'working stage1')
            owner=mounts['Preboot']/'owner';owner.write_bytes(b'protected')
            payload=mounts['System']/'firmware';payload.write_bytes(b'old')
            record={'replacements':{'System':['firmware'],'Preboot':[],'Recovery':[]},
                    'backup_inventory':{role:transaction.inventory(mount) for role,mount in mounts.items()},
                    'boot_sha256':sha256(boot)}
            payload.write_bytes(b'new')
            transaction.validate_resume(mounts,record)
            owner.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Protected installed object'):
                transaction.validate_resume(mounts,record)
            owner.write_bytes(b'protected');boot.write_bytes(b'wrong stage1')
            with self.assertRaisesRegex(ValueError,'Protected installed object'):
                transaction.validate_resume(mounts,record)

    def test_resume_ignores_only_generated_data_spotlight_index(self):
        from common import sha256
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);mounts={role:root/role for role in ('System','Data','Preboot','Recovery')}
            for mount in mounts.values():mount.mkdir()
            resources=mounts['System']/transaction.card.RESOURCES;resources.mkdir(parents=True)
            boot=resources/'boot.bin';boot.write_bytes(b'working stage1')
            index=mounts['Data']/transaction.SPOTLIGHT_INDEX;index.mkdir(parents=True)
            journal=index/'journalAttr.23';journal.write_bytes(b'old generated data')
            owner=mounts['Data']/'private/var/db/dslocal/owner';owner.parent.mkdir();owner.write_bytes(b'owner')
            record={'replacements':{'System':[],'Preboot':[],'Recovery':[]},
                    'backup_inventory':{role:transaction.inventory(mount) for role,mount in mounts.items()},
                    'boot_sha256':sha256(boot)}
            journal.write_bytes(b'new generated data');(index/'new-index').write_bytes(b'new')
            transaction.validate_resume(mounts,record)
            # Saved backups still validate every file, including their frozen index.
            self.assertNotEqual(transaction.inventory(mounts['Data']),record['backup_inventory']['Data'])
            owner.write_bytes(b'changed owner')
            with self.assertRaisesRegex(ValueError,'Protected installed object'):
                transaction.validate_resume(mounts,record)
            owner.write_bytes(b'owner')
            import shutil
            shutil.rmtree(index);index.symlink_to(root/'System',target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'Spotlight index root'):
                transaction.validate_resume(mounts,record)

    def test_resumed_stage_uses_recorded_replacement_set(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);system=root/'System';resources=system/transaction.card.RESOURCES
            resources.mkdir(parents=True);(resources/'boot.bin').write_bytes(b'changed')
            record={'backup':str(root/'backup'),'replacements':{'System':['firmware']},
                    'boot_sha256':'not the current hash'}
            with patch.object(transaction,'copy_replacements') as copier:
                with self.assertRaisesRegex(ValueError,'protected Linux loader'):
                    transaction.stage_upgrade(root/'candidate',root,record,{}, {},{},None,{'System':system})
            copier.assert_called_once_with(root/'candidate/payload',{'System':system},record['replacements'])

    def test_pending_upgrade_blocks_normal_loader_staging(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            state=out/'stub-upgrade-state.json'
            state.write_text(json.dumps({'phase':'awaiting-recovery'}))
            with self.assertRaisesRegex(ValueError,'pending Apple stub upgrade'):
                enrollment._check_stub_upgrade(out)
            state.write_text(json.dumps({'phase':'complete'}))
            enrollment._check_stub_upgrade(out)

    def test_unknown_candidate_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source/System';source.mkdir(parents=True)
            (source/'escape').symlink_to('/etc/passwd');destination=root/'destination';destination.mkdir()
            with self.assertRaisesRegex(ValueError,'escapes role'):
                transaction.copy_replacements(root/'source',{'System':destination},{'System':['escape']})
            self.assertFalse((destination/'escape').exists())

    def test_forced_enrollment_is_bound_to_build(self):
        text=(ROOT/'sdboot/recovery-enroll.sh').read_text()
        self.assertIn('[ "$FORCE_ENROLLMENT" = 0 ]',text)
        self.assertIn('stub-enrolled.txt',text)
        self.assertIn('STUB_BUILD=',text)


if __name__=='__main__':unittest.main()
