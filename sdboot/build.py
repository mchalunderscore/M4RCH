#!/usr/bin/env python3
"""Build a fresh native SD installation and its independent fixed loader."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import uuid

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib"))
from common import manifest_files, run, sha256, verify_manifest, write_json
from project import runtime, identify_mac
try:
    from . import media
except ImportError:
    import media


def configuration():
    config = json.loads((PROJECT / "sdboot/config.json").read_text())
    local = PROJECT / "sdboot/config.local.json"
    if local.exists():
        overrides = json.loads(local.read_text())
        if overrides.keys() - config.keys():
            raise ValueError("Unknown local configuration keys")
        config.update(overrides)
    if (config["model"], config["board"]) != ("Mac16,8", "j614s"):
        raise ValueError("Only the 14-inch M4 Pro Mac16,8 / J614s is supported")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,30}", config["username"]):
        raise ValueError("Invalid username")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", config["hostname"]):
        raise ValueError("Invalid hostname")
    if not isinstance(config["full_name"], str) or any(c in config["full_name"] for c in ":\n\r"):
        raise ValueError("Invalid full name")
    for key, low, high in (("root_gib", 8, 128), ("boot_mib", 256, 2048), ("jobs", 1, 32)):
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise ValueError(f"{key} must be an integer in {low}..{high}")
    config["root_uuid"] = str(uuid.UUID(config["root_uuid"]))
    if not re.fullmatch(r"[A-Za-z0-9_+/-]+", config["timezone"]) or ".." in config["timezone"].split("/"):
        raise ValueError("Invalid timezone")
    if not isinstance(config["packages"], list) or any(not isinstance(n, str) or not re.fullmatch(r"[a-z0-9][a-z0-9+_.-]*", n) for n in config["packages"]):
        raise ValueError("Invalid package list")
    return config


def builder(action, config):
    # A named Linux volume must not be mounted writable by two builder VMs.
    # Keep separate CLI invocations (including make -j with multiple targets)
    # from racing the compiler tree, package transaction or filesystem image.
    out = PROJECT / "out/sdboot"
    out.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(out / ".build.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another SD-image build is running; wait for it before starting another target") from None
        return _builder(action, config)
    finally:
        os.close(descriptor)


def _builder(action, config):
    rt = runtime()
    image = "builder-m4rch-1.0.0:" + sha256(PROJECT / "sdboot/Containerfile")[:12]
    if subprocess.run([rt, "image", "inspect", image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        run([rt, "build", "--platform", "linux/arm64", "-t", image, "-f", PROJECT / "sdboot/Containerfile", PROJECT / "sdboot"])
    out = PROJECT / "out/sdboot"
    out.mkdir(parents=True, exist_ok=True)
    (PROJECT / "cache/sdboot-packages").mkdir(parents=True, exist_ok=True)
    volume = "m4rch-sdboot-work-" + hashlib.sha256(str(PROJECT).encode()).hexdigest()[:10]
    if subprocess.run([rt, "volume", "inspect", volume], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        run([rt, "volume", "create", *(["-s", "32G"] if rt == "container" else []), volume])
    command = [rt, "run", "--rm", "--platform", "linux/arm64", "--cpus", str(config["jobs"]), "--memory", os.environ.get("MEMORY", "8G")]
    if action in ("image", "packages"):
        command += ["--cap-add", "SYS_ADMIN"]
    # Kernel artifacts use a separate output tree from the SD image.
    selected = out / "hardware" if action == "kernel" else out
    selected.mkdir(exist_ok=True)
    command += ["--mount", f"type=volume,source={volume},target=/work",
                "-v", f"{PROJECT}:/project:ro", "-v", f"{PROJECT / 'cache'}:/cache",
                "-v", f"{PROJECT / 'cache/sdboot-packages'}:/cache/desktop-packages",
                "-v", f"{selected}:/out",
                image, "python3", "/project/sdboot/build.py", action, "--inside"]
    run(command)


def kernel_directory(out):
    directory = out / "hardware/experimental"
    if not directory.is_dir():
        raise ValueError("Build the matching kernel first: make kernel")
    hardware = verify_manifest(directory / "boot/hardware-manifest.json")
    if sha256(directory / "modules.tar.gz") != hardware["modules_sha256"]:
        raise ValueError("Kernel module archive checksum mismatch")
    return directory


def kernel(config, lock):
    from boot import build_hardware
    from driver_tools import stage
    from hardware_profile import BLOCKED_MODULES
    hardware = build_hardware(config, lock, "experimental")
    directory = Path("/out/experimental")
    stage(PROJECT, directory / "driver-tools", modules_archive=directory / "modules.tar.gz",
          kernel_release=hardware["kernel_release"], kernel_sha256=sha256(directory / "boot/Image.gz"), blocked_modules=BLOCKED_MODULES)


def payload(out, config, lock, kernel_dir):
    """Validate the normal ESP exported by the packaged rootfs build."""
    root = verify_manifest(out / "rootfs-manifest.json")
    init = verify_manifest(out / "initramfs-manifest.json")
    loader = verify_manifest(out / "loader-manifest.json")
    if loader.get("kind") != "j614s-sd-loader" or loader.get("boot_protocol") != "uefi-arm64":
        raise ValueError("Build the UEFI bridge with make loader before composing its SD image")
    if sha256(kernel_dir / "boot/t6040-j614s.dtb") != loader["inputs"]["baseline_dtb"]:
        raise ValueError("Kernel baseline DT differs from the fixed loader. Put SD-only DT edits in sdboot/board.dtso; changing the baseline requires make loader and re-enrollment.")
    for manifest in (root, init):
        if manifest["config"] != config:
            raise ValueError("Packaged root configuration is stale; run make image")
        if manifest["kernel_image_sha256"] != sha256(kernel_dir / "boot/Image.gz"):
            raise ValueError("Kernel packages and root image differ; run make image for a fresh card, or make packages for pacman updates")
    directory = out / "esp"
    paths = sorted(str(path.relative_to(out)) for path in directory.rglob("*") if path.is_file())
    if not paths:
        raise ValueError("No packaged EFI boot files; run make image first")
    write_json(out / "payload-manifest.json", {"schema": 2, "layout": media.LAYOUT,
        "config": config, "kernel_release": init["kernel_release"],
        "required_loader_sha256": loader["files"]["loader.bin"]["sha256"],
        "baseline_dtb_sha256": loader["inputs"]["baseline_dtb"], "hardware_tested": False,
        "files": manifest_files(out, paths)})
    validate_compose(out, config)


def validate_compose(out, config):
    root = verify_manifest(out / "rootfs-manifest.json")
    init = verify_manifest(out / "initramfs-manifest.json")
    boot = verify_manifest(out / "payload-manifest.json")
    loader = verify_manifest(out / "loader-manifest.json")
    if loader.get("boot_protocol") != "uefi-arm64":
        raise ValueError("Build the UEFI bridge with make loader before composing its SD image")
    for name, manifest in (("rootfs", root), ("initramfs", init), ("payload", boot)):
        if manifest["config"] != config:
            raise ValueError(f"{name} configuration is stale; rebuild it before composing the image")
    if root["kernel_release"] != init["kernel_release"] or boot["kernel_release"] != init["kernel_release"]:
        raise ValueError("Packaged root, ESP and initramfs kernel releases differ; run make image")
    if boot["required_loader_sha256"] != loader["files"]["loader.bin"]["sha256"]:
        raise ValueError("ESP manifest names a different fixed loader; run make image")
    if boot["files"].get("esp/initramfs-linux-m4rch.img") != init["files"]["initramfs.cpio.gz"]:
        raise ValueError("ESP and generated initramfs differ; run make image")
    media._esp(out, config)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("image", "kernel", "packages", "loader", "verify", "smoke", "flash", "boot", "boot-safe", "boot-status"))
    parser.add_argument("--disk")
    parser.add_argument("--model", choices=("Mac16,8",))
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--replace-pending", action="store_true",
                        help="explicitly supersede a verified pending loader during boot staging")
    args = parser.parse_args()
    if args.replace_pending and (args.action not in ("boot", "boot-safe") or args.inside):
        parser.error("--replace-pending is only valid for boot staging on macOS")
    config = configuration()
    lock = json.loads((PROJECT / "sources.lock.json").read_text())
    out = Path("/out") if args.inside else PROJECT / "out/sdboot"
    if args.inside:
        if platform.system() != "Linux" or platform.machine() not in ("aarch64", "arm64"):
            raise ValueError("Builder must run ARM64 Linux")
        os.environ["SOURCE_DATE_EPOCH"] = str(lock["source_date_epoch"])
        if args.action == "kernel":
            kernel(config, lock)
            return
        if args.action in ("image", "packages"):
            import grub
            grub.build(PROJECT, out, config, lock)
        directory = kernel_directory(out)
        if args.action in ("image", "loader"):
            import loader
            loader.build(PROJECT, out, config, lock, directory, nvme=False)
            loader.build(PROJECT, out / "nvme-loader", config, lock, directory, nvme=True)
        if args.action in ("image", "packages"):
            import rootfs
            rootfs.build(PROJECT, out, config, lock, directory, packages_only=args.action == "packages")
        if args.action == "image":
            payload(out, config, lock, directory)
            validate_compose(out, config)
            media.compose(out, config)
        if args.action == "smoke":
            import smoke_native
            smoke_native.build(PROJECT, out, config, lock, directory)
        return
    out.mkdir(parents=True, exist_ok=True)
    if args.action == "flash":
        if not args.disk:
            raise ValueError("Pass DISK=/dev/diskN for the intended SD card")
        media.flash(out, config, args.disk)
        return
    if args.action in ("boot", "boot-safe", "boot-status"):
        import enrollment
        if args.action in ("boot", "boot-safe"):
            enrollment.prepare(PROJECT, out, replace_pending=args.replace_pending, nvme=args.action != "boot-safe")
        else:
            enrollment.status(PROJECT, out)
        return
    if args.action == "verify":
        for name in ("loader", "rootfs", "initramfs", "payload", "card"):
            manifest = verify_manifest(out / (name + "-manifest.json"))
            if "config" in manifest and manifest["config"] != config:
                raise ValueError(f"{name} configuration is stale")
        validate_compose(out, config)
        verify_manifest(out / "custom-packages-manifest.json")
        print("All UEFI image and package artifacts verified; native SD boot remains a hardware test.")
        return
    identify_mac(args.model)
    if args.action in ("image", "packages"):
        from firmware import prepare
        prepare(PROJECT / "cache", PROJECT / "cache/firmware", None)
        if args.action == "image" and platform.system() == "Darwin":
            import stub_payload
            stub_payload.prepare(PROJECT / "cache", PROJECT / "out/stub")
    if args.action in ("image", "kernel"):
        builder("kernel", config)
        if args.action == "kernel":
            return
    builder(args.action, config)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print("m4rch: " + str(exc), file=sys.stderr)
        sys.exit(1)
