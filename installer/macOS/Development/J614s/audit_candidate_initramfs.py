#!/usr/bin/env python3
"""Read-only checks for an initramfs generated from the candidate package."""

import argparse
import io
import json
from pathlib import Path
import stat
import tarfile

from dissect.btrfs import Btrfs
import zstandard

import preflight
import prepare_rebuilt_package as candidate
import rootfs_audit
import source_image_audit


def audit(image, source_root, staged):
    if preflight.sha256(source_root) != source_image_audit.EXPECTED["root.img"]:
        raise ValueError("source root image hash mismatch")
    receipt = json.loads((staged / "candidate-receipt.json").read_text())
    for name, digest in receipt["source_hashes"].items():
        if preflight.sha256(staged / name) != digest:
            raise ValueError(f"staged source changed: {name}")
    closure = candidate.verify_modules(staged / "modules.tar.gz")
    data = image.read_bytes()
    _, offset = rootfs_audit.cpio_entries(data)
    while offset < len(data) and data[offset] == 0:
        offset += 1
    if data[offset : offset + 4] != b"\x28\xb5\x2f\xfd":
        raise ValueError("candidate initramfs is not Zstandard compressed")
    with zstandard.ZstdDecompressor().stream_reader(
        io.BytesIO(data[offset:])
    ) as stream:
        unpacked = stream.read(rootfs_audit.MAX_DECOMPRESSED + 1)
    if len(unpacked) > rootfs_audit.MAX_DECOMPRESSED:
        raise ValueError("candidate initramfs exceeds unpacked limit")
    entries, _ = rootfs_audit.cpio_entries(unpacked)

    def regular(path):
        item = entries.get(path)
        if item is None or not stat.S_ISREG(item[0]):
            raise ValueError(f"missing initramfs file: {path}")
        return item[1]

    prefix = f"lib/modules/{candidate.RELEASE}/"
    with tarfile.open(staged / "modules.tar.gz", "r:gz") as archive:
        for module in closure:
            path = prefix + module
            if regular("usr/" + path) != archive.extractfile(path).read():
                raise ValueError(f"initramfs module differs from candidate: {module}")
    fs = Btrfs(source_root.open("rb"))
    for path in (
        "usr/lib/aurora/aurora-initrd-root",
        "etc/aurora/image-layout",
        "usr/libexec/aurora/load-vendor-firmware",
        "usr/libexec/aurora/peripheral-firmware",
    ):
        expected = source_image_audit.read_text(fs, "/root/" + path).encode()
        if regular(path) != expected:
            raise ValueError(f"initramfs file differs from source image: {path}")
    regular("usr/bin/cryptsetup")
    service = regular("usr/lib/systemd/system/aurora-initrd-root.service")
    if b"ExecStart=/usr/lib/aurora/aurora-initrd-root\n" not in service:
        raise ValueError("Aurora root service does not start its first-boot hook")
    enabled = entries.get(
        "usr/lib/systemd/system/initrd.target.wants/aurora-initrd-root.service"
    )
    if (
        enabled is None
        or not stat.S_ISLNK(enabled[0])
        or enabled[1] != b"../aurora-initrd-root.service"
    ):
        raise ValueError("Aurora root service is not enabled in the initramfs")
    vendor_service = regular("usr/lib/systemd/system/aurora-vendor-firmware.service")
    if (
        vendor_service
        != source_image_audit.read_text(
            fs, "/root/usr/lib/aurora/initrd/aurora-vendor-firmware.service"
        ).encode()
    ):
        raise ValueError("Aurora firmware service differs from the source image")
    enabled_vendor = entries.get(
        "usr/lib/systemd/system/initrd.target.wants/aurora-vendor-firmware.service"
    )
    if (
        enabled_vendor is None
        or not stat.S_ISLNK(enabled_vendor[0])
        or enabled_vendor[1] != b"../aurora-vendor-firmware.service"
    ):
        raise ValueError("Aurora firmware service is not enabled in the initramfs")
    if (
        regular("usr/lib/modprobe.d/m4rch-j614s.conf")
        != (staged / "m4rch-j614s.conf").read_bytes()
    ):
        raise ValueError("initramfs J614s module options differ from package")
    return {
        "initramfs_sha256": preflight.sha256(image),
        "kernel_release": candidate.RELEASE,
        "verified_module_closure_count": len(closure),
        "aurora_first_boot_files_verified": True,
        "native_boot_tested": False,
        "install_ready": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("initramfs", type=Path)
    parser.add_argument("source_root_image", type=Path)
    parser.add_argument("staged_package", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            audit(args.initramfs, args.source_root_image, args.staged_package), indent=2
        )
    )


if __name__ == "__main__":
    main()
