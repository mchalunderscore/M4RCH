"""Reproduce Wallace's J614s firmware from pinned, public Apple restore inputs.

This only downloads files and mounts one downloaded DMG read-only. It never
flashes firmware, reads user credentials, or changes macOS boot policy. Apple's
blobs remain local build inputs and are not part of the project source tree.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from common import download, run, sha256, write_json


ASAHI_REVISION = "c53d66dc71937efa2530d4323c81addaebb5a09b"
ASAHI_SHA256 = "c9a9acda2fade5db085055d8694e00a265b22e8f41d26d759b7527ccdb6034c7"
IPSW_VERSION = "3.1.702"
IPSW_TOOL_HASHES = {
    "arm64": "6c2d29bd550ac35a03299d64b2ea9cb671983f345897deb9d4757ef10f09a84d",
    "x86_64": "a024e00625ac72849fa821e31f4606cefcf222a34431716b77260c37e6d27749",
}
APPLE_URL = (
    "https://updates.cdn-apple.com/2026SpringFCS/fullrestores/140-24263/"
    "B95838F0-6815-4F0B-A039-156526C081AD/UniversalMac_26.5.2_25F84_Restore.ipsw"
)
APPLE_SIZE = 19769902281
MANIFEST_SHA256 = "a6e764ca158e10ea2ace9b74701f445eefbf012c9cdb5aaa616aa10a0b5197ef"
BASE_MEMBER = "022-21678-099.dmg.aea"
BASE_SHA256 = "fe56fcb5a0aa2e0214dbe69f108ed35670bf33d32fdc346c6efb1784cf7705cd"
DMG_SHA256 = "48067a9bfc7714bde6e61223399bff2aa7bd1fe1b2c1f24c86d455ea801b1301"
TRACKPAD_MEMBER = "Firmware/J614s_Multitouch.im4p"
TRACKPAD_SHA256 = "4f06afea3e412010fc56ed7dc1214d62fa48b400dbf4f75e261f14e8afe00bf4"

# Independently recorded by Wallace's paired-firmware corpus, July 24 2026.
# Fail on any changed converter output, even when the IPSW passes its checks.
EXPECTED = {
    "apple/tpmtfw-j614s.bin": "a1f4131d0cb7caf6fa15b19f47725458a6d7b0e3a34f15169339d5541663d9e2",
    "brcm/brcmbt4388c2-apple,mriya-u.bin": "842258ff94948558073010494f0d8f5ab6d1d539e1b07b7b37790ca4cd9c923e",
    "brcm/brcmbt4388c2-apple,mriya-u.ptb": "6f0f1002c45ef7feffe03aef9f4927ecdfdac3baefafeffda742d51ff2752d29",
    "brcm/brcmfmac4388c0-pcie.apple,mriya-WLMT-a.txt": "02137cf6fec8e437206f23b6542a9a7cdc8ca39a2ea9b2e07ce2d4bc5409913b",
    "brcm/brcmfmac4388c0-pcie.apple,mriya-WLMT-u.txt": "4d0f3187f2e0dd708f5271bffdc43cc63e4d68a3c3449d8c8ff580286eb75bf0",
    "brcm/brcmfmac4388c0-pcie.apple,mriya.bin": "cd49096c0b0f95caf5e0fd53e1460b8b6ed21f4aba9c314bc0602d6bec77f4bb",
    "brcm/brcmfmac4388c0-pcie.apple,mriya.clm_blob": "822fd43c5502d77d1e7c910e44255bc878b0fa5b046b5133450f6f928098f26b",
    "brcm/brcmfmac4388c0-pcie.apple,mriya.sig": "97ce17756689483a468e52bab27978023727cb7e8b3e372f23a36d410366cae6",
    "brcm/brcmfmac4388c0-pcie.apple,mriya.txcap_blob": "7a588168ee5ab1c891e0fadaef56592e84b6c766f91e92b9f08820b822f243fb",
    "brcm/brcmfmac4388c2-pcie.apple,mriya-WLMT-a.txt": "a30428331a385392a04d535d5c106bd2517de0bfb244c58e4e2464c937ff013c",
    "brcm/brcmfmac4388c2-pcie.apple,mriya-WLMT-u.txt": "203251922cfcf95f2233290d75def5ae88e41dfda77af36d8426d9d6db1db3d9",
    "brcm/brcmfmac4388c2-pcie.apple,mriya.bin": "7cfae8622feeb119c756ae707d26f3a94f1cde44becefacf27ecf1fdc586d93b",
    "brcm/brcmfmac4388c2-pcie.apple,mriya.clm_blob": "af8df65b766a6e2c450892819ecf8422289463e342aa748532c110032140f309",
    "brcm/brcmfmac4388c2-pcie.apple,mriya.sig": "9abb8c1afe0413339f5eca7706150c507a7bca5d244b0a4c6f79e4c28d2ce7cf",
    "brcm/brcmfmac4388c2-pcie.apple,mriya.txcap_blob": "2ee489bb7b59b74bad259969344d513b7a6803e83f3563b2ce090df18f53a013",
}


def final_hashes():
    """Include the C2 aliases required by this kernel's BCM4388 revision table."""
    expected = dict(EXPECTED)
    for vendor in ("u", "a"):
        for suffix in ("bin", "clm_blob", "txcap_blob", "sig", "txt"):
            source = "brcm/brcmfmac4388c2-pcie.apple,mriya"
            if suffix == "txt":
                source += "-WLMT-" + vendor
            target = "brcm/brcmfmac4388c0-pcie.apple,mriya-WLMT-" + vendor
            expected[target + "." + suffix] = EXPECTED[source + "." + suffix]
    for suffix in ("bin", "ptb"):
        expected["brcm/brcmbt4388c2-apple,mriya." + suffix] = EXPECTED[
            "brcm/brcmbt4388c2-apple,mriya-u." + suffix]
    return expected


