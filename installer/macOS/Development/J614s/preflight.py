#!/usr/bin/env python3
"""Read-only audit of retained M4RCH inputs for a J614s installer candidate."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile

INPUTS = {
    "kernel": (
        "cache/aurora1-promotion/linux-package/Image",
        "1ef76fe0a222fb9caa2c03efc63986a7c1c0209158519b9e6a793be92c78b071",
    ),
    "config": (
        "cache/aurora1-promotion/linux-package/kernel.config",
        "80d5c60810efbd76d60e419e12c10465dd7dc491e381bbf8c644c921d5b6c16e",
    ),
    "dtb": (
        "cache/aurora1-promotion/linux-package/apple-j614s.dtb",
        "e2435554bfda78178d4427fc2645b8f024885048e1946ae74cd619094365efc8",
    ),
    "modules": (
        "cache/aurora1-promotion/linux-package/modules.tar.gz",
        "10e02c338089df27008f9420e1a95f984b64c0ebf9354bbc321e2f3e79b38d5e",
    ),
    "m1n1_stage2": (
        "cache/installed-20261031/m1n1.bin",
        "fe9571af510cec542852e88a21928be29a855c66b2937fc3938a6cdedb3fc501",
    ),
    "uboot": (
        "cache/jack-promotion/inputs/u-boot-nodtb.bin",
        "b25192d5f2f4c07f49ee0cc6f15d2c9ec5199cf201cc608c1a651c249ba0b018",
    ),
}
RELEASE = "7.3.0-m4rch-aurora1"
MODULE = f"lib/modules/{RELEASE}/kernel/fs/btrfs/btrfs.ko"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_modules(path):
    with tarfile.open(path, "r:gz") as archive:
        members = [item for item in archive if item.name.removeprefix("./") == MODULE]
        return len(members) == 1 and members[0].isfile() and members[0].size > 0


def audit(root):
    checks = {}
    for name, (relative, expected) in INPUTS.items():
        path = root / relative
        if not path.is_file():
            checks[name] = {"status": "missing", "path": relative}
            continue
        actual = sha256(path)
        checks[name] = {
            "status": "ok" if actual == expected else "mismatch",
            "path": relative,
            "sha256": actual,
        }
    config = root / INPUTS["config"][0]
    modules = root / INPUTS["modules"][0]
    if checks["config"]["status"] == "ok":
        checks["btrfs_config"] = {
            "status": (
                "ok"
                if "CONFIG_BTRFS_FS=m" in config.read_text().splitlines()
                else "missing"
            )
        }
    if checks["modules"]["status"] == "ok":
        try:
            present = inspect_modules(modules)
        except (OSError, tarfile.TarError):
            present = False
        checks["btrfs_module"] = {
            "status": "ok" if present else "missing",
            "release": RELEASE,
        }
    return {
        "target": "Mac16,8 / apple,j614s / T6040",
        "inputs": checks,
        "inputs_verified": all(item["status"] == "ok" for item in checks.values()),
        "install_ready": False,
        "note": "Input hashes do not qualify a boot chain, initramfs, firmware, signed catalog, or physical installation.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "m4rch_root",
        type=Path,
        help="extracted M4RCH repository including its private cache",
    )
    args = parser.parse_args()
    result = audit(args.m4rch_root)
    print(json.dumps(result, indent=2))
    return 0 if result["inputs_verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
