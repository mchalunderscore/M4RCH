"""Portable card-assembly checks; no disk tools or host policy are invoked."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import card


def identifier(number):
    return f"aaaaaaaa-bbbb-4ccc-8ddd-{number:012x}"


class CardLayoutTests(unittest.TestCase):


    def test_mount_requires_verified_volume_below_volumes(self):
        info = {"DeviceIdentifier": "disk11s1", "VolumeUUID": identifier(5), "MountPoint": "/Volumes/m4rch"}
        dutil = Mock()
        dutil.info.return_value = info
        self.assertEqual(card.mounted(dutil, "disk11s1"), Path("/Volumes/m4rch"))
        dutil.run.assert_not_called()
        for mount in ("/", "/System/Volumes/Data", "relative", "/Volumes"):
            with self.subTest(mount=mount):
                dutil.info.return_value = dict(info, MountPoint=mount)
                with self.assertRaises(ValueError):
                    card.mounted(dutil, "disk11s1")
        dutil.info.side_effect = [info, dict(info, VolumeUUID=identifier(99))]
        with self.assertRaisesRegex(ValueError, "does not belong"):
            card.mounted(dutil, "disk11s1")

    def test_mount_rechecks_identity_after_mounting(self):
        info = {"DeviceIdentifier": "disk11s1", "VolumeUUID": identifier(5)}
        mounted = dict(info, MountPoint="/Volumes/m4rch")
        dutil = Mock()
        dutil.info.side_effect = [info, mounted, mounted]
        self.assertEqual(card.mounted(dutil, "disk11s1"), Path("/Volumes/m4rch"))
        dutil.run.assert_called_once_with("mount", "disk11s1")


if __name__ == "__main__":
    unittest.main()
