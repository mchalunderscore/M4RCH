"""macOS disk inventory and fail-closed SD-card target validation.

Inspection never mounts, repairs, formats, blesses, or changes boot policy.
Callers must recheck a saved plan immediately before any destructive operation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import plistlib
import re
import subprocess

from common import run


WHOLE = re.compile(r"disk[0-9]+\Z")
SLICE = re.compile(r"(disk[0-9]+)s[0-9]+\Z")
PROTECTED_CONTENT = {"Apple_APFS_ISC", "Apple_APFS_Recovery"}
IDENTITY_FIELDS = (
    "DeviceIdentifier", "DeviceNode", "TotalSize", "DeviceBlockSize",
    "Internal", "VirtualOrPhysical", "WholeDisk", "Writable", "BusProtocol",
    "DeviceTreePath", "MediaName", "Removable", "RemovableMedia", "Ejectable",
    "IORegistryEntryID", "MediaUUID", "SerialNumber",
)
LAYOUT_FIELDS = (
    "DeviceIdentifier", "Content", "Size", "DiskUUID", "VolumeUUID",
    "APFSContainerUUID", "ContainerReference", "DesignatedPhysicalStore",
    "Roles", "APFSVolumeGroupID", "PartitionMapPartitionOffset",
)


def device_name(value):
    if not isinstance(value, str):
        raise ValueError("The target must be a whole disk such as /dev/disk4")
    name = value.removeprefix("/dev/")
    if not WHOLE.fullmatch(name):
        raise ValueError("The target must be a whole disk such as /dev/disk4; slices and raw nodes are refused")
    return name


def _descendant(name, whole):
    return isinstance(name, str) and (name == whole or re.fullmatch(re.escape(whole) + r"s[0-9]+(?:s[0-9]+)?", name))


def _nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nodes(child)


def _layout(value):
    """Exclude mount state, mutable usage counts and other volatile metadata."""
    rows = [{key: node[key] for key in LAYOUT_FIELDS if key in node}
            for node in _nodes(value) if any(key in node for key in LAYOUT_FIELDS)]
    rows.sort(key=lambda item: json.dumps(item, sort_keys=True))
    return rows


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class DiskUtil:
    def get(self, *args):
        result = subprocess.run(["/usr/sbin/diskutil", *map(str, args)],
                                check=True, stdout=subprocess.PIPE)
        return plistlib.loads(result.stdout)

    def run(self, *args):
        return run(["/usr/sbin/diskutil", *args])

    def info(self, target):
        return self.get("info", "-plist", target)

    def list(self):
        return self.get("list", "-plist")

    def apfs(self):
        return self.get("apfs", "list", "-plist")

    def image_info(self):
        result = subprocess.run(["/usr/bin/hdiutil", "info", "-plist"],
                                check=True, stdout=subprocess.PIPE)
        return plistlib.loads(result.stdout)

    def root_stores(self, apfs):
        """Protect whole physical disks containing either live System or Data."""
        containers = {item["ContainerReference"]: item for item in apfs.get("Containers", [])}
        result = set()
        for mount in ("/", "/System/Volumes/Data"):
            info = self.info(mount)
            reference = info.get("APFSContainerReference")
            container = containers.get(reference)
            if container is None:
                raise ValueError(f"Cannot resolve the APFS container for current {mount}; refusing disk operations")
            stores = {entry.get("DeviceIdentifier") for entry in container.get("PhysicalStores", [])}
            direct = {entry.get("APFSPhysicalStore") for entry in info.get("APFSPhysicalStores", [])}
            if not stores or None in stores or (direct and direct != stores):
                raise ValueError(f"Cannot unambiguously resolve physical stores for current {mount}")
            for store in stores:
                match = SLICE.fullmatch(store) if isinstance(store, str) else None
                if match is None:
                    raise ValueError(f"Invalid current-system physical store: {store!r}")
                store_info = self.info(store)
                parent = store_info.get("ParentWholeDisk")
                if store_info.get("DeviceIdentifier") != store or parent != match.group(1):
                    raise ValueError(f"Cannot resolve parent disk of current-system store {store}")
                parent_info = self.info(parent)
                if parent_info.get("DeviceIdentifier") != parent or parent_info.get("WholeDisk") is not True:
                    raise ValueError(f"Cannot verify current-system whole disk {parent}")
                result.add(parent)
        if not result:
            raise ValueError("No current-system physical disks could be protected")
        return sorted(result)

    def _image_path(self, name, info, token):
        if not isinstance(token, dict) or set(token) != {"device", "path"}:
            raise ValueError("A rehearsal requires an attached-image device/path token")
        if device_name(token["device"]) != name or info.get("VirtualOrPhysical") != "Virtual":
            raise ValueError("Rehearsal target is not the specified virtual image device")
        image = Path(token["path"]).resolve(strict=True)
        if not image.is_file():
            raise ValueError("The rehearsal backing path must be a regular disk-image file")
        for attached in self.image_info().get("images", []):
            backing = attached.get("image-path")
            if not isinstance(backing, str) or Path(backing).resolve() != image:
                continue
            devices = {entity.get("dev-entry") for entity in attached.get("system-entities", [])}
            if "/dev/" + name in devices:
                return str(image)
        raise ValueError("hdiutil does not associate this whole device with the rehearsal image")

    def inspect_target(self, device, config, allow_image=None):
        name = device_name(device)
        info = self.info(name)
        if info.get("DeviceIdentifier") != name or info.get("DeviceNode") != "/dev/" + name:
            raise ValueError("diskutil returned a different target device")
        if info.get("WholeDisk") is not True or info.get("Writable") is not True:
            raise ValueError("The target must be a writable whole disk")
        inventory = self.list()
        apfs = self.apfs()
        roots = self.root_stores(apfs)
        if name in roots:
            raise ValueError("Refusing a disk containing the current System or Data volume")
        disks = [item for item in inventory.get("AllDisksAndPartitions", [])
                 if item.get("DeviceIdentifier") == name]
        if name not in inventory.get("WholeDisks", []) or len(disks) != 1:
            raise ValueError("The target is missing or ambiguous in the whole-disk inventory")
        target = disks[0]
        related = [target]
        for item in inventory.get("AllDisksAndPartitions", []):
            if item is not target and _descendant(item.get("DeviceIdentifier"), name):
                related.append(item)
        for container in apfs.get("Containers", []):
            if any(_descendant(store.get("DeviceIdentifier"), name)
                   for store in container.get("PhysicalStores", [])):
                related.append(container)
        if any(node.get("Content") in PROTECTED_CONTENT for item in related for node in _nodes(item)):
            raise ValueError("Refusing a disk containing Apple system boot or recovery storage")
        image_path = None
        if allow_image is not None:
            image_path = self._image_path(name, info, allow_image)
            kind = "image"
        else:
            path = info.get("DeviceTreePath", "")
            if (info.get("VirtualOrPhysical") != "Physical"
                    or info.get("BusProtocol") != "Secure Digital"
                    or info.get("Removable") is not True
                    or info.get("RemovableMedia") is not True
                    or info.get("Ejectable") is not True
                    or not isinstance(path, str)
                    or re.search(r"/pcie-sdreader@[0-9a-fA-F]+\Z", path) is None):
                raise ValueError("Only a removable physical card in the built-in SD reader is accepted")
            kind = "sd"
        size = info.get("TotalSize")
        image_gib, stub_gib = config.get("image_gib"), config.get("stub_gib", 4)
        if any(type(value) is not int or value <= 0 for value in (image_gib, stub_gib)):
            raise ValueError("Image and stub sizes must be positive integer GiB values")
        required = (image_gib + stub_gib + 1) * 1024**3
        if type(size) is not int or size < required or target.get("Size") != size:
            raise ValueError(f"Target size is inconsistent or smaller than required {required} bytes")
        fingerprint = {key: info.get(key) for key in IDENTITY_FIELDS}
        if image_path:
            stat = Path(image_path).stat()
            fingerprint["image"] = {"path": image_path, "device": stat.st_dev, "inode": stat.st_ino}
        return {
            "device": name, "node": "/dev/" + name, "bytes": size,
            "media_name": info.get("MediaName", ""),
            "bus_protocol": info.get("BusProtocol", ""),
            "device_tree_path": info.get("DeviceTreePath", ""),
            "kind": kind, "root_stores": roots, "required_bytes": required,
            "fingerprint": fingerprint,
            "layout_fingerprint": _digest([_layout(item) for item in related]),
        }

    def assert_unchanged(self, summary, config, allow_image=None):
        current = self.inspect_target(summary["device"], config, allow_image)
        if (current["fingerprint"] != summary["fingerprint"]
                or current["layout_fingerprint"] != summary["layout_fingerprint"]):
            raise ValueError("Target identity or partition layout changed since the plan; create a new plan")
        return current


def inspect_target(device, config, allow_image=None, dutil=None):
    return (dutil or DiskUtil()).inspect_target(device, config, allow_image)
