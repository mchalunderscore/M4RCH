import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from card_disk import DiskUtil, device_name


GIB = 1024**3
CONFIG = {"image_gib": 8, "stub_gib": 4}


class FakeDiskUtil(DiskUtil):
    def __init__(self):
        self.infos = {
            "disk4": {
                "DeviceIdentifier": "disk4", "DeviceNode": "/dev/disk4",
                "TotalSize": 32 * GIB, "DeviceBlockSize": 512,
                "Internal": True, "VirtualOrPhysical": "Physical",
                "WholeDisk": True, "Writable": True,
                "BusProtocol": "Secure Digital", "MediaName": "Built In SDXC Reader",
                "DeviceTreePath": "IODeviceTree:/arm-io@10F00000/apcie0@B0000000/pci-bridge1@1/pcie-sdreader@0",
                "Removable": True, "RemovableMedia": True, "Ejectable": True,
            },
            "/": {"APFSContainerReference": "disk3", "APFSPhysicalStores": [{"APFSPhysicalStore": "disk0s2"}]},
            "/System/Volumes/Data": {"APFSContainerReference": "disk3", "APFSPhysicalStores": [{"APFSPhysicalStore": "disk0s2"}]},
            "disk0s2": {"DeviceIdentifier": "disk0s2", "ParentWholeDisk": "disk0"},
            "disk0": {"DeviceIdentifier": "disk0", "WholeDisk": True},
        }
        self.inventory = {
            "WholeDisks": ["disk0", "disk3", "disk4"],
            "AllDisksAndPartitions": [{"DeviceIdentifier": "disk4", "Size": 32 * GIB,
                "Content": "FDisk_partition_scheme", "Partitions": [
                    {"DeviceIdentifier": "disk4s1", "Content": "Windows_NTFS",
                     "Size": 31 * GIB, "VolumeUUID": "card-volume-id", "MountPoint": "/Volumes/ARCHM4"}]}],
        }
        self.containers = {"Containers": [{"ContainerReference": "disk3", "PhysicalStores": [{"DeviceIdentifier": "disk0s2"}]}]}
        self.images = {"images": []}

    def info(self, target):
        return copy.deepcopy(self.infos[target])

    def list(self):
        return copy.deepcopy(self.inventory)

    def apfs(self):
        return copy.deepcopy(self.containers)

    def image_info(self):
        return copy.deepcopy(self.images)

    def run(self, *args):
        raise AssertionError("Validation must never mutate a disk")


