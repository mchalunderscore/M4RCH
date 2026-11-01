#!/usr/bin/env python3
"""Build an unsigned J614s stage-2 overlay for an Aurora filesystem bundle.

This development tool does not alter the source bundle, build an installer,
sign a catalog, authorize a device, or modify a disk.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re

import build_stage2
import preflight

BOARD = "j614sap"
MEMBER = "esp/m1n1/boot-j614s.bin"
BOARD_PATTERN = re.compile(r"j[0-9]+[a-z]*ap\Z")


def regular(root, relative):
    """Reject links along all components before reading a bundle member."""
    path = root
    for part in Path(relative).parts:
        if part in ("", ".", "..") or part.startswith("/"):
            raise ValueError("invalid bundle path")
        path = path / part
        if path.is_symlink():
            raise ValueError(f"symbolic link in bundle path: {relative}")
    if not path.is_file():
        raise ValueError(f"missing regular bundle file: {relative}")
    return path


def checked_manifest(bundle):
    source = regular(bundle, "esp/m1n1/boot.bin")
    manifest = json.loads(regular(bundle, "stage2.json").read_text())
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"schema", "sourceSha256", "boards"}
        or manifest["schema"] != 1
    ):
        raise ValueError("invalid upstream stage-2 manifest")
    if preflight.sha256(source) != manifest["sourceSha256"]:
        raise ValueError("common stage-2 source hash mismatch")
    boards = manifest["boards"]
    if not isinstance(boards, dict) or not boards or BOARD in boards:
        raise ValueError("invalid boards or J614s already present")
    for board, record in boards.items():
        if not isinstance(board, str) or not BOARD_PATTERN.fullmatch(board):
            raise ValueError("invalid board identifier")
        expected_member = f"esp/m1n1/boot-{board.removesuffix('ap')}.bin"
        if not isinstance(record, dict) or set(record) != {"member", "bytes", "sha256"}:
            raise ValueError("invalid board record")
        if record["member"] != expected_member or type(record["bytes"]) is not int:
            raise ValueError("invalid board member or size")
        source = regular(bundle, expected_member)
        if (
            source.stat().st_size != record["bytes"]
            or preflight.sha256(source) != record["sha256"]
        ):
            raise ValueError(f"board member identity mismatch: {board}")
    return manifest


def generate(bundle, m4rch, output):
    output_location = output.resolve()
    if output_location.is_relative_to(
        bundle.resolve()
    ) or output_location.is_relative_to(m4rch.resolve()):
        raise ValueError("overlay must be outside both input trees")
    manifest = checked_manifest(bundle)
    audit = preflight.audit(m4rch)
    if not audit["inputs_verified"]:
        raise ValueError("M4RCH retained-input preflight failed")
    inputs = {}
    for name in ("m1n1_stage2", "dtb", "uboot"):
        path, expected = preflight.INPUTS[name]
        content = regular(m4rch, path).read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"{name} changed during build")
        inputs[name] = content
    candidate = build_stage2.assemble(
        inputs["m1n1_stage2"], inputs["dtb"], inputs["uboot"]
    )
    manifest["boards"][BOARD] = {
        "member": MEMBER,
        "bytes": len(candidate),
        "sha256": hashlib.sha256(candidate).hexdigest(),
    }
    # Create a new overlay only after every input check has passed.
    output.mkdir(parents=True, exist_ok=False)
    member = output / MEMBER
    member.parent.mkdir(parents=True)
    member.write_bytes(candidate)
    (output / "stage2.json").write_text(json.dumps(manifest, indent=2) + "\n")
    receipt = {
        "target": "Mac16,8 / apple,j614s / T6040",
        "member": MEMBER,
        "sha256": hashlib.sha256(candidate).hexdigest(),
        "unsigned_development_overlay": True,
        "install_ready": False,
    }
    (output / "j614s-overlay-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="existing Aurora filesystem bundle")
    parser.add_argument("m4rch", type=Path, help="extracted M4RCH with retained inputs")
    parser.add_argument("output", type=Path, help="new overlay directory")
    args = parser.parse_args()
    try:
        result = generate(args.bundle, args.m4rch, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(1, f"J614s stage-2 overlay refused: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
