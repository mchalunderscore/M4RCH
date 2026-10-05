"""Existing internal-stub identities against fake disk inventory only."""
import copy
import hashlib
import json
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import card
import internal_boot as internal


def uid(number):
    return f"00000000-0000-4000-8000-{number:012d}"


class InternalBootTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="arch-m4-internal-test-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.project = self.base / "project"
        (self.project / "out").mkdir(parents=True)
        self.host = uid(1)
        self.sd = {"device": "disk7", "root_device": "disk7s2",
                   "root_partition_uuid": uid(5), "root_volume_uuid": uid(6),
                   "root_image": "", "root_uuid": uid(2)}
        self.boot = b"enrolled internal m1n1 and U-Boot loader\x00\xff"
        self.boot_info = {"sha256": hashlib.sha256(self.boot).hexdigest(), "bytes": len(self.boot)}
        self.main = {"vgid": uid(10), "store_uuid": uid(11),
                     "current_bytes": 100 * 1024**3, "target_bytes": 96 * 1024**3}
        self.receipt = {"format": "arch-m4-internal-created-v1", "plan": {"main": self.main},
                        "container": "disk8", "container_uuid": uid(12), "store_uuid": uid(13),
                        "initial_volume_uuid": uid(14), "bytes": 4 * 1024**3}
        self.identity = {
            "schema": 1, "storage_mode": "internal-stub", "platform_uuid": self.host,
            "vgid": uid(15), "store_uuid": self.receipt["store_uuid"],
            "source_macos_vgid": self.main["vgid"], "source_macos_store_uuid": self.main["store_uuid"],
            **self.sd, "status": "prepared", "boot_sha256": self.boot_info["sha256"],
            "boot_bytes": self.boot_info["bytes"],
            "roles": {role: {"uuid": uid(index + 20), "device": f"disk8s{index + 1}"}
                      for index, role in enumerate(("System", "Data", "Preboot", "Recovery"))},
        }
        self.system = self.base / "internal/System"
        self.resources = self.system / card.RESOURCES
        self.resources.mkdir(parents=True)
        (self.resources / "boot.bin").write_bytes(self.boot)
        (self.resources / "card.json").write_text(json.dumps(self.identity))
        self.core = self.system / "System/Library/CoreServices"
        self.core.mkdir(parents=True)
        (self.core / "SystemVersion.plist").write_text("original Apple version metadata")
        (self.system / ".IAPhysicalMedia").write_text("installer")
        self.state = {"format": "arch-m4-internal-boot-v1", "platform_uuid": self.host,
                      "phase": "ready", "partition": self.receipt,
                      "sd": {k: self.sd[k] for k in internal.SD_KEYS}, "identity": copy.deepcopy(self.identity)}
        self.container = {"APFSContainerUUID": self.receipt["container_uuid"], "ContainerReference": "disk8",
                          "Volumes": [{"Roles": [role], "APFSVolumeUUID": entry["uuid"],
                                       "DeviceIdentifier": entry["device"]}
                                      for role, entry in self.identity["roles"].items()]}
        self.dutil = Mock()
        self.dutil.info.return_value = {"MountPoint": str(self.system)}
        self.dutil.apfs.side_effect = lambda: {"Containers": [copy.deepcopy(self.container)]}
        self.dutil.get.side_effect = lambda *args: {"Containers": [{"VolumeGroups": [{
            "APFSVolumeGroupUUID": self.identity["vgid"], "Volumes": [
                {"Role": role, "DeviceIdentifier": self.identity["roles"][role]["device"]}
                for role in ("System", "Data")]}]}]}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(card, "require_macos"))
        self.stack.enter_context(patch.object(card, "platform_uuid", return_value=self.host))
        self.stack.enter_context(patch.object(card.os, "geteuid", return_value=0))
        self.resolve = self.stack.enter_context(patch.object(internal, "resolve_partition"))
        self.write_state()

    def write_state(self):
        (self.project / internal.STATE).write_text(json.dumps(self.state))

    def test_state_rejects_foreign_machine_and_unknown_format(self):
        self.assertEqual(internal.read_state(self.project), self.state)
        for field, value in (("platform_uuid", uid(99)), ("format", "other-format")):
            with self.subTest(field=field):
                self.state[field] = value
                self.write_state()
                with self.assertRaises(ValueError):
                    internal.read_state(self.project)
                self.state[field] = self.host if field == "platform_uuid" else "arch-m4-internal-boot-v1"

    def test_state_path_rejects_symlinks(self):
        path = self.project / internal.STATE
        path.unlink()
        path.symlink_to(self.resources / "card.json")
        with self.assertRaises(ValueError):
            internal.read_state(self.project)

    def test_container_resolution_requires_exactly_one_uuid_match(self):
        self.assertEqual(internal.container_for(self.dutil, self.receipt), self.container)
        for containers in ([], [self.container, self.container]):
            disk = Mock()
            disk.apfs.return_value = {"Containers": containers}
            with self.assertRaises(ValueError):
                internal.container_for(disk, self.receipt)
            disk.run.assert_not_called()

    def test_read_roles_rejects_additional_groups_duplicate_uuids_and_roles(self):
        valid = internal.read_roles(self.dutil, self.container, self.receipt["store_uuid"], self.sd)
        self.assertEqual(valid["roles"], self.identity["roles"])
        for fault in ("extra-role", "missing-role", "duplicate-uuid", "groups", "wrong-member"):
            with self.subTest(fault=fault):
                container = copy.deepcopy(self.container)
                disk = Mock()
                disk.apfs.return_value = {"Containers": [container]}
                disk.get.return_value = self.dutil.get()
                if fault == "extra-role": container["Volumes"].append(copy.deepcopy(container["Volumes"][0]))
                if fault == "missing-role": container["Volumes"].pop()
                if fault == "duplicate-uuid":
                    disk.apfs.return_value["Containers"].append({"Volumes": [copy.deepcopy(container["Volumes"][0])]})
                if fault == "groups":
                    disk.get.return_value["Containers"][0]["VolumeGroups"].append({})
                if fault == "wrong-member":
                    disk.get.return_value["Containers"][0]["VolumeGroups"][0]["Volumes"][0]["DeviceIdentifier"] = "disk3s3"
                with self.assertRaises(ValueError):
                    internal.read_roles(disk, container, self.receipt["store_uuid"], self.sd)
                disk.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