def check_files(root, expected):
    root = Path(root)
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"Unexpected firmware filesystem entry: {path}")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != set(expected):
        raise ValueError(f"Firmware file set differs from the pinned profile: "
                         f"missing={sorted(set(expected) - actual)}, extra={sorted(actual - set(expected))}")
    for name, digest in expected.items():
        path = root / name
        if not path.is_file() or path.is_symlink() or sha256(path) != digest:
            raise ValueError(f"Firmware is missing or does not match pinned 25F84 content: {path}")


def extract_regular(archive, destination, prefix=""):
    """Extract only ordinary files from an already hash-verified archive."""
    with tarfile.open(archive, "r:gz") as source:
        for member in source.getmembers():
            if prefix and not member.name.startswith(prefix):
                continue
            name = member.name[len(prefix):] if prefix else member.name
            if not name or member.isdir() or member.issym():
                continue
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or not member.isfile():
                raise ValueError(f"Unexpected archive member: {member.name}")
            target = Path(destination) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(member) as inp, target.open("wb") as out:
                shutil.copyfileobj(inp, out)
            target.chmod(0o755 if member.mode & 0o111 else 0o644)


def fetch_apple_members(cache):
    from urlcache import URLCache
    manifest_path = cache / "BuildManifest.plist"
    base = cache / BASE_MEMBER
    trackpad = cache / Path(TRACKPAD_MEMBER).name
    if (manifest_path.exists() and sha256(manifest_path) == MANIFEST_SHA256
            and base.exists() and sha256(base) == BASE_SHA256
            and trackpad.exists() and sha256(trackpad) == TRACKPAD_SHA256):
        return base, trackpad
    print("Reading Apple's pinned restore archive (only BaseSystem + trackpad, approximately 1.1 GiB).", flush=True)
    # The upstream range reader avoids downloading the 19.8 GB whole archive.
    # All consumed outputs are authenticated by pinned hashes below.
    with contextlib.redirect_stdout(sys.stderr):
        remote = URLCache(APPLE_URL)
        try:
            if remote.size != APPLE_SIZE:
                raise ValueError(f"Unexpected Apple restore archive size: {remote.size}")
            with zipfile.ZipFile(remote) as archive:
                manifest_data = archive.read("BuildManifest.plist")
                if hashlib.sha256(manifest_data).hexdigest() != MANIFEST_SHA256:
                    raise ValueError("Apple BuildManifest SHA-256 does not match")
                manifest = plistlib.loads(manifest_data)
                if manifest.get("ProductBuildVersion") != "25F84":
                    raise ValueError("Apple restore build is not 25F84")
                identities = [i for i in manifest["BuildIdentities"]
                              if i["Info"].get("DeviceClass") == "j614sap"
                              and i["Info"].get("RestoreBehavior") == "Erase"
                              and i["Info"].get("Variant") == "macOS Customer"]
                if len(identities) != 1:
                    raise ValueError("Expected one J614s customer restore identity")
                entries = identities[0]["Manifest"]
                if entries["BaseSystem"]["Info"]["Path"] != BASE_MEMBER:
                    raise ValueError("Unexpected BaseSystem member")
                touch = entries["Multitouch"]["Info"]
                if (touch.get("Path") != TRACKPAD_MEMBER or not touch.get("IsFUDFirmware")
                        or touch.get("IsLoadedByiBoot") or touch.get("IsLoadedByiBootStage1")):
                    raise ValueError("Unexpected J614s multitouch firmware entry")
                manifest_path.write_bytes(manifest_data)
                for member, target, digest in ((BASE_MEMBER, base, BASE_SHA256),
                                               (TRACKPAD_MEMBER, trackpad, TRACKPAD_SHA256)):
                    if digest and target.exists() and sha256(target) == digest:
                        continue
                    part = target.with_suffix(target.suffix + ".part")
                    with archive.open(member) as inp, part.open("wb") as out:
                        shutil.copyfileobj(inp, out, 8 * 1024 * 1024)
                    if digest and sha256(part) != digest:
                        raise ValueError(f"Wrong Apple member SHA-256: {member}")
                    part.replace(target)
        finally:
            remote.close_connection()
    return base, trackpad


