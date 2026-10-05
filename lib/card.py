"""Checked macOS boot-volume and raw SD-write primitives."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
import hashlib
import os
from pathlib import Path
import platform
import plistlib
import re
import subprocess
import sys
import uuid

from common import run

APP = "Finish Installation.app"
RESOURCES = Path(APP) / "Contents/Resources"


def canonical_uuid(value):
    return str(uuid.UUID(value)).upper()


def require_macos():
    if platform.system() != "Darwin":
        raise ValueError("Boot stub preparation requires macOS diskutil and hdiutil")
    model = subprocess.check_output(["sysctl", "-n", "hw.model"], text=True).strip()
    if model != "Mac16,8":
        raise ValueError("This experimental stub is only for Mac16,8")


def platform_uuid():
    data = plistlib.loads(subprocess.check_output(
        ["ioreg", "-a", "-rd1", "-c", "IOPlatformExpertDevice"]))
    return canonical_uuid(data[0]["IOPlatformUUID"])


def confirm(phrase, explanation):
    print(explanation, flush=True)
    if not sys.stdin.isatty():
        raise ValueError("This operation needs an interactive terminal; no unattended confirmation")
    if input(f"Type {phrase!r} to continue: ") != phrase:
        raise ValueError("Cancelled; confirmation did not match")


def checked_path(base, relative, *, leaf_symlink=False):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unsafe path below a mounted card volume")
    cursor = Path(base)
    for index, component in enumerate(relative.parts):
        cursor = cursor / component
        if cursor.is_symlink() and not (leaf_symlink and index == len(relative.parts) - 1):
            raise ValueError(f"Unexpected symlink in card destination: {cursor}")
    return cursor


def mounted(dutil, volume, *, allow_mount=True):
    info = dutil.info(volume)
    if not info.get("MountPoint"):
        if not allow_mount:
            raise ValueError("Volume is no longer mounted; read-only inspection will not mount it")
        dutil.run("mount", volume)
        info = dutil.info(volume)
    path = Path(info.get("MountPoint", ""))
    if not path.is_absolute() or not str(path).startswith("/Volumes/") or path.is_symlink():
        raise ValueError(f"Unsafe or missing volume mount point: {volume}")
    check = dutil.info(str(path))
    if (check.get("DeviceIdentifier") != info.get("DeviceIdentifier")
            or not info.get("VolumeUUID") or check.get("VolumeUUID") != info["VolumeUUID"]):
        raise ValueError("Mounted directory does not belong to the requested volume")
    return path


def mounted_writable(dutil, volume, expected_uuid):
    """Remount only an already identified card volume, then recheck its identity."""
    path = mounted(dutil, volume)

    def checked(info):
        if (info.get("DeviceIdentifier") != volume
                or info.get("VolumeUUID") != expected_uuid
                or info.get("MountPoint") != str(path)):
            raise ValueError("Card volume identity or mount point changed before a write")
        if info.get("APFSSnapshot") is True or info.get("Sealed") in (True, "Yes"):
            raise ValueError("Refusing to remount a snapshot or sealed System volume")
        if info.get("WritableMedia") is not True:
            raise ValueError("Card volume's underlying media is not writable")
        if type(info.get("WritableVolume")) is not bool:
            raise ValueError("Cannot determine whether the card volume is writable")
        return info

    before = checked(dutil.info(str(path)))
    if not before["WritableVolume"]:
        # APFS System-role volumes normally mount read-only after reattachment.
        # Pinned Asahi uses this same update-mount operation for stub repair.
        run(["/sbin/mount", "-u", "-w", path])
    after = checked(dutil.info(volume))
    check_path = checked(dutil.info(str(path)))
    for field in ("ParentWholeDisk", "APFSContainerReference", "APFSPhysicalStores", "DiskUUID", "FilesystemType"):
        if any(info.get(field) != before.get(field) for info in (after, check_path)):
            raise ValueError("Card volume backing storage changed during remount")
    if not all(info.get("WritableVolume") is True and info.get("Writable") is True
               for info in (after, check_path)):
        raise ValueError(f"Card volume is still read-only after remount: {path}")
    return path


def set_bootable(path):
    """APFS boot-volume flag, as used by pinned Asahi util.py (not LocalPolicy)."""
    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    function = library.fsctl
    function.restype = ctypes.c_int
    function.argtypes = (ctypes.c_char_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_int), ctypes.c_uint)
    flag = ctypes.c_int(1)
    if function(os.fsencode(path), 0xc0044a57, ctypes.byref(flag), 0) == -1:
        raise OSError(ctypes.get_errno(), "Unable to mark APFS System volume bootable")


def launcher_files():
    return {
        Path(APP) / "Contents/MacOS/launch.sh": b'#!/bin/sh\nexec /System/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal "${0%/*}/../Resources/enroll.sh"\n',
        Path(APP) / "Contents/Info.plist": plistlib.dumps({
            "CFBundleDisplayName": "Install m4rch", "CFBundleExecutable": "launch.sh"}),
        Path(".IAPhysicalMedia"): plistlib.dumps({
            "AppName": APP, "ProductBuildVersion": "25F84", "ProductVersion": "26.5.2"}),
    }


def source_off_target(dutil, image, device):
    # diskutil accepts a device or mount point, not an arbitrary directory.
    # df -P identifies the mounted filesystem even across macOS firmlinks.
    output = subprocess.check_output(["/bin/df", "-P", str(image.resolve())], text=True)
    sources = [line.split()[0] for line in output.splitlines()[1:] if line.split()]
    if len(sources) != 1 or not re.fullmatch(r"/dev/disk[0-9]+(?:s[0-9]+)*", sources[0]):
        raise ValueError("Cannot identify the image source's local disk")
    info = dutil.info(sources[0])
    stores = info.get("APFSPhysicalStores", [])
    parents = {dutil.info(x["APFSPhysicalStore"]).get("ParentWholeDisk") for x in stores}
    if not parents:
        parents = {info.get("ParentWholeDisk")}
    if None in parents or device in parents:
        raise ValueError("Cannot prove that the image source is outside the target SD card")


def verify_flashed(device, size, expected):
    with open(device, "rb", buffering=0) as stream:
        verify_flashed_stream(stream, size, expected)


def verify_flashed_stream(stream, size, expected):
    digest = hashlib.sha256()
    stream.seek(0)
    remaining = size
    while remaining:
        data = stream.read(min(4 * 1024 ** 2, remaining))
        if not data:
            raise ValueError("Flash readback ended before the image boundary")
        digest.update(data)
        remaining -= len(data)
    if digest.hexdigest() != expected:
        raise ValueError("Flashed SD image failed SHA-256 readback verification")


@contextmanager
def exclusive_disk(dutil, summary, config):
    """Keep macOS from reprobing/remounting between dependent raw operations."""
    dutil.assert_unchanged(summary, config)
    dutil.run("unmountDisk", summary["device"])
    dutil.assert_unchanged(summary, config)
    raw = "/dev/r" + summary["device"]
    # IOMediaBSDClient maps O_EXLOCK to exclusive I/O Kit media access.
    # NONBLOCK makes contention an error rather than an unbounded wait.
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_EXLOCK | os.O_NONBLOCK
    descriptor = os.open(raw, flags)
    with os.fdopen(descriptor, "r+b", buffering=0) as stream:
        yield stream


def write_and_verify_image(image, stream, size, expected, total_bytes):
    from gpt import relocate_stream, sync_disk
    stream.seek(0)
    written = 0
    next_progress = 1024 ** 3
    with image.open("rb") as source:
        while block := source.read(4 * 1024 ** 2):
            pending = memoryview(block)
            while pending:
                count = stream.write(pending)
                if count is None or count <= 0:
                    raise OSError("Unable to complete the SD image write")
                pending = pending[count:]
                written += count
            if written >= next_progress:
                print(f"Wrote {written / 1024 ** 3:.1f} / {size / 1024 ** 3:.1f} GiB", flush=True)
                next_progress += 1024 ** 3
    if written != size:
        raise ValueError("Source image size changed during the write")
    sync_disk(stream)
    print("Verifying the complete flashed image before relocating GPT metadata ...", flush=True)
    verify_flashed_stream(stream, size, expected)
    relocate_stream(stream, total_bytes)


def source_owner_metadata(dutil):
    info = dutil.info("/")
    group = canonical_uuid(info["APFSVolumeGroupID"])
    cref = info["APFSContainerReference"]
    container = next(x for x in dutil.apfs()["Containers"] if x["ContainerReference"] == cref)
    preboot = [x for x in container["Volumes"] if x.get("Roles") == ["Preboot"]]
    if len(preboot) != 1:
        raise ValueError("Cannot identify the current macOS Preboot volume")
    # The source is the existing OS's mounted Preboot; never use this source
    # mount as an installation destination (mounted() deliberately rejects it).
    pb_info = dutil.info(preboot[0]["DeviceIdentifier"])
    mount = pb_info.get("MountPoint")
    if not mount or dutil.info(mount).get("VolumeUUID") != pb_info.get("VolumeUUID"):
        raise ValueError("Current macOS Preboot must be mounted and have the expected identity")
    path = Path(mount) / group / "var/db/AdminUserRecoveryInfo.plist"
    if path.is_symlink() or not path.is_file():
        raise ValueError("Current macOS owner recovery metadata is missing")
    # Parse to reject an empty or malformed owner record, but never log it.
    data = path.read_bytes()
    owners = plistlib.loads(data)
    if not owners or not isinstance(owners, dict):
        raise ValueError("Current macOS has no usable owner recovery metadata")
    return data
