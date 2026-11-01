import hashlib
import unittest

import build_m4rch_grub


class GrubTests(unittest.TestCase):
    def setUp(self):
        self.source = (
            b"linux-aurora linux-aurora linux-aurora linux-aurora\n"
            b"linux /vmlinuz-linux-aurora root=UUID=example\n"
            b"initrd /initramfs-linux-aurora.img\n"
            b"linux /vmlinuz-linux-aurora root=UUID=example\n"
            b"initrd /initramfs-linux-aurora.img\n"
        )
        self.digest = hashlib.sha256(self.source).hexdigest()

    def test_only_kernel_names_change_and_tampering_is_rejected(self):
        candidate = build_m4rch_grub.render(self.source, self.digest)
        self.assertEqual(
            candidate.replace(b" " + build_m4rch_grub.BOOT_OPTIONS, b"").replace(
                b"linux-m4rch", b"linux-aurora"
            ),
            self.source,
        )
        self.assertEqual(candidate.count(build_m4rch_grub.BOOT_OPTIONS), 2)
        self.assertIn(b"modprobe.blacklist=snd_soc_tas2764,snd_soc_tas2770", candidate)
        with self.assertRaises(ValueError):
            build_m4rch_grub.render(self.source + b"# changed\n", self.digest)

    def test_wrong_boot_entry_is_rejected_even_with_matching_hash(self):
        changed = self.source.replace(
            b"linux /vmlinuz-linux-aurora", b"linux /different-kernel", 1
        )
        with self.assertRaises(ValueError):
            build_m4rch_grub.render(changed, hashlib.sha256(changed).hexdigest())


if __name__ == "__main__":
    unittest.main()
