#!/usr/bin/env python3
"""Compile and run the actual pure C core against RAM with ASan/UBSan."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCES = [HERE / "gfx-coordinate-core.h", HERE / "test-coordinate-core.c", Path(__file__).resolve()]
EVIDENCE = [ROOT / "docs/evidence/2026-10-09-gfx-native-shutdown-coordination.json",
            ROOT / "docs/evidence/2026-10-09-gfx-native-shutdown-coordination.md"]


def pin(path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "out/gfx-native-coordinate/core-qualification.json")
    args = parser.parse_args()
    compiler = shutil.which("clang")
    if compiler is None:
        raise SystemExit("clang is required for the offline ASan/UBSan qualification")
    inputs = [pin(path) for path in SOURCES + EVIDENCE]
    result = {"schema": "m4rch.gfx-coordinate-core-qualification.v1",
              "hardware_access": False, "privileged_access": False,
              "source_changes": False, "inputs": inputs,
              "compiler": compiler,
              "compiler_version": subprocess.check_output([compiler, "--version"], text=True).splitlines()[0],
              "sanitizers": ["address", "undefined"],
              "leak_detection": False,
              "leak_detection_limit": "LeakSanitizer cannot run under this host's ptrace restrictions; ASan memory checks and UBSan remain enabled.",
              "qualification_scope": "Actual C header, mocked RAM callbacks, deterministic ordered traces and meaningful failure paths.",
              "limitations": [
                  "The core does not perform physical target15/0 transitions; surrounding owner ordering is not tested by this RAM harness.",
                  "read_ptd must return the raw second PTD word; status bit54 from the native decoded Entry is intentionally not accepted.",
                  "A single serialized owner must use the session and shared request/voter resources; whole-word RMW is not atomic against another writer.",
                  "The request refresh preserves a preflight mutation, but an external update after the final snapshot can still be overwritten and evade post-ACK readback.",
                  "STATUS0 and all-ones rejection, sample cap, paced polling and exact readbacks are intentionally stricter than native behavior.",
                  "Native busy polling differs from the future experimental sleep callback; no GPU DMA retirement, hardware teardown or rendering proof follows."
              ]}
    with tempfile.TemporaryDirectory(prefix="gfx-coordinate-core-") as tmp:
        binary = Path(tmp) / "coordinate-core-test"
        command = [compiler, "-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                   "-fno-omit-frame-pointer", "-fsanitize=address,undefined",
                   str(HERE / "test-coordinate-core.c"), "-o", str(binary)]
        build = subprocess.run(command, text=True, capture_output=True)
        result["build"] = {"flags": command[1:command.index(str(HERE / "test-coordinate-core.c"))],
                           "returncode": build.returncode, "stdout": build.stdout, "stderr": build.stderr}
        if build.returncode == 0:
            env = os.environ.copy()
            env["ASAN_OPTIONS"] = "detect_leaks=0:halt_on_error=1:abort_on_error=1"
            env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
            run = subprocess.run([str(binary)], text=True, capture_output=True, env=env, timeout=60)
            result["run"] = {"returncode": run.returncode, "stdout": run.stdout, "stderr": run.stderr}
            if run.returncode == 0:
                result["tests"] = json.loads(run.stdout)
    result["source_hashes_unchanged_during_run"] = inputs == [pin(path) for path in SOURCES + EVIDENCE]
    result["passed"] = (result["build"]["returncode"] == 0 and
                        result.get("run", {}).get("returncode") == 0 and
                        result["source_hashes_unchanged_during_run"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "receipt": str(args.output),
                      "tests": result.get("tests"),
                      "receipt_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))
    if not result["passed"]:
        print(result["build"]["stderr"] + result.get("run", {}).get("stderr", ""))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
