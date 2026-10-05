"""Native FAT32/ext4 SD images and explicit macOS SD-card operations.

The Mac's enrolled loader is deliberately outside this module. The SD's EFI
System Partition contains GRUB and the pacman-managed Linux boot files.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import uuid
import zlib

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
import gpt
from common import run, sha256
from card_disk import DiskUtil

LAYOUT = "arch-m4-uefi-v2"
MIB = 1024**2
GIB = 1024**3
SECTOR = 512
ALIGN = MIB // SECTOR
ESP = "C12A7328-F81F-11D2-BA4B-00A0C93EC93B"
LINUX = "0FC63DAF-8483-4772-8E79-3D69D8477DE4"
MARKER = "arch-m4-card.json"
ESP_REQUIRED = frozenset({"EFI/BOOT/BOOTAA64.EFI", "grub/grub.cfg",
                          "vmlinuz-linux-m4rch", "initramfs-linux-m4rch.img",
                          "dtbs/board.dtbo"})


def identities(config):
    root = uuid.UUID(config["root_uuid"])
    return {"layout": LAYOUT, "root_uuid": str(root),
            **{key: str(uuid.uuid5(root, LAYOUT + ":" + purpose)).upper()
               for key, purpose in (("disk_guid", "disk"),
                                    ("boot_partition_uuid", "boot"),
                                    ("root_partition_uuid", "root"))}}


def boot_fat_uuid(config):
    serial = uuid.UUID(identities(config)["boot_partition_uuid"]).hex[:8].upper()
    return serial[:4] + "-" + serial[4:]


def geometry(boot_bytes, root_bytes):
    """Two MiB-aligned partitions followed by space for the backup GPT."""
    if any(type(size) is not int or size <= 0 or size % MIB
           for size in (boot_bytes, root_bytes)):
        raise ValueError("Filesystem sizes must be positive whole MiB values")
    start = ALIGN
    root_start = start + boot_bytes // SECTOR
    root_end = root_start + root_bytes // SECTOR - 1
    sectors = ((root_end + 1 + 33 + ALIGN - 1) // ALIGN) * ALIGN
    return {"bytes": sectors * SECTOR, "boot_first_lba": start,
            "boot_last_lba": root_start - 1, "root_first_lba": root_start,
            "root_last_lba": root_end, "last_usable_lba": sectors - 34}


def _sizes(config):
    boot, root = config["boot_mib"], config["root_gib"]
    if (type(boot) is not int or not 64 <= boot <= 2048
            or type(root) is not int or not 1 <= root <= 2048):
        raise ValueError("boot_mib must be 64..2048 and root_gib must be 1..2048")
    return boot * MIB, root * GIB


def _header(current, alternate, table_lba, sectors, disk_guid, checksum):
    raw = bytearray(SECTOR)
    gpt.HEADER.pack_into(raw, 0, b"EFI PART", 0x10000, 92, 0, 0,
                        current, alternate, 34, sectors - 34,
                        uuid.UUID(disk_guid).bytes_le, table_lba, 128, 128,
                        checksum)
    struct.pack_into("<I", raw, 16, zlib.crc32(raw[:92]) & 0xffffffff)
    return raw


def write_gpt(stream, layout, ids):
    """Write only GPT metadata to an already sized regular image file."""
    size = layout["bytes"]
    if os.fstat(stream.fileno()).st_size != size:
        raise ValueError("Image extent does not match GPT geometry")
    sectors = size // SECTOR
    table = bytearray(128 * 128)
    for index, (kind, guid, first, last, name) in enumerate((
            (ESP, ids["boot_partition_uuid"], layout["boot_first_lba"],
             layout["boot_last_lba"], "ARCHBOOT"),
            (LINUX, ids["root_partition_uuid"], layout["root_first_lba"],
             layout["root_last_lba"], "ARCHROOT"))):
        offset = index * 128
        struct.pack_into("<16s16sQQQ", table, offset, uuid.UUID(kind).bytes_le,
                         uuid.UUID(guid).bytes_le, first, last, 0)
        encoded = name.encode("utf-16-le")
        table[offset + 56:offset + 56 + len(encoded)] = encoded
    checksum = zlib.crc32(table) & 0xffffffff
    mbr = bytearray(SECTOR)
    mbr[450] = 0xee
    struct.pack_into("<II", mbr, 454, 1, min(sectors - 1, 0xffffffff))
    mbr[510:512] = b"\x55\xaa"
    for position, data in ((0, mbr),
            (SECTOR, _header(1, sectors - 1, 2, sectors, ids["disk_guid"], checksum)),
            (2 * SECTOR, table), ((sectors - 33) * SECTOR, table),
            ((sectors - 1) * SECTOR,
             _header(sectors - 1, 1, sectors - 33, sectors, ids["disk_guid"], checksum))):
        stream.seek(position)
        stream.write(data)


def _ext4(stream, offset=0):
    stream.seek(offset + 1024)
    raw = stream.read(1024)
    if len(raw) != 1024 or raw[56:58] != b"\x53\xef":
        raise ValueError("Root partition does not contain an ext4 superblock")
    # EXT4_FEATURE_INCOMPAT_EXTENTS distinguishes ext4 from ext2/ext3 here.
    if not struct.unpack_from("<I", raw, 96)[0] & 0x40:
        raise ValueError("Root filesystem does not enable ext4 extents")
    return {"uuid": str(uuid.UUID(bytes=raw[104:120])),
            "label": raw[120:136].split(b"\0", 1)[0].decode("ascii", "strict")}


def _regular(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular, non-symlink file: {path}")
    return path


def _file_info(path):
    path = _regular(path)
    return {"bytes": path.stat().st_size, "sha256": sha256(path)}


def _esp(out, config):
    """Verify the complete exported ESP before opening any image or disk."""
    out = Path(out)
    manifest = json.loads(_regular(out / "payload-manifest.json").read_text())
    if manifest.get("layout") != LAYOUT or manifest.get("config") != config:
        raise ValueError("UEFI payload configuration is stale; rebuild the image")
    base = out / "esp"
    if base.is_symlink() or not base.is_dir():
        raise ValueError("Expected a non-symlink esp directory")
    files = {}
    for path in sorted(base.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"ESP contains a non-regular path: {path}")
        if path.is_dir():
            continue
        relative = path.relative_to(base).as_posix()
        # Mtools and firmware both consume these paths. Keep their spelling
        # portable and unambiguous, including on FAT's case-insensitive names.
        if (any(not component or component in (".", "..")
                or any(not (c.isascii() and (c.isalnum() or c in "._-")) for c in component)
                for component in relative.split("/"))
                or relative.casefold() in {name.casefold() for name in files}):
            raise ValueError(f"Unsafe or duplicate ESP filename: {relative}")
        files[relative] = _file_info(path)
    if not ESP_REQUIRED.issubset(files):
        raise ValueError("ESP is missing required GRUB, kernel, initramfs or DT files")
    expected = {"esp/" + path: info for path, info in files.items()}
    if manifest.get("files") != expected:
        raise ValueError("ESP contents do not match the payload manifest")
    efi = (base / "EFI/BOOT/BOOTAA64.EFI").read_bytes()
    if len(efi) < 64 or efi[:2] != b"MZ":
        raise ValueError("BOOTAA64.EFI is not a PE executable")
    offset = struct.unpack_from("<I", efi, 0x3c)[0]
    if (offset > len(efi) - 6 or efi[offset:offset + 4] != b"PE\0\0"
            or struct.unpack_from("<H", efi, offset + 4)[0] != 0xaa64):
        raise ValueError("BOOTAA64.EFI is not an AArch64 PE executable")
    with (base / "vmlinuz-linux-m4rch").open("rb") as stream:
        header = stream.read(64)
    if len(header) != 64 or header[56:60] != b"ARM\x64":
        raise ValueError("vmlinuz-linux-m4rch is not an uncompressed ARM64 Image")
    if not files["initramfs-linux-m4rch.img"]["bytes"]:
        raise ValueError("The initramfs is empty")
    return files


def _copy_partition(source, stream, offset):
    """Copy while preserving sparse zero runs; hash the exact input bytes."""
    digest = hashlib.sha256()
    stream.seek(offset)
    written = 0
    with source.open("rb") as source_stream:
        while block := source_stream.read(4 * MIB):
            digest.update(block)
            if block.strip(b"\0"):
                stream.write(block)
            else:
                stream.seek(len(block), os.SEEK_CUR)
            written += len(block)
    return {"bytes": written, "sha256": digest.hexdigest()}


def compose(out: Path, config: dict):
    """Build m4rch.img from the verified ESP tree and ext4 root on Linux."""
    if sys.platform != "linux":
        raise ValueError("Image composition runs inside the Linux builder")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = _esp(out, config)
    root = _regular(out / "rootfs.ext4")
    boot_bytes, root_bytes = _sizes(config)
    if root.stat().st_size != root_bytes:
        raise ValueError("rootfs.ext4 size differs from root_gib")
    ids = identities(config)
    with root.open("rb") as stream:
        if _ext4(stream) != {"uuid": ids["root_uuid"], "label": "ARCHROOT"}:
            raise ValueError("Root filesystem UUID or ARCHROOT label differs from config")
    if 3 * sum(info["bytes"] for info in files.values()) + 8 * MIB > boot_bytes:
        raise ValueError("ARCHBOOT needs room for the ESP and staged package updates")
    layout = geometry(boot_bytes, root_bytes)
    marker = {**ids, "boot_first_lba": layout["boot_first_lba"],
              "root_first_lba": layout["root_first_lba"], "files": files}
    with tempfile.TemporaryDirectory(prefix=".media-", dir=out) as temporary:
        work = Path(temporary)
        fat = work / "boot.fat"
        with fat.open("xb") as stream:
            stream.truncate(boot_bytes)
        run(["mkfs.vfat", "-F", "32", "-n", "ARCHBOOT", "-i",
             boot_fat_uuid(config).replace("-", ""), fat])
        marker_path = work / MARKER
        marker_path.write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n")
        directories = {parent.as_posix() for relative in files
                       for parent in Path(relative).parents
                       if parent != Path(".")}
        for directory in sorted(directories, key=lambda name: (name.count("/"), name)):
            run(["mmd", "-i", fat, "::/" + directory])
        for relative in files:
            run(["mcopy", "-i", fat, out / "esp" / relative, "::/" + relative])
        run(["mcopy", "-i", fat, marker_path, "::/" + MARKER])
        for relative, expected in files.items():
            copied = work / "readback"
            run(["mcopy", "-i", fat, "::/" + relative, copied])
            if _file_info(copied) != expected:
                raise ValueError(f"FAT32 ESP readback differs from the build: {relative}")
            copied.unlink()
        image = work / "m4rch.img"
        with image.open("x+b") as stream:
            stream.truncate(layout["bytes"])
            write_gpt(stream, layout, ids)
            fat_info = _copy_partition(fat, stream, layout["boot_first_lba"] * SECTOR)
            root_info = _copy_partition(root, stream, layout["root_first_lba"] * SECTOR)
            if fat_info["bytes"] != boot_bytes or root_info["bytes"] != root_bytes:
                raise ValueError("Filesystem source size changed during image creation")
            gpt.sync_disk(stream)
        checked = gpt.inspect(image)
        with image.open("rb") as stream:
            if _ext4(stream, layout["root_first_lba"] * SECTOR)["uuid"] != ids["root_uuid"]:
                raise ValueError("Composed image has a different root UUID")
        manifest = {"layout": LAYOUT, "config": config, "card": marker,
                    "gpt": checked, "files": {
                        "m4rch.img": {"bytes": image.stat().st_size,
                                        "sha256": sha256(image)},
                        **{"esp/" + path: info for path, info in files.items()},
                        "rootfs.ext4": root_info}}
        _atomic_json(work / "card-manifest.json", manifest)
        image.replace(out / "m4rch.img")
        (work / "card-manifest.json").replace(out / "card-manifest.json")
    print(f"Built {out / 'm4rch.img'}; ext4 grows to fill the card on boot.", flush=True)
    return manifest


def _atomic_json(path, value):
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    _atomic_bytes(path, data)


def _atomic_bytes(path, data):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"Refusing symlink destination: {path}")
    descriptor, name = tempfile.mkstemp(prefix=".arch-m4-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.read_bytes() != data:
            raise ValueError("Metadata write failed readback verification")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _disk_config():
    # Reuse the legacy target identity/protected-disk validation without its
    # APFS image-size formula. Exact native image capacity is checked below.
    return {"image_gib": 1, "stub_gib": 1}


def _require_macos():
    if sys.platform != "darwin":
        raise ValueError("Physical card operations require macOS")
    if os.geteuid() != 0:
        raise ValueError("Physical card operations require sudo")


def _manifest(out, config):
    path = _regular(Path(out) / "card-manifest.json")
    manifest = json.loads(path.read_text())
    if manifest.get("layout") != LAYOUT or manifest.get("config") != config:
        raise ValueError("Card manifest configuration is stale; rebuild the image")
    image = _regular(Path(out) / "m4rch.img")
    expected = manifest["files"]["m4rch.img"]
    if image.stat().st_size != expected["bytes"] or sha256(image) != expected["sha256"]:
        raise ValueError("Card image failed manifest verification")
    if gpt.inspect(image) != manifest["gpt"]:
        raise ValueError("Card image GPT differs from its manifest")
    return manifest


def flash(out: Path, config: dict, device: str):
    """Interactively erase one explicitly selected removable built-in SD card."""
    _require_macos()
    from card import confirm, exclusive_disk, source_off_target, write_and_verify_image
    out = Path(out)
    manifest = _manifest(out, config)
    image = out / "m4rch.img"
    expected = manifest["files"]["m4rch.img"]
    dutil = DiskUtil()
    summary = dutil.inspect_target(device, _disk_config())
    if summary["bytes"] < expected["bytes"]:
        raise ValueError("The SD card is smaller than the built image")
    if summary["fingerprint"]["DeviceBlockSize"] != SECTOR:
        raise ValueError("This image requires 512-byte logical sectors")
    source_off_target(dutil, image, summary["device"])
    for attached in dutil.image_info().get("images", []):
        if Path(attached.get("image-path", "/")).resolve() == image.resolve():
            raise ValueError("Detach the source image before flashing")
    confirm("ERASE " + summary["node"],
            f"{summary['node']}: {summary['media_name']}, {summary['bytes']} bytes.\n"
            "This erases every partition and all existing Linux data on this SD card.\n"
            f"Image: {image}. The internal boot volume is not changed.")
    source_off_target(dutil, image, summary["device"])
    # A single exclusive raw descriptor covers copy, complete bounded readback
    # and GPT relocation, avoiding macOS remounts between write and reopen.
    with exclusive_disk(dutil, summary, _disk_config()) as stream:
        write_and_verify_image(image, stream, expected["bytes"], expected["sha256"], summary["bytes"])
    dutil.run("eject", summary["device"])
    print("Verified flash complete. Reinsert the card before loader setup.", flush=True)
    return manifest