@contextlib.contextmanager
def mounted_readonly(dmg, directory):
    mountpoint = directory / "basesystem"
    mountpoint.mkdir()
    # -nobrowse avoids Finder side effects; no partition table or disk is edited.
    result = subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-plist",
                             "-mountpoint", str(mountpoint), str(dmg)],
                            check=True, capture_output=True)
    devices = [entity["dev-entry"] for entity in plistlib.loads(result.stdout)["system-entities"]
               if entity.get("mount-point") == str(mountpoint)]
    if len(devices) != 1:
        # The mountpoint remains a valid detach target if parsing failed.
        subprocess.run(["hdiutil", "detach", str(mountpoint)], check=False)
        raise ValueError("Could not identify the downloaded BaseSystem read-only mount")
    try:
        yield mountpoint
    finally:
        run(["hdiutil", "detach", devices[0]])


def convert(base_system, trackpad, stage):
    from asahi_firmware.bluetooth import BluetoothFWCollection
    from asahi_firmware.multitouch import MultitouchFWCollection
    from asahi_firmware.wifi import WiFiFWCollection
    raw = stage / "raw"
    wifi = raw / "wifi"
    bt = raw / "bluetooth"
    fud = raw / "fud" / "j614s"
    for directory in (wifi, bt, fud):
        directory.mkdir(parents=True)
    dext = base_system / "System/Library/DriverExtensions/com.apple.DriverKit-AppleBCMWLAN.dext/Firmware"
    for path in sorted(dext.rglob("*mriya*")):
        if path.is_file():
            target = wifi / path.relative_to(dext)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    for path in sorted((base_system / "usr/share/firmware/bluetooth").iterdir()):
        if "mriya" in path.name.lower() and path.is_file():
            shutil.copyfile(path, bt / path.name)
    shutil.copyfile(trackpad, fud / "Multitouch.im4p")
    output = stage / "vendorfw"
    for collection in (WiFiFWCollection(wifi).files(), BluetoothFWCollection(bt).files(),
                       MultitouchFWCollection(fud.parent).files()):
        for name, firmware in collection:
            if name not in EXPECTED:
                raise ValueError(f"Unexpected converted firmware: {name}")
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(firmware.data)
            target.chmod(0o644)
    check_files(output, EXPECTED)
    data = (output / "apple/tpmtfw-j614s.bin").read_bytes()
    magic, version, header, size, offset = struct.unpack_from("<4sIIII", data)
    if magic != b"HIDF" or version != 1 or header != 32 or size != len(data) - 32 or offset >= size:
        raise ValueError("Invalid J614s trackpad HIDF image")
    add_aliases(output)
    shutil.rmtree(raw)


def add_aliases(output):
    for vendor in ("u", "a"):
        for suffix in ("bin", "clm_blob", "txcap_blob", "sig", "txt"):
            source = "brcm/brcmfmac4388c2-pcie.apple,mriya"
            if suffix == "txt":
                source += "-WLMT-" + vendor
            target = "brcm/brcmfmac4388c0-pcie.apple,mriya-WLMT-" + vendor
            shutil.copyfile(output / (source + "." + suffix), output / (target + "." + suffix))
    for suffix in ("bin", "ptb"):
        shutil.copyfile(output / ("brcm/brcmbt4388c2-apple,mriya-u." + suffix),
                        output / ("brcm/brcmbt4388c2-apple,mriya." + suffix))


