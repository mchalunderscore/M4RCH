#!/usr/bin/env python3
"""Build selected Gravity Asahi Mesa offline into a new private prefix.

This runs compiler/code-generator processes only. It never loads the driver,
opens a render node, runs the linked harness, or installs system libraries.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[2]
BASE = ROOT / "out/gpu-native-20261006"
SELECTED = ROOT / "out/gpu-desktop-integration-v2/source/mesa"
METADATA = ("src/asahi/lib/agx_device.c", "src/asahi/lib/agx_g16_model.h")


def pin(path):
    data = Path(path).read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def manifest(root):
    rows = []
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            rows.append({"path": rel, "symlink": os.readlink(path)})
        elif path.is_file():
            rows.append({"path": rel, **pin(path)})
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return {"root": str(root), "files": len(rows),
            "tree_sha256": hashlib.sha256(encoded).hexdigest(), "entries": rows}


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", help="New directory under repository out/")
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    dest = Path(args.destination).resolve()
    dest.relative_to(ROOT / "out")
    if args.jobs < 1:
        parser.error("jobs must be positive")
    dest.mkdir(parents=True, exist_ok=False)
    (dest / "logs").mkdir()
    source, build, prefix = (dest / name for name in ("source", "build", "prefix"))
    commands = []
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt = {"schema": "m4rch.gpu-desktop-mesa-linked.v1", "started_utc": started,
               "destination": str(dest), "status": "running", "commands": commands,
               "helper": {"path": str(Path(__file__).resolve()), **pin(__file__)},
               "t6040_normal_startup_enabled": False,
               "mesa_g16s_execution_enabled": False, "hardware_accessed": False,
               "harness_executed": False, "system_install": False,
               "platform_limit": "Wayland protocols are not installed; uses prior GBM/surfaceless platform set"}
    save(dest / "process.json", {"pid": os.getpid(), "started_utc": started,
                                "phase": "source-staging"})

    def run(name, command, *, cwd=ROOT):
        logfile = dest / "logs" / (name + ".log")
        item = {"phase": name, "argv": [str(x) for x in command], "cwd": str(cwd),
                "log": str(logfile), "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        commands.append(item)
        save(dest / "commands.json", commands)
        print(json.dumps({"phase": name, "argv": item["argv"]}), flush=True)
        began = time.monotonic()
        with logfile.open("w") as log:
            process = subprocess.Popen(item["argv"], cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
            item["pid"] = process.pid
            save(dest / "process.json", {"pid": os.getpid(), "child_pid": process.pid,
                                        "phase": name, "log": str(logfile)})
            code = process.wait()
        item.update(exit=code, elapsed_seconds=round(time.monotonic() - began, 3),
                    log_sha256=pin(logfile)["sha256"])
        save(dest / "commands.json", commands)
        print(json.dumps({"phase": name, "exit": code, "seconds": item["elapsed_seconds"]}), flush=True)
        if code:
            raise RuntimeError(f"{name} failed with exit {code}; see {logfile}")
        return logfile

    try:
        baselines = {}
        for name in ("mesa-full", "mesa-build", "mesa-prefix"):
            value = manifest(BASE / name)
            save(dest / ("baseline-" + name + "-before.json"), value)
            baselines[name] = value["tree_sha256"]
        receipt["baseline_tree_pins"] = baselines
        selected = {rel: {"path": str(SELECTED / rel), **pin(SELECTED / rel)} for rel in METADATA}
        receipt["selected_metadata"] = selected
        shutil.copytree(BASE / "mesa-full", source, symlinks=True)
        for rel in METADATA:
            shutil.copyfile(SELECTED / rel, source / rel)
            if pin(source / rel) != pin(SELECTED / rel):
                raise RuntimeError("selected metadata copy differs: " + rel)
        staged = manifest(source)
        save(dest / "source-manifest.json", staged)
        receipt["source_tree_sha256"] = staged["tree_sha256"]
        receipt["environment"] = {k: os.environ[k] for k in
            ("CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS", "PKG_CONFIG_PATH", "LLVM_CONFIG")
            if k in os.environ}
        for tool in ("meson", "ninja", "cc", "c++", "python3", "llvm-config", "readelf"):
            run("tool-" + tool.replace("+", "p"), [tool, "--version"])
        run("wayland-dependency", ["python3", "-c",
            "import subprocess; p=subprocess.run(['pkg-config','--modversion','wayland-protocols']); print('pkg_config_exit='+str(p.returncode))"])
        configure = ["meson", "setup", str(build), str(source), "--wrap-mode=nofallback",
                     "--prefix=" + str(prefix), "--libdir=lib", "-Dbuildtype=debugoptimized",
                     "-Dgallium-drivers=asahi", "-Dvulkan-drivers=[]", "-Dplatforms=[]",
                     "-Dllvm=enabled", "-Dglx=disabled", "-Degl=enabled", "-Dgbm=enabled",
                     "-Dtools=drm-shim"]
        run("configure", configure)
        run("compile", ["ninja", "-C", str(build), "-j", str(args.jobs)])
        run("install-private", ["meson", "install", "-C", str(build), "--no-rebuild"])
        artifact_paths = sorted(p for p in prefix.rglob("*")
                                if p.is_file() and not p.is_symlink() and p.read_bytes()[:4] == b"\x7fELF")
        artifacts = []
        for i, artifact in enumerate(artifact_paths):
            log = run("elf-" + str(i), ["readelf", "-h", "-d", "-n", str(artifact)])
            text = log.read_text()
            artifacts.append({"path": str(artifact), **pin(artifact), "elf_evidence": str(log),
                              "dynamic_entries": [line.strip() for line in text.splitlines()
                                                  if any(s in line for s in ("(NEEDED)", "(SONAME)", "(RPATH)", "(RUNPATH)"))]})
        receipt["artifacts"] = artifacts
        run("harness-link", ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I" + str(source / "include"), "-I" + str(source / "include/drm-uapi"),
            "-I" + str(source / "src/asahi/lib"),
            "-I" + str(prefix / "include"), str(KIT / "headless-smoke.c"),
            "-L" + str(prefix / "lib"), "-Wl,-rpath," + str(prefix / "lib"),
            "-Wl,-z,defs", "-lgbm", "-lEGL", "-lGLESv2", "-ldrm", "-lm",
            "-o", str(dest / "headless-smoke")])
        log = run("harness-elf", ["readelf", "-h", "-d", "-n", str(dest / "headless-smoke")])
        receipt["harness"] = {"path": str(dest / "headless-smoke"), **pin(dest / "headless-smoke"),
                              "elf_evidence": str(log), "executed": False}
        preserved = {}
        for name, before in baselines.items():
            after = manifest(BASE / name)
            preserved[name] = after["tree_sha256"] == before
        receipt["baseline_preserved"] = preserved
        receipt["selected_metadata_preserved"] = all(pin(SELECTED / rel) == {k: v for k, v in selected[rel].items() if k != "path"} for rel in METADATA)
        if not all(preserved.values()) or not receipt["selected_metadata_preserved"]:
            raise RuntimeError("input preservation check failed")
        receipt["status"] = "linked-preparation-only"
        receipt["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save(dest / "receipt.json", receipt)
        save(dest / "process.json", {"pid": os.getpid(), "phase": "complete", "status": receipt["status"]})
        print(json.dumps({"status": receipt["status"], "artifacts": len(artifacts), "receipt": str(dest / "receipt.json")}), flush=True)
        return 0
    except Exception as exc:
        receipt.update(status="failed", error=str(exc), finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save(dest / "failure.json", receipt)
        print(str(exc), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
