#!/usr/bin/env python3
"""Inspect the authenticated Aurora image files without mounting or modifying them."""

import argparse
import io
import json
from pathlib import Path
import re
import stat

from dissect.btrfs import Btrfs
from dissect.extfs import ExtFS
import zstandard

import preflight
import rootfs_audit

EXPECTED = {
    "metadata.json": "ad493a0a151a118aac85d37866c5a370d307aa41ac234edf7e45568a50e8bd8a",
    "root.img": "67d786d8e4344c3d9b9c7f96de558d39d66292eafcd1c0c9f537aea074b1b39e",
    "boot.img": "b31d16057880f56f8b1292f439d8c12701884dc1d64fbb0955463e4ac746ed50",
}
REQUIRED_HOOKS = ("asahi", "aurora-vendor", "sd-encrypt", "aurora-root", "filesystems")
MAX_TEXT_BYTES = 1024 * 1024


def is_regular(entry):
    if hasattr(entry, "is_file"):
        return entry.is_file()
    return stat.S_ISREG(entry.inode.i_mode)


def read_text(fs, path):
    entry = fs.get(path)
    if not is_regular(entry):
        raise ValueError(f"not a regular image file: {path}")
    with entry.open() as stream:
        data = stream.read(MAX_TEXT_BYTES + 1)
    if len(data) > MAX_TEXT_BYTES:
        raise ValueError(f"image file exceeds limit: {path}")
    return data.decode("utf-8")


def audit_source_initramfs(root, boot):
    entry = boot.get("/initramfs-linux-aurora.img")
    if not is_regular(entry) or entry.size > 128 * 1024 * 1024:
        raise ValueError("invalid source initramfs")
    with entry.open() as stream:
        data = stream.read()
    _, offset = rootfs_audit.cpio_entries(data)
    while offset < len(data) and data[offset] == 0:
        offset += 1
    if data[offset : offset + 4] != b"\x28\xb5\x2f\xfd":
        raise ValueError("source initramfs is not Zstandard compressed")
    with zstandard.ZstdDecompressor().stream_reader(
        io.BytesIO(data[offset:])
    ) as stream:
        unpacked = stream.read(rootfs_audit.MAX_DECOMPRESSED + 1)
    if len(unpacked) > rootfs_audit.MAX_DECOMPRESSED:
        raise ValueError("source initramfs exceeds unpacked limit")
    entries, _ = rootfs_audit.cpio_entries(unpacked)
    modules = "usr/lib/modules/7.3.0-1-5-ARCH/"
    required = [
        "usr/lib/aurora/aurora-initrd-root",
        "usr/lib/systemd/system/aurora-initrd-root.service",
        "usr/bin/cryptsetup",
        "etc/aurora/image-layout",
        modules + "kernel/fs/btrfs/btrfs.ko",
        modules + "kernel/drivers/md/dm-crypt.ko",
        modules + "kernel/drivers/nvme/host/nvme-apple.ko",
    ]
    for name in required:
        if name not in entries or not stat.S_ISREG(entries[name][0]):
            raise ValueError(f"source initramfs file missing or invalid: {name}")
    for path in ("usr/lib/aurora/aurora-initrd-root", "etc/aurora/image-layout"):
        expected = read_text(root, "/root/" + path).encode("utf-8")
        if entries[path][1] != expected:
            raise ValueError(f"source initramfs file differs from root image: {path}")
    return {"kernel_release": "7.3.0-1-5-ARCH", "required_files": required}


