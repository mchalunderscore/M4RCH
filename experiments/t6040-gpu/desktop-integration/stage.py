#!/usr/bin/env python3
"""Reproduce selected-source staging; never mutate a frozen source tree."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[2]

def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

def stage(destination):
    destination = Path(destination).resolve()
    destination.relative_to(ROOT / "out")
    manifest = json.loads((KIT / "base-inputs.json").read_text())
    for item in manifest["input_pins"]:
        actual = pin(item["path"])
        if actual["sha256"] != item["sha256"] or actual["bytes"] != item["bytes"]:
            raise ValueError("Frozen source changed: " + item["path"])
    destination.mkdir(parents=True, exist_ok=False)
    inputs = [pin(KIT / "base-inputs.json")]
    for item in manifest["input_pins"]:
        source = Path(item["path"])
        for prefix in ["base", "source"]:
            target = destination / prefix / item["family"] / item["relative_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    commands = []
    for family, name in [("linux", "gravity-linux-g16-topology-binding.patch"),
                         ("mesa", "gravity-mesa-g16-device-metadata.patch")]:
        patch = KIT / name
        inputs.append(pin(patch))
        command = ["patch", "--batch", "--fuzz=0", "-p1", "--input", str(patch)]
        result = subprocess.run(command, cwd=destination / "source" / family,
                                text=True, capture_output=True, check=False)
        commands.append({"command": command, "exit": result.returncode,
                         "stdout": result.stdout, "stderr": result.stderr})
        if result.returncode:
            (destination / "stage-failed.json").write_text(json.dumps(commands, indent=2) + "\n")
            raise RuntimeError("Patch application failed; evidence preserved")
    outputs = []
    for item in manifest["input_pins"]:
        outputs.append({"family": item["family"], "relative_path": item["relative_path"],
                        **pin(destination / "source" / item["family"] / item["relative_path"])})
    receipt = {"schema": "m4rch.gpu-desktop-integration-stage.v1",
               "scope": "Selected source copies only; no builds, controls or hardware reads",
               "base_input_pins": manifest["input_pins"], "tool_input_pins": inputs,
               "commands": commands, "output_pins": outputs,
               "t6040_normal_startup_enabled": False, "mesa_g16s_execution_enabled": False}
    with (destination / "stage-receipt.json").open("x") as file:
        json.dump(receipt, file, indent=2); file.write("\n")
    return receipt

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", help="A new directory beneath repository out/")
    args = parser.parse_args()
    receipt = stage(args.destination)
    print(json.dumps({"destination": str(Path(args.destination).resolve()),
                      "selected_files": len(receipt["output_pins"])}))
