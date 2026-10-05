"""Validate raw GPT images and relocate backup GPT metadata after flashing.

Only 512-byte sectors and ordinary protective MBRs are supported. Relocation
never moves or resizes a partition. A caller operating on a device must first
validate its identity, unmount it, and supply its independently measured size.
"""
from __future__ import annotations

import fcntl
import os
import stat
import struct
import sys
import uuid
import zlib


SECTOR = 512
HEADER = struct.Struct("<8sIIIIQQQQ16sQIII")
MAX_TABLE_BYTES = 16 * 1024**2
# Darwin <sys/disk.h>: _IO('d', 22). Unlike fsync on a character device,
# this asks the disk driver to synchronize its media cache.
DKIOCSYNCHRONIZECACHE = 0x20006416


def sync_disk(stream):
    """Flush an open image/device, including a Darwin disk's media cache.

    Device identity and exclusive/unmounted access remain the caller's job.
    Cache-sync errors deliberately propagate; callers must not continue with
    dependent metadata writes or report a successfully synchronized flash.
    """
    stream.flush()
    descriptor = stream.fileno()
    mode = os.fstat(descriptor).st_mode
    if sys.platform == "darwin" and (stat.S_ISCHR(mode) or stat.S_ISBLK(mode)):
        if stat.S_ISBLK(mode):
            os.fsync(descriptor)
        fcntl.ioctl(descriptor, DKIOCSYNCHRONIZECACHE)
    else:
        os.fsync(descriptor)


def _size(value, sector_size):
    if sector_size != SECTOR:
        raise ValueError("Only 512-byte GPT sectors are supported")
    if type(value) is not int or value < 6 * SECTOR or value % SECTOR:
        raise ValueError("GPT disk size must be a positive whole number of 512-byte sectors")
    return value


def _open(path, writable=False):
    flags = (os.O_RDWR if writable else os.O_RDONLY) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        mode = os.fstat(descriptor).st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISBLK(mode) or stat.S_ISCHR(mode)):
            raise ValueError("GPT input must be a regular image file or a disk device")
        return os.fdopen(descriptor, "r+b" if writable else "rb", buffering=0)
    except BaseException:
        os.close(descriptor)
        raise


def _capacity(stream, supplied):
    info = os.fstat(stream.fileno())
    if stat.S_ISREG(info.st_mode):
        if supplied is not None and supplied != info.st_size:
            raise ValueError("Supplied GPT target size differs from the backing file size")
        return _size(info.st_size, SECTOR)
    if supplied is None:
        raise ValueError("Disk devices require an independently measured total_bytes value")
    return _size(supplied, SECTOR)


def _read(stream, offset, size, limit):
    if offset < 0 or size < 0 or offset + size > limit:
        raise ValueError("GPT read lies outside the declared image")
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("Truncated GPT header or partition table")
    return data


def _crc(data):
    return zlib.crc32(data) & 0xffffffff


def _header(raw):
    values = HEADER.unpack_from(raw)
    (signature, revision, length, checksum, reserved, current, alternate,
     first, last, disk_guid, table, count, entry_size, table_checksum) = values
    if signature != b"EFI PART" or revision != 0x10000:
        raise ValueError("Invalid or unsupported GPT header signature/revision")
    if not HEADER.size <= length <= SECTOR or reserved != 0:
        raise ValueError("Invalid GPT header length or reserved field")
    checked = bytearray(raw[:length])
    struct.pack_into("<I", checked, 16, 0)
    if _crc(checked) != checksum:
        raise ValueError("GPT header CRC mismatch")
    if (count < 1 or entry_size < 128 or entry_size % 128
            or count * entry_size > MAX_TABLE_BYTES):
        raise ValueError("Unsupported GPT partition-table dimensions")
    if disk_guid == bytes(16):
        raise ValueError("GPT disk GUID is empty")
    return dict(revision=revision, length=length, current=current, alternate=alternate,
                first=first, last=last, disk_guid=disk_guid, table=table,
                count=count, entry_size=entry_size, table_checksum=table_checksum)