def prepare(cache: Path, output: Path, firmware_dir=None):
    """Return manifest; publish verified files in output/vendorfw atomically.

    firmware_dir optionally imports an already-converted 25F84 corpus. Its
    hashes must match this project, so Linux builders can operate without macOS.
    """
    cache, output = Path(cache).resolve(), Path(output).resolve()
    if output.exists():
        check_files(output / "vendorfw", final_hashes())
        manifest = json.loads((output / "manifest.json").read_text())
        if manifest.get("files") != final_hashes():
            raise ValueError("Cached firmware manifest differs from the pinned profile")
        return manifest
    output.parent.mkdir(parents=True, exist_ok=True)
    inputs = cache / "firmware-inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="firmware-tools-", dir=inputs) as temporary:
        work = Path(temporary)
        stage = Path(tempfile.mkdtemp(prefix=".firmware-stage-", dir=output.parent))
        try:
            if firmware_dir is not None:
                origin = Path(firmware_dir).resolve()
                if (origin / "vendorfw").is_dir():
                    origin /= "vendorfw"
                # Accept either a pristine converter corpus or the final aliases.
                for name, digest in EXPECTED.items():
                    path = origin / name
                    accepted = {digest, final_hashes()[name]}
                    if not path.is_file() or path.is_symlink() or sha256(path) not in accepted:
                        raise ValueError(f"Import does not match the pinned firmware corpus: {path}")
                    target = stage / "vendorfw" / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
                add_aliases(stage / "vendorfw")
            else:
                if sys.platform != "darwin":
                    raise ValueError("Firmware extraction needs macOS hdiutil; import a verified corpus with --firmware-dir")
                arch = platform.machine()
                if arch not in IPSW_TOOL_HASHES:
                    raise ValueError(f"Unsupported macOS architecture: {arch}")
                archive = download("https://codeload.github.com/AsahiLinux/asahi-installer/tar.gz/" + ASAHI_REVISION,
                                   inputs / "asahi-installer-c53d66dc.tar.gz", ASAHI_SHA256)
                extract_regular(archive, work / "asahi", "asahi-installer-" + ASAHI_REVISION + "/src/")
                extract_regular(archive, work / "asahi/asahi_firmware",
                                "asahi-installer-" + ASAHI_REVISION + "/asahi_firmware/")
                sys.path.insert(0, str(work / "asahi"))
                try:
                    base, trackpad = fetch_apple_members(inputs)
                    dmg = inputs / BASE_MEMBER.removesuffix(".aea")
                    if not dmg.exists() or sha256(dmg) != DMG_SHA256:
                        filename = f"ipsw_{IPSW_VERSION}_macOS_{arch}.tar.gz"
                        helper = download(f"https://github.com/blacktop/ipsw/releases/download/v{IPSW_VERSION}/{filename}",
                                          inputs / filename, IPSW_TOOL_HASHES[arch])
                        extract_regular(helper, work / "ipsw")
                        # The helper fetches Apple's public FCS key and authenticates AEA.
                        # It writes only inside this project's cache.
                        run([work / "ipsw/ipsw", "fw", "aea", base, "-o", inputs])
                        if not dmg.is_file() or sha256(dmg) != DMG_SHA256:
                            raise ValueError("Decrypted BaseSystem does not match the pinned SHA-256")
                    with mounted_readonly(dmg, work) as base_system:
                        convert(base_system, trackpad, stage)
                finally:
                    sys.path.remove(str(work / "asahi"))
            check_files(stage / "vendorfw", final_hashes())
            manifest = {
                "schema": 1, "model": "Mac16,8", "device_class": "j614sap",
                "apple_build": "25F84", "apple_url": APPLE_URL,
                "build_manifest_sha256": MANIFEST_SHA256,
                "base_system_aea_sha256": BASE_SHA256, "base_system_dmg_sha256": DMG_SHA256,
                "trackpad_im4p_sha256": TRACKPAD_SHA256,
                "asahi_revision": ASAHI_REVISION, "asahi_source_sha256": ASAHI_SHA256,
                "ipsw_tool_version": IPSW_VERSION, "files": final_hashes(),
                "notes": ["Wireless firmware uses the C2-to-C0 aliases documented by Wallace.",
                          "Bluetooth corpus is the known-good USI (-u) module variant.",
                          "These are volatile peripheral payloads; no host firmware was flashed."]}
            write_json(stage / "manifest.json", manifest)
            stage.replace(output)
            print(f"Verified J614s Wi-Fi, Bluetooth and trackpad firmware: {output}", flush=True)
            return manifest
        finally:
            if stage.exists():
                shutil.rmtree(stage)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--firmware-dir", type=Path)
    args = parser.parse_args()
    prepare(args.cache, args.output, args.firmware_dir)
