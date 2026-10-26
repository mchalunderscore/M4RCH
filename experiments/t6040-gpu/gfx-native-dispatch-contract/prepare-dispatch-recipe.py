#!/usr/bin/env python3
"""Prepare a distinct PID/subpriority-coherent native scheduler recipe offline.

No hardware, module loading, or source-candidate mutation. This is not an ASID
change, a QoS-ID allocation, an execution fix, or a native lifecycle proof.
"""
import argparse
import hashlib
import json
import re
import shutil
import struct
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BINARY_SHA = "3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e"
AUDIT = REPO / "docs/evidence/2026-10-09-native-scheduler-state.json"
PAGE = 16384
FILES = (
    "backing.bin", "render-data.h", "preparation.json", "graph-before.bin",
    "graph-receipt.json", "graph-contract.h", "job-data.h", "graph-map.h",
    "command-pool-map.h", "render-backing-map.h", "boot-contract.h",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pin(path):
    path = path.resolve()
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": digest(data)}


def native_reader(binary):
    segments = []
    offset = 32
    for _ in range(struct.unpack_from("<I", binary, 16)[0]):
        command, length = struct.unpack_from("<II", binary, offset)
        if command == 25:
            segments.append(struct.unpack_from("<QQQQ", binary, offset + 24))
        offset += length

    def read(va, size):
        for vm, _vmsize, fileoff, filesize in segments:
            if vm <= va and va + size <= vm + filesize:
                return binary[fileoff + va - vm:fileoff + va - vm + size]
        raise ValueError("Native machine range is not fully file-backed")
    return read


def prepare(source, output, macho):
    source, output, macho = source.resolve(), output.resolve(), macho.resolve()
    if output.exists() or source == output or source in output.parents:
        raise ValueError("Choose a distinct absent output outside the source candidate")
    source_pins = [pin(source / name) for name in FILES]
    binary = macho.read_bytes()
    if digest(binary) != BINARY_SHA:
        raise ValueError("Private native driver identity mismatch")
    audit = json.loads(AUDIT.read_text())
    if audit["binary_sha256"] != BINARY_SHA:
        raise ValueError("Native audit driver identity mismatch")
    read = native_reader(binary)
    ranges = {}
    for name in ("channel_pid_getter", "channel_subpriority_getter", "config_companions"):
        record = audit["native_ranges"][name]
        start, end = int(record["start"], 0), int(record["end_exclusive"], 0)
        if digest(read(start, end - start)) != record["sha256"]:
            raise ValueError("Native machine range identity mismatch: " + name)
        ranges[name] = record

    preparation = json.loads((source / "preparation.json").read_text())
    data = bytearray((source / "backing.bin").read_bytes())
    if preparation["pages"] != 56 or len(data) != 56 * PAGE or digest(data) != preparation["data_sha256"]:
        raise ValueError("Expected exact captured 56-page render backing")
    header = (source / "render-data.h").read_text()
    marker = "static const u8 render_bytes["
    if header.count(marker) != 1 or digest(header.encode()) != preparation["header_sha256"]:
        raise ValueError("Render header provenance mismatch")
    prefix, initializer = header.split(marker)
    reconstructed = bytearray(len(data))
    for position, value in re.findall(r"\[(0x[0-9a-f]+|[0-9]+)\]=(0x[0-9a-f]+|[0-9]+)", initializer):
        reconstructed[int(position, 0)] = int(value, 0)
    if reconstructed != data:
        raise ValueError("Compiled render initializer differs from binary backing")
    original = bytes(data)
    changes = []
    expected_offsets = set()
    queues = preparation["owned_scheduler"]
    if [q["stage"] for q in queues] != ["ta", "3d"]:
        raise ValueError("Expected existing TA and fragment channel identities")
    for q in queues:
        index = preparation["firmware_aliases"].index(q["state_fw"])
        if index not in (48, 50):
            raise ValueError("Unexpected queue-state backing identity")
        offset = index * PAGE
        config = offset + (int(q["config_fw"], 0) - int(q["state_fw"], 0))
        if config != offset + 0x1000 or struct.unpack_from("<I", data, config)[0] != 15:
            raise ValueError("Expected existing opcode-15 configuration at state+0x1000")
        pid = struct.unpack_from("<I", data, offset + 0x48)[0]
        subpriority = struct.unpack_from("<I", data, offset + 0x40)[0]
        if pid != q["queue_id"] + 1 or subpriority != 1:
            raise ValueError("Captured channel getter operands changed")
        if tuple(struct.unpack_from("<II", data, config + 0x5a)) != (0, 0):
            raise ValueError("Source already changed from the captured inconsistent recipe")
        for name, field, value, state_field in (
            ("pid", 0x5a, pid, 0x48), ("subpriority", 0x5e, subpriority, 0x40),
        ):
            old = struct.unpack_from("<I", data, config + field)[0]
            struct.pack_into("<I", data, config + field, value)
            expected_offsets.update(range(config + field, config + field + 4))
            changes.append({"stage": q["stage"], "queue_id": q["queue_id"],
                            "field": name, "channel_state_offset": hex(state_field),
                            "config_offset": hex(field), "backing_offset": hex(config + field),
                            "before": old, "after": value,
                            "binding": "Current native channel getter operand; experimental supplied process/policy value"})
    byte_changes = [{"offset": hex(i), "before": a, "after": b}
                    for i, (a, b) in enumerate(zip(original, data)) if a != b]
    if len(byte_changes) != 4 or any(int(c["offset"], 0) not in expected_offsets for c in byte_changes):
        raise ValueError("Only the four proven PID/subpriority low bytes may change")
    for index in (49, 51):
        if original[index * PAGE:(index + 1) * PAGE] != data[index * PAGE:(index + 1) * PAGE]:
            raise ValueError("Scheduler work records changed")
    graph = output / "graph"
    graph.mkdir(parents=True, exist_ok=False)
    for name in FILES:
        shutil.copy2(source / name, graph / name)
    new_header = prefix + "static const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={" + ",".join(
        "[" + hex(i) + "]=" + hex(value) for i, value in enumerate(data) if value) + "};\n"
    (graph / "backing.bin").write_bytes(data)
    (graph / "render-data.h").write_text(new_header)
    trial = {"schema": "m4rch.native-dispatch-recipe.v1", "changes": changes,
             "changed_bytes": byte_changes, "changed_byte_count": 4,
             "native_ranges": ranges, "source_candidate": str(source),
             "native_binary_sha256": BINARY_SHA, "source_backing_sha256": digest(original),
             "hardware_actions": False, "candidate_loaded": False,
             "preserved": ["all channel-state bytes", "QoS ID+0x56", "header selector1",
                           "queue masks and kicks", "all KSM work/register/dependency records",
                           "job-data.h", "graph-before.bin", "device and firmware mappings",
                           "all shader/target/parameter/completion bytes"],
             "qualification": "Matches native config getters to the existing same channel state. Does not allocate a native PID/QoS identity, reproduce reason/mutex lifecycle, or prove this discrepancy blocked execution."}
    preparation.update(data_sha256=digest(data), header_sha256=digest(new_header.encode()),
                       native_dispatch_recipe=trial,
                       qualification="Distinct offline native-consistent PID/subpriority recipe; no GPU execution or retirement proved.")
    (graph / "preparation.json").write_text(json.dumps(preparation, indent=2) + "\n")
    for name in FILES:
        if name not in ("backing.bin", "render-data.h", "preparation.json") and (graph / name).read_bytes() != (source / name).read_bytes():
            raise ValueError("Unrelated source artifact changed: " + name)
    report = {"schema": "m4rch.native-dispatch-recipe-preparation.v1", "prepared": True,
              "hardware_actions": False, "source": str(source), "output": str(graph),
              "native_ranges": ranges, "recipe": trial,
              "inputs": source_pins + [pin(AUDIT), pin(macho), pin(Path(__file__))],
              "outputs": [pin(graph / name) for name in FILES]}
    (output / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--macho", type=Path, default=Path("/boot/GPUC003/private-apple/com.apple.AGXG16X"))
    args = parser.parse_args()
    report = prepare(args.source, args.output, args.macho)
    print(json.dumps({"prepared": True, "output": report["output"], "changed_bytes": 4,
                      "hardware_actions": False, "receipt": str(args.output / "receipt.json")}, indent=2))


if __name__ == "__main__":
    main()
