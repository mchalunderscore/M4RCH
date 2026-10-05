"""Plan a separate internal APFS boot container without touching Apple boot storage.

inspect(), recover_created(), and validate_created() are read-only. create() requires root and a plan
which the caller has shown to, and explicitly confirmed with, the user. The
caller also binds that plan to the Mac platform UUID and its chosen SD/config.
No operation in this module erases, deletes, blesses, or changes boot policy.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import re
import stat
import uuid

from card_disk import DiskUtil

GIB = 1024**3
STUB_BYTES = 4 * GIB
GAP_BYTES = 128 * 1024**2
VOLUME_NAME = "M4RCH"
PLAN_FORMAT = "arch-m4-internal-plan-v1"
CREATED_FORMAT = "arch-m4-internal-created-v1"
WHOLE = re.compile(r"disk[0-9]+\Z")
SLICE = re.compile(r"(disk[0-9]+)s[0-9]+\Z")
SYSTEM_SNAPSHOT = re.compile(r"(disk[0-9]+s[0-9]+)s[0-9]+\Z")
DISK_KEYS = ("DeviceIdentifier", "DeviceNode", "TotalSize", "DeviceBlockSize",
             "Internal", "VirtualOrPhysical", "WholeDisk", "Writable",
             "BusProtocol", "DeviceTreePath", "MediaName", "Removable",
             "RemovableMedia", "Ejectable")


def _uuid(value, label):
    try:
        parsed = str(uuid.UUID(value)).upper()
    except (ValueError, AttributeError, TypeError):
        raise ValueError(f"Missing or invalid {label} UUID") from None
    return parsed


def _positive(value, label):
    if type(value) is not int or value <= 0:
        raise ValueError(f"Missing or invalid {label}")
    return value


def _one(items, label):
    if len(items) != 1:
        raise ValueError(f"Cannot identify exactly one {label}")
    return items[0]


def _volume(volume):
    roles = volume.get("Roles")
    if (not isinstance(roles, list) or any(not isinstance(role, str) for role in roles)
            or not SLICE.fullmatch(volume.get("DeviceIdentifier", ""))):
        raise ValueError("Invalid APFS volume identity")
    if volume.get("Locked") is not False:
        raise ValueError("All APFS volumes must be unlocked before partition planning")
    return {"uuid": _uuid(volume.get("APFSVolumeUUID"), "APFS volume"),
            "roles": sorted(roles), "name": volume.get("Name", ""),
            "encrypted": volume.get("Encryption"), "filevault": volume.get("FileVault")}


def _container(container):
    stores = container.get("PhysicalStores", [])
    if not stores:
        raise ValueError("APFS container has no physical stores")
    return {
        "uuid": _uuid(container.get("APFSContainerUUID"), "APFS container"),
        "stores": sorted(_uuid(store.get("DiskUUID"), "physical store") for store in stores),
        "volumes": sorted((_volume(volume) for volume in container.get("Volumes", [])),
                          key=lambda item: item["uuid"]),
    }


def _partition(dutil, listed, whole, block):
    device = listed.get("DeviceIdentifier", "")
    match = SLICE.fullmatch(device)
    if match is None or match.group(1) != whole:
        raise ValueError("Invalid internal partition identifier")
    info = dutil.info(device)
    if (info.get("DeviceIdentifier") != device or info.get("ParentWholeDisk") != whole
            or info.get("WholeDisk") is not False or info.get("Internal") is not True):
        raise ValueError("Internal partition identity changed during inspection")
    part = {"device": device, "uuid": _uuid(info.get("DiskUUID"), "GPT partition"),
            "content": info.get("Content"),
            "offset": _positive(info.get("PartitionMapPartitionOffset"), "partition offset"),
            "bytes": _positive(info.get("Size"), "partition size")}
    if (part["uuid"] != _uuid(listed.get("DiskUUID"), "listed GPT partition")
            or part["content"] != listed.get("Content") or part["bytes"] != listed.get("Size")
            or part["offset"] % block or part["bytes"] % block):
        raise ValueError("Internal partition inventory is inconsistent")
    return part


def _snapshot(dutil):
    """Resolve the running System/Data pair; never accept a caller-selected disk."""
    root = dutil.info("/")
    data = dutil.info("/System/Volumes/Data")
    reference = root.get("APFSContainerReference")
    if (not isinstance(reference, str) or not WHOLE.fullmatch(reference)
            or data.get("APFSContainerReference") != reference):
        raise ValueError("Current System and Data must share one APFS container")
    vgid = _uuid(root.get("APFSVolumeGroupID"), "current System volume group")
    if vgid != _uuid(data.get("APFSVolumeGroupID"), "current Data volume group"):
        raise ValueError("Current System and Data volume groups differ")
    root_device = root.get("DeviceIdentifier", "")
    if root.get("APFSSnapshot") is True:
        match = SYSTEM_SNAPSHOT.fullmatch(root_device)
        if match is None:
            raise ValueError("Cannot resolve the current System snapshot volume")
        root_device = match.group(1)
    if not SLICE.fullmatch(root_device):
        raise ValueError("Cannot resolve the current System volume")
    containers = dutil.apfs().get("Containers", [])
    main = _one([c for c in containers if c.get("ContainerReference") == reference],
                "current macOS APFS container")
    stores = main.get("PhysicalStores", [])
    store = _one(stores, "current macOS physical store")
    store_device = store.get("DeviceIdentifier", "")
    match = SLICE.fullmatch(store_device)
    if match is None or main.get("DesignatedPhysicalStore") != store_device:
        raise ValueError("Cannot resolve a single current macOS physical store")
    whole = match.group(1)
    for info in (root, data):
        direct = info.get("APFSPhysicalStores", [])
        if direct != [{"APFSPhysicalStore": store_device}]:
            raise ValueError("Current System/Data physical-store mapping is inconsistent")
    system = _one([v for v in main.get("Volumes", []) if v.get("DeviceIdentifier") == root_device],
                  "current System volume")
    data_volume = _one([v for v in main.get("Volumes", [])
                        if v.get("DeviceIdentifier") == data.get("DeviceIdentifier")],
                       "current Data volume")
    if system.get("Roles") != ["System"] or data_volume.get("Roles") != ["Data"]:
        raise ValueError("Current System/Data APFS roles are inconsistent")
    system_info = dutil.info(root_device)
    for live, volume in ((system_info, system), (data, data_volume)):
        if (_uuid(live.get("VolumeUUID"), "live volume") != _uuid(volume.get("APFSVolumeUUID"), "listed volume")
                or _uuid(live.get("APFSVolumeGroupID"), "live volume group") != vgid
                or live.get("APFSContainerReference") != reference):
            raise ValueError("Current System/Data volume identity changed during inspection")
    disk = dutil.info(whole)
    # This Mac reports VirtualOrPhysical=Unknown for its built-in ANS SSD.
    # Resolve it through the active root, then require its Apple Fabric path.
    if (disk.get("DeviceIdentifier") != whole or disk.get("DeviceNode") != "/dev/" + whole
            or disk.get("WholeDisk") is not True or disk.get("Internal") is not True
            or disk.get("Writable") is not True or disk.get("BusProtocol") != "Apple Fabric"
            or disk.get("VirtualOrPhysical") not in ("Physical", "Unknown")
            or disk.get("Removable") is not False or disk.get("RemovableMedia") is not False
            or disk.get("Ejectable") is not False or disk.get("Content") != "GUID_partition_scheme"
            or not re.search(r"/ans@[0-9a-fA-F]+/", disk.get("DeviceTreePath", ""))):
        raise ValueError("Current macOS is not on a supported internal Apple SSD")
    block = _positive(disk.get("DeviceBlockSize"), "SSD block size")
    if block != 4096:
        raise ValueError("Only a 4096-byte internal Apple SSD is supported")
    size = _positive(disk.get("TotalSize"), "SSD size")
    inventory = dutil.list()
    listed_disk = _one([item for item in inventory.get("AllDisksAndPartitions", [])
                        if item.get("DeviceIdentifier") == whole], "internal SSD inventory")
    if (whole not in inventory.get("WholeDisks", []) or listed_disk.get("Size") != size
            or listed_disk.get("Content") != "GUID_partition_scheme"):
        raise ValueError("Internal whole-disk inventory is inconsistent")
    partitions = sorted((_partition(dutil, p, whole, block) for p in listed_disk.get("Partitions", [])),
                        key=lambda p: p["offset"])
    if len({p["uuid"] for p in partitions}) != len(partitions):
        raise ValueError("Duplicate internal GPT partition UUIDs")
    for left, right in zip(partitions, partitions[1:]):
        if left["offset"] + left["bytes"] > right["offset"]:
            raise ValueError("Overlapping internal GPT partitions")
    if not partitions or partitions[-1]["offset"] + partitions[-1]["bytes"] >= size:
        raise ValueError("Invalid internal GPT partition bounds")
    for content in ("Apple_APFS_ISC", "Apple_APFS_Recovery"):
        _one([p for p in partitions if p["content"] == content], content + " partition")
    main_part = _one([p for p in partitions if p["device"] == store_device], "current macOS partition")
    if (main_part["content"] != "Apple_APFS"
            or main_part["uuid"] != _uuid(store.get("DiskUUID"), "main physical store")
            or main_part["bytes"] != store.get("Size")
            or main_part["bytes"] != main.get("CapacityCeiling")):
        raise ValueError("Current macOS container and GPT store disagree")
    internal = [c for c in containers if any(SLICE.fullmatch(s.get("DeviceIdentifier", ""))
                and SLICE.fullmatch(s["DeviceIdentifier"]).group(1) == whole
                for s in c.get("PhysicalStores", []))]
    if any(any(SLICE.fullmatch(s.get("DeviceIdentifier", "")) is None
               or SLICE.fullmatch(s["DeviceIdentifier"]).group(1) != whole
               for s in c.get("PhysicalStores", [])) for c in internal):
        raise ValueError("Multi-disk internal APFS containers are unsupported")
    identities = sorted((_container(c) for c in internal), key=lambda c: c["uuid"])
    if len({c["uuid"] for c in identities}) != len(identities):
        raise ValueError("Duplicate internal APFS container UUIDs")
    partition_uuids = {p["uuid"] for p in partitions}
    internal_stores = [store for c in identities for store in c["stores"]]
    if (len(set(internal_stores)) != len(internal_stores)
            or not set(internal_stores).issubset(partition_uuids)):
        raise ValueError("Internal APFS stores do not map uniquely to GPT partitions")
    all_uuids = [v["uuid"] for c in identities for v in c["volumes"]]
    if len(set(all_uuids)) != len(all_uuids):
        raise ValueError("Duplicate internal APFS volume UUIDs")
    return {"disk": {key: disk.get(key) for key in DISK_KEYS},
            "partitions": partitions, "apfs": identities,
            "main": {"container": reference,
                     "container_uuid": _uuid(main.get("APFSContainerUUID"), "main container"),
                     "store": store_device, "store_uuid": main_part["uuid"],
                     "system": root_device, "system_uuid": _uuid(system.get("APFSVolumeUUID"), "System"),
                     "data": data_volume["DeviceIdentifier"],
                     "data_uuid": _uuid(data_volume.get("APFSVolumeUUID"), "Data"),
                     "vgid": vgid, "current_bytes": main_part["bytes"]}}, containers


def inspect(dutil=None):
    """Return a read-only, JSON-serializable, fixed 4 GiB boot-stub plan."""
    dutil = dutil or DiskUtil()
    state, _ = _snapshot(dutil)
    reserved = {label + suffix for label in (VOLUME_NAME, "Arch M4 Boot", "m4rch Boot")
                for suffix in ("", " - Data", " Preboot", " Recovery")}
    if any(v["name"] in reserved for c in state["apfs"] for v in c["volumes"]):
        raise ValueError("An internal Linux boot volume already exists; inspect the previous operation instead of shrinking again")
    main = state["main"]
    target = main["current_bytes"] - STUB_BYTES - GAP_BYTES
    limits = dutil.get("apfs", "resizeContainer", main["container"], "limits", "-plist")
    if (limits.get("Type") != "APFSContainerReference"
            or limits.get("ContainerCurrentSize") != main["current_bytes"]
            or limits.get("CurrentSize") != main["current_bytes"]):
        raise ValueError("Current APFS resize limits do not match the selected container")
    minimum = _positive(limits.get("MinimumSizePreferred"), "preferred APFS minimum size")
    no_guard = _positive(limits.get("MinimumSizeNoGuard"), "absolute APFS minimum size")
    maximum = _positive(limits.get("MaximumSize"), "maximum APFS size")
    if not no_guard <= minimum <= target < main["current_bytes"] <= maximum:
        raise ValueError("macOS cannot safely spare 4 GiB plus a 128 MiB partition gap at its current resize limits")
    main["target_bytes"] = target
    # resizeContainer rejects partitionDisk's R specifier. A trailing free
    # triplet with size 0 keeps the preceding APFS partition at its exact size.
    # This syntax is exercised on an attached disposable image; see docs.
    return {"format": PLAN_FORMAT, **state, "stub_bytes": STUB_BYTES, "gap_bytes": GAP_BYTES,
            "volume_name": VOLUME_NAME, "resize_limits": limits,
            "resize_argv": ["apfs", "resizeContainer", main["container"], f"{target}B",
                            "APFS", VOLUME_NAME, f"{STUB_BYTES}B",
                            "Free Space", "unused", "0"]}


def _stable_plan(plan):
    result = copy.deepcopy(plan)
    result.pop("resize_limits", None)  # Recomputed usage/limits must permit the same command.
    return result


def _partition_identity(part):
    return {k: v for k, v in part.items() if k != "device"}


def _validate_after(dutil, plan):
    current, containers = _snapshot(dutil)
    if current["disk"] != plan["disk"]:
        raise ValueError("Internal SSD identity changed after partition creation")
    old_main = plan["main"]
    new_main = current["main"]
    stable_keys = ("container_uuid", "store_uuid", "system_uuid", "data_uuid", "vgid")
    if (any(old_main[k] != new_main[k] for k in stable_keys)
            or new_main["current_bytes"] != old_main["target_bytes"]):
        raise ValueError("Current macOS identities or resized container size do not match the plan")
    expected = {p["uuid"]: _partition_identity(p) for p in plan["partitions"]}
    expected[old_main["store_uuid"]]["bytes"] = old_main["target_bytes"]
    actual = {p["uuid"]: _partition_identity(p) for p in current["partitions"]}
    if any(actual.get(key) != value for key, value in expected.items()):
        raise ValueError("An existing GPT partition identity, content, offset, or size changed unexpectedly")
    added = _one([p for p in current["partitions"] if p["uuid"] not in expected], "new internal partition")
    original_main = _one([p for p in plan["partitions"] if p["uuid"] == old_main["store_uuid"]], "original main store")
    free_start = original_main["offset"] + old_main["target_bytes"]
    free_end = original_main["offset"] + original_main["bytes"]
    if (added["content"] != "Apple_APFS" or added["bytes"] != STUB_BYTES
            or added["offset"] < free_start or added["offset"] + added["bytes"] > free_end):
        raise ValueError("New boot partition is not exactly 4 GiB within the newly freed range")
    old_containers = {c["uuid"]: c for c in plan["apfs"]}
    now_containers = {c["uuid"]: c for c in current["apfs"]}
    if any(now_containers.get(key) != value for key, value in old_containers.items()):
        raise ValueError("Existing APFS container or volume identities changed unexpectedly")
    created_identity = _one([c for c in current["apfs"] if c["uuid"] not in old_containers], "new internal APFS container")
    if created_identity["stores"] != [added["uuid"]]:
        raise ValueError("New APFS container does not exclusively own the new partition")
    created = _one([c for c in containers if _uuid(c.get("APFSContainerUUID"), "container") == created_identity["uuid"]],
                   "created APFS container")
    if (created.get("CapacityCeiling") != STUB_BYTES
            or created.get("DesignatedPhysicalStore") != added["device"]):
        raise ValueError("Created APFS container size/store is inconsistent")
    return {"container": created["ContainerReference"], "container_uuid": created_identity["uuid"],
            "store": added["device"], "store_uuid": added["uuid"], "bytes": STUB_BYTES}, created


def _check_blank(dutil, created):
    volume = _one(created.get("Volumes", []), "blank initial boot volume")
    _volume(volume)
    # Internal Apple-silicon APFS storage is encrypted even without FileVault.
    # _validate_after has already established the internal Apple SSD identity;
    # distinguish its transparent encryption from password protection instead
    # of demanding Encryption=False. Unknown encryption states remain unsafe.
    if (type(volume.get("Encryption")) is not bool
            or volume.get("FileVault") is not False
            or volume.get("CryptoMigrationOn") is not False):
        raise ValueError("Created boot volume must have known encryption status, FileVault off, and no cryptographic migration")
    if (volume.get("Roles") != [] or volume.get("Name") != VOLUME_NAME
            or type(volume.get("CapacityInUse")) is not int
            or not 0 <= volume["CapacityInUse"] <= 16 * 1024**2):
        raise ValueError("Created boot volume is not a fresh roleless volume")
    info = dutil.info(volume["DeviceIdentifier"])
    mount = info.get("MountPoint")
    if (info.get("DeviceIdentifier") != volume["DeviceIdentifier"]
            or info.get("APFSContainerReference") != created["ContainerReference"]
            or _uuid(info.get("VolumeUUID"), "new mounted volume") != _uuid(volume.get("APFSVolumeUUID"), "new volume")
            or not isinstance(mount, str) or not mount.startswith("/Volumes/")
            or not Path(mount).is_dir() or Path(mount).is_symlink()):
        raise ValueError("Cannot verify the freshly created boot volume mount")
    # macOS may create these bookkeeping directories as soon as it mounts a
    # blank volume. Any other entry is evidence against a fresh destination.
    for entry in Path(mount).iterdir():
        mode = entry.lstat().st_mode
        if entry.name not in {".fseventsd", ".Spotlight-V100", ".Trashes"} or not stat.S_ISDIR(mode):
            raise ValueError("Fresh boot volume contains unexpected files; refusing to populate it")
    return volume


def create(dutil, plan):
    """Execute an explicitly confirmed plan once; never retry or roll back."""
    if os.geteuid() != 0:
        raise PermissionError("Internal partition creation requires root")
    if not isinstance(plan, dict) or plan.get("format") != PLAN_FORMAT:
        raise ValueError("Invalid internal partition plan")
    current = inspect(dutil)
    if _stable_plan(current) != _stable_plan(plan):
        raise ValueError("Internal disk identity or layout changed since the plan; create and confirm a new plan")
    # Exactly one reviewed Apple resize operation; no erase or rollback path.
    dutil.run(*current["resize_argv"])
    return recover_created(dutil, plan)


def recover_created(dutil, plan):
    """Recognize a completed resize with a still-blank destination, read-only.

