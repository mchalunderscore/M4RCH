import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import card


class CardHostTests(unittest.TestCase):
    def test_flash_source_must_resolve_to_another_physical_disk(self):
        dutil = Mock()
        dutil.info.side_effect = lambda target: ({"APFSPhysicalStores": [{"APFSPhysicalStore": "disk0s2"}]}
                                                if target == "/dev/disk3s5" else {"ParentWholeDisk": "disk0"})
        with patch("card.subprocess.check_output", return_value="Filesystem Blocks Used Available Capacity Mounted on\n/dev/disk3s5 1 1 0 100% /System/Volumes/Data\n"):
            card.source_off_target(dutil, Path("out/arch-m4.img"), "disk4")
            with self.assertRaisesRegex(ValueError, "outside"):
                card.source_off_target(dutil, Path("out/arch-m4.img"), "disk0")
        with patch("card.subprocess.check_output", return_value="Filesystem Blocks Used Available Capacity Mounted on\nserver:/share 1 1 0 100% /Volumes/share\n"):
            with self.assertRaisesRegex(ValueError, "local disk"):
                card.source_off_target(dutil, Path("out/arch-m4.img"), "disk4")

    def test_flash_readback_checks_exact_image_extent(self):
        with tempfile.TemporaryDirectory() as temporary:
            disk = Path(temporary) / "disk.img"
            disk.write_bytes(b"image" + b"unused card space")
            expected = hashlib.sha256(b"image").hexdigest()
            card.verify_flashed(disk, 5, expected)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                card.verify_flashed(disk, 6, expected)
            with self.assertRaisesRegex(ValueError, "boundary"):
                card.verify_flashed(disk, 100, expected)


    def test_mount_rejects_live_system_paths_without_writes(self):
        for mount in ("/", "/System/Volumes/Data", "/System/Volumes/Preboot", "relative/path"):
            with self.subTest(mount=mount):
                dutil = Mock()
                dutil.info.return_value = {"DeviceIdentifier": "disk5s1", "MountPoint": mount, "VolumeUUID": "abc"}
                with self.assertRaises(ValueError):
                    card.mounted(dutil, "disk5s1")
                dutil.run.assert_not_called()

    def test_mount_rejects_directory_resolving_to_different_volume(self):
        dutil = Mock()
        dutil.info.side_effect = [
            {"DeviceIdentifier": "disk5s1", "MountPoint": "/Volumes/ArchM4", "VolumeUUID": "target"},
            {"DeviceIdentifier": "disk3s1", "MountPoint": "/Volumes/ArchM4", "VolumeUUID": "system"},
        ]
        with self.assertRaisesRegex(ValueError, "does not belong"):
            card.mounted(dutil, "disk5s1")
        dutil.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
