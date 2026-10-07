import copy
import gzip
import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('nvme_macos',Path(__file__).resolve().parents[1]/'scripts/migrate-nvme-macos.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class OfflineMigrationTests(unittest.TestCase):
    def test_appended_initramfs_overrides_init_preserves_other_files(self):
        original=gzip.compress(m.newc([('init',stat.S_IFREG|0o755,b'old'),('etc/sdboot.conf',stat.S_IFREG|0o644,b"KERNEL_RELEASE='test'\n"),('bin/busybox',stat.S_IFREG|0o755,b'binary')]))
        candidate=original+gzip.compress(m.newc([('init',stat.S_IFREG|0o755,b'new'),('etc/nvme-root.conf',stat.S_IFREG|0o644,b'uuid')]))
        members=m.initramfs_members(candidate)
        self.assertEqual(members['init'],(stat.S_IFREG|0o755,b'new'))
        self.assertEqual(members['bin/busybox'][1],b'binary')
        self.assertEqual(members['etc/nvme-root.conf'][1],b'uuid')

    def test_early_archive_is_preserved_and_main_is_parsed(self):
        early=m.newc([('early',stat.S_IFREG|0o644,b'early')])
        main=gzip.compress(m.newc([('init',stat.S_IFREG|0o755,b'new')]))
        self.assertEqual(m.initramfs_members(early+bytes(23)+main)['init'][1],b'new')

    def test_invalid_archive_rejected(self):
        for data in (b'bad',gzip.compress(b'070701truncated')):
            with self.assertRaises(ValueError):m.initramfs_members(data)

    def test_clone_pads_last_sector_and_reads_back_copy(self):
        with tempfile.TemporaryDirectory() as d:
            source,target=Path(d)/'source',Path(d)/'target'
            content=bytes(range(256))*18
            source.write_bytes(content);target.write_bytes(bytes(8192))
            digest=m.clone(source,target,len(content),8192)
            self.assertEqual(source.read_bytes(),content)
            self.assertEqual(target.read_bytes()[:len(content)],content)
            self.assertEqual(target.read_bytes()[len(content):],bytes(8192-len(content)))
            self.assertEqual(digest,m.hashlib.sha256(content).hexdigest())

    def test_clone_refuses_small_destination_without_writing(self):
        with tempfile.TemporaryDirectory() as d:
            source,target=Path(d)/'source',Path(d)/'target'
            source.write_bytes(bytes(4608));target.write_bytes(b'sentinel')
            with self.assertRaises(ValueError):m.clone(source,target,4608,4096)
            self.assertEqual(target.read_bytes(),b'sentinel')

    def test_archive_creates_module_parents_without_replacing_existing_symlinks(self):
        path='usr/lib/modules/release/kernel/apple-sart.ko'
        files=m.archive_with_parents([(path,stat.S_IFREG|0o644,b'module'),('sbin/loader',stat.S_IFREG|0o755,b'loader')],{'usr':None,'usr/lib':None,'sbin':None})
        names=[name for name,_,_ in files]
        self.assertEqual(names[:3],['usr/lib/modules','usr/lib/modules/release','usr/lib/modules/release/kernel'])
        self.assertNotIn('sbin',names)
        self.assertLess(names.index('usr/lib/modules/release/kernel'),names.index(path))
        self.assertEqual(m.cpio_members(m.newc(files))[path][1],b'module')

    def test_completed_clone_resume_requires_digest_and_exact_targets(self):
        root={'uuid':'root','offset':4096};esp={'uuid':'esp','offset':0}
        state={'phase':'cloning','clone_sha256':'a'*64,'root':root,'esp':esp}
        self.assertTrue(m.completed_clone(state,root,esp))
        self.assertFalse(m.completed_clone({'phase':'partitioned'},root,esp))
        for change in ({'clone_sha256':''},{'root':{'uuid':'other','offset':4096}},{'esp':{'uuid':'esp','offset':4096}}):
            invalid={**state,**change}
            with self.assertRaises(ValueError):m.completed_clone(invalid,root,esp)

    def test_nvme_module_dependencies_are_loaded_before_driver(self):
        deps='kernel/nvme-apple.ko: kernel/nvme-core.ko kernel/apple-sart.ko\nkernel/nvme-core.ko: kernel/helper.ko\nkernel/helper.ko:\nkernel/apple-sart.ko:\n'
        self.assertEqual(m.module_order(deps,'fs/ext4/ext4.ko\n'),['kernel/helper.ko','kernel/nvme-core.ko','kernel/apple-sart.ko','kernel/nvme-apple.ko'])
        self.assertEqual(m.module_order(deps,'kernel/nvme-apple.ko\n'),[])

    def test_missing_dependency_or_cycle_rejected(self):
        for deps in ('kernel/nvme-apple.ko: missing.ko\n','kernel/nvme-apple.ko: kernel/other.ko\nkernel/other.ko: kernel/nvme-apple.ko\n'):
            with self.assertRaises(ValueError):m.module_order(deps,'')

    def test_split_rejects_changed_neighbor_or_gap(self):
        before=[dict(uuid='protected',number=2,offset=0,bytes=4096,type='apfs'),dict(uuid='reserve',number=7,offset=4096,bytes=12288,type=m.BASIC_TYPE)]
        plan=dict(reservation_uuid='reserve',reservation_offset=4096,reservation_bytes=12288,esp_bytes=4096)
        after=[copy.deepcopy(before[0]),dict(uuid='esp',number=7,offset=4096,bytes=4096,type=m.ESP_TYPE),dict(uuid='root',number=5,offset=8192,bytes=8192,type=m.ROOT_TYPE)]
        self.assertEqual(m.validate_split(before,after,plan,True)[1]['uuid'],'root')
        after[0]['number']=6
        self.assertEqual(m.validate_split(before,after,plan,True)[1]['uuid'],'root')
        after[0]['bytes']=8192
        with self.assertRaises(ValueError):m.validate_split(before,after,plan,True)
        after[0]=copy.deepcopy(before[0]);after[2]['offset']+=4096
        with self.assertRaises(ValueError):m.validate_split(before,after,plan,True)

if __name__=='__main__':unittest.main()
