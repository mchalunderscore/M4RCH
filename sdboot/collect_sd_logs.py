#!/usr/bin/env python3
"""Read selected Arch SD logs on macOS; never mount, repair or write the card.

Uses the project-local upstream debugfs in read-only recovery mode. Only
metadata, pacman.log and bounded regular journal files are copied to a new local
directory. Run with sudo because macOS protects raw block devices.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import resource
import stat
import subprocess
import sys
import tempfile
import time
import uuid

PROJECT = Path(__file__).resolve().parents[1]
DEBUGFS = PROJECT / "out/native-ext4-tools/e2fsprogs-1.47.4/debugfs/debugfs"
DEBUGFS_SHA256 = "2aa2090834ab130d0ffea769a15fb7152691c93d6934de78d07123d246388b2a"
ROOT_UUID = "a0418040-b5b3-4ae8-9288-1c7c6dbda604"
ROOT_PARTITION_UUID = "5D3356D1-51E3-513C-8CFF-BC034A445A99"
MIB = 1024 * 1024
MAX_FILE = 64 * MIB
MAX_TOTAL = 256 * MIB
MAX_FILES = 32
MAX_MACHINES = 4
MAX_COMMANDS = 80
MACHINE = re.compile(r"[0-9a-f]{32}\Z")
JOURNAL = re.compile(r"[A-Za-z0-9_@.+-]+\.journal~?\Z")


def disk_info(name):
    result = subprocess.run(["/usr/sbin/diskutil", "info", "-plist", name],
                            check=True, capture_output=True)
    return plistlib.loads(result.stdout)


def validate_disk(device, info=disk_info):
    if not re.fullmatch(r"/dev/disk[0-9]+", device):
        raise ValueError("Use a whole SD disk, for example /dev/disk7")
    name = device.removeprefix("/dev/")
    whole, part = info(name), info(name + "s2")
    if (whole.get("DeviceIdentifier") != name
            or whole.get("DeviceNode") != device
            or whole.get("WholeDisk") is not True
            or whole.get("VirtualOrPhysical") != "Physical"
            or whole.get("BusProtocol") != "Secure Digital"
            or not (whole.get("Removable") is True
                    or whole.get("RemovableMedia") is True)):
        raise ValueError("The selected disk is not a physical removable SD card")
    if (part.get("DeviceIdentifier") != name + "s2"
            or part.get("DeviceNode") != device + "s2"
            or part.get("ParentWholeDisk") != name
            or part.get("WholeDisk") is not False
            or part.get("Content") != "Linux Filesystem"
            or str(part.get("DiskUUID", "")).upper() != ROOT_PARTITION_UUID
            or part.get("Mounted") is True or part.get("MountPoint")):
        raise ValueError("Partition 2 is not this project's unmounted Linux root")
    return device + "s2", whole, part


def validate_superblock(raw):
    sb = raw[1024:2048]
    if (len(raw) != 4096 or sb[56:58] != b"\x53\xef"
            or str(uuid.UUID(bytes=bytes(sb[104:120]))) != ROOT_UUID
            or sb[120:136].split(b"\0", 1)[0] != b"ARCHROOT"):
        raise ValueError("The SD ext4 identity does not match ARCHROOT")


def safe_directory(path):
    for part in (*reversed(path.parents), path):
        if not stat.S_ISDIR(part.lstat().st_mode):
            raise ValueError(f"Expected a real, non-symlink directory: {part}")


def child_limits(size):
    def apply():
        resource.setrlimit(resource.RLIMIT_FSIZE, (size, size))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return apply


class Capture:
    def __init__(self, device, destination, debugfs=DEBUGFS):
        if any(char in str(destination) for char in '\\"\r\n'):
            raise ValueError("Capture path contains unsupported quoting characters")
        self.device, self.destination, self.debugfs = device, destination, debugfs
        self.total = 0
        self.files = 0
        self.messages = []
        self.commands = 0
        self.deadline = time.monotonic() + 300

    def command(self, request, limit=4 * MIB, *, missing_ok=False):
        # -c avoids loading allocation bitmaps from the unreplayed filesystem.
        # No shell, -w, -n, replay or arbitrary user-supplied request.
        remaining = self.deadline - time.monotonic()
        if self.commands >= MAX_COMMANDS or remaining <= 0:
            raise ValueError("Diagnostic command/time limit reached; partial capture saved")
        self.commands += 1
        with tempfile.TemporaryFile(dir=self.destination) as output, \
                tempfile.TemporaryFile(dir=self.destination) as errors:
            result = subprocess.run([str(self.debugfs), "-c", "-R", request, self.device],
                                    stdout=output, stderr=errors,
                                    timeout=min(90, remaining), preexec_fn=child_limits(limit))
            output.seek(0)
            text = output.read(4 * MIB).decode("utf-8", "replace")
            errors.seek(0)
            diagnostics = errors.read(4 * MIB).decode("utf-8", "replace")
        self.messages.append("$ debugfs -c -R " + repr(request) + "\n" + text + diagnostics)
        # debugfs often returns zero even when it could not open the filesystem.
        # Never feed its /dev/... error messages into the directory parser, or
        # mistake unreadable metadata for a missing optional log. Also reject
        # its automatic retry that disables checks after a bad SB checksum.
        problems = [line for line in diagnostics.splitlines()
                    if line.strip() and not re.fullmatch(r"debugfs [0-9].*", line)]
        if "Checksum errors in superblock! Retrying..." in text:
            problems.insert(0, "debugfs attempted to disable checks after a superblock checksum error")
        if (not result.returncode and missing_ok and problems
                and all(re.fullmatch(r"[^\n]+: File not found by ext2_lookup", line)
                        for line in problems)):
            return ""
        if result.returncode or problems:
            reason = problems[0] if problems else f"exit status {result.returncode}"
            raise ValueError(f"Read-only debugfs failed for {request!r}: {reason}")
        return text

    def listing(self, directory):
        rows = []
        for line in self.command("ls -p " + directory, missing_ok=True).splitlines():
            if not line.startswith("/"):
                continue
            fields = line.split("/")
            if len(fields) != 8 or not fields[2].isdigit():
                raise ValueError("Unexpected debugfs directory listing")
            rows.append((fields[5], int(fields[2], 8)))
            if len(rows) >= 512:
                raise ValueError("Diagnostic directory entry limit reached")
        return rows

    def dump(self, source, destination):
        details = self.command("stat " + source, missing_ok=True)
        size = re.search(r"\bSize:\s+([0-9]+)", details)
        if "Type: regular" not in details or not size:
            self.messages.append("Skipped absent/non-regular file: " + source)
            return
        size = int(size.group(1))
        if (size > MAX_FILE or self.total + size > MAX_TOTAL
                or self.files >= MAX_FILES):
            self.messages.append("Skipped file beyond diagnostic size/count limit: " + source)
            return
        if destination.exists() or destination.is_symlink():
            raise ValueError("Capture output unexpectedly exists")
        # dump creates only one regular local file; unlike rdump it does not
        # reproduce filesystem-supplied directory names, links or permissions.
        self.command(f'dump {source} "{destination}"', MAX_FILE + 4096)
        if (not destination.exists() or not stat.S_ISREG(destination.lstat().st_mode)
                or destination.stat().st_size != size):
            raise ValueError("Diagnostic file extraction was incomplete")
        destination.chmod(0o600)
        self.total += size
        self.files += 1

    def collect(self):
        try:
            self.command("stats")
            self.command("stat <8>")
            self.command("logdump -S")
            self.dump("/var/log/pacman.log", self.destination / "pacman.log")
            journals = self.destination / "journal"
            journals.mkdir(mode=0o700)
            machines = candidates = 0
            for machine, mode in self.listing("/var/log/journal"):
                if not MACHINE.fullmatch(machine) or not stat.S_ISDIR(mode):
                    continue
                if machines >= MAX_MACHINES:
                    self.messages.append("Stopped at diagnostic machine-directory limit")
                    break
                machines += 1
                target = journals / machine
                target.mkdir(mode=0o700)
                for filename, mode in self.listing("/var/log/journal/" + machine):
                    if not JOURNAL.fullmatch(filename) or not stat.S_ISREG(mode):
                        continue
                    if candidates >= MAX_FILES:
                        self.messages.append("Stopped at diagnostic journal candidate limit")
                        return
                    candidates += 1
                    self.dump("/var/log/journal/" + machine + "/" + filename,
                              target / filename)
        finally:
            (self.destination / "debugfs.txt").write_text("\n".join(self.messages))


def restore_ownership(destination):
    # Only the newly-created, private output tree, never the SD or parent dirs.
    uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
    if (os.geteuid() == 0 and uid and gid and uid.isdecimal() and gid.isdecimal()
            and 0 < int(uid) < 2**31 and 0 < int(gid) < 2**31):
        for path in [*destination.rglob("*"), destination]:
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode) or stat.S_ISREG(mode):
                os.chown(path, int(uid), int(gid), follow_symlinks=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disk", required=True)
    args = parser.parse_args()
    if sys.platform != "darwin" or os.geteuid() != 0:
        raise ValueError("Run this read-only macOS collector with sudo")
    if (not stat.S_ISREG(DEBUGFS.lstat().st_mode)
            or hashlib.sha256(DEBUGFS.read_bytes()).hexdigest() != DEBUGFS_SHA256):
        raise ValueError("The project-local debugfs binary is missing or changed")
    device, whole, part = validate_disk(args.disk)
    with open(device, "rb", buffering=0) as stream:
        raw = stream.read(4096)
    validate_superblock(raw)
    base = PROJECT / "out/sdboot/diagnostics"
    safe_directory(base.parent)
    # The common parent contains only private per-capture directories. Keep it
    # traversable if this first invocation creates it as root under sudo.
    try:
        base.mkdir(mode=0o755)
    except FileExistsError:
        pass
    else:
        base.chmod(0o755)
    safe_directory(base)
    os.umask(0o077)
    prefix = "native-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
    destination = Path(tempfile.mkdtemp(prefix=prefix, dir=base))
    try:
        (destination / "superblock.bin").write_bytes(raw)
        (destination / "disk.json").write_text(json.dumps({"disk": whole, "root": part}, indent=2))
        print(f"Reading {device}; saving selected logs to {destination}", flush=True)
        Capture(device, destination).collect()
    finally:
        restore_ownership(destination)
    print("Capture complete. The SD card was opened read-only and was not mounted or repaired.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        sys.exit("m4rch: " + str(error))
