#!/usr/bin/env python3
"""Publish a native handover/diagnostic kit without replacing a kernel."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
WRAPPER = b'''#!/bin/sh
set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
kit=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
(cd "$kit" && sha256sum -c SHA256SUMS) || exit 1
exec python3 "$kit/m4rch-cpu-benchmark" "$@"
'''
COLLECTOR = b'''#!/bin/sh
set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
kit=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
(cd "$kit" && sha256sum -c SHA256SUMS) || exit 1
exec python3 "$kit/m4rch-native-lab" "$@"
'''
README = b'''Native USB and CPU investigation kit for the J614s

Start with HANDOVER.md: it describes this round's evidence run and the return
archive. Its cooling and idle safeguards take priority over the optional
benchmark examples below.

This kit changes no kernel, boot flags, Apple enrollment or fan settings.
Run it from an Alice terminal in Linux. Replace KIT with this directory's
absolute path, usually /boot/cpu-tools-ID. No installation is necessary.

python3 KIT/m4rch-cpu-benchmark --inspect

From the directory containing the same Geekbench binary used previously:
sudo sh KIT/run.sh --cpus all --output "$HOME/cpu-default" -- ./geekbench7
sudo sh KIT/run.sh --cpus performance --output "$HOME/cpu-pcores" -- ./geekbench7

Both commands preserve the existing governors. Root lets the monitoring
parent read cpuinfo_cur_freq, which Linux exposes with mode 0400. The workload
still runs as Alice, and the capture belongs to Alice. An unprivileged null
clock reading does not prove the attribute is absent. The second uses only the
eight performance cores and measures their effect on the single-core score;
its multicore score is an eight-core result. Keep all twelve cores for the
normal multicore comparison. Choose a new output directory for every run.
The workload output, including any result URL, stays in your terminal.

Optional: after the first comparisons, test only the first P cluster with
its governor temporarily set to performance; other policies are untouched:
sudo sh KIT/run.sh --cpus p0 --output "$HOME/cpu-p0-default" -- ./geekbench7
# After cooling to the same starting temperature:
sudo sh KIT/run.sh --cpus p0 --governor performance \
    --output "$HOME/cpu-p0-performance" -- ./geekbench7

Compare those two four-core runs to isolate the governor's effect.
The first native pair reported high CPU sensor readings. Inspect cooling and
root-readable clocks before a governor experiment; native-agent-followup.md
contains the next checks and instructions.md contains the full setup guide.
The command still runs as the invoking non-root user. Governors are restored
when it exits or receives Ctrl-C/SIGTERM. A forced kill or loss of power
cannot run cleanup; metadata records the original governors, and reboot
restores the normal boot policy. No frequency limits or fan controls are
written. With idle=nop, increasing idle frequencies can increase heat.

Use AC power, the same binary/version and comparable starting temperatures.
Close busy background applications before each run. Each capture contains
metadata.json, samples.jsonl and summary.json with CPU placement, requested
and hardware-reported clocks, temperatures, fan RPM and power conditions.
Copy the captures to /boot for reading from macOS, or archive them there:
sudo tar -czf /boot/cpu-results.tar.gz -C "$HOME" cpu-default cpu-pcores

The Python files are also installed by config-m4rch packages as
m4rch-cpu-benchmark and m4rch-power-report. This standalone kit lets you
try them on the current working kernel without a package transaction.

HANDOVER.md adds the USB2, CPU idle, scheduling and cooling investigation.
Use collect.sh for read-only snapshots and a private return archive.
'''


def publish(project=PROJECT, out=None):
    project = Path(project)
    out = Path(out) if out is not None else project / "out/sdboot"
    contents = {
        "m4rch-cpu-benchmark": (project / "sdboot/cpu_benchmark.py").read_bytes(),
        "m4rch-power-report": (project / "sdboot/peripheral_policy.py").read_bytes(),
        "run.sh": WRAPPER,
        "README.txt": README,
        "instructions.md": (project / "docs/native-agent-instructions.md").read_bytes(),
        "native-agent-followup.md": (project / "docs/native-agent-followup.md").read_bytes(),
        "HANDOVER.md": (project / "HANDOVER.md").read_bytes(),
        "m4rch-native-lab": (project / "sdboot/native_lab.py").read_bytes(),
        "collect.sh": COLLECTOR,
    }
    capacity = project / "sdboot/cpu_capacity.py"
    if capacity.is_file():
        contents["m4rch-verify-capacity"] = capacity.read_bytes()
    port_map = out / "macos-port-map.json"
    if port_map.exists() or port_map.is_symlink():
        if port_map.is_symlink() or not port_map.is_file():
            raise ValueError("Mac port map must be a regular file")
        data = port_map.read_bytes()
        parsed = json.loads(data)
        if parsed.get("schema") != 1 or parsed.get("model") != "Mac16,8":
            raise ValueError("Mac port map is for a different target")
        contents["macos-port-map.json"] = data
    contents["HANDOVER.md"] = re.sub(
        rb"(?m)^kit=/boot/cpu-tools-[A-Za-z0-9]+$",
        b"kit=/boot/cpu-tools-ID", contents["HANDOVER.md"])
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    identity = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:12]
    # Resolve the delivered path after choosing the content identity. The
    # handover input participates in that identity; its rendered bytes are
    # covered by the final manifest and checksums.
    contents["HANDOVER.md"] = re.sub(
        rb"(?m)^kit=/boot/cpu-tools-[A-Za-z0-9]+$",
        ("kit=/boot/cpu-tools-" + identity).encode(), contents["HANDOVER.md"])
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    receipt = {"schema": 1, "kind": "j614s-cpu-experiment-tools", "identity": identity,
               "files": hashes, "kernel_changed": False, "enrollment_required": False}
    contents["manifest.json"] = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    contents["SHA256SUMS"] = "".join(
        hashlib.sha256(data).hexdigest() + "  " + name + "\n"
        for name, data in sorted(contents.items())).encode()
    out.mkdir(parents=True, exist_ok=True)
    destination = out / ("cpu-tools-" + identity)
    if destination.exists() or destination.is_symlink():
        if (destination.is_symlink() or not destination.is_dir() or
                {path.name for path in destination.iterdir()} != set(contents) or
                any((destination / name).is_symlink() or
                    not (destination / name).is_file() or
                    (destination / name).read_bytes() != data
                    for name, data in contents.items())):
            raise ValueError("Published CPU kit changed; preserve it and choose a different output root")
        return destination
    temporary = Path(tempfile.mkdtemp(prefix=".cpu-tools-", dir=out))
    try:
        for name, data in contents.items():
            path = temporary / name
            path.write_bytes(data)
            path.chmod(0o755 if name.startswith("m4rch-") or name in ("run.sh", "collect.sh") else 0o644)
        temporary.chmod(0o755)
        temporary.rename(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="output root, default out/sdboot")
    args = parser.parse_args()
    print(publish(out=args.out))


if __name__ == "__main__":
    main()
