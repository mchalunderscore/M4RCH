#!/usr/bin/env python3
"""Stage native T6040 components in a fresh full Gravity module source set."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]

def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

def stage(destination):
    destination = Path(destination).resolve()
    destination.relative_to(ROOT / "out")
    baseline = ROOT / "out/gpu-gravity-contract/linux/drivers/gpu/drm/asahi"
    selected = ROOT / "out/gpu-desktop-integration-v2/source/linux/drivers/gpu/drm/asahi"
    receipt = json.loads((ROOT / "out/gpu-desktop-integration-v2/stage-receipt.json").read_text())
    for item in receipt["output_pins"]:
        if item["family"] == "linux":
            actual = pin(item["path"])
            if actual["sha256"] != item["sha256"] or actual["bytes"] != item["bytes"]:
                raise ValueError("Selected source changed: " + item["path"])
    destination.mkdir(exist_ok=False, parents=True)
    source = destination / "source/linux/drivers/gpu/drm/asahi"
    shutil.copytree(baseline, source)
    for item in selected.iterdir():
        if item.is_file():
            shutil.copyfile(item, source / item.name)
    # Generated build objects are not source inputs and are never copied into
    # the new owner. The preserved full baseline itself remains untouched.
    for item in source.rglob("*"):
        if item.is_file() and (item.suffix in (".o", ".ko") or item.name.startswith(".")
                or item.name in ("Module.symvers", "modules.order")):
            item.unlink()
    shutil.copytree(source, destination / "base")
    patch = KIT / "gravity-native-t6040-components.patch"
    command = ["patch", "--batch", "--fuzz=0", "-p1", "--input", str(patch)]
    result = subprocess.run(command, cwd=destination / "source/linux", text=True,
                            capture_output=True, check=False)
    commands = [{"command": command, "returncode": result.returncode,
                 "stdout": result.stdout, "stderr": result.stderr}]
    if result.returncode:
        (destination / "stage-failed.json").write_text(json.dumps(commands, indent=2) + "\n")
        raise RuntimeError("Patch failed; evidence preserved")
    shutil.copyfile(KIT / "g16_t6040.rs", source / "g16_t6040.rs")
    shutil.copytree(source, destination / "build-owner")
    report = {"schema": "m4rch.gravity-native-t6040-components.stage.v1",
              "base": str(baseline), "selected": str(selected),
              "inputs": [pin(KIT / "stage.py"), pin(patch), pin(KIT / "g16_t6040.rs")],
              "commands": commands,
              "source_files": [pin(p) for p in sorted(source.rglob("*")) if p.is_file()],
              "unresolved_slots": [3, 22, 27, 39, 41], "hardware_actions": [],
              "normal_startup_enabled": False, "complete_boot_bundle": False,
              "qualification": "Native T6040 component is selected directly by Gravity Platform::new()/hwdata() and the FirmwareSpace mapping path. Full bundle/power/region-C producers reject T6040; execution remains disabled. No hardware."}
    (destination / "stage-receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    arguments = parser.parse_args()
    report = stage(arguments.destination)
    print(json.dumps({"source_files": len(report["source_files"]), "normal_startup_enabled": False}))
