#!/usr/bin/env python3
"""Assemble a local J614s stage-2 candidate from verified M4RCH inputs."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct

import preflight


def assemble(prefix, dtb, uboot):
    # This is the split-loader layout in M4RCH bce491f:sdboot/split_loader.py.
    if not prefix or len(prefix) % 16384:
        raise ValueError("m1n1 stage-2 prefix is not 16 KiB aligned")
    if len(dtb) < 40 or struct.unpack_from(">II", dtb) != (0xD00DFEED, len(dtb)):
        raise ValueError("invalid J614s device tree")
    if len(uboot) < 64 or uboot[56:60] != b"ARM\x64":
        raise ValueError("invalid ARM64 U-Boot image")
    offset, extent = struct.unpack_from("<QQ", uboot, 8)
    if offset or not len(uboot) <= extent <= 32 * 1024 * 1024:
        raise ValueError("invalid U-Boot memory footprint")
    return prefix + dtb + gzip.compress(uboot, compresslevel=9, mtime=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("m4rch_root", type=Path)
    parser.add_argument("output", type=Path, help="new, empty output directory")
    args = parser.parse_args()
    report = preflight.audit(args.m4rch_root)
    if not report["inputs_verified"]:
        parser.error("retained-input preflight failed; no output created")
    files = {
        name: (args.m4rch_root / preflight.INPUTS[name][0]).read_bytes()
        for name in ("m1n1_stage2", "dtb", "uboot")
    }
    # Check the bytes actually read, not only the earlier preflight result.
    for name, content in files.items():
        if hashlib.sha256(content).hexdigest() != preflight.INPUTS[name][1]:
            parser.error(f"{name} changed during the build")
    candidate = assemble(files["m1n1_stage2"], files["dtb"], files["uboot"])
    args.output.mkdir(parents=True, exist_ok=False)
    target = args.output / "boot-j614s-candidate.bin"
    target.write_bytes(candidate)
    receipt = {
        "target": report["target"],
        "source_recipe": "M4RCH bce491f:sdboot/split_loader.py",
        "inputs": {name: preflight.INPUTS[name][1] for name in files},
        "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
        "native_boot_verified": False,
        "install_ready": False,
    }
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
