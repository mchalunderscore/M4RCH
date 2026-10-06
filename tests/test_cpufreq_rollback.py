import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('clock_restore', Path(__file__).resolve().parents[1]/'experiments/cpufreq-snapshot/restore-boot.py')
restore = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(restore)


class RollbackTests(unittest.TestCase):
    def prepare(self, root):
        kit = root/'cpufreq-snapshot-01'; kit.mkdir()
        old, new = b'accepted-kernel', b'diagnostic-kernel'
        (root/'vmlinuz-linux-m4rch').write_bytes(new)
        (root/'initramfs-linux-m4rch.img').write_bytes(b'current-initrd')
        backup = kit/'rollback-boot'; backup.mkdir()
        (backup/'vmlinuz-linux-m4rch').write_bytes(old)
        (backup/'initramfs-linux-m4rch.img').write_bytes(b'accepted-initrd')
        receipt = {'kernel_image_sha256':hashlib.sha256(new).hexdigest(),
                   'accepted_kernel_image_sha256':hashlib.sha256(old).hexdigest(),
                   'boot_uuid_linux':'EXPECTED'}
        (kit/'build.json').write_text(json.dumps(receipt))
        (kit/'rollback-boot.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in backup.iterdir()}))
        return kit

    def invoke(self, kit, uuid='EXPECTED'):
        def read(cmd, **kwargs):
            if cmd[0] == 'blkid': return uuid+'\n'
            return ('vfat\n' if 'FSTYPE' in cmd else '/dev/example\n')
        with patch.object(restore, '__file__', str(kit/'restore-boot.py')), patch.object(restore.os,'geteuid',return_value=0), patch.object(restore.platform,'system',return_value='Linux'), patch.object(restore.subprocess,'check_output',side_effect=read), patch.object(restore.subprocess,'run'):
            restore.main()

    def test_restore_exact_accepted_payload(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve();kit = self.prepare(root)
            self.invoke(kit)
            self.assertEqual((root/'vmlinuz-linux-m4rch').read_bytes(),b'accepted-kernel')
            self.assertEqual((root/'initramfs-linux-m4rch.img').read_bytes(),b'accepted-initrd')

    def test_different_card_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve();kit = self.prepare(root)
            with self.assertRaises(ValueError): self.invoke(kit,'OTHER')
            self.assertEqual((root/'vmlinuz-linux-m4rch').read_bytes(),b'diagnostic-kernel')

    def test_corrupt_backup_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve();kit = self.prepare(root)
            (kit/'rollback-boot/initramfs-linux-m4rch.img').write_bytes(b'corrupt')
            with self.assertRaises(ValueError): self.invoke(kit)
            self.assertEqual((root/'vmlinuz-linux-m4rch').read_bytes(),b'diagnostic-kernel')
            self.assertEqual((root/'initramfs-linux-m4rch.img').read_bytes(),b'current-initrd')

    def test_unrelated_current_kernel_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve();kit = self.prepare(root)
            (root/'vmlinuz-linux-m4rch').write_bytes(b'later-generation')
            with self.assertRaises(ValueError): self.invoke(kit)
            self.assertEqual((root/'vmlinuz-linux-m4rch').read_bytes(),b'later-generation')

    def test_symlink_destination_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve();kit = self.prepare(root)
            p = root/'initramfs-linux-m4rch.img';p.unlink();p.symlink_to(kit/'rollback-boot/initramfs-linux-m4rch.img')
            with self.assertRaises(ValueError): self.invoke(kit)
            self.assertEqual((root/'vmlinuz-linux-m4rch').read_bytes(),b'diagnostic-kernel')


if __name__ == '__main__': unittest.main()