class CardDiskTests(unittest.TestCase):
    def test_actual_internal_sd_reader_shape_is_accepted(self):
        disk = FakeDiskUtil()
        summary = disk.inspect_target("/dev/disk4", CONFIG)
        self.assertEqual(summary["kind"], "sd")
        self.assertEqual(summary["root_stores"], ["disk0"])
        self.assertEqual(summary["required_bytes"], 13 * GIB)
        self.assertTrue(summary["fingerprint"]["Internal"])

    def test_rejects_slices_raw_nodes_and_ambiguous_names(self):
        for target in ("disk4s1", "/dev/rdisk4", "../disk4", "disk4\n", "disk4;echo", ""):
            with self.subTest(target=target), self.assertRaises(ValueError):
                device_name(target)

    def test_rejects_ssd_usb_virtual_readonly_and_nonremovable_targets(self):
        for key, value in (("DeviceTreePath", "IODeviceTree:/arm-io/ans@0/AppleANS"),
                           ("BusProtocol", "USB"), ("VirtualOrPhysical", "Virtual"),
                           ("Writable", False), ("WholeDisk", False),
                           ("Removable", False), ("RemovableMedia", False), ("Ejectable", False)):
            with self.subTest(key=key):
                disk = FakeDiskUtil()
                disk.infos["disk4"][key] = value
                with self.assertRaises(ValueError):
                    disk.inspect_target("disk4", CONFIG)

    def test_rejects_current_system_store_even_if_it_looks_like_sd(self):
        disk = FakeDiskUtil()
        for mount in ("/", "/System/Volumes/Data"):
            disk.infos[mount]["APFSPhysicalStores"] = [{"APFSPhysicalStore": "disk4s2"}]
        disk.containers["Containers"][0]["PhysicalStores"] = [{"DeviceIdentifier": "disk4s2"}]
        disk.infos["disk4s2"] = {"DeviceIdentifier": "disk4s2", "ParentWholeDisk": "disk4"}
        with self.assertRaisesRegex(ValueError, "current System or Data"):
            disk.inspect_target("disk4", CONFIG)

    def test_rejects_sibling_data_volume_on_target_physical_disk(self):
        disk = FakeDiskUtil()
        disk.infos["/System/Volumes/Data"] = {"APFSContainerReference": "disk7", "APFSPhysicalStores": [{"APFSPhysicalStore": "disk4s9"}]}
        disk.containers["Containers"].append({"ContainerReference": "disk7", "PhysicalStores": [{"DeviceIdentifier": "disk4s9"}]})
        disk.infos["disk4s9"] = {"DeviceIdentifier": "disk4s9", "ParentWholeDisk": "disk4"}
        with self.assertRaisesRegex(ValueError, "current System or Data"):
            disk.inspect_target("disk4", CONFIG)

    def test_missing_or_inconsistent_current_root_mapping_fails_closed(self):
        for change in ("missing_container", "empty_stores", "inconsistent_stores", "missing_parent"):
            with self.subTest(change=change):
                disk = FakeDiskUtil()
                if change == "missing_container":
                    disk.infos["/"]["APFSContainerReference"] = "disk99"
                elif change == "empty_stores":
                    disk.containers["Containers"][0]["PhysicalStores"] = []
                elif change == "inconsistent_stores":
                    disk.infos["/"]["APFSPhysicalStores"] = [{"APFSPhysicalStore": "disk4s2"}]
                else:
                    del disk.infos["disk0s2"]["ParentWholeDisk"]
                with self.assertRaises(ValueError):
                    disk.inspect_target("disk4", CONFIG)

    def test_rejects_boot_and_recovery_partitions(self):
        for content in ("Apple_APFS_ISC", "Apple_APFS_Recovery"):
            with self.subTest(content=content):
                disk = FakeDiskUtil()
                disk.inventory["AllDisksAndPartitions"][0]["Partitions"][0]["Content"] = content
                with self.assertRaisesRegex(ValueError, "system boot or recovery"):
                    disk.inspect_target("disk4", CONFIG)

    def test_capacity_and_inventory_size_must_agree_and_fit(self):
        for size, listed in ((12 * GIB, 12 * GIB), (32 * GIB, 31 * GIB), (None, 32 * GIB)):
            with self.subTest(size=size, listed=listed):
                disk = FakeDiskUtil()
                disk.infos["disk4"]["TotalSize"] = size
                disk.inventory["AllDisksAndPartitions"][0]["Size"] = listed
                with self.assertRaisesRegex(ValueError, "size"):
                    disk.inspect_target("disk4", CONFIG)

    def test_remount_does_not_change_plan_but_card_or_partition_change_does(self):
        disk = FakeDiskUtil()
        summary = disk.inspect_target("disk4", CONFIG)
        part = disk.inventory["AllDisksAndPartitions"][0]["Partitions"][0]
        part["MountPoint"] = "/Volumes/ARCHM4 1"
        disk.assert_unchanged(summary, CONFIG)
        part["VolumeUUID"] = "different-card-volume"
        with self.assertRaisesRegex(ValueError, "changed since the plan"):
            disk.assert_unchanged(summary, CONFIG)
        part["VolumeUUID"] = "card-volume-id"
        disk.infos["disk4"]["MediaName"] = "Different Card"
        with self.assertRaisesRegex(ValueError, "changed since the plan"):
            disk.assert_unchanged(summary, CONFIG)

    def test_image_requires_virtual_device_and_verified_backing_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary) / "test.img"
            image.write_bytes(b"test image fixture")
            disk = FakeDiskUtil()
            token = {"device": "disk4", "path": str(image)}
            disk.images = {"images": [{"image-path": str(image), "system-entities": [{"dev-entry": "/dev/disk4"}]}]}
            with self.assertRaisesRegex(ValueError, "virtual image"):
                disk.inspect_target("disk4", CONFIG, token)
            disk.infos["disk4"]["VirtualOrPhysical"] = "Virtual"
            self.assertEqual(disk.inspect_target("disk4", CONFIG, token)["kind"], "image")
            disk.images["images"][0]["system-entities"][0]["dev-entry"] = "/dev/disk8"
            with self.assertRaisesRegex(ValueError, "hdiutil"):
                disk.inspect_target("disk4", CONFIG, token)


if __name__ == "__main__":
    unittest.main()