This recovers the creation receipt when diskutil succeeded but a later check or
process failure interrupted create(). The caller must retain the original plan
and bind it to its confirmed operation; this never repeats the resize.
"""
    if not isinstance(plan, dict) or plan.get("format") != PLAN_FORMAT:
        raise ValueError("Invalid internal partition plan")
    result, container = _validate_after(dutil, plan)
    volume = _check_blank(dutil, container)
    return {"format": CREATED_FORMAT, "plan": copy.deepcopy(plan), **result,
            "initial_volume": volume["DeviceIdentifier"],
            "initial_volume_uuid": _uuid(volume.get("APFSVolumeUUID"), "initial boot volume")}


def validate_created(dutil, receipt):
    """Re-resolve a receipt by UUID after later boot-volume setup, read-only.

The newly created container may acquire System/Data/Preboot/Recovery volumes;
its original neighbors, physical range, and the live macOS must remain intact.
Returns current device numbers, which need not match those at creation time.
"""
    if not isinstance(receipt, dict) or receipt.get("format") != CREATED_FORMAT:
        raise ValueError("Invalid internal container creation receipt")
    plan = receipt.get("plan", {})
    if plan.get("format") != PLAN_FORMAT:
        raise ValueError("Invalid plan in internal container receipt")
    result, container = _validate_after(dutil, plan)
    if any(result[key] != receipt.get(key) for key in ("container_uuid", "store_uuid", "bytes")):
        raise ValueError("Created boot container identity no longer matches its receipt")
    return {**result, "volumes": copy.deepcopy(container.get("Volumes", []))}
