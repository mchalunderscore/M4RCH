"""Stage Apple's pinned recovery/boot files without touching disks or policy.

The layout follows Asahi's MIT-licensed StubInstaller at ASAHI_REVISION.
Preboot/ and Recovery/ here are relative to the eventual volume-group UUID.
No machine owner records, credentials, personalized tickets, or UUIDs are saved.
The caller supplies those only when installing onto an explicitly chosen disk.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import shutil
import stat
import sys
import tempfile
import zipfile

from common import download, sha256, write_json
import firmware


ROOT = Path(__file__).resolve().parent.parent
LOCK_PATH = ROOT / "stub-inputs.lock.json"
EXCLUDE = {"BaseSystem", "OS", "Ap,SystemVolumeCanonicalMetadata",
           "RestoreRamDisk", "RestoreTrustCache"}
BOOTABILITY_PREFIX = "BootabilityBundle/Restore/Bootability/"
RESTORE_PREFIX = "Firmware/Manifests/restore/macOS Customer/"


def relative_path(name):
    path = PurePosixPath(name)
    if (not name or name == "." or path.is_absolute() or ".." in path.parts
            or "\x00" in name or str(path) != name):
        raise ValueError(f"Unsafe payload path: {name!r}")
    return path


def load_lock():
    lock = json.loads(LOCK_PATH.read_text())
    expected = {"schema": 1, "apple_url": firmware.APPLE_URL,
                "apple_size": firmware.APPLE_SIZE, "apple_build": "25F84",
                "apple_version": "26.5.2", "model": "Mac16,8",
                "device_class": "j614sap", "board_id": "0x04", "chip_id": "0x6040",
                "build_manifest_sha256": firmware.MANIFEST_SHA256,
                "base_system_dmg_sha256": firmware.DMG_SHA256,
                "asahi_revision": firmware.ASAHI_REVISION,
                "asahi_source_sha256": firmware.ASAHI_SHA256,
                "restore_bundle_path": "restore"}
    if any(lock.get(key) != value for key, value in expected.items()):
        raise ValueError("Stub input lock does not match the supported 25F84 profile")
    for name, info in lock["files"].items():
        relative_path(name)
        if (len(info["sha256"]) != 64 or info["bytes"] < 0
                or stat.S_IFMT(info["mode"]) not in (stat.S_IFREG, stat.S_IFLNK)
                or info["mode"] & 0o7000):
            raise ValueError(f"Invalid locked Apple member: {name}")
    return lock


def select_identity(manifest, build="25F84"):
    if manifest.get("ProductBuildVersion") != build:
        raise ValueError(f"Stub BuildManifest must be {build}")
    matches = [identity for identity in manifest["BuildIdentities"]
               if identity.get("ApBoardID") == "0x04"
               and identity.get("ApChipID") == "0x6040"
               and identity["Info"].get("DeviceClass") == "j614sap"
               and identity["Info"].get("RestoreBehavior") == "Erase"
               and identity["Info"].get("Variant") == "macOS Customer"]
    if len(matches) != 1:
        raise ValueError("Expected exactly one J614s/T6040 customer restore identity")
    return matches[0]


def restore_members(identity):
    return {value["Info"]["Path"] for key, value in identity["Manifest"].items()
            if key not in EXCLUDE and not key.startswith("Cryptex")}


def check_input(path, info):
    return (path.is_file() and not path.is_symlink()
            and path.stat().st_size == info["bytes"]
            and sha256(path) == info["sha256"])


def fetch_inputs(cache, source, lock):
    inputs = cache / "stub-inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    missing = []
    for name, info in lock["files"].items():
        path = inputs / name
        if path.exists() or path.is_symlink():
            if not check_input(path, info):
                raise ValueError(f"Cached stub input changed; remove and retry: {path}")
        else:
            missing.append(name)
    if not missing:
        return inputs
    sys.path.insert(0, str(source / "src"))
    try:
        from urlcache import URLCache
        print(f"Downloading {len(missing)} pinned Apple boot/recovery metadata members.", flush=True)
        with contextlib.redirect_stdout(sys.stderr):
            remote = URLCache(firmware.APPLE_URL)
            try:
                if remote.size != firmware.APPLE_SIZE:
                    raise ValueError("Apple restore archive size changed")
                with zipfile.ZipFile(remote) as archive:
                    manifest = archive.read("BuildManifest.plist")
                    if hashlib.sha256(manifest).hexdigest() != firmware.MANIFEST_SHA256:
                        raise ValueError("Apple BuildManifest changed")
                    for name in missing:
                        info = lock["files"][name]
                        member = archive.getinfo(name)
                        if member.file_size != info["bytes"] or member.external_attr >> 16 != info["mode"]:
                            raise ValueError(f"Apple archive metadata changed: {name}")
                        path = inputs / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        part = path.with_name(path.name + ".part")
                        with archive.open(member) as src, part.open("wb") as dst:
                            shutil.copyfileobj(src, dst, 1024 * 1024)
                        if not check_input(part, info):
                            raise ValueError(f"Apple stub member SHA-256 changed: {name}")
                        part.replace(path)
            finally:
                remote.close_connection()
    finally:
        sys.path.remove(str(source / "src"))
    return inputs


def safe_link(root, destination, target):
    if not target or PurePosixPath(target).is_absolute() or "\x00" in target:
        raise ValueError(f"Unsafe Apple framework symlink: {target!r}")
    resolved = (destination.parent / target).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Apple framework symlink escapes payload: {destination}")
    destination.symlink_to(target)


def copy_member(inputs, stage, lock, name, destination):
    relative_path(name)
    relative_path(destination)
    info = lock["files"][name]
    source = inputs / name
    if not check_input(source, info):
        raise ValueError(f"Unverified Apple member: {name}")
    target = stage / destination
    target.parent.mkdir(parents=True, exist_ok=True)
    if stat.S_ISLNK(info["mode"]):
        safe_link(stage, target, source.read_text())
    else:
        shutil.copyfile(source, target)
        target.chmod(info["mode"] & 0o777)


def assemble(inputs, dmg, apple_manifest, source, stage, lock):
    identity = select_identity(apple_manifest, lock["apple_build"])
    members = restore_members(identity)
    if not members <= lock["files"].keys():
        raise ValueError("Identity contains unlocked restore members")
    bootcaches = plistlib.loads((inputs / "usr/standalone/bootcaches.plist").read_bytes())
    bless = bootcaches["bless2"]
    if not bless.get("SupportsPairedRecovery") or not bless.get("SupportsExternalPrebootObjects"):
        raise ValueError("Pinned boot metadata does not support paired external Recovery")
    # 25F84 removed RestoreBundlePath from bootcaches. Its BootabilityBrain
    # instead uses the literal 'restore'; see docs/stub-layout.md for evidence.
    if bless.get("RestoreBundlePath", "restore") != "restore":
        raise ValueError("Unexpected restore bundle layout")
    restore = "Preboot/restore"
    cs = "System/System/Library/CoreServices"
    for directory in ("Data/private/var/db/dslocal", "System/Finish Installation.app/Contents/Resources",
                      restore, "Recovery/usr/standalone/firmware"):
        (stage / directory).mkdir(parents=True, exist_ok=True)
    copy_member(inputs, stage, lock, "usr/standalone/bootcaches.plist", "System/usr/standalone/bootcaches.plist")
    copy_member(inputs, stage, lock, "PlatformSupport.plist", cs + "/PlatformSupport.plist")
    system_version = plistlib.loads((inputs / "SystemVersion.plist").read_bytes())
    if (system_version.get("ProductBuildVersion") != lock["apple_build"]
            or system_version.get("ProductVersion") != lock["apple_version"]):
        raise ValueError("Unexpected stub SystemVersion")
    system_version["ProductUserVisibleVersion"] += " (stub)"
    (stage / cs / "SystemVersion.plist").write_bytes(plistlib.dumps(system_version))
    filtered = copy.deepcopy(apple_manifest)
    filtered["BuildIdentities"] = [identity]
    (stage / restore / "BuildManifest.plist").write_bytes(plistlib.dumps(filtered))
    for name in ("SystemVersion.plist", "RestoreVersion.plist", "usr/standalone/bootcaches.plist"):
        copy_member(inputs, stage, lock, name, restore + "/" + name)
    for name in sorted(lock["files"]):
        if name.startswith(BOOTABILITY_PREFIX):
            destination = restore + "/Bootability/" + name.removeprefix(BOOTABILITY_PREFIX)
        elif name.startswith(RESTORE_PREFIX):
            destination = restore + "/" + name.removeprefix(RESTORE_PREFIX)
        elif name in members:
            destination = restore + "/" + name
        else:
            continue
        copy_member(inputs, stage, lock, name, destination)
    copy_member(inputs, stage, lock, "BootabilityBundle/Restore/Firmware/Bootability.dmg.trustcache",
                restore + "/Bootability/Bootability.trustcache")
    if not dmg.is_file() or dmg.is_symlink() or sha256(dmg) != lock["base_system_dmg_sha256"]:
        raise ValueError("Recovery BaseSystem must match the selected profile's decrypted DMG")
    target_dmg = stage / "Recovery/usr/standalone/firmware/arm64eBaseSystem.dmg"
    shutil.copyfile(dmg, target_dmg)
    target_dmg.chmod(0o644)
    # Preserve Asahi's launcher and its licence; the caller generates step2.sh
    # with real volume identities and inserts the verified Linux boot object.
    shutil.copytree(source / "src/step2/Finish Installation.app",
                    stage / "System/Finish Installation.app", dirs_exist_ok=True)
    shutil.copyfile(source / "src/step2/IAPhysicalMedia.plist", stage / "System/.IAPhysicalMedia")
    shutil.copyfile(source / "LICENSE", stage / "ASAHI-LICENSE")


def inventory(root):
    files, links, directories = {}, {}, []
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if name == "manifest.json":
            continue
        if path.is_symlink():
            target = os.readlink(path)
            if PurePosixPath(target).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError(f"Unsafe payload symlink: {name}")
            links[name] = target
        elif path.is_file():
            files[name] = {"bytes": path.stat().st_size, "sha256": sha256(path),
                           "mode": stat.S_IMODE(path.stat().st_mode)}
        elif path.is_dir():
            directories.append(name)
        else:
            raise ValueError(f"Unsupported payload entry: {path}")
    return files, links, directories


def verify(payload):
    payload = Path(payload).resolve()
    manifest = json.loads((payload / "manifest.json").read_text())
    load_lock()
    expected = {"schema": 1, "apple_build": "25F84", "model": "Mac16,8",
                "device_class": "j614sap", "board_id": "0x04", "chip_id": "0x6040",
                "restore_bundle_path": "restore", "input_lock_sha256": sha256(LOCK_PATH),
                "builder_sha256": sha256(__file__)}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("Cached stub payload metadata differs from the pinned builder/profile")
    files, links, directories = inventory(payload)
    if files != manifest.get("files") or links != manifest.get("symlinks") or directories != manifest.get("directories"):
        raise ValueError("Stub payload file content, mode, links, or directories changed")
    return manifest


def prepare(cache, output):
    cache, output = Path(cache).resolve(), Path(output).resolve()
    lock = load_lock()
    if output.exists():
        return verify(output)
    cache.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    firmware_inputs = cache / "firmware-inputs"
    dmg = firmware_inputs / firmware.BASE_MEMBER.removesuffix(".aea")
    manifest_path = firmware_inputs / "BuildManifest.plist"
    if not dmg.exists() or not manifest_path.exists():
        firmware.prepare(cache, cache / "stub-vendorfw")
    if sha256(manifest_path) != firmware.MANIFEST_SHA256:
        raise ValueError("Cached Apple BuildManifest changed")
    archive = download("https://codeload.github.com/AsahiLinux/asahi-installer/tar.gz/" + firmware.ASAHI_REVISION,
                       firmware_inputs / "asahi-installer-c53d66dc.tar.gz", firmware.ASAHI_SHA256)
    with tempfile.TemporaryDirectory(prefix="stub-tools-", dir=cache) as temporary:
        source = Path(temporary)
        firmware.extract_regular(archive, source, "asahi-installer-" + firmware.ASAHI_REVISION + "/")
        inputs = fetch_inputs(cache, source, lock)
        stage = Path(tempfile.mkdtemp(prefix=".stub-stage-", dir=output.parent))
        try:
            assemble(inputs, dmg, plistlib.loads(manifest_path.read_bytes()), source, stage, lock)
            files, links, directories = inventory(stage)
            manifest = {
                "schema": 1, "model": "Mac16,8", "device_class": "j614sap",
                "board_id": "0x04", "chip_id": "0x6040", "apple_build": "25F84",
                "apple_version": "26.5.2", "restore_bundle_path": "restore",
                "asahi_revision": firmware.ASAHI_REVISION,
                "input_lock_sha256": sha256(LOCK_PATH), "builder_sha256": sha256(__file__),
                "files": files, "symlinks": links, "directories": directories,
                "notes": ["Preboot and Recovery trees are relative to the target volume-group UUID.",
                          "This payload has no owner records, personalized tickets or boot policy.",
                          "The 25F84 BaseSystem is decrypted from its authenticated AEA input.",
                          "External SD recognition, personalization and native boot remain experimental."]}
            write_json(stage / "manifest.json", manifest)
            verify(stage)
            stage.replace(output)
            print(f"Verified unpersonalized J614s Apple boot payload: {output}", flush=True)
            return manifest
        finally:
            if stage.exists():
                shutil.rmtree(stage)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.cache, args.output)