def _protective_mbr(raw, sector_count):
    if raw[510:512] != b"\x55\xaa":
        raise ValueError("Missing protective MBR signature")
    occupied = [offset for offset in range(446, 510, 16) if raw[offset + 4]]
    if len(occupied) != 1:
        raise ValueError("Hybrid or missing protective MBR is not supported")
    offset = occupied[0]
    start, length = struct.unpack_from("<II", raw, offset + 8)
    if raw[offset + 4] != 0xee or start != 1 or length != min(sector_count - 1, 0xffffffff):
        raise ValueError("Protective MBR does not match the GPT image size")
    return offset


def _partitions(table, header):
    result, identifiers = [], set()
    for index in range(header["count"]):
        entry = table[index * header["entry_size"]:(index + 1) * header["entry_size"]]
        type_guid, identifier = entry[:16], entry[16:32]
        if type_guid == bytes(16):
            continue
        first, last, attributes = struct.unpack_from("<QQQ", entry, 32)
        if not header["first"] <= first <= last <= header["last"]:
            raise ValueError("GPT partition extends outside the usable disk range")
        if identifier == bytes(16) or identifier in identifiers:
            raise ValueError("GPT partition GUID is empty or duplicated")
        identifiers.add(identifier)
        result.append({"index": index + 1,
                       "type_guid": str(uuid.UUID(bytes_le=type_guid)).upper(),
                       "guid": str(uuid.UUID(bytes_le=identifier)).upper(),
                       "first_lba": first, "last_lba": last, "attributes": attributes,
                       "name": entry[56:128].decode("utf-16-le", errors="replace").rstrip("\0")})
    ordered = sorted(result, key=lambda item: item["first_lba"])
    if any(left["last_lba"] >= right["first_lba"] for left, right in zip(ordered, ordered[1:])):
        raise ValueError("GPT partitions overlap")
    return result


def _load(stream, total_bytes):
    count = total_bytes // SECTOR
    mbr = _read(stream, 0, SECTOR, total_bytes)
    mbr_offset = _protective_mbr(mbr, count)
    primary_raw = _read(stream, SECTOR, SECTOR, total_bytes)
    primary = _header(primary_raw)
    table_bytes = primary["count"] * primary["entry_size"]
    table_sectors = (table_bytes + SECTOR - 1) // SECTOR
    if primary["current"] != 1 or primary["alternate"] != count - 1:
        raise ValueError("Primary GPT header does not describe the exact image size")
    if not (2 <= primary["table"]
            and primary["table"] + table_sectors <= primary["first"]
            <= primary["last"] < count - 1 - table_sectors):
        raise ValueError("GPT usable range overlaps headers or partition tables")
    backup_raw = _read(stream, (count - 1) * SECTOR, SECTOR, total_bytes)
    backup = _header(backup_raw)
    if (backup["current"] != count - 1 or backup["alternate"] != 1
            or backup["table"] != count - 1 - table_sectors):
        raise ValueError("Backup GPT header or partition table is misplaced")
    for field in ("revision", "length", "first", "last", "disk_guid", "count", "entry_size", "table_checksum"):
        if primary[field] != backup[field]:
            raise ValueError(f"Primary and backup GPT metadata disagree: {field}")
    # Raw disk I/O requires full sectors even when a GPT's entry array uses
    # only part of its final sector. Padding is outside the table's CRC.
    table = _read(stream, primary["table"] * SECTOR,
                  table_sectors * SECTOR, total_bytes)[:table_bytes]
    backup_table = _read(stream, backup["table"] * SECTOR,
                         table_sectors * SECTOR, total_bytes)[:table_bytes]
    if _crc(table) != primary["table_checksum"] or table != backup_table:
        raise ValueError("GPT partition-table CRC or backup copy mismatch")
    partitions = _partitions(table, primary)
    metadata = {"sector_size": SECTOR, "bytes": total_bytes,
                "disk_guid": str(uuid.UUID(bytes_le=primary["disk_guid"])).upper(),
                "primary_header_lba": 1, "backup_header_lba": count - 1,
                "first_usable_lba": primary["first"], "last_usable_lba": primary["last"],
                "entry_count": primary["count"], "entry_size": primary["entry_size"],
                "entries_crc32": f"{primary['table_checksum']:08x}", "partitions": partitions}
    return metadata, primary, mbr, mbr_offset, primary_raw, backup_raw, table


