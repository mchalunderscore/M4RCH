import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stub_upgrade', ROOT / 'scripts/prepare-stub-upgrade.py')
upgrade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upgrade)


class StubUpgradeTests(unittest.TestCase):
    def identity(self):
        return {'ApBoardID': '0x04', 'ApChipID': '0x6040',
                'Info': {'DeviceClass': 'j614sap', 'RestoreBehavior': 'Erase', 'Variant': 'macOS Customer'},
                'Manifest': {'iBoot': {'Info': {'Path': 'Firmware/iBoot.im4p'}},
                             'OS': {'Info': {'Path': 'os.dmg.aea'}}}}

    def test_target_build_cannot_be_accepted_by_default_profile(self):
        manifest = {'ProductBuildVersion': upgrade.BUILD, 'BuildIdentities': [self.identity()]}
        with self.assertRaises(ValueError):
            upgrade.stub.select_identity(manifest)
        self.assertEqual(upgrade.stub.select_identity(manifest, upgrade.BUILD), self.identity())
        manifest['BuildIdentities'][0]['ApChipID'] = '0x8132'
        with self.assertRaises(ValueError):
            upgrade.stub.select_identity(manifest, upgrade.BUILD)

    def test_selected_files_include_bootability_but_not_system_image(self):
        archive = Mock()
        archive.infolist.return_value = [Mock(filename=upgrade.stub.BOOTABILITY_PREFIX+'test', is_dir=lambda: False)]
        selected = upgrade.selected_members(archive, self.identity())
        self.assertIn('Firmware/iBoot.im4p', selected)
        self.assertIn(upgrade.stub.BOOTABILITY_PREFIX+'test', selected)
        self.assertNotIn('os.dmg.aea', selected)

    def test_existing_candidate_is_preserved(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temporary:
            with unittest.mock.patch.object(sys, 'platform', 'darwin'):
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    upgrade.prepare(Path(temporary))

    def test_candidate_cannot_repin_its_own_modified_inputs(self):
        import json
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = json.loads(upgrade.PROFILE.read_text())
            lock['files']['SystemVersion.plist']['sha256'] = '0' * 64
            (root / 'target-inputs.lock.json').write_text(json.dumps(lock))
            with self.assertRaisesRegex(ValueError, 'published target profile'):
                upgrade.verify_candidate(root)

    def test_truncated_gfx_container_is_rejected(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / 'gpu.im4p'
            for data in (b'', b'\x30', b'\x30\x82\x10', b'\x30\x10\x16\x04IM4P'):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    upgrade.gfx_metadata(path)


if __name__ == '__main__':
    unittest.main()
