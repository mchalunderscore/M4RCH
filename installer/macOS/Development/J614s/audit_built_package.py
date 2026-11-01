#!/usr/bin/env python3
"""Compare an unsigned makepkg output against the staged kernel inputs."""

import argparse
import json
from pathlib import Path
import tarfile

import preflight
import prepare_rebuilt_package as candidate

MASKS = {"etc/systemd/system/aurora-sep.service", "etc/systemd/system/aurora-sep.timer"}


def verify(package, staged):
    receipt = json.loads((staged / "candidate-receipt.json").read_text())
    if (
        receipt["kernel_release"] != candidate.RELEASE
        or receipt["install_ready"] is not False
    ):
        raise ValueError("invalid staged candidate receipt")
    for name, digest in receipt["source_hashes"].items():
        if preflight.sha256(staged / name) != digest:
            raise ValueError(f"staged source changed: {name}")
    module_prefix = f"lib/modules/{candidate.RELEASE}/"
    modules = {}
    with tarfile.open(staged / "modules.tar.gz", "r:gz") as archive:
        for member in archive:
            name = member.name.removeprefix("./")
            if name.startswith(module_prefix) and member.isfile():
                if name in modules:
                    raise ValueError(f"duplicate staged module path: {name}")
                modules[name] = archive.extractfile(member).read()
    expected = {
        "etc/default/update-m1n1": (staged / "update-m1n1").read_bytes(),
        "etc/default/grub.d/50-m4rch.cfg": (staged / "50-m4rch.cfg").read_bytes(),
        "etc/mkinitcpio.d/linux-m4rch.preset": (
            staged / "linux-m4rch.preset"
        ).read_bytes(),
        "etc/mkinitcpio-m4rch.conf": (staged / "mkinitcpio-m4rch.conf").read_bytes(),
        "usr/lib/modprobe.d/m4rch-j614s.conf": (
            staged / "m4rch-j614s.conf"
        ).read_bytes(),
        f"usr/{module_prefix}vmlinuz": (staged / "Image").read_bytes(),
        f"usr/{module_prefix}pkgbase": b"linux-m4rch\n",
        "usr/lib/asahi-boot/apple-j614s.dtb": (staged / "apple-j614s.dtb").read_bytes(),
    }
    expected.update({"usr/" + name: contents for name, contents in modules.items()})
    seen, masks, info = set(), set(), None
    with tarfile.open(package, "r:xz") as archive:
        for member in archive:
            name = member.name.removeprefix("./")
            if name in seen:
                raise ValueError(f"duplicate package path: {name}")
            seen.add(name)
            if name.startswith("/") or ".." in name.split("/"):
                raise ValueError(f"unsafe package path: {name}")
            if name in MASKS:
                if not member.issym() or member.linkname != "/dev/null":
                    raise ValueError(f"SEP mask missing or changed: {name}")
                masks.add(name)
            elif (
                member.issym()
                or member.islnk()
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError(f"unexpected package member type: {name}")
            if name == ".PKGINFO":
                info = archive.extractfile(member).read().decode("utf-8")
            if (
                name.startswith("usr/" + module_prefix)
                and member.isfile()
                and name not in expected
            ):
                raise ValueError(f"unexpected packaged module file: {name}")
            if name in expected:
                if (
                    not member.isfile()
                    or archive.extractfile(member).read() != expected[name]
                ):
                    raise ValueError(f"packaged content differs: {name}")
    if set(expected) - seen or masks != MASKS:
        raise ValueError("package is missing required kernel files or SEP masks")
    if info is None or not {
        "pkgname = linux-m4rch",
        "pkgver = 7.3.0-29",
        "arch = aarch64",
        "backup = etc/default/update-m1n1",
        "backup = etc/default/grub.d/50-m4rch.cfg",
    }.issubset(set(info.splitlines())):
        raise ValueError("package identity mismatch")
    return {
        "package_sha256": preflight.sha256(package),
        "kernel_release": candidate.RELEASE,
        "verified_module_files": len(modules),
        "sep_units_masked": True,
        "generic_m1n1_update_disabled": True,
        "native_boot_tested": False,
        "install_ready": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("staged_inputs", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.package, args.staged_inputs), indent=2))


if __name__ == "__main__":
    main()
