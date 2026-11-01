#!/usr/bin/env python3
"""Compare the retained kernel package with its independently retained inputs."""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile

import preflight
import rootfs_audit

PACKAGE = "cache/aurora1-promotion/linux-package/linux-m4rch-7.3.0-29-aarch64.pkg.tar.xz"
PACKAGE_SHA256 = "694d55cff0af4c3dca12e4b678220cda16bad84cffaedeb26ef5613614d0b4c7"
CRYPTO_ROOTS = (
    "kernel/drivers/md/dm-crypt.ko",
    "kernel/crypto/xts.ko",
)
REQUIRED_CONFIG = {
    "CONFIG_NVME_APPLE": "m",
    "CONFIG_BLK_DEV_DM": "y",
    "CONFIG_DM_CRYPT": "m",
    "CONFIG_BTRFS_FS": "m",
    "CONFIG_CRYPTO_AES": "y",
    "CONFIG_CRYPTO_XTS": "m",
}


def checked_config(text):
    values = {}
    for line in text.splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            if key in values:
                raise ValueError(f"duplicate kernel config setting: {key}")
            values[key] = value
    missing = [
        key for key, expected in REQUIRED_CONFIG.items() if values.get(key) != expected
    ]
    if missing:
        raise ValueError(f"unexpected kernel configuration: {', '.join(missing)}")
    return {key: values[key] for key in REQUIRED_CONFIG}


def regular_bytes(archive, name):
    member = archive.getmember(name)
    if not member.isfile():
        raise ValueError(f"not a regular archive file: {name}")
    return archive.extractfile(member).read()


def audit(root):
    package = root / PACKAGE
    if preflight.sha256(package) != PACKAGE_SHA256:
        raise ValueError("kernel package digest mismatch")
    for key in ("kernel", "config", "modules"):
        relative, digest = preflight.INPUTS[key]
        if preflight.sha256(root / relative) != digest:
            raise ValueError(f"retained {key} digest mismatch")
    config = checked_config((root / preflight.INPUTS["config"][0]).read_text())
    prefix = f"lib/modules/{preflight.RELEASE}/"
    with tarfile.open(root / preflight.INPUTS["modules"][0], "r:gz") as source:
        dependencies = regular_bytes(source, prefix + "modules.dep")
        closure = rootfs_audit.module_closure(
            dependencies.decode("utf-8"), rootfs_audit.ROOTS + CRYPTO_ROOTS
        )
        expected = {name: regular_bytes(source, prefix + name) for name in closure}
    with tarfile.open(package, "r:xz") as archive:
        package_prefix = "usr/" + prefix
        kernel = regular_bytes(archive, package_prefix + "vmlinuz")
        if hashlib.sha256(kernel).hexdigest() != preflight.INPUTS["kernel"][1]:
            raise ValueError("package kernel differs from retained Image")
        if regular_bytes(archive, package_prefix + "modules.dep") != dependencies:
            raise ValueError("package module dependency index differs")
        for name, contents in expected.items():
            if regular_bytes(archive, package_prefix + name) != contents:
                raise ValueError(f"package module differs: {name}")
    return {
        "kernel_package_sha256": PACKAGE_SHA256,
        "release": preflight.RELEASE,
        "kernel_matches_retained_image": True,
        "module_dependency_index_matches": True,
        "matching_storage_and_crypto_modules": closure,
        "required_kernel_config": config,
        "luks_conversion_verified": False,
        "install_ready": False,
        "note": "Matching files and configuration do not prove LUKS conversion, Aurora initramfs hooks, or hardware boot.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("m4rch_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.m4rch_root), indent=2))


if __name__ == "__main__":
    main()
