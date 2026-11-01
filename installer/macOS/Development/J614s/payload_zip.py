#!/usr/bin/env python3
"""Create an unsigned J614s stage-2 candidate from a verified Aurora ZIP.

The two expected source SHA-256 values must come from the independently
authenticated Aurora catalog. This tool neither authenticates that catalog nor
signs a new one. No archive member is extracted to the filesystem.
"""

import argparse
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import tempfile
import zipfile

import build_stage2
import payload_stage2
import preflight
import stage1_inspect

SHA256 = re.compile(r"[a-f0-9]{64}\Z")
OUTPUT_PAYLOAD = "j614s-development-unsigned.zip"


def verify_hash(path, expected):
    if not SHA256.fullmatch(expected):
        raise ValueError("expected SHA-256 must be 64 lowercase hexadecimal characters")
    if path.is_symlink() or not path.is_file() or preflight.sha256(path) != expected:
        raise ValueError(f"source SHA-256 mismatch or invalid source file: {path.name}")


def validate_members(archive):
    names = set()
    for item in archive.infolist():
        name = item.filename
        parts = name.removesuffix("/").split("/")
        if (
            not name
            or name.startswith("/")
            or "\\" in name
            or any(part in ("", ".", "..") for part in parts)
            or name in names
            or item.flag_bits & 1
            or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
        ):
            raise ValueError(f"unsafe or duplicate ZIP member: {name!r}")
        mode = item.external_attr >> 16
        kind = stat.S_IFMT(mode)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError(f"non-regular ZIP member: {name!r}")
        if item.is_dir() != (kind == stat.S_IFDIR) and kind:
            raise ValueError(f"inconsistent ZIP member type: {name!r}")
        names.add(name)
    required = {
        "boot.img",
        "root.img",
        "esp/m1n1/boot.bin",
        "esp/aurora/stage1.bin",
        "esp/EFI/BOOT/BOOTAA64.EFI",
        "aurora-volume.icns",
    }
    if not required.issubset(names) or payload_stage2.MEMBER in names:
        raise ValueError(
            "missing required source ZIP members or J614s member already exists"
        )
    return names


def metadata_target(data):
    if len(data) > 65536:
        raise ValueError("metadata exceeds installer limit")
    parsed = json.loads(data)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("os_list"), list):
        raise ValueError("invalid Aurora metadata")
    matches = [
        item
        for item in parsed["os_list"]
        if isinstance(item, dict)
        and item.get("omarchy_target") == "apple-silicon-full-os"
    ]
    if len(matches) != 1:
        raise ValueError("metadata must contain exactly one full-OS target")
    target = matches[0]
    if (
        target.get("installation_profile") != "arch-minimal"
        or target.get("layout_kind") != "alarm-btrfs-v1"
        or target.get("next_object") != "m1n1/boot.bin"
    ):
        raise ValueError("unexpected source profile or boot contract")
    policy = target.get("aurora_stage2")
    if (
        not isinstance(policy, dict)
        or set(policy) != {"kind", "board_members"}
        or policy["kind"] != "board-file-v1"
    ):
        raise ValueError("missing board-specific stage-2 metadata")
    boards = policy["board_members"]
    if not isinstance(boards, dict) or payload_stage2.BOARD in boards:
        raise ValueError("invalid board mapping or J614s already present")
    return parsed, target


def make_candidate(m4rch):
    report = preflight.audit(m4rch)
    if not report["inputs_verified"]:
        raise ValueError("M4RCH retained-input preflight failed")
    inputs = {}
    for name in ("m1n1_stage2", "dtb", "uboot"):
        relative, expected = preflight.INPUTS[name]
        data = payload_stage2.regular(m4rch, relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"{name} changed after preflight")
        inputs[name] = data
    return build_stage2.assemble(inputs["m1n1_stage2"], inputs["dtb"], inputs["uboot"])


def make_stage1_template(path, expected):
    verify_hash(path, expected)
    original = path.read_bytes()
    report = stage1_inspect.inspect(original, expected)
    if not report.get("aurora_native_config_compatible"):
        raise ValueError("stage 1 must use the Aurora CFG01 contract")
    offset = report["config_offset"]
    # The installer fills a fresh ESP UUID later. Do not carry the original
    # machine's GPT identity into the private development payload.
    stage2_path = b";m1n1/boot.bin"
    body = struct.pack("<II", 1, 0)
    body += b"00000000-0000-0000-0000-000000000000" + bytes(4)
    body += stage2_path + bytes(192 - len(stage2_path))
    body += struct.pack("<I", binascii.crc32(body))
    candidate = original[:offset] + body + original[offset + 244 :]
    candidate_hash = hashlib.sha256(candidate).hexdigest()
    check = stage1_inspect.inspect(candidate, candidate_hash)
    if check["original_esp_uuid"] != "00000000-0000-0000-0000-000000000000":
        raise ValueError("stage-1 template retained its original ESP UUID")
    if (
        report["original_esp_uuid"] != "00000000-0000-0000-0000-000000000000"
        and report["original_esp_uuid"].encode() in candidate
    ):
        raise ValueError("stage-1 image retains its original ESP UUID elsewhere")
    return candidate


