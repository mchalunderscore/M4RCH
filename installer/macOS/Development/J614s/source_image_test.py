import unittest

import source_image_audit


class SourceImageTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "os_list": [
                {
                    "omarchy_target": "apple-silicon-full-os",
                    "partitions": [
                        {"volume_id": "0xE8DC7E45"},
                        {"image": "boot.img"},
                        {"image": "root.img"},
                    ],
                }
            ]
        }
        self.root = "root-uuid"
        self.boot = "boot-uuid"
        self.fstab = "\n".join(
            [
                "UUID=root-uuid / btrfs subvol=root,compress=zstd:1 0 0",
                "UUID=root-uuid /home btrfs subvol=home 0 0",
                "UUID=boot-uuid /boot ext4 defaults 0 2",
                "UUID=E8DC-7E45 /boot/efi vfat defaults 0 2",
            ]
        )
        self.layout = (
            "format=1\nroot_uuid=root-uuid\nboot_uuid=boot-uuid\nroot_subvolume=root\n"
        )
        self.hooks = "HOOKS=(asahi aurora-vendor sd-encrypt aurora-root filesystems)"
        self.grub = "search --fs-uuid boot-uuid\nlinux /vmlinuz-linux-aurora root=UUID=root-uuid rootflags=subvol=root\ninitrd /initramfs-linux-aurora.img\n"

    def validate(self):
        return source_image_audit.validate_contents(
            self.metadata,
            self.root,
            self.boot,
            self.fstab,
            self.layout,
            self.hooks,
            self.grub,
        )

    def test_verified_layout_and_rejection_of_wrong_root(self):
        self.assertEqual(self.validate()["esp_fat_uuid"], "E8DC-7E45")
        self.fstab = self.fstab.replace("subvol=root", "subvol=wrong")
        with self.assertRaises(ValueError):
            self.validate()

    def test_rejects_missing_encryption_hook_and_wrong_grub_root(self):
        self.hooks = self.hooks.replace("sd-encrypt ", "")
        with self.assertRaises(ValueError):
            self.validate()
        self.hooks = "HOOKS=(asahi aurora-vendor sd-encrypt aurora-root filesystems)"
        self.grub = (
            self.grub.replace("root=UUID=root-uuid", "root=UUID=wrong")
            + "# root-uuid\n"
        )
        with self.assertRaises(ValueError):
            self.validate()


if __name__ == "__main__":
    unittest.main()
