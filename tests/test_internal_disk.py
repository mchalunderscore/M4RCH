"""No physical disks: fixture checks for the one permitted partition operation."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import internal_disk as internal

GIB = 1024**3


def uid(number):
    return f"00000000-0000-4000-8000-{number:012x}"


class FakeDiskUtil:
    def __init__(self):
        self.commands = []
        self.after_hook = None
        self.volume_mount = "/Volumes/M4RCH"
        self.limits = {"ContainerCurrentSize": 100 * GIB, "CurrentSize": 100 * GIB,
                       "MaximumSize": 100 * GIB, "MinimumSizeNoGuard": 40 * GIB,
                       "MinimumSizePreferred": 50 * GIB, "Type": "APFSContainerReference"}
        self.disk = {"DeviceIdentifier": "disk0", "DeviceNode": "/dev/disk0",
                     "TotalSize": 110 * GIB, "DeviceBlockSize": 4096, "Internal": True,
                     "VirtualOrPhysical": "Unknown", "WholeDisk": True, "Writable": True,
                     "BusProtocol": "Apple Fabric", "DeviceTreePath": "IODeviceTree:/arm-io/ans@123/iop-ans-nub/AppleANS3CGv2Controller",
                     "MediaName": "APPLE SSD", "Removable": False, "RemovableMedia": False,
                     "Ejectable": False, "Content": "GUID_partition_scheme"}
        self.parts = [self.part("disk0s1", 1, "Apple_APFS_ISC", 24576, GIB),
                      self.part("disk0s2", 2, "Apple_APFS", GIB + 24576, 100 * GIB),
                      self.part("disk0s3", 3, "Apple_APFS_Recovery", 101 * GIB + 24576, 5 * GIB)]
        self.containers = [self.container("disk1", 11, self.parts[0], [self.volume("disk1s1", 101, "iSCPreboot", ["Preboot"])]),
                           self.container("disk2", 12, self.parts[2], [self.volume("disk2s1", 102, "Recovery", ["Recovery"])]),
                           self.container("disk3", 13, self.parts[1], [self.volume("disk3s1", 103, "Macintosh HD - Data", ["Data"]),
                                                                    self.volume("disk3s3", 104, "Macintosh HD", ["System"])])]
        self.roots = {"/": {"DeviceIdentifier": "disk3s3s1", "APFSSnapshot": True,
                             "APFSContainerReference": "disk3", "APFSVolumeGroupID": uid(20),
                             "APFSPhysicalStores": [{"APFSPhysicalStore": "disk0s2"}], "VolumeUUID": uid(200)},
                      "/System/Volumes/Data": {"DeviceIdentifier": "disk3s1", "APFSSnapshot": False,
                             "APFSContainerReference": "disk3", "APFSVolumeGroupID": uid(20),
                             "APFSPhysicalStores": [{"APFSPhysicalStore": "disk0s2"}], "VolumeUUID": uid(103)}}

    @staticmethod
    def part(device, number, content, offset, size):
        return {"DeviceIdentifier": device, "DiskUUID": uid(number), "Content": content,
                "PartitionMapPartitionOffset": offset, "Size": size, "WholeDisk": False,
                "Internal": True, "ParentWholeDisk": "disk0"}

    @staticmethod
    def volume(device, number, name, roles):
        return {"DeviceIdentifier": device, "APFSVolumeUUID": uid(number), "Name": name,
                "Roles": roles, "Locked": False, "Encryption": False,
                "FileVault": False, "CryptoMigrationOn": False, "CapacityInUse": 1024**2}

    @staticmethod
    def container(reference, number, part, volumes):
        return {"ContainerReference": reference, "APFSContainerUUID": uid(number),
                "CapacityCeiling": part["Size"], "DesignatedPhysicalStore": part["DeviceIdentifier"],
                "PhysicalStores": [{"DeviceIdentifier": part["DeviceIdentifier"],
                                   "DiskUUID": part["DiskUUID"], "Size": part["Size"]}], "Volumes": volumes}

    def info(self, target):
        if target in self.roots:
            return copy.deepcopy(self.roots[target])
        if target == "disk0":
            return copy.deepcopy(self.disk)
        for part in self.parts:
            if part["DeviceIdentifier"] == target:
                return copy.deepcopy(part)
        for container in self.containers:
            for volume in container["Volumes"]:
                if volume["DeviceIdentifier"] == target:
                    return {"DeviceIdentifier": target, "VolumeUUID": volume["APFSVolumeUUID"],
                            "APFSContainerReference": container["ContainerReference"],
                            "APFSVolumeGroupID": uid(20) if container["ContainerReference"] == "disk3" else uid(30),
                            "MountPoint": self.volume_mount}
        raise AssertionError(f"Unexpected diskutil info target {target!r}")

    def list(self):
        return {"WholeDisks": ["disk0"], "AllDisksAndPartitions": [
            {"DeviceIdentifier": "disk0", "Content": "GUID_partition_scheme", "Size": self.disk["TotalSize"],
             "Partitions": copy.deepcopy(self.parts)}]}

    def apfs(self):
        return {"Containers": copy.deepcopy(self.containers)}

    def get(self, *args):
        if args != ("apfs", "resizeContainer", "disk3", "limits", "-plist"):
            raise AssertionError(f"Unexpected diskutil get {args!r}")
        return copy.deepcopy(self.limits)

    def run(self, *args):
        expected = ("apfs", "resizeContainer", "disk3", f"{100 * GIB - internal.STUB_BYTES - internal.GAP_BYTES}B",
                    "APFS", "M4RCH", f"{internal.STUB_BYTES}B", "Free Space", "unused", "0")
        if args != expected:
            raise AssertionError(f"Unsafe/unexpected mutation {args!r}")
        self.commands.append(args)
        main = self.parts[1]
        main["Size"] -= internal.STUB_BYTES + internal.GAP_BYTES
        self.containers[2]["CapacityCeiling"] = main["Size"]
        self.containers[2]["PhysicalStores"][0]["Size"] = main["Size"]
        new = self.part("disk0s4", 4, "Apple_APFS", main["PartitionMapPartitionOffset"] + main["Size"], internal.STUB_BYTES)
        self.parts.append(new)
        self.containers.append(self.container("disk4", 14, new, [self.volume("disk4s1", 105, internal.VOLUME_NAME, [])]))
        if self.after_hook:
            self.after_hook(self)


class InternalDiskTests(unittest.TestCase):
    def create(self, disk, plan=None):
        plan = plan or internal.inspect(disk)
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(internal.os, "geteuid", return_value=0), patch.object(internal, "Path", return_value=Path(temporary)):
                return internal.create(disk, plan)

    def test_readonly_plan_resolves_actual_apple_unknown_physical_type(self):
        disk = FakeDiskUtil()
        plan = internal.inspect(disk)
        self.assertEqual(plan["main"]["system_uuid"], uid(104).upper())
        self.assertEqual(plan["main"]["vgid"], uid(20).upper())
        self.assertEqual(plan["main"]["target_bytes"], 100 * GIB - internal.STUB_BYTES - internal.GAP_BYTES)
        self.assertEqual(plan["resize_argv"][-4:], ["4294967296B", "Free Space", "unused", "0"])
        self.assertEqual(json.loads(json.dumps(plan)), plan)
        self.assertEqual(disk.commands, [])

    def test_rejects_wrong_host_transport_external_virtual_or_removable(self):
        for key, value in (("BusProtocol", "Secure Digital"), ("Internal", False), ("VirtualOrPhysical", "Virtual"),
                           ("Removable", True), ("Writable", False), ("DeviceTreePath", "/virtual/disk")):
            disk = FakeDiskUtil()
            disk.disk[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                internal.inspect(disk)
            self.assertEqual(disk.commands, [])

    def test_rejects_split_current_system_and_data_or_changed_uuid(self):
        for key, value in (("APFSContainerReference", "disk9"), ("APFSVolumeGroupID", uid(999)),
                           ("VolumeUUID", uid(999)), ("APFSPhysicalStores", [{"APFSPhysicalStore": "disk0s3"}])):
            disk = FakeDiskUtil()
            disk.roots["/System/Volumes/Data"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                internal.inspect(disk)

    def test_refuses_multistore_locked_and_missing_apple_recovery(self):
        for change in ("multiple", "locked", "recovery"):
            disk = FakeDiskUtil()
            if change == "multiple":
                disk.containers[2]["PhysicalStores"].append(copy.deepcopy(disk.containers[0]["PhysicalStores"][0]))
            elif change == "locked":
                disk.containers[2]["Volumes"][0]["Locked"] = True
            else:
                disk.parts[2]["Content"] = "Apple_APFS"
            with self.subTest(change=change), self.assertRaises(ValueError):
                internal.inspect(disk)

    def test_refuses_repeated_creation_name(self):
        disk = FakeDiskUtil()
        disk.containers[2]["Volumes"][0]["Name"] = internal.VOLUME_NAME
        with self.assertRaisesRegex(ValueError, "already exists"):
            internal.inspect(disk)

    def test_limits_must_match_current_container_and_allow_preferred_minimum(self):
        for key, value in (("CurrentSize", 99 * GIB), ("MinimumSizePreferred", 99 * GIB),
                           ("MinimumSizePreferred", None), ("MinimumSizeNoGuard", 60 * GIB),
                           ("Type", "APFSPhysicalStore")):
            disk = FakeDiskUtil()
            disk.limits[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                internal.inspect(disk)

    def test_create_requires_root_without_any_mutation(self):
        disk = FakeDiskUtil()
        plan = internal.inspect(disk)
        with patch.object(internal.os, "geteuid", return_value=501), self.assertRaises(PermissionError):
            internal.create(disk, plan)
        self.assertEqual(disk.commands, [])

    def test_revalidates_stable_identities_and_command_before_mutation(self):
        for change in ("uuid", "name", "command", "gap", "unexpected_key"):
            disk = FakeDiskUtil()
            plan = internal.inspect(disk)
            if change == "uuid":
                disk.parts[0]["DiskUUID"] = uid(999)
            elif change == "name":
                disk.containers[2]["Volumes"][0]["Name"] = "Changed"
            elif change == "command":
                plan["resize_argv"] = ["eraseDisk", "APFS", "Oops", "disk0"]
            elif change == "gap":
                plan["gap_bytes"] = 0
            else:
                plan["extra"] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.create(disk, plan)
            self.assertEqual(disk.commands, [])

    def test_usage_limits_rechecked_without_requiring_identical_volatile_counts(self):
        disk = FakeDiskUtil()
        plan = internal.inspect(disk)
        disk.limits["MinimumSizePreferred"] += GIB
        receipt = self.create(disk, plan)
        self.assertEqual(receipt["container"], "disk4")
        self.assertEqual(receipt["initial_volume_uuid"], uid(105).upper())
        self.assertEqual(len(disk.commands), 1)
        disk = FakeDiskUtil()
        plan = internal.inspect(disk)
        disk.limits["MinimumSizePreferred"] = 99 * GIB
        with self.assertRaises(ValueError):
            self.create(disk, plan)
        self.assertEqual(disk.commands, [])

    def test_preserves_existing_partitions_and_volumes_and_never_rolls_back(self):
        for change in ("uuid", "offset", "size", "content", "volume"):
            disk = FakeDiskUtil()
            def bad_after(d):
                if change == "volume":
                    d.containers[0]["Volumes"][0]["APFSVolumeUUID"] = uid(999)
                else:
                    key = {"uuid": "DiskUUID", "offset": "PartitionMapPartitionOffset", "size": "Size", "content": "Content"}[change]
                    d.parts[0][key] = uid(999) if change == "uuid" else "Apple_APFS" if change == "content" else d.parts[0][key] + 4096
            disk.after_hook = bad_after
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.create(disk)
            self.assertEqual(len(disk.commands), 1)

    def test_new_container_must_be_separate_exact_size_and_lone_roleless_volume(self):
        for change in ("size", "role", "extra_volume", "name"):
            disk = FakeDiskUtil()
            def bad_after(d):
                container = d.containers[-1]
                volume = container["Volumes"][0]
                if change == "size":
                    d.parts[-1]["Size"] += 4096
                elif change == "role":
                    volume["Roles"] = ["Data"]
                elif change == "extra_volume":
                    container["Volumes"].append(d.volume("disk4s2", 106, "Unexpected", []))
                else:
                    volume["Name"] = "Unexpected"
            disk.after_hook = bad_after
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.create(disk)
            self.assertEqual(len(disk.commands), 1)

    def test_hardware_encryption_without_filevault_is_a_valid_blank_volume(self):
        disk = FakeDiskUtil()
        disk.after_hook = lambda d: d.containers[-1]["Volumes"][0].update(Encryption=True)
        receipt = self.create(disk)
        self.assertEqual(receipt["initial_volume_uuid"], uid(105).upper())
        self.assertEqual(len(disk.commands), 1)

    def test_blank_volume_rejects_filevault_locks_migration_and_unknown_states(self):
        for key, value in (("FileVault", True), ("FileVault", None),
                           ("Locked", True), ("Locked", None),
                           ("CryptoMigrationOn", True), ("CryptoMigrationOn", None),
                           ("Encryption", None), ("Encryption", "true"), ("Encryption", 1)):
            disk = FakeDiskUtil()
            disk.after_hook = lambda d: d.containers[-1]["Volumes"][0].update({key: value})
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.create(disk)
            self.assertEqual(len(disk.commands), 1)

    def test_recovers_completed_creation_readonly_without_repeating_resize(self):
        disk = FakeDiskUtil()
        plan = internal.inspect(disk)
        disk.run(*plan["resize_argv"])
        disk.containers[-1]["Volumes"][0]["Encryption"] = True
        with tempfile.TemporaryDirectory() as temporary:
            mount = Path(temporary)
            for name in (".Trashes", ".Spotlight-V100", ".fseventsd"):
                (mount / name).mkdir()
            with patch.object(internal.os, "geteuid", return_value=501), patch.object(internal, "Path", return_value=mount):
                receipt = internal.recover_created(disk, plan)
        self.assertEqual(receipt["format"], internal.CREATED_FORMAT)
        self.assertEqual(receipt["plan"], plan)
        self.assertEqual(receipt["container_uuid"], uid(14).upper())
        self.assertEqual(receipt["initial_volume_uuid"], uid(105).upper())
        self.assertEqual(len(disk.commands), 1)

    def test_recovery_rejects_changed_layout_or_populated_destination(self):
        for change in ("unresized", "main_uuid", "old_partition", "extra_volume", "contents"):
            disk = FakeDiskUtil()
            plan = internal.inspect(disk)
            if change != "unresized":
                disk.run(*plan["resize_argv"])
            if change == "main_uuid":
                disk.containers[2]["APFSContainerUUID"] = uid(999)
            elif change == "old_partition":
                disk.parts[0]["PartitionMapPartitionOffset"] += 4096
            elif change == "extra_volume":
                disk.containers[-1]["Volumes"].append(disk.volume("disk4s2", 106, "Unexpected", []))
            with tempfile.TemporaryDirectory() as temporary:
                mount = Path(temporary)
                if change == "contents":
                    (mount / "user-data.txt").write_text("do not replace")
                with patch.object(internal, "Path", return_value=mount):
                    with self.subTest(change=change), self.assertRaises(ValueError):
                        internal.recover_created(disk, plan)
            self.assertEqual(len(disk.commands), 0 if change == "unresized" else 1)

    def test_blank_volume_rejects_files_and_symlink_bookkeeping(self):
        for kind in ("file", "symlink"):
            disk = FakeDiskUtil()
            plan = internal.inspect(disk)
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary)
                if kind == "file":
                    (path / "precious.txt").write_text("user data")
                else:
                    (path / ".fseventsd").symlink_to(path, target_is_directory=True)
                with patch.object(internal.os, "geteuid", return_value=0), patch.object(internal, "Path", return_value=path):
                    with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "unexpected files"):
                        internal.create(disk, plan)
            self.assertEqual(len(disk.commands), 1)

    def test_creation_failure_is_not_retried_or_rolled_back(self):
        disk = FakeDiskUtil()
        plan = internal.inspect(disk)
        def fail(*args):
            disk.commands.append(args)
            raise RuntimeError("diskutil failed after a possible partial resize")
        disk.run = fail
        with patch.object(internal.os, "geteuid", return_value=0), self.assertRaises(RuntimeError):
            internal.create(disk, plan)
        self.assertEqual(len(disk.commands), 1)

    def test_receipt_allows_boot_volume_setup_and_re_resolves_gpt_device_numbers(self):
        disk = FakeDiskUtil()
        receipt = self.create(disk)
        new_container = disk.containers[-1]
        new_container["Volumes"][0]["Roles"] = ["Data"]
        new_container["Volumes"].append(disk.volume("disk4s2", 106, "M4RCH", ["System"]))
        disk.parts[-1]["DeviceIdentifier"] = "disk0s5"
        new_container["PhysicalStores"][0]["DeviceIdentifier"] = "disk0s5"
        new_container["DesignatedPhysicalStore"] = "disk0s5"
        result = internal.validate_created(disk, receipt)
        self.assertEqual(result["store"], "disk0s5")
        self.assertEqual(len(result["volumes"]), 2)
        self.assertEqual(len(disk.commands), 1)
        receipt["container_uuid"] = uid(999)
        with self.assertRaisesRegex(ValueError, "receipt"):
            internal.validate_created(disk, receipt)


if __name__ == "__main__":
    unittest.main()