def prepare(
    payload,
    metadata,
    payload_digest,
    metadata_digest,
    m4rch,
    output,
    stage1=None,
    stage1_digest=None,
):
    output_location = output.resolve()
    if output_location.is_relative_to(m4rch.resolve()) or any(
        output_location.is_relative_to(path.parent.resolve())
        for path in (payload, metadata)
    ):
        raise ValueError("output must be outside all input trees")
    if output.exists() or output.is_symlink():
        raise ValueError("output already exists")
    verify_hash(payload, payload_digest)
    verify_hash(metadata, metadata_digest)
    original = metadata.read_bytes()
    if hashlib.sha256(original).hexdigest() != metadata_digest:
        raise ValueError("metadata changed after validation")
    data, target = metadata_target(original)
    if stage1 is None or stage1_digest is None:
        raise ValueError("a verified CFG01 stage 1 and SHA-256 are required")
    stage1_candidate = make_stage1_template(stage1, stage1_digest)
    candidate = make_candidate(m4rch)
    target["aurora_stage2"]["board_members"][
        payload_stage2.BOARD
    ] = payload_stage2.MEMBER
    target["package"] = OUTPUT_PAYLOAD
    target["allowed_device_classes"] = [payload_stage2.BOARD]
    # Aurora interprets this key as stage-1 compatibility. Its contents are
    # strictly experimental here: this output is unsigned and must never be
    # confused with a published, physically-qualified support catalog.
    target["aurora_stage1"] = {
        "kind": "common-raw-v1",
        "qualified_machines": {"j614sap": ["26.6.2"]},
    }
    output_metadata = (json.dumps(data, indent=2) + "\n").encode()
    if len(output_metadata) > 65536:
        raise ValueError("candidate metadata exceeds installer limit")
    with zipfile.ZipFile(payload) as source:
        names = validate_members(source)
        for board, member in target["aurora_stage2"]["board_members"].items():
            if board == payload_stage2.BOARD:
                continue
            if not isinstance(board, str) or not payload_stage2.BOARD_PATTERN.fullmatch(
                board
            ):
                raise ValueError("invalid existing board mapping")
            if (
                member != f"esp/m1n1/boot-{board.removesuffix('ap')}.bin"
                or member not in names
            ):
                raise ValueError(f"missing or invalid existing stage-2 member: {board}")
        if not output.parent.is_dir():
            raise ValueError("output parent does not exist")
        temp = Path(tempfile.mkdtemp(prefix=".j614s-payload-", dir=output.parent))
        try:
            candidate_zip = temp / OUTPUT_PAYLOAD
            with zipfile.ZipFile(candidate_zip, "w", allowZip64=True) as destination:
                for item in source.infolist():
                    if item.filename == "esp/aurora/stage1.bin":
                        destination.writestr(item, stage1_candidate)
                    elif item.is_dir():
                        destination.writestr(item, b"")
                    else:
                        with source.open(item) as stream, destination.open(
                            item, "w", force_zip64=True
                        ) as target_file:
                            shutil.copyfileobj(stream, target_file, 1024 * 1024)
                destination.writestr(
                    payload_stage2.MEMBER, candidate, compress_type=zipfile.ZIP_DEFLATED
                )
            (temp / "metadata.json").write_bytes(output_metadata)
            receipt = {
                "target": "Mac16,8 / apple,j614s / T6040",
                "source_payload_sha256": payload_digest,
                "source_metadata_sha256": metadata_digest,
                "candidate_payload_sha256": preflight.sha256(candidate_zip),
                "candidate_metadata_sha256": hashlib.sha256(
                    output_metadata
                ).hexdigest(),
                "stage2_sha256": hashlib.sha256(candidate).hexdigest(),
                "source_stage1_sha256": stage1_digest,
                "stage1_template_sha256": hashlib.sha256(stage1_candidate).hexdigest(),
                "stage1_board_firmware_mapping_experimental": True,
                "stage1_native_boot_verified": False,
                "unsigned_development_candidate": True,
                "install_ready": False,
            }
            (temp / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
            # Source could be replaced during streaming: refuse changed input.
            verify_hash(payload, payload_digest)
            verify_hash(metadata, metadata_digest)
            if output.exists() or output.is_symlink():
                raise ValueError("output appeared during assembly")
            os.rename(temp, output)
            return receipt
        finally:
            if temp.exists():
                shutil.rmtree(temp)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("m4rch", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--payload-sha256", required=True)
    parser.add_argument("--metadata-sha256", required=True)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--stage1-sha256", required=True)
    args = parser.parse_args()
    try:
        result = prepare(
            args.payload,
            args.metadata,
            args.payload_sha256,
            args.metadata_sha256,
            args.m4rch,
            args.output,
            args.stage1,
            args.stage1_sha256,
        )
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.exit(1, f"J614s ZIP overlay refused: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
