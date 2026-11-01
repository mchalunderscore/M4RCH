#!/usr/bin/env python3
"""Inspect a hash-identified M4RCH stage 1 for Aurora compatibility.

This build-time diagnostic reads an explicitly supplied file and may export a
compatible base. It never enrolls or personalizes an Apple boot object, and
does not assert boot readiness.
"""

import argparse
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys

ALIGNMENT = 16384
MAX_LEGACY_BASE = (4 << 20) - 1024
MAX_NATIVE_IMAGE = 64 << 20
MARKER = b"AURORA-S1-CFG01\x00"
TRAILER = re.compile(
    rb"chainload=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    rb"[0-9a-f]{4}-[0-9a-f]{12});boot\.bin\n"
    rb"chosen\.asahi,efi-system-partition=\1\n\x00{4}"
)
EXPECTED = re.compile(r"[0-9a-f]{64}\Z")
UUID = re.compile(rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")


def inspect_native(data, observed):
    if len(data) > MAX_NATIVE_IMAGE or not data.endswith(b"STACKBOT"):
        raise ValueError("native stage 1 exceeds the 64 MiB limit or lacks STACKBOT")
    if data.count(MARKER) != 1:
        raise ValueError("native stage 1 must contain one CFG01 marker")
    offset = data.index(MARKER) + len(MARKER)
    if offset + 244 > len(data) - 8:
        raise ValueError("native stage-1 CFG01 block is truncated")
    block = data[offset : offset + 244]
    version, window = struct.unpack_from("<II", block)
    uuid = block[8:44]
    if version != 1 or window > 99999 or not UUID.fullmatch(uuid):
        raise ValueError("invalid stage-1 CFG01 version, window, or UUID")
    if block[44:48] != bytes(4):
        raise ValueError("invalid stage-1 CFG01 UUID padding")
    path_field = block[48:240]
    path_value, separator, padding = path_field.partition(b"\0")
    if not separator or any(padding) or not path_value.startswith(b";"):
        raise ValueError("invalid stage-1 CFG01 path padding")
    path = path_value[1:]
    if (
        not path
        or len(path) + 1 >= 192
        or any(value < 0x20 or value >= 0x7F or value == ord(";") for value in path)
        or b"\\" in path
        or any(part in (b"", b".", b"..") for part in path.split(b"/"))
    ):
        raise ValueError("invalid stage-1 CFG01 relative path")
    expected_crc = struct.unpack_from("<I", block, 240)[0]
    if binascii.crc32(block[:240]) != expected_crc:
        raise ValueError("invalid stage-1 CFG01 CRC-32")
    return {
        "format": "aurora-cfg01-v1",
        "configured_sha256": observed,
        "configured_bytes": len(data),
        "config_offset": offset,
        "original_esp_uuid": uuid.decode("ascii"),
        "original_stage2_path": path.decode("ascii"),
        "window_ms": window,
        "aurora_native_config_compatible": True,
        "aurora_legacy_base_compatible": False,
        "native_boot_verified": False,
        "install_ready": False,
    }


def inspect(data, expected_sha256):
    if not EXPECTED.fullmatch(expected_sha256):
        raise ValueError("expected SHA-256 must be 64 lowercase hexadecimal digits")
    observed = hashlib.sha256(data).hexdigest()
    if observed != expected_sha256:
        raise ValueError(
            "stage-1 SHA-256 does not match the explicitly supplied digest"
        )
    if MARKER in data:
        return inspect_native(data, observed)
    if not data or len(data) % ALIGNMENT:
        raise ValueError("M4RCH configured stage 1 is not 16 KiB aligned")
    candidates = [
        match
        for match in TRAILER.finditer(data)
        if match.start() > 0
        and match.start() % ALIGNMENT == 0
        and not any(data[match.end() :])
    ]
    if len(candidates) != 1:
        raise ValueError(
            "expected one aligned M4RCH chainload trailer and zero padding"
        )
    match = candidates[0]
    base = data[: match.start()]
    legacy_checks = {
        "base_at_most_aurora_limit": len(base) <= MAX_LEGACY_BASE,
        "base_ends_stackbot": base.endswith(b"STACKBOT"),
        "base_has_no_aurora_config_marker": MARKER not in base,
    }
    return {
        "format": "m4rch-legacy-text-v1",
        "configured_sha256": observed,
        "configured_bytes": len(data),
        "base_sha256": hashlib.sha256(base).hexdigest(),
        "base_bytes": len(base),
        "original_esp_uuid": match.group(1).decode("ascii"),
        "original_stage2_path": "boot.bin",
        "aurora_legacy_base_checks": legacy_checks,
        "aurora_legacy_base_compatible": all(legacy_checks.values()),
        "native_boot_verified": False,
        "install_ready": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage1", type=Path, help="readable copy of configured M4RCH stage 1"
    )
    parser.add_argument(
        "--sha256", required=True, help="independently recorded configured file SHA-256"
    )
    exports = parser.add_mutually_exclusive_group()
    exports.add_argument(
        "--legacy-base-output",
        type=Path,
        help="write the compatible base as a new private file; never overwrite",
    )
    exports.add_argument(
        "--native-stage1-output",
        type=Path,
        help="copy a validated CFG01 image as a new private file; never overwrite",
    )
    args = parser.parse_args()
    try:
        data = args.stage1.read_bytes()
        report = inspect(data, args.sha256)
        output = None
        content = None
        if args.legacy_base_output is not None:
            if not report["aurora_legacy_base_compatible"]:
                raise ValueError(
                    "stage 1 does not satisfy Aurora's legacy base contract"
                )
            output = args.legacy_base_output
            content = data[: report["base_bytes"]]
        if args.native_stage1_output is not None:
            if not report.get("aurora_native_config_compatible"):
                raise ValueError("stage 1 does not contain an Aurora CFG01 block")
            output = args.native_stage1_output
            content = data
        if output is not None:
            descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
    except (OSError, ValueError) as error:
        print(f"stage1 inspection failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return (
        0
        if report.get("aurora_native_config_compatible")
        or report["aurora_legacy_base_compatible"]
        else 2
    )


if __name__ == "__main__":
    sys.exit(main())