def validate_contents(
    metadata, root_uuid, boot_uuid, fstab, layout, hooks, grub, kernel="linux-aurora"
):
    if kernel not in ("linux-aurora", "linux-m4rch"):
        raise ValueError("unexpected kernel name")
    targets = [
        x
        for x in metadata["os_list"]
        if x.get("omarchy_target") == "apple-silicon-full-os"
    ]
    if len(targets) != 1:
        raise ValueError("metadata has no unique full OS target")
    partitions = targets[0]["partitions"]
    if len(partitions) != 3 or [p.get("image") for p in partitions[1:]] != [
        "boot.img",
        "root.img",
    ]:
        raise ValueError("unexpected metadata partition images")
    volume_id = partitions[0].get("volume_id", "")
    if not re.fullmatch(r"0x[0-9a-fA-F]{8}", volume_id):
        raise ValueError("unexpected ESP volume ID")
    fat_uuid = volume_id[2:6].upper() + "-" + volume_id[6:].upper()
    rows = [
        line.split()
        for line in fstab.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    expected = {
        "/": ("UUID=" + root_uuid, "btrfs", "subvol=root"),
        "/home": ("UUID=" + root_uuid, "btrfs", "subvol=home"),
        "/boot": ("UUID=" + boot_uuid, "ext4", None),
        "/boot/efi": ("UUID=" + fat_uuid, "vfat", None),
    }
    for mountpoint, (device, filesystem, option) in expected.items():
        matches = [row for row in rows if len(row) >= 4 and row[1] == mountpoint]
        if len(matches) != 1 or matches[0][0] != device or matches[0][2] != filesystem:
            raise ValueError(f"fstab mismatch: {mountpoint}")
        if option and option not in matches[0][3].split(","):
            raise ValueError(f"fstab subvolume mismatch: {mountpoint}")
    pairs = dict(line.split("=", 1) for line in layout.splitlines() if "=" in line)
    if pairs != {
        "format": "1",
        "root_uuid": root_uuid,
        "boot_uuid": boot_uuid,
        "root_subvolume": "root",
    }:
        raise ValueError("Aurora first-boot layout does not match the images")
    hook_lines = re.findall(r"^HOOKS=\(([^\n]*)\)$", hooks, re.MULTILINE)
    if len(hook_lines) != 1:
        raise ValueError("unexpected Aurora mkinitcpio hook definition")
    hook_names = hook_lines[0].split()
    try:
        indexes = [hook_names.index(hook) for hook in REQUIRED_HOOKS]
    except ValueError as exc:
        raise ValueError("required Aurora initramfs hook missing") from exc
    if indexes != sorted(indexes) or any(
        hook_names.count(hook) != 1 for hook in REQUIRED_HOOKS
    ):
        raise ValueError("Aurora initramfs hooks are duplicated or out of order")
    linux_lines = re.findall(
        rf"^\s*linux\s+/vmlinuz-{re.escape(kernel)}\s+([^\n]+)$", grub, re.MULTILINE
    )
    initrd_lines = re.findall(
        rf"^\s*initrd\s+/initramfs-{re.escape(kernel)}\.img\s*$", grub, re.MULTILINE
    )
    searches = re.findall(r"^\s*search\s+[^\n]*--fs-uuid[^\n]*$", grub, re.MULTILINE)
    if (
        not linux_lines
        or len(linux_lines) != len(initrd_lines)
        or not all(
            "root=UUID=" + root_uuid in line.split()
            and "rootflags=subvol=root" in line.split()
            for line in linux_lines
        )
        or not any(boot_uuid in line for line in searches)
    ):
        raise ValueError(
            "GRUB does not reference the image UUIDs and expected boot files"
        )
    return {
        "root_uuid": root_uuid,
        "boot_uuid": boot_uuid,
        "esp_fat_uuid": fat_uuid,
        "hooks": hook_names,
    }


def audit(directory):
    for name, digest in EXPECTED.items():
        if preflight.sha256(directory / name) != digest:
            raise ValueError(f"authenticated input digest mismatch: {name}")
    metadata = json.loads((directory / "metadata.json").read_text())
    with (directory / "root.img").open("rb") as root_file, (
        directory / "boot.img"
    ).open("rb") as boot_file:
        root, boot = Btrfs(root_file), ExtFS(boot_file)
        if root.sector_size != 4096 or root.node_size != 16384:
            raise ValueError("unexpected Btrfs geometry")
        top = root.get("/").subvolume.objectid
        subvolumes = []
        for path in ("/root", "/home"):
            entry = root.get(path)
            if not entry.is_dir() or entry.inum != entry.subvolume.root.inum:
                raise ValueError(f"missing Btrfs subvolume: {path}")
            subvolumes.append(entry.subvolume.objectid)
        if top in subvolumes or len(set(subvolumes)) != 2:
            raise ValueError("root and home are not distinct Btrfs subvolumes")
        for path in (
            "/root/usr/lib/initcpio/install/aurora-root",
            "/root/usr/lib/aurora/aurora-initrd-root",
            "/root/var/lib/aurora/firstboot/pending",
        ):
            if not root.get(path).is_file():
                raise ValueError(f"missing first-boot component: {path}")
        if (
            read_text(root, "/root/usr/lib/aurora/image-format").strip()
            != "aurora-btrfs-v1"
        ):
            raise ValueError("unexpected Aurora first-boot image format")
        sep_loader = read_text(root, "/root/usr/libexec/aurora-sep-load")
        sep_preset = read_text(
            root, "/root/usr/lib/systemd/system-preset/80-aurora-sep.preset"
        )
        if "modprobe apple_sep xart_writes=1 provision_keybag=1" not in sep_loader:
            raise ValueError("source SEP loader changed; review its xART behavior")
        if "enable aurora-sep.timer" not in sep_preset.splitlines():
            raise ValueError(
                "source SEP preset changed; review its activation behavior"
            )
        for path in ("/vmlinuz-linux-aurora", "/initramfs-linux-aurora.img"):
            if not is_regular(boot.get(path)):
                raise ValueError(f"missing boot image file: {path}")
        result = validate_contents(
            metadata,
            str(root.uuid),
            str(boot.uuid),
            read_text(root, "/root/etc/fstab"),
            read_text(root, "/root/etc/aurora/image-layout"),
            read_text(root, "/root/etc/mkinitcpio.conf.d/90-aurora.conf"),
            read_text(boot, "/grub/grub.cfg"),
        )
        result["source_initramfs"] = audit_source_initramfs(root, boot)
        result["source_sep_requires_j614s_override"] = True
    result.update(
        {
            "source_images_verified": True,
            "m4rch_kernel_installed": False,
            "install_ready": False,
        }
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.source_directory), indent=2))


if __name__ == "__main__":
    main()