def inspect(path, sector_size=512, total_bytes=None):
    """Validate both GPT copies against the exact file/device capacity."""
    with _open(path) as stream:
        return inspect_stream(stream, total_bytes=total_bytes, sector_size=sector_size)


def inspect_stream(stream, total_bytes=None, sector_size=512):
    """Validate GPT using an existing descriptor without closing or reopening it.

    Regular files are checked against their measured size. For devices,
    total_bytes is the caller's independently established GPT extent; this may
    be the original image extent while finishing a flash onto a larger disk.
    The caller owns the descriptor and any exclusive/unmounted access.
    """
    if sector_size != SECTOR:
        raise ValueError("Only 512-byte GPT sectors are supported")
    capacity = _capacity(stream, total_bytes)
    return _load(stream, capacity)[0]


def _updated(raw, current, alternate, last, table):
    result = bytearray(raw)
    struct.pack_into("<QQ", result, 24, current, alternate)
    struct.pack_into("<Q", result, 48, last)
    struct.pack_into("<Q", result, 72, table)
    struct.pack_into("<I", result, 16, 0)
    length = struct.unpack_from("<I", result, 12)[0]
    struct.pack_into("<I", result, 16, _crc(result[:length]))
    return bytes(result)


def _write(stream, offset, data):
    stream.seek(offset)
    view = memoryview(data)
    while view:
        written = stream.write(view)
        if written is None or written <= 0:
            raise OSError("Unable to finish writing GPT metadata")
        view = view[written:]


def relocate(path, total_bytes, sector_size=512):
    """Move backup GPT to the end of an already-expanded image or flashed disk.

    The old GPT must still be complete at its original declared end. The target
    must already have total_bytes capacity; this function does not resize files.
    Old backup sectors remain in now-unused space. Partitions are unchanged.
    """
    with _open(path, writable=True) as stream:
        return relocate_stream(stream, total_bytes, sector_size=sector_size)


def relocate_stream(stream, total_bytes, sector_size=512):
    """Relocate GPT through a descriptor the caller keeps open and exclusive.

    The caller owns the descriptor; this function never closes or reopens it.
    Keeping one writable raw-disk descriptor across image copy, readback and
    relocation avoids triggering macOS media reprobes between these steps.
    Partition contents, starts, sizes and UUIDs remain unchanged.
    """
    _size(total_bytes, sector_size)
    capacity = _capacity(stream, total_bytes)
    primary = _header(_read(stream, SECTOR, SECTOR, capacity))
    old_size = (primary["alternate"] + 1) * SECTOR
    if old_size > capacity:
        raise ValueError("Refusing to shrink GPT or relocate beyond target capacity")
    before, primary, mbr, mbr_offset, primary_raw, backup_raw, table = _load(stream, old_size)
    if old_size == capacity:
        return before
    last = capacity // SECTOR - 1
    table_sectors = (len(table) + SECTOR - 1) // SECTOR
    table_lba = last - table_sectors
    last_usable = table_lba - 1
    new_backup = _updated(backup_raw, last, 1, last_usable, table_lba)
    new_primary = _updated(primary_raw, 1, last, last_usable, primary["table"])
    new_mbr = bytearray(mbr)
    struct.pack_into("<I", new_mbr, mbr_offset + 12, min(last, 0xffffffff))
    # Preserve the primary partition table throughout the operation. Commit
    # its updated header only after the new backup is durable; on very small
    # expansions the new backup can overlap the obsolete backup sectors.
    _write(stream, table_lba * SECTOR, table.ljust(table_sectors * SECTOR, b"\0"))
    _write(stream, last * SECTOR, new_backup)
    sync_disk(stream)
    _write(stream, 0, new_mbr)
    _write(stream, SECTOR, new_primary)
    sync_disk(stream)
    after = _load(stream, capacity)[0]
    if before["partitions"] != after["partitions"] or before["entries_crc32"] != after["entries_crc32"]:
        raise ValueError("Partition definitions changed during GPT relocation")
    return after
