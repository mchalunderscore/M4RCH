#!/usr/bin/env python3
"""Compare the current J614s ATC handoff with the pre-trial property hashes."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

BASELINE = Path("cache/j614s-atc-ownership-experiment/baseline-property-hashes.json")
TREE = Path("/sys/firmware/devicetree/base")
NODES = {
    "atcphy0": "phy@382a90000", "atcphy1": "phy@38aa90000",
    "atcphy2": "phy@392a90000", "atcphy3": "phy@39aa90000",
    "usb0": "usb@382280000", "usb1": "usb@38a280000", "usb2": "usb@392280000",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-alias", action="store_true", help="check the alias-free trial")
    args = parser.parse_args()
    baseline = json.loads(BASELINE.read_text())
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if boot_id == baseline["boot_id"]:
        print("REFUSED: still on the baseline boot; the trial has not run.")
        return 2
    properties = baseline["property_sha256"]
    if len(properties) != 57:
        raise ValueError("baseline must contain all 57 recorded properties")
    missing, different = [], []
    for name, expected in sorted(properties.items()):
        parts = name.split("/")
        if len(parts) != 2 or parts[0] not in NODES.values() or not parts[1].startswith("apple,tunable-"):
            raise ValueError("unexpected property path in baseline")
        try:
            data = (TREE / name).read_bytes()
        except FileNotFoundError:
            missing.append(name)
            continue
        if hashlib.sha256(data).hexdigest() != expected:
            different.append(name)
    print(f"Current boot: {boot_id}; properties checked: {len(properties)}")
    for alias, name in NODES.items():
        try:
            status = (TREE / name / "status").read_bytes().rstrip(b"\0").decode()
        except FileNotFoundError:
            status = "missing"
        try:
            target = (TREE / "aliases" / alias).read_bytes().rstrip(b"\0").decode()
        except FileNotFoundError:
            target = "missing"
        print(f"{alias}: target={target} status={status}")
        expected_status = {"okay", "disabled"} if alias == "atcphy3" else {"okay"}
        expected_target = "missing" if args.no_alias else "/" + name
        if target != expected_target or status not in expected_status:
            different.append(f"{alias}: alias or status")
    print(f"Missing properties: {len(missing)}; different properties or nodes: {len(different)}")
    for name in missing:
        print(f"MISSING {name}")
    for name in different:
        print(f"DIFFERENT {name}")
    print("Hashes are not printed. Matching hashes alone do not establish that each port works.")
    return 1 if missing or different else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        sys.exit(2)
