#!/usr/bin/env python3
"""Validate and install one module release beside existing releases, never probe it."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile


NAMES = {"install.sh", "install-driver-modules.py", "m4rch-driver-diagnostics", "modules.tar.gz", "autoload-blocklist.conf", "README.txt"}


def digest(stream):
    value = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        value.update(chunk)
    return value.hexdigest()


def regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular file: {path}")


def metadata(source):
    path = source / "driver-tools-manifest.json"
    regular(path)
    manifest = json.loads(path.read_text())
    release = manifest.get("kernel_release", "")
    if manifest.get("schema") != 1 or not isinstance(release, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}", release):
        raise ValueError("Invalid driver-tools manifest or kernel release")
    if not re.fullmatch(r"[0-9a-f]{64}", manifest.get("kernel_image_sha256", "")):
        raise ValueError("Invalid kernel image identity")
    if manifest.get("archive_prefix") != f"usr/lib/modules/{release}":
        raise ValueError("Module archive prefix does not match the kernel release")
    if set(manifest.get("files", {})) != NAMES:
        raise ValueError("Unexpected or missing driver-tools manifest files")
    for name, info in manifest["files"].items():
        path = source / name
        regular(path)
        with path.open("rb") as stream:
            if path.stat().st_size != info.get("bytes") or digest(stream) != info.get("sha256"):
                raise ValueError(f"Artifact failed verification: {path}")
    blocked = manifest.get("blocked_modules")
    if not isinstance(blocked, list) or not blocked or any(
            not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name)
            for name in blocked) or len(blocked) != len(set(blocked)):
        raise ValueError("Invalid autoload blocklist")
    lines = (source / "autoload-blocklist.conf").read_text().splitlines()
    if [line for line in lines if line and not line.startswith("#")] != [
            f"blacklist {name}" for name in blocked]:
        raise ValueError("Autoload blocklist differs from the manifest")
    return manifest


def archive_members(archive, release):
    """Reject every link, special file, duplicate, and path outside this release."""
    prefix = PurePosixPath("usr/lib/modules") / release
    ancestors = set(prefix.parents) - {PurePosixPath(".")}
    members = {}
    has_module = False
    for member in archive.getmembers():
        name = member.name.rstrip("/") if member.isdir() else member.name
        path = PurePosixPath(name)
        if not name or path.is_absolute() or ".." in path.parts or str(path) != name:
            raise ValueError(f"Unsafe module archive path: {member.name!r}")
        if path in members:
            raise ValueError(f"Duplicate module archive path: {name}")
        if not member.isfile() and not member.isdir():
            raise ValueError(f"Module archive contains a link or special file: {name}")
        if path != prefix and prefix not in path.parents and not (member.isdir() and path in ancestors):
            raise ValueError(f"Module archive escapes its release directory: {name}")
        members[path] = member
        has_module |= member.isfile() and name.endswith((".ko", ".ko.xz", ".ko.zst", ".ko.gz"))
    for path in members:
        if any(parent in members and not members[parent].isdir() for parent in path.parents):
            raise ValueError(f"Module archive places a file below another file: {path}")
    if not has_module:
        raise ValueError("Module archive contains no kernel modules")
    return members


def install(source, root=Path("/"), depmod="depmod"):
    source, root = Path(source), Path(root)
    manifest = metadata(source)
    release = manifest["kernel_release"]
    prefix = PurePosixPath(manifest["archive_prefix"])
    modules = root / "usr/lib/modules"
    for directory in (root / "usr", root / "usr/lib", modules):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ValueError(f"Expected a real directory: {directory}")
    helper = root / "usr/local/bin/m4rch-driver-diagnostics"
    for directory in (root / "usr/local", helper.parent):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ValueError(f"Expected a real directory: {directory}")
    if helper.is_symlink() or (helper.exists() and not helper.is_file()):
        raise ValueError(f"Expected a regular helper destination: {helper}")
    blocklist = root / "etc/modprobe.d/m4rch-drivers.conf"
    for directory in (root / "etc", blocklist.parent):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ValueError(f"Expected a real directory: {directory}")
    blocklist_data = (source / "autoload-blocklist.conf").read_bytes()
    if blocklist.is_symlink() or (blocklist.exists() and (
            not blocklist.is_file() or blocklist.read_bytes() != blocklist_data)):
        raise ValueError(f"Existing autoload configuration was preserved; compare it with autoload-blocklist.conf: {blocklist}")
    target = modules / release
    # Use one open descriptor for the archive hash, validation and extraction.
    with (source / "modules.tar.gz").open("rb") as stream:
        if digest(stream) != manifest["files"]["modules.tar.gz"]["sha256"]:
            raise ValueError("Module archive changed after verification")
        stream.seek(0)
        with tarfile.open(fileobj=stream, mode="r:gz") as archive:
            members = archive_members(archive, release)
            if target.exists() or target.is_symlink():
                raise ValueError(f"Module release already exists; it was not overwritten: {target}")
            # All archive members are validated before creating any destination.
            modules.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".arch-m4-modules-", dir=modules) as temporary:
                staging = Path(temporary)
                for path, member in members.items():
                    destination = staging / str(path)
                    if member.isdir():
                        destination.mkdir(parents=True, exist_ok=True)
                        destination.chmod(0o755)
                    else:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with archive.extractfile(member) as original, destination.open("xb") as output:
                            shutil.copyfileobj(original, output)
                        destination.chmod(0o644)
                # depmod expects /lib/modules; Arch uses /lib -> usr/lib.
                (staging / "lib").symlink_to("usr/lib", target_is_directory=True)
                subprocess.run([depmod, "-b", str(staging), release], check=True)
                # Publish the blocklist before making any modules discoverable.
                blocklist.parent.mkdir(parents=True, exist_ok=True)
                if not blocklist.exists():
                    with blocklist.open("xb") as output:
                        output.write(blocklist_data)
                    blocklist.chmod(0o644)
                (staging / str(prefix)).rename(target)
    helper.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=helper.parent, prefix=".driver-diagnostics-", delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write((source / "m4rch-driver-diagnostics").read_bytes())
            output.flush()
            temporary.chmod(0o755)
            temporary.replace(helper)
        finally:
            temporary.unlink(missing_ok=True)
    os.sync() if hasattr(os, "sync") else None
    print(f"Installed modules for {release}. Existing module releases were preserved.")
    print(f"Matching compressed kernel image SHA-256: {manifest['kernel_image_sha256']}")
    running = os.uname().release
    if running != release:
        print(f"Running {running}; these modules will be used after booting {release}.")
    print("No driver was loaded or unloaded. Controller aliases in the blocklist require explicit driver loading.")
    print("Their drivers remain available through explicit modprobe commands; use the documented test groups.")
    print("Capture a report: sudo m4rch-driver-diagnostics --output /run/initramfs/sd/m4rch-driver-diagnostics.txt")
    return manifest


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or os.geteuid() != 0 or os.uname().sysname != "Linux":
            raise ValueError("Run install.sh with sudo inside the Arch installation")
        install(Path(sys.argv[1]))
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, subprocess.CalledProcessError) as error:
        print(f"install-driver-tools: {error}", file=sys.stderr)
        sys.exit(1)
