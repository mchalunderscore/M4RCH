"""Writable remount regressions using the observed macOS System-volume shape."""
import copy
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import card


class WritableMountTests(unittest.TestCase):
    volume = "disk5s2"
    uuid = "00000000-0000-4000-8000-000000000021"
    path = Path("/Volumes/m4rch")

    def info(self, writable=False, **changes):
        value = {"DeviceIdentifier": self.volume, "VolumeUUID": self.uuid,
                 "MountPoint": str(self.path), "Writable": writable,
                 "WritableVolume": writable, "WritableMedia": True,
                 "APFSSnapshot": False, "Sealed": "No", "FilesystemType": "apfs",
                 "ParentWholeDisk": "disk5", "APFSContainerReference": "disk5",
                 "APFSPhysicalStores": [{"APFSPhysicalStore": "disk4s2"}]}
        value.update(changes)
        return value

    def dutil(self, before, after=None, path_after=None):
        dutil = Mock()
        # mounted() resolves device and mountpoint, then the writable helper
        # checks before and both ways again after the mount operation.
        dutil.info.side_effect = [self.info(), self.info(), before,
                                 after or before, path_after or after or before]
        return dutil

    def test_system_remounts_writable_and_retains_exact_identity(self):
        dutil = self.dutil(self.info(), self.info(True))
        with patch("card.run") as run:
            self.assertEqual(card.mounted_writable(dutil, self.volume, self.uuid), self.path)
        run.assert_called_once_with(["/sbin/mount", "-u", "-w", self.path])
        dutil.run.assert_not_called()

    def test_already_writable_retry_does_not_remount(self):
        dutil = self.dutil(self.info(True))
        with patch("card.run") as run:
            self.assertEqual(card.mounted_writable(dutil, self.volume, self.uuid), self.path)
        run.assert_not_called()

    def test_rejects_wrong_identity_snapshots_seals_and_readonly_media_before_command(self):
        for changes in ({"VolumeUUID": "other"}, {"DeviceIdentifier": "disk0s2"},
                        {"MountPoint": "/"}, {"APFSSnapshot": True}, {"Sealed": "Yes"},
                        {"WritableMedia": False}, {"WritableVolume": None}):
            with self.subTest(changes=changes), patch("card.run") as run:
                with self.assertRaises(ValueError):
                    card.mounted_writable(self.dutil(self.info(**changes)), self.volume, self.uuid)
                run.assert_not_called()

    def test_remount_success_must_actually_make_volume_writable(self):
        for after in (self.info(), self.info(True, Writable=False)):
            with self.subTest(after=after), patch("card.run"):
                with self.assertRaisesRegex(ValueError, "still read-only"):
                    card.mounted_writable(self.dutil(self.info(), after), self.volume, self.uuid)

    def test_rechecks_identity_in_both_directions_and_backing_store(self):
        for changes in ({"VolumeUUID": "other"}, {"MountPoint": "/Volumes/other"},
                        {"APFSPhysicalStores": [{"APFSPhysicalStore": "disk0s2"}]}):
            for direction in ("device", "path"):
                after = self.info(True)
                path_after = copy.deepcopy(after)
                (after if direction == "device" else path_after).update(changes)
                with self.subTest(changes=changes, direction=direction), patch("card.run"):
                    with self.assertRaises(ValueError):
                        card.mounted_writable(self.dutil(self.info(), after, path_after), self.volume, self.uuid)

    def test_mount_error_stops_without_claiming_writable(self):
        dutil = self.dutil(self.info())
        with patch("card.run", side_effect=subprocess.CalledProcessError(1, "mount")):
            with self.assertRaises(subprocess.CalledProcessError):
                card.mounted_writable(dutil, self.volume, self.uuid)
        self.assertEqual(dutil.info.call_count, 3)


if __name__ == "__main__":
    unittest.main()
