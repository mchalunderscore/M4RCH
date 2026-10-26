#!/usr/bin/env python3
"""Audit by default; explicitly install only the reviewed additive kernel files.

Never mount/remount, invoke package hooks, regenerate EFI, select a new default,
load modules, touch the GPU, or reboot. The caller supplies a writable boot mount.
Failed installations leave only new paths for inspection, with a progress receipt.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

WORK = Path(__file__).resolve().parent
RECEIPT = WORK / "artifact-receipt.json"
RELEASE = "7.1.13-m4rch-gpu-reset"
MODULE_DST = Path("/usr/lib/modules") / RELEASE
MODULE_PARTIAL = Path("/usr/lib/modules/." + RELEASE + ".GFXR001.partial")
BOOT_DST = Path("/boot/GFXR001")
BOOT_PARTIAL = Path("/boot/.GFXR001.partial")
GRUB = Path("/boot/grub/grub.cfg")
GRUB_PARTIAL = Path("/boot/grub/.GFXR001-additive.cfg")
RESULT = WORK / "install-result.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify_files(records):
    for rec in records:
        p = Path(rec["path"])
        require(p.is_file() and not p.is_symlink(), "Missing or linked input: " + str(p))
        require(p.stat().st_size == rec["bytes"] and digest(p) == rec["sha256"],
                "Input changed: " + str(p))


def read_artifact(path, artifact_records):
    expected = artifact_records[str(path)]
    data = path.read_bytes()
    require(len(data) == expected["bytes"] and
            hashlib.sha256(data).hexdigest() == expected["sha256"],
            "Artifact bytes changed: " + str(path))
    return data


def verify_tree(directory, records):
    expected = {r["relative_path"] for r in records}
    actual = set()
    for p in directory.rglob("*"):
        require(not p.is_symlink(), "Unexpected module-tree symlink: " + str(p))
        if p.is_file():
            actual.add(str(p.relative_to(directory)))
    require(actual == expected, "Module-tree files differ: " + str(directory))
    for rec in records:
        rel = Path(rec["relative_path"])
        require(not rel.is_absolute() and ".." not in rel.parts, "Unsafe relative path")
        p = directory / rel
        require(p.stat().st_size == rec["bytes"] and digest(p) == rec["sha256"],
                "Module-tree input changed: " + str(p))


def verify_boot(directory, boot_files, artifact_records):
    for source, name in boot_files.items():
        expected = artifact_records[source]
        target = directory / name
        require(target.is_file() and not target.is_symlink() and
                target.stat().st_size == expected["bytes"] and
                digest(target) == expected["sha256"],
                "Boot payload differs from reviewed record: " + str(target))


def verify_host(records, allow_new_grub=False):
    for name, rec in records.items():
        if allow_new_grub and name == str(GRUB):
            continue
        p = Path(name)
        require(p.is_file() and p.stat().st_size == rec["bytes"] and
                digest(p) == rec["sha256"], "Protected host file changed: " + name)


def findmnt(field, target):
    return subprocess.check_output(
        ["findmnt", "--noheadings", "--raw", "--output", field, "--target", target],
        text=True).strip()


def verify_mounts():
    require(findmnt("FSTYPE", "/boot") == "vfat", "Boot is not vfat")
    require(findmnt("UUID", "/boot").upper() == "33CE-1F10", "Wrong boot FAT UUID")
    require(findmnt("PARTUUID", "/boot").lower() ==
            "5fdb35c6-3a66-416d-8358-6555fd99fcc5", "Wrong boot partition UUID")
    require("rw" in findmnt("OPTIONS", "/boot").split(","),
            "Boot is read-only; caller must deliberately enable writes separately")
    require(findmnt("FSTYPE", "/") == "ext4", "Root is not ext4")
    require(findmnt("UUID", "/").lower() ==
            "7568fe83-378f-5b78-ab12-ccc36ff09a90", "Wrong root UUID")
    require(findmnt("PARTUUID", "/").lower() ==
            "e80ee324-c4c5-4f3e-81b7-464adb71d41a", "Wrong root partition UUID")


def write_new(path, data):
    with path.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def save_progress(state):
    temp = RESULT.with_suffix(".json.tmp")
    temp.write_text(json.dumps(state, indent=2) + "\n")
    os.replace(temp, RESULT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--receipt-sha256", help="Reviewed artifact-receipt.json SHA256")
    args = parser.parse_args()
    require(RECEIPT.is_file(), "Missing reviewed artifact receipt")
    receipt_bytes = RECEIPT.read_bytes()
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    if args.execute:
        require(os.geteuid() == 0, "Execution requires root")
        require(args.receipt_sha256 == receipt_sha,
                "Execution requires the exact reviewed artifact receipt SHA256")
    elif args.receipt_sha256:
        require(args.receipt_sha256 == receipt_sha, "Artifact receipt hash differs")
    receipt = json.loads(receipt_bytes)
    require(receipt["schema"] == "m4rch.gfx-reset-additive-artifacts.v1", "Wrong schema")
    require(receipt["kernel_release"] == RELEASE, "Wrong release")
    verify_files(receipt["artifact_files"])
    artifact_records = {r["path"]: r for r in receipt["artifact_files"]}
    require(len(artifact_records) == len(receipt["artifact_files"]),
            "Duplicate artifact source record")
    names = set()
    for source, name in receipt["boot_files"].items():
        require(source in artifact_records, "Boot source lacks reviewed record: " + source)
        require(name not in ("", ".", "..") and Path(name).name == name and
                "/" not in name and "\\" not in name and name not in names,
                "Unsafe or duplicate boot basename")
        names.add(name)
    require({"vmlinuz", "initramfs.img", "grub-before.cfg"} <= names,
            "Required boot artifacts absent")
    module_source = Path(receipt["module_directory"])
    verify_tree(module_source, receipt["module_files"])
    protected = receipt["protected_host_files"]
    verify_host(protected)
    before = read_artifact(WORK / "grub-before.cfg", artifact_records)
    after = read_artifact(WORK / "grub-additive.cfg", artifact_records)
    entry = read_artifact(WORK / "additive-entry.cfg", artifact_records)
    require(after == before + entry, "New GRUB text does not preserve exact old prefix")
    require(before.count(b"menuentry ") == 4 and after.count(b"menuentry ") == 5,
            "Unexpected menu count")
    require(before.count(b"set default=1\n") == 1 and
            after.count(b"set default=1\n") == 1, "Existing default must stay unchanged")
    require(GRUB.read_bytes() == before, "Current GRUB no longer matches review")
    if not args.execute:
        print("Audit passed; no writes or mount probes. New entry index 4; default remains 1.")
        print("Execute only after separate writable-boot preparation with --execute "
              "--receipt-sha256 " + receipt_sha)
        return

    # Share the normal updater's lock, without running the updater itself.
    lock = Path("/run/lock/arch-m4-boot.lock")
    with lock.open("a") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        verify_mounts()
        verify_host(protected)
        require(not RESULT.exists(), "Previous result exists; inspect before another attempt")
        for p in [MODULE_DST, MODULE_PARTIAL, BOOT_DST, BOOT_PARTIAL, GRUB_PARTIAL]:
            require(not os.path.lexists(p), "New target already exists: " + str(p))
        require(os.statvfs("/usr/lib/modules").f_bavail *
                os.statvfs("/usr/lib/modules").f_frsize >
                receipt["module_bytes"] + 1048576, "Insufficient module filesystem space")
        require(os.statvfs("/boot").f_bavail * os.statvfs("/boot").f_frsize >
                receipt["boot_bytes"] + 1048576, "Insufficient boot filesystem space")
        state = {"schema": "m4rch.gfx-reset-additive-install.v1",
                 "started_unix": time.time(), "artifact_receipt_sha256": receipt_sha,
                 "baseline_grub_sha256": digest(GRUB), "default": 1,
                 "module_destination": str(MODULE_DST), "boot_destination": str(BOOT_DST),
                 "actions": [], "status": "started", "reboot_performed": False,
                 "hardware_reset_performed": False, "modules_loaded": False,
                 "mount_changed_by_installer": False}
        save_progress(state)
        try:
            shutil.copytree(module_source, MODULE_PARTIAL)
            verify_tree(MODULE_PARTIAL, receipt["module_files"])
            BOOT_PARTIAL.mkdir()
            for src, name in receipt["boot_files"].items():
                source = Path(src)
                write_new(BOOT_PARTIAL / name, read_artifact(source, artifact_records))
            verify_boot(BOOT_PARTIAL, receipt["boot_files"], artifact_records)
            state["actions"].append("New module and boot trees staged and verified")
            save_progress(state)
            verify_mounts()
            verify_host(protected)
            os.rename(MODULE_PARTIAL, MODULE_DST)
            state["actions"].append("New release modules published")
            save_progress(state)
            os.rename(BOOT_PARTIAL, BOOT_DST)
            state["actions"].append("New isolated boot artifacts published")
            save_progress(state)
            os.sync()
            # Recheck old text immediately before the sole existing-file publication.
            verify_host(protected)
            verify_boot(BOOT_DST, receipt["boot_files"], artifact_records)
            require(GRUB.read_bytes() == before, "GRUB changed during staging")
            write_new(GRUB_PARTIAL, after)
            require(GRUB_PARTIAL.read_bytes() == after, "Staged GRUB differs")
            subprocess.run(["grub-script-check", str(GRUB_PARTIAL)], check=True)
            require(GRUB.read_bytes() == before, "GRUB changed before publication")
            os.replace(GRUB_PARTIAL, GRUB)
            os.sync()
            require(GRUB.read_bytes() == after, "Published GRUB differs")
            verify_boot(BOOT_DST, receipt["boot_files"], artifact_records)
            verify_tree(MODULE_DST, receipt["module_files"])
            verify_host(protected, allow_new_grub=True)
            state.update(status="complete", finished_unix=time.time(),
                         current_grub_sha256=digest(GRUB), kernel_sha256=digest(BOOT_DST / "vmlinuz"),
                         initramfs_sha256=digest(BOOT_DST / "initramfs.img"),
                         module_manifest_sha256=receipt["module_manifest_sha256"],
                         baseline_grub_prefix_retained=GRUB.read_bytes().startswith(before),
                         previous_boot_entries_preserved=True)
            save_progress(state)
            print("Additive installation complete; default remains 1. No reboot or GPU operation.")
        except BaseException as error:
            state.update(status="partial", failure=str(error), finished_unix=time.time())
            save_progress(state)
            raise


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError, KeyError) as error:
        print("REFUSED/FAILED: " + str(error), file=sys.stderr)
        raise SystemExit(1)
