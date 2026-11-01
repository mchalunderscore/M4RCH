#!/usr/bin/env python3
"""Read-only validation of the retained M4RCH initramfs module closure."""

import argparse
import gzip
import io
import json
from pathlib import Path
import stat
import subprocess
import tarfile
import tempfile

import preflight

INITRAMFS = "cache/jack-promotion/recovery/before/initramfs-linux-m4rch.img"
INITRAMFS_SHA256 = "d7c3bc9f981c41e5c090cad5e03b053846cf1e81f34d47cb82d0f30d6850f8e7"
RELEASE = preflight.RELEASE
ROOTS = (
    "kernel/fs/btrfs/btrfs.ko",
    "kernel/drivers/nvme/host/nvme-apple.ko",
)
MAX_DECOMPRESSED = 256 * 1024 * 1024


def cpio_entries(data):
    """Parse one bounded newc archive without extracting files."""
    entries = {}
    pos = 0
    while True:
        if pos + 110 > len(data):
            raise ValueError("truncated cpio header")
        header = data[pos : pos + 110]
        if header[:6] not in (b"070701", b"070702"):
            raise ValueError("unsupported cpio header")
        try:
            values = [int(header[i : i + 8], 16) for i in range(6, 110, 8)]
        except ValueError as exc:
            raise ValueError("invalid cpio header") from exc
        mode, size, namesize = values[1], values[6], values[11]
        if namesize < 1 or pos + 110 + namesize > len(data):
            raise ValueError("invalid cpio name length")
        raw_name = data[pos + 110 : pos + 110 + namesize]
        if raw_name[-1:] != b"\0":
            raise ValueError("unterminated cpio name")
        name = raw_name[:-1].decode("utf-8")
        pos = (pos + 110 + namesize + 3) & ~3
        end = pos + size
        if end > len(data):
            raise ValueError("truncated cpio file")
        if name == "TRAILER!!!":
            return entries, (end + 3) & ~3
        if name in entries:
            raise ValueError("duplicate cpio entry")
        entries[name] = (mode, data[pos:end])
        pos = (end + 3) & ~3


def read_main_archive(path):
    data = path.read_bytes()
    _, end = cpio_entries(data)
    while end < len(data) and data[end] == 0:
        end += 1
    if data[end : end + 3] != b"\x1f\x8b\x08":
        raise ValueError("expected gzip-compressed main initramfs")
    with gzip.GzipFile(fileobj=io.BytesIO(data[end:])) as stream:
        unpacked = stream.read(MAX_DECOMPRESSED + 1)
    if len(unpacked) > MAX_DECOMPRESSED:
        raise ValueError("initramfs exceeds unpacked limit")
    return cpio_entries(unpacked)[0]


def module_closure(modules_dep, roots=ROOTS):
    mapping = {}
    for line in modules_dep.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError("invalid modules.dep line")
        name, deps = line.split(":", 1)
        if name in mapping or not name.startswith("kernel/"):
            raise ValueError("invalid or duplicate module dependency")
        mapping[name] = deps.split()
    pending, seen = list(roots), set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        if name not in mapping:
            raise ValueError(f"missing dependency record: {name}")
        seen.add(name)
        pending.extend(mapping[name])
    return sorted(seen)


def verify_boot_parameters(entries):
    """Exercise retained shell functions with fake mount and modprobe commands."""

    def script(name):
        entry = entries.get(name)
        if not entry or not stat.S_ISREG(entry[0]):
            raise ValueError(f"missing initramfs script: {name}")
        return entry[1].decode("utf-8")

    init = script("init")
    functions = script("init_functions")
    config = script("config")
    module_line = "modprobe -qab ${earlymodules//,/ } $MODULES"
    if init.count(module_line) != 1:
        raise ValueError("init early-module loading path changed")
    with tempfile.TemporaryDirectory(prefix="j614s-initramfs-audit-") as directory:
        root = Path(directory)
        (root / "init_functions").write_text(functions)
        (root / "config").write_text(config)
        harness = (
            r"""set -e
source "$1/init_functions"
source "$1/config"
parse_cmdline parse_cmdline_item "$1/cmdline" <<< 'root=UUID=example rootflags=subvol=root,compress=zstd:1 rootfstype=btrfs rw earlymodules=btrfs'
modprobe() { printf 'module:%s\n' "$@"; }
mount() { printf 'mount:%s\n' "$@"; }
msg() { :; }
"""
            + module_line
            + r"""
default_mount_handler /sysroot
"""
        )
        result = subprocess.run(
            ["/bin/bash", "-c", harness, "j614s-audit", str(root)],
            check=True,
            text=True,
            capture_output=True,
            timeout=10,
        ).stdout.splitlines()
    expected_mount = [
        "mount:-t",
        "mount:btrfs",
        "mount:-o",
        "mount:rw,subvol=root,compress=zstd:1",
        "mount:UUID=example",
        "mount:/sysroot",
    ]
    if "module:-qab" not in result or "module:btrfs" not in result:
        raise ValueError("earlymodules=btrfs was not passed to modprobe")
    if [line for line in result if line.startswith("mount:")] != expected_mount:
        raise ValueError("root, rootfstype or rootflags were not passed to mount")
    return {
        "earlymodules_btrfs": "passed to modprobe",
        "root_uuid": "passed to mount",
        "rootfstype": "btrfs passed to mount",
        "rootflags": "subvol=root,compress=zstd:1 passed to mount",
        "rw": "passed to mount",
        "test_environment": "mocked mount and modprobe under bash; not a native boot",
    }


def audit(root):
    image = root / INITRAMFS
    archive = root / preflight.INPUTS["modules"][0]
    if preflight.sha256(image) != INITRAMFS_SHA256:
        raise ValueError("retained initramfs hash mismatch")
    if preflight.sha256(archive) != preflight.INPUTS["modules"][1]:
        raise ValueError("retained modules archive hash mismatch")
    entries = read_main_archive(image)
    prefix = f"lib/modules/{RELEASE}/"
    with tarfile.open(archive, "r:gz") as source:
        dep = source.extractfile(prefix + "modules.dep")
        if dep is None:
            raise ValueError("modules.dep is not a regular file")
        closure = module_closure(dep.read().decode("utf-8"))
        for name in closure:
            member = source.getmember(prefix + name)
            if not member.isfile():
                raise ValueError(f"module is not a regular file: {name}")
            original = source.extractfile(member).read()
            entry = entries.get("usr/" + prefix + name)
            if entry is None or not stat.S_ISREG(entry[0]) or entry[1] != original:
                raise ValueError(f"initramfs module missing or different: {name}")
    init = entries.get("init")
    return {
        "initramfs_sha256": INITRAMFS_SHA256,
        "release": RELEASE,
        "module_closure": closure,
        "init_present": bool(init and (stat.S_ISREG(init[0]) or stat.S_ISLNK(init[0]))),
        "boot_parameters": verify_boot_parameters(entries),
        "native_btrfs_boot_verified": False,
        "note": "Mocked shell checks do not validate real UUID discovery, init hooks, firmware, or a native boot.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("m4rch_root", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.m4rch_root), indent=2))
    except (
        OSError,
        UnicodeError,
        ValueError,
        KeyError,
        tarfile.TarError,
        subprocess.SubprocessError,
    ) as exc:
        parser.exit(1, f"audit failed: {exc}\n")


if __name__ == "__main__":
    main()
