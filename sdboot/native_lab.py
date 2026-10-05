#!/usr/bin/env python3
"""Read-only USB/CPU snapshots and private return archives for native work."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import time

LIMIT = 2 * 1024 * 1024
TEXT_PROPERTIES = {"compatible", "status", "device_type", "method", "phy-names",
                   "clock-names", "reg-names", "power-role", "data-role",
                   "enable-method", "arch-m4,ans-handoff"}
CELL_PROPERTIES = {"reg", "phandle", "linux,phandle", "power-domains", "interrupts",
                   "interrupt-parent", "phys", "clocks", "resets", "remote-endpoint",
                   "port-number", "cpu-idle-states", "capacity-dmips-mhz",
                   "memory-region", "psci-suspend-param", "entry-latency-us",
                   "exit-latency-us", "min-residency-us", "#power-domain-cells",
                   "#phy-cells", "#address-cells", "#size-cells"}


def read(path, limit=32768):
    try:
        with path.open("rb") as source:
            data = source.read(limit + 1)
        if len(data) > limit:
            return {"error": "read limit exceeded"}
        return data.decode("utf-8", errors="replace").strip()
    except OSError as exc:
        return {"error": str(exc)}


def command(argv):
    started = time.monotonic()
    try:
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=20, check=False)
        return {"argv": argv, "exit": result.returncode,
                "seconds": round(time.monotonic() - started, 3),
                "truncated": len(result.stdout) > LIMIT,
                "output": result.stdout[:LIMIT].decode("utf-8", errors="replace")}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"argv": argv, "error": str(exc)}


def device_tree(root):
    result = {}
    if not root.is_dir():
        return {"error": "live device tree unavailable"}
    for directory, subdirs, names in os.walk(root, followlinks=False):
        subdirs[:] = sorted(d for d in subdirs if not (Path(directory) / d).is_symlink())
        relative = Path(directory).relative_to(root).as_posix()
        path = "/" if relative == "." else "/" + relative
        if not (path in ("/", "/chosen", "/aliases", "/psci") or
                re.search(r"/(cpus|idle-states|psci[^/]*|usb[^/]*|phy[^/]*|dart[^/]*|spmi[^/]*|"
                          r"usb-pd[^/]*|connector|pmgr[^/]*|power-domains)(/|$)", path)):
            continue
        props = {}
        for name in sorted(names):
            file = Path(directory) / name
            if file.is_symlink() or name not in TEXT_PROPERTIES | CELL_PROPERTIES:
                # Alias targets are useful for resolving all three port graphs.
                if path != "/aliases" or file.is_symlink():
                    continue
            try:
                with file.open("rb") as source:
                    raw = source.read(32769)
                if len(raw) > 32768:
                    props[name] = {"error": "property limit exceeded"}
                elif name in TEXT_PROPERTIES or path == "/aliases":
                    props[name] = raw.rstrip(b"\0").decode("utf-8", errors="replace").split("\0")
                else:
                    props[name] = {"hex": raw.hex(), "cells": [int.from_bytes(raw[i:i+4], "big")
                        for i in range(0, len(raw), 4)] if len(raw) % 4 == 0 else None}
            except OSError as exc:
                props[name] = {"error": str(exc)}
        result[path] = props
        if len(result) >= 4096:
            result["_truncated"] = True
            break
    return result


def bus_devices(root, bus):
    result = {}
    for directory in sorted((root / "bus" / bus / "devices").glob("*"))[:512]:
        if bus == "platform" and not re.search(r"usb|dwc|xhci|phy|spmi|typec|cpuidle", directory.name):
            continue
        entry = {name: read(directory / name) for name in
                 ("uevent", "modalias", "power/runtime_status", "power/control")}
        for link in ("driver", "of_node"):
            value = directory / link
            entry[link] = str(value.resolve()) if value.is_symlink() else None
        if bus == "usb":
            entry.update({name: read(directory / name) for name in
                          ("idVendor", "idProduct", "speed", "authorized", "bConfigurationValue")})
        result[directory.name] = entry
    return result


def kernel_config(proc, boot, release):
    try:
        with gzip.open(proc / "config.gz", "rb") as source:
            raw = source.read(LIMIT + 1)
        if len(raw) > LIMIT:
            return {"error": "kernel config limit exceeded"}
        text = raw.decode("utf-8")
        source_name = "/proc/config.gz"
    except (OSError, EOFError, UnicodeError):
        source_name = "config-" + release
        text = read(boot / source_name, LIMIT)
        if not isinstance(text, str):
            return text
    selected = [line for line in text.splitlines() if re.search(
        r"CONFIG_(CPU_IDLE|ARM_.*IDLE|ARM_PSCI|CPU_FREQ|ARM_APPLE|ENERGY_MODEL|"
        r"SCHED_|UCLAMP|ARM64_AMU|PM|PHY_APPLE|TYPEC_TPS|USB_DWC|USB_XHCI|SPMI)", line)]
    return {"source": source_name, "settings": selected}


def snapshot(output, label, *, sysfs=Path("/sys"), proc=Path("/proc"),
             boot=Path("/boot"), runner=command, kit=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", label):
        raise ValueError("Use a short label containing letters, digits, dots, dashes or underscores")
    output = Path(output).absolute()
    if not output.parent.is_dir() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("Output needs an existing parent with no symlink path components")
    output.mkdir(mode=0o700)
    (output / "INCOMPLETE").write_text("Capture has not completed.\n")
    release = platform.release()
    result = {"schema": 1, "label": label, "utc": datetime.now(timezone.utc).isoformat(),
              "kernel": release, "uptime": read(proc / "uptime"),
              "cmdline": read(proc / "cmdline"), "interrupts": read(proc / "interrupts", LIMIT),
              "kernel_config": kernel_config(proc, boot, release),
              "efi": {"present": (sysfs / "firmware/efi").is_dir(),
                      "systab": read(sysfs / "firmware/efi/systab"),
                      "fw_platform_size": read(sysfs / "firmware/efi/fw_platform_size")},
              "device_tree": device_tree(sysfs / "firmware/devicetree/base"),
              "usb_devices": bus_devices(sysfs, "usb"),
              "platform_devices": bus_devices(sysfs, "platform")}
    (output / "hardware.json").write_text(json.dumps(result, indent=2) + "\n")
    jobs = {"kernel-log": ["journalctl", "-b", "-k", "--no-pager", "-n", "1500"],
            "usb": ["lsusb"], "usb-tree": ["lsusb", "-t"], "pci": ["lspci", "-nnk"],
            "packages": ["pacman", "-Q"], "mounts": ["findmnt", "-o", "TARGET,SOURCE,FSTYPE,OPTIONS"],
            "cpu": ["lscpu", "-e"], "modules": ["lsmod"],
            "usb-service": ["systemctl", "--no-pager", "--full", "status", "m4rch-usb.service", "arch-m4-usb.service"]}
    if kit is not None:
        jobs["power"] = ["python3", str(kit / "m4rch-power-report"), "--runtime"]
        jobs["topology"] = ["python3", str(kit / "m4rch-cpu-benchmark"), "--inspect"]
    for name, argv in jobs.items():
        (output / (name + ".json")).write_text(json.dumps(runner(argv), indent=2) + "\n")
    (output / "INCOMPLETE").unlink()
    (output / "COMPLETE").write_text("Snapshot complete; command failures are retained as evidence.\n")
    return output


def bundle(source, output):
    source, output = Path(source).absolute(), Path(output).absolute()
    if any(p.is_symlink() for p in (source, *source.parents, output, *output.parents)):
        raise ValueError("Archive paths must not use symlinks")
    if not source.is_dir() or not output.parent.is_dir() or output.is_relative_to(source):
        raise ValueError("Use a capture directory and an archive outside that directory")
    if not (source / "HANDOVER.md").is_file():
        raise ValueError("Write the native agent's HANDOVER.md inside the capture directory first")
    paths = sorted(source.rglob("*"))
    if any(p.is_symlink() or not (p.is_file() or p.is_dir()) for p in paths):
        raise ValueError("Return archives may contain only regular files and directories")
    files = [p for p in paths if p.is_file()]
    if any(p.stat().st_size > 32 * LIMIT for p in files) or sum(p.stat().st_size for p in files) > 128 * LIMIT:
        raise ValueError("Return archive exceeds capture limits; select relevant evidence")
    hashes = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    temporary = output.with_name(output.name + ".partial")
    if output.exists() or output.is_symlink() or temporary.exists() or temporary.is_symlink():
        raise ValueError("Choose a new archive name")
    with temporary.open("xb") as stream:
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            for path in paths:
                archive.add(path, arcname=str(path.relative_to(source)), recursive=False)
    # Refuse promotion if the selected evidence changed while it was archived.
    if any(hashlib.sha256((source / name).read_bytes()).hexdigest() != digest for name, digest in hashes.items()):
        raise ValueError("Capture changed during archiving; partial archive retained")
    # FAT ESPs do not support hard links. Exclusive creation still prevents
    # overwriting an earlier return archive; publish only after this succeeds.
    with output.open("xb") as final, temporary.open("rb") as staged:
        shutil.copyfileobj(staged, final)
        final.flush()
        os.fsync(final.fileno())
    temporary.unlink()
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    take = actions.add_parser("snapshot")
    take.add_argument("--output", type=Path, required=True)
    take.add_argument("--label", required=True)
    pack = actions.add_parser("bundle")
    pack.add_argument("--input", type=Path, required=True)
    pack.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("Run this kit on native Linux")
    if args.action == "snapshot":
        if os.geteuid() != 0:
            parser.error("Use sudo for protected clock and kernel-log reads")
        print(snapshot(args.output, args.label, kit=Path(__file__).resolve().parent))
    else:
        print(bundle(args.input, args.output))


if __name__ == "__main__":
    main()
