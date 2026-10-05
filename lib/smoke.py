"""Shared ext4 inspection and signed package fixtures for native-image VM checks."""
from __future__ import annotations

import json
import re

from common import run, sha256


def debugfs(image, commands, work):
    command_file = work / "debugfs.commands"
    command_file.write_text("\n".join(commands) + "\n")
    result = run(["debugfs", "-w", "-f", command_file, image], capture_output=True, text=True)
    # debugfs returns zero for many command-level errors. Callers verify the
    # written files by dumping them, rather than trusting that return value.
    return result.stdout + result.stderr


def dump_file(image, source, destination):
    run(["debugfs", "-R", f"dump {source} {destination}", image], capture_output=True, text=True)
    if not destination.is_file():
        raise ValueError(f"debugfs could not read back {source}")
    return destination.read_bytes()


def signed_package_fixture(lockfile, cache):
    """Use an already downloaded, pinned package without resolving any mirror."""
    entries = json.loads(lockfile.read_text())["files"]
    packages = [entry for entry in entries
                if re.fullmatch(r"default-cursors-[A-Za-z0-9_.+-]+\.pkg\.tar\.(?:xz|zst)", entry["filename"])]
    if len(packages) != 1:
        raise ValueError("Pinned smoke package default-cursors is missing or ambiguous")
    package = packages[0]
    signatures = [entry for entry in entries if entry["filename"] == package["filename"] + ".sig"]
    if len(signatures) != 1:
        raise ValueError("Pinned smoke package signature is missing or ambiguous")
    files = [cache / entry["filename"] for entry in (package, signatures[0])]
    for file, entry in zip(files, (package, signatures[0])):
        if not file.is_file() or sha256(file) != entry["sha256"]:
            raise ValueError(f"Pinned smoke package input failed verification: {file}")
    return files
