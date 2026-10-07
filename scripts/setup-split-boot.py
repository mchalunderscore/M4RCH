#!/usr/bin/env python3
"""Install ESP /boot.bin, then optionally stage the one-time enrolled stage 1."""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT / "sdboot"), str(PROJECT / "lib")]
import enrollment
from common import sha256, verify_manifest, write_json, run
from split_loader import ESP_UUID


def install_stage2(source, esp, backup):
    destination = esp / "boot.bin"
    if destination.is_symlink() or (destination.exists() and not destination.is_file()):
        raise ValueError("ESP boot.bin must be a regular non-symlink file")
    backup.mkdir(parents=True, exist_ok=False)
    previous = None
    if destination.exists():
        previous = sha256(destination)
        shutil.copyfile(destination, backup / "boot.bin")
        if sha256(backup / "boot.bin") != previous:
            raise ValueError("Stage-2 rollback copy failed verification")
    expected = sha256(source)
    # Only replace the directory entry after the complete new file is synced.
    fd, name = tempfile.mkstemp(prefix=".boot-bin-", dir=esp)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream, source.open("rb") as incoming:
            shutil.copyfileobj(incoming, stream)
            stream.flush(); os.fsync(stream.fileno())
        if sha256(temporary) != expected:
            raise ValueError("Stage-2 staged copy failed verification")
        temporary.replace(destination)
        run(["sync"])
        if sha256(destination) != expected:
            raise ValueError("ESP stage-2 readback failed verification")
    finally:
        temporary.unlink(missing_ok=True)
    return {"stage2_sha256": expected, "previous_sha256": previous,
            "rollback_directory": str(backup), "destination": str(destination)}


def stage2_source(out, use_gravity=False):
    source = out / "split-loader/boot.bin"
    gravity = None
    if use_gravity:
        gravity = verify_manifest(out / "gravity-loader/loader-manifest.json")
        if (gravity.get("kind") != "j614s-gravity-stage2" or
            gravity.get("stage2_path") != "boot.bin" or
            gravity["inputs"].get("esp_partuuid") != ESP_UUID or
            gravity["inputs"].get("stage1_sha256") != sha256(out / "split-loader/loader.bin")):
            raise ValueError("Gravity stage 2 does not match this enrolled stage-1/ESP contract")
        source = out / "gravity-loader/boot.bin"
    return source, gravity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage2-only", action="store_true")
    parser.add_argument("--gravity", action="store_true", help="Install the separately verified Gravity stage 2")
    args = parser.parse_args()
    if args.gravity and not args.stage2_only:
        parser.error("--gravity requires --stage2-only; the enrolled stage 1 stays unchanged")
    if os.geteuid() != 0:
        raise ValueError("Run sudo make stage2 or sudo make boot-split")
    out = PROJECT / "out/sdboot"
    manifest = verify_manifest(out / "split-loader/loader-manifest.json")
    verify_manifest(out / "internal-loader/loader-manifest.json")
    enrollment._source(out, "stage1")
    if manifest.get("stage2_path") != "boot.bin" or manifest["inputs"].get("esp_partuuid") != ESP_UUID:
        raise ValueError("Split-loader ESP identity/path changed")
    if not (PROJECT / "out/internal-layout-extension.json").exists():
        raise ValueError("Complete the existing internal ESP setup first")
    source, gravity = stage2_source(out, args.gravity)
    # Reuse the existing UUID-bound mount resolver; never enumerate an SD card.
    spec = importlib.util.spec_from_file_location("internal_esp", PROJECT / "scripts/internal-esp.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    value, esp = module.mount(ESP_UUID)
    parent = module.m.info(value["ParentWholeDisk"])
    if not parent.get("Internal") or value.get("Content") != "EFI":
        raise ValueError("Stage 2 requires the internal EFI System Partition")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = PROJECT / "out/split-boot-backups" / stamp
    record = install_stage2(source, esp, backup)
    if gravity is not None:
        record["sources"] = gravity["inputs"]["profile"]["sources"]
    record.update(esp_partuuid=ESP_UUID, stage1_sha256=sha256(out / "split-loader/loader.bin"))
    # Keep a Mac-local copy of the proven monolithic bundle for Recovery rollback.
    monolithic = out / "internal-loader/loader.bin"
    shutil.copyfile(monolithic, backup / "monolithic-loader.bin")
    write_json(backup / "receipt.json", record)
    write_json(out / "split-boot-state.json", record)
    print("Verified ESP stage 2:", esp / "boot.bin")
    print("Rollback backup:", backup)
    if gravity is not None:
        kit = esp / "loader-alignment"
        if kit.is_symlink():
            raise ValueError("Alignment kit destination must not be a symlink")
        kit.mkdir(exist_ok=True)
        for name in ("HANDOVER.md", "collect.sh", "profile.json", "loader-manifest.json"):
            destination = kit / name
            if destination.is_symlink():
                raise ValueError("Alignment kit file must not be a symlink: " + name)
            if destination.exists():
                shutil.copyfile(destination, backup / ("alignment-" + name))
            source = out / "gravity-loader" / name
            shutil.copyfile(source, destination)
            if sha256(source) != sha256(destination):
                raise ValueError("Alignment kit copy failed verification: " + name)
        run(["sync"])
        print("Linux handover:", kit / "HANDOVER.md")
    if args.stage2_only:
        print("Stage 1 and Apple enrollment were not changed.")
    else:
        enrollment.prepare(PROJECT, out, nvme="stage1")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit("m4rch: " + str(error))
