import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('idle_rollback', Path(__file__).resolve().parents[1] / 'experiments/t6040-idle/select-normal.py')
rollback = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rollback)

class IdleRollback(unittest.TestCase):
    def fixture(self, root):
        kit = root / 'idle-trial-01'; kit.mkdir()
        (root/'grub').mkdir()
        (root/'vmlinuz-linux-m4rch').write_bytes(b'normal kernel')
        (root/'initramfs-linux-m4rch.img').write_bytes(b'normal initrd')
        normal=b'set default=m4rch-normal\n';trial=b'set default=m4rch-idle\n'
        (kit/'grub-normal.cfg').write_bytes(normal);(kit/'grub-trial.cfg').write_bytes(trial)
        (root/'grub/grub.cfg').write_bytes(trial)
        h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        receipt={'normal_kernel_sha256':h(root/'vmlinuz-linux-m4rch'),'initramfs_sha256':h(root/'initramfs-linux-m4rch.img')}
        for name in ('grub-normal.cfg','grub-trial.cfg'):receipt[name+'_sha256']=h(kit/name)
        (kit/'build.json').write_text(json.dumps(receipt));(kit/'card.json').write_text(json.dumps({'macos_volume_uuid':'expected-card'}))
        return kit,{'MountPoint':str(root),'VolumeUUID':'expected-card'},normal,trial

    def test_switch_preserves_kernel(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);kit,info,normal,trial=self.fixture(root)
            rollback.select(root,kit,info)
            self.assertEqual((root/'grub/grub.cfg').read_bytes(),normal)
            self.assertEqual((root/'vmlinuz-linux-m4rch').read_bytes(),b'normal kernel')

    def test_wrong_card_or_changed_cfg_rejected_before_write(self):
        for failure in ('card','cfg','backup','kernel','symlink'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as d:
                root=Path(d);kit,info,normal,trial=self.fixture(root)
                cfg=root/'grub/grub.cfg'
                if failure=='card':info['VolumeUUID']='other'
                elif failure=='cfg':cfg.write_bytes(b'edited')
                elif failure=='backup':(kit/'grub-normal.cfg').write_bytes(b'bad')
                elif failure=='kernel':(root/'vmlinuz-linux-m4rch').write_bytes(b'other')
                else:
                    cfg.unlink();cfg.symlink_to(kit/'grub-trial.cfg')
                before=cfg.read_bytes()
                with self.assertRaises(ValueError):rollback.select(root,kit,info)
                self.assertEqual(cfg.read_bytes(),before)

if __name__ == '__main__':unittest.main()
