#!/usr/bin/env python3
"""Export only USB resource/routing metadata from this Mac's IODeviceTree."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import plistlib
import re
import subprocess

FIELDS = {"name", "compatible", "device_type", "reg", "ranges", "AAPL,phandle",
          "#address-cells", "#size-cells", "interrupts", "interrupt-parent",
          "clock-gates", "power-domains", "atc-phy", "atc-phy-parent",
          "acio-parent", "usb-drd-parent", "port-number", "port-type",
          "port", "PortNumber", "PortType", "rid", "transport", "instance"}


def select(root):
    result = {}
    def walk(nodes, parent=""):
        if isinstance(nodes, dict):
            nodes = [nodes]
        for node in nodes:
            name = node.get("IORegistryEntryName", "?")
            path = parent + "/" + name
            if re.fullmatch(r"arm-io|usb-drd\d+(?:-port-(?:hs|ss))?|atc-phy\d+|nub-spmi-a\d+|hpm\d+", name):
                props = {}
                for key in sorted(FIELDS & node.keys()):
                    value = node[key]
                    if isinstance(value, bytes):
                        # Preserve ADT byte order; do not treat these as Linux DT cells.
                        if len(value) > 32768:
                            continue
                        value = {"hex": value.hex(), "little_endian_u32":
                            [int.from_bytes(value[i:i+4], "little") for i in range(0, len(value), 4)]
                            if len(value) % 4 == 0 else None}
                    elif not isinstance(value, (str, int, bool)):
                        continue
                    props[key] = value
                result[path] = props
            walk(node.get("IORegistryEntryChildren", []), path)
    walk(root)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    model = subprocess.check_output(["/usr/sbin/sysctl", "-n", "hw.model"], text=True).strip()
    if model != "Mac16,8":
        parser.error("This handover targets Mac16,8")
    root = plistlib.loads(subprocess.check_output(["/usr/sbin/ioreg", "-a", "-p", "IODeviceTree", "-l"]))
    result = {"schema": 1, "model": model, "utc": datetime.now(timezone.utc).isoformat(),
              "encoding": "raw IODeviceTree/ADT bytes, not Linux big-endian DT cells",
              "nodes": select(root)}
    if not result["nodes"]:
        parser.error("No USB port metadata found")
    with args.output.open("x") as output:
        output.write(json.dumps(result, indent=2) + "\n")
    print(f"Exported {len(result['nodes'])} routing/resource nodes to {args.output}")


if __name__ == "__main__":
    main()
