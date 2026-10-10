#!/usr/bin/env python3
"""Finish the private Wayland Mesa build interrupted by a machine reboot.

The caller must have established that the old compiler process is gone. This
preserves the incomplete command and log rather than assigning it an exit code.
Only compiler, installer-to-private-prefix and ELF inspection processes run.
"""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

KIT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("wayland_builder", KIT / "build_mesa_wayland.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
ROOT = builder.ROOT


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    dest = args.destination.resolve()
    dest.relative_to(ROOT / "out")
    if args.jobs < 1:
        parser.error("jobs must be positive")
    if (dest / "receipt.json").exists() or (dest / "resume-receipt.json").exists():
        parser.error("already resumed or completed; inspect the existing process handle")
    commands = json.loads((dest / "commands.json").read_text())
    if commands[-1]["phase"] != "compile" or "exit" in commands[-1]:
        parser.error("expected an interrupted compile entry")
    if any(item.get("exit") != 0 for item in commands[:-1]):
        parser.error("an earlier command did not complete successfully")
    archive_dir = dest / "interrupted-before-resume-v1"
    archive_dir.mkdir()
    for name in ("commands.json", "process.json", "logs/compile.log"):
        target = archive_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(dest / name, target)
    shutil.copyfile(KIT / "build_mesa_wayland.py", archive_dir / "build_mesa_wayland-present-at-resume.py")
    source, build, prefix = (dest / name for name in ("source", "build", "prefix"))
    protocol_source = dest / "wayland-protocols-1.41"
    protocol_prefix = dest / "protocols-prefix"
    previous = ROOT / "out/gpu-desktop-mesa-linked-v1"
    baseline_pins = {name: json.loads((dest / ("baseline-" + name + "-before.json")).read_text())["tree_sha256"]
                     for name in ("mesa-full", "mesa-build", "mesa-prefix")}
    source_manifest = json.loads((dest / "source-manifest.json").read_text())
    protocol_manifest = json.loads((dest / "protocols-source-manifest.json").read_text())
    prior_prefix = json.loads((dest / "prior-linked-prefix-before.json").read_text())
    selected = {rel: {"path": str(builder.SELECTED / rel), **builder.pin(builder.SELECTED / rel)}
                for rel in builder.METADATA}
    for name, expected in baseline_pins.items():
        if builder.manifest(builder.BASE / name)["tree_sha256"] != expected:
            raise RuntimeError("baseline changed before resume: " + name)
    for directory, manifest in ((source, source_manifest), (protocol_source, protocol_manifest),
                                (previous / "prefix", prior_prefix)):
        if builder.manifest(directory)["tree_sha256"] != manifest["tree_sha256"]:
            raise RuntimeError("saved input tree changed: " + str(directory))
    if not all(builder.pin(source / rel) == builder.pin(builder.SELECTED / rel) for rel in builder.METADATA):
        raise RuntimeError("staged selected metadata changed")
    options = {x["name"]: x["value"] for x in json.loads((build / "meson-info/intro-buildoptions.json").read_text())}
    if options["platforms"] != ["wayland"] or options["gallium-drivers"] != ["asahi"]:
        raise RuntimeError("saved platform/driver options differ")
    dependencies = json.loads((build / "meson-info/intro-dependencies.json").read_text())
    if not any(x.get("name") == "wayland-protocols" and x.get("version") == "1.41" for x in dependencies):
        raise RuntimeError("private protocol dependency differs")
    protocol_archive = dest / "wayland-protocols-1.41.tar.xz"
    if builder.pin(protocol_archive)["sha256"] != "2786b6b1b79965e313f2c289c12075b9ed700d41844810c51afda10ee329576b":
        raise RuntimeError("protocol archive differs from selected wrap")
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    receipt = {
        "schema": "m4rch.gpu-desktop-mesa-wayland.v1", "destination": str(dest), "status": "resuming",
        "started_utc": commands[0]["started_utc"], "resumed_utc": now(),
        "commands": commands, "requested_platforms": ["wayland"],
        "helper_present_at_resume": {"path": str(KIT / "build_mesa_wayland.py"), **builder.pin(KIT / "build_mesa_wayland.py"),
                                     "contemporaneous_initial_helper_pin_available": False},
        "resume_helper": {"path": str(Path(__file__).resolve()), **builder.pin(__file__)},
        "resume_invocation_argv": [str(Path(__file__).resolve())] + sys.argv[1:],
        "interruption": {"reason": "user reboot; original compile process terminated", "observed_after_boot_id": boot_id,
                         "original_terminal_exit_observed": False,
                         "original_process_record": str(archive_dir / "process.json"),
                         "original_commands": {"path": str(archive_dir / "commands.json"), **builder.pin(archive_dir / "commands.json")},
                         "original_compile_log": {"path": str(archive_dir / "logs/compile.log"), **builder.pin(archive_dir / "logs/compile.log")}},
        "baseline_tree_pins": baseline_pins, "source_tree_sha256": source_manifest["tree_sha256"],
        "selected_metadata": selected, "selected_metadata_pin_time": "resume; independently matches prebuild source manifest",
        "prior_linked_receipt": {"path": str(previous / "receipt.json"), **builder.pin(previous / "receipt.json"), "pin_time": "resume"},
        "prior_linked_prefix_tree_sha256": prior_prefix["tree_sha256"],
        "protocols_source_tree_sha256": protocol_manifest["tree_sha256"],
        "protocols_archive": {"path": str(protocol_archive), **builder.pin(protocol_archive),
                              "official_url": "https://gitlab.freedesktop.org/wayland/wayland-protocols/-/releases/1.41/downloads/wayland-protocols-1.41.tar.xz",
                              "selected_wrap": {"path": str(source / "subprojects/wayland-protocols.wrap"), **builder.pin(source / "subprojects/wayland-protocols.wrap")}},
        "wayland_dependency_evidence": [x for x in dependencies if x.get("name", "").startswith("wayland")],
        "t6040_normal_startup_enabled": False, "mesa_g16s_execution_enabled": False,
        "hardware_accessed": False, "harness_executed": False, "system_install": False, "protocols_system_install": False,
        "provenance_note": "Original builder receipt existed only in process memory. Saved manifests, commands and logs reconstruct these fields; original invocation and initial environment are not claimed.",
    }
    commands[-1]["interruption_observation"] = {"status": "interrupted-by-reboot", "terminal_exit_observed": False, "observed_utc": now()}
    environment = dict(os.environ)
    environment["PKG_CONFIG_PATH"] = str(protocol_prefix / "share/pkgconfig") + (os.pathsep + environment["PKG_CONFIG_PATH"] if environment.get("PKG_CONFIG_PATH") else "")
    receipt["effective_resume_build_environment"] = {key: environment[key] for key in
        ("CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS", "PKG_CONFIG_PATH", "LLVM_CONFIG") if key in environment}

    def checkpoint():
        builder.save(dest / "commands.json", commands)
        builder.save(dest / "resume-receipt.json", receipt)

    def run(name, argv):
        logfile = dest / "logs" / (name + ".log")
        item = {"phase": name, "argv": [str(x) for x in argv], "cwd": str(ROOT), "log": str(logfile), "started_utc": now()}
        commands.append(item)
        checkpoint()
        start = time.monotonic()
        with logfile.open("x") as output:
            process = subprocess.Popen(item["argv"], cwd=ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT)
            item["pid"] = process.pid
            builder.save(dest / "process.json", {"pid": os.getpid(), "child_pid": process.pid, "boot_id": boot_id, "phase": name, "log": str(logfile)})
            checkpoint()
            print(json.dumps({"phase": name, "pid": process.pid}), flush=True)
            code = process.wait()
        item.update(exit=code, elapsed_seconds=round(time.monotonic()-start, 3), log_sha256=builder.pin(logfile)["sha256"])
        checkpoint()
        print(json.dumps({"phase": name, "exit": code}), flush=True)
        if code:
            raise RuntimeError(f"{name} failed with exit {code}; see {logfile}")
        return logfile

    checkpoint()
    try:
        run("compile-resumed-v1", ["ninja", "-C", str(build), "-j", str(args.jobs)])
        run("install-private", ["meson", "install", "-C", str(build), "--no-rebuild"])
        artifacts = []
        paths = sorted(p for p in prefix.rglob("*") if p.is_file() and not p.is_symlink() and p.read_bytes()[:4] == b"\x7fELF")
        for i, artifact in enumerate(paths):
            log = run("elf-" + str(i), ["readelf", "-h", "-d", "-n", str(artifact)])
            artifacts.append({"path": str(artifact), **builder.pin(artifact), "elf_evidence": str(log),
                              "dynamic_entries": [line.strip() for line in log.read_text().splitlines() if any(x in line for x in ("(NEEDED)", "(SONAME)", "(RPATH)", "(RUNPATH)"))]})
        receipt["artifacts"] = artifacts
        run("harness-link", ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I" + str(source / "include"), "-I" + str(source / "include/drm-uapi"), "-I" + str(source / "src/asahi/lib"),
            "-I" + str(prefix / "include"), str(KIT / "headless-smoke.c"), "-L" + str(prefix / "lib"),
            "-Wl,-rpath," + str(prefix / "lib"), "-Wl,-z,defs", "-lgbm", "-lEGL", "-lGLESv2", "-ldrm", "-lm", "-o", str(dest / "headless-smoke")])
        receipt["harness"] = {"path": str(dest / "headless-smoke"), **builder.pin(dest / "headless-smoke"), "executed": False}
        receipt["protocols_config_pins"] = [{"path": str(p), **builder.pin(p)} for p in (
            dest / "protocols-build/meson-private/cmd_line.txt", dest / "protocols-build/meson-info/intro-buildoptions.json",
            dest / "protocols-build/build.ninja", protocol_prefix / "share/pkgconfig/wayland-protocols.pc")]
        receipt["compile_logs"] = [str(dest / "logs/compile.log"), str(dest / "logs/compile-resumed-v1.log")]
        receipt["status"] = "linked-preparation-only"
        receipt["finished_utc"] = now()
        checkpoint()
        builder.save(dest / "post-link.json", receipt)
        builder.save(dest / "process.json", {"phase": "linked-awaiting-finalizer", "status": receipt["status"]})
        print(json.dumps({"status": receipt["status"], "post_link": str(dest / "post-link.json")}), flush=True)
        return 0
    except Exception as exc:
        receipt.update(status="resume-failed", error=str(exc), finished_utc=now())
        checkpoint()
        builder.save(dest / "process.json", {"phase": "resume-failed", "error": str(exc)})
        print(str(exc), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
