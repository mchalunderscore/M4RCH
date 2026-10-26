#!/usr/bin/env python3
"""Small offline module/header/criteria qualification; never run the EGL harness."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from stage import KIT, ROOT, pin, stage

def qualify(staging, output):
    staging = Path(staging).resolve()
    output = Path(output).resolve()
    staging.relative_to(ROOT / "out")
    output.relative_to(ROOT / "out")
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema": "m4rch.gpu-desktop-integration-qualification.v1",
              "passed": False, "hardware_reads_or_controls": False,
              "full_kernel_or_mesa_build": False, "egl_harness_executed": False,
              "commands": [], "input_pins": []}
    def command(argv, name, environment=None):
        result = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, timeout=60,
                                env=None if environment is None else {**os.environ, **environment})
        (output / (name + ".stdout")).write_text(result.stdout)
        (output / (name + ".stderr")).write_text(result.stderr)
        report["commands"].append({"argv": argv, "exit": result.returncode,
                                   "environment_overrides": environment or {},
                                   "stdout": pin(output / (name + ".stdout")),
                                   "stderr": pin(output / (name + ".stderr"))})
        if result.returncode:
            raise RuntimeError(name + " failed")
        return result.stdout
    try:
        manifest = json.loads((KIT / "base-inputs.json").read_text())
        for item in manifest["input_pins"]:
            actual = pin(item["path"])
            if actual["sha256"] != item["sha256"] or actual["bytes"] != item["bytes"]:
                raise ValueError("Frozen source changed: " + item["path"])
        replay = stage(output / "patch-replay")
        for item in replay["output_pins"]:
            selected = pin(staging / "source" / item["family"] / item["relative_path"])
            if selected["sha256"] != item["sha256"]:
                raise ValueError("Selected source differs from reproducible patch: " + selected["path"])
            report["input_pins"].append(selected)
        report["patch_replay_exact"] = True
        kernel = staging / "source/linux/drivers/gpu/drm/asahi"
        mesa = staging / "source/mesa/src/asahi/lib"
        tests = output / "profile-tests.rs"
        tests.write_text("#[path=" + json.dumps(str(kernel / "g16_profile.rs")) + "] mod profile;\n" +
                         "include!(" + json.dumps(str(KIT / "topology-tests.rs")) + ");\n")
        command(["rustc", "--edition=2021", "--test", str(tests), "-o", str(output / "profile-tests")], "rust-build")
        rust = command([str(output / "profile-tests"), "--nocapture"], "rust-run")
        report["rust_tests"] = int(re.search(r"test result: ok\. (\d+) passed", rust).group(1))
        includes = ["-I" + str(mesa), "-I" + str(KIT)]
        cflags = ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-g", "-O1",
                  "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        command(cflags + includes + [str(KIT / "mesa-topology-tests.c"), "-o", str(output / "mesa-topology-tests")], "mesa-pure-build")
        sanitizer_environment = {"ASAN_OPTIONS": "detect_leaks=0:halt_on_error=1"}
        report["leak_sanitizer"] = "Disabled: thread inspection is unsupported in this execution environment. Pure header/criteria tests do not allocate heap storage; address/undefined checks remain enabled."
        c = command([str(output / "mesa-topology-tests")], "mesa-pure-run", sanitizer_environment)
        report["mesa_assertions"] = int(re.search(r"Mesa topology assertions: (\d+)", c).group(1))
        expected = "BIND,16,24640,83,1,2,10,16,987,987"
        if re.findall(r"BIND,[0-9,]+", rust) != [expected] or re.findall(r"BIND,[0-9,]+", c) != [expected]:
            raise ValueError("Kernel/Mesa J614s topology does not match independently expected identity")
        report["canonical_kernel_mesa_topology_match"] = expected
        command(cflags + includes + [str(KIT / "smoke-criteria-tests.c"), "-o", str(output / "smoke-criteria-tests")], "criteria-build")
        criteria = command([str(output / "smoke-criteria-tests")], "criteria-run", sanitizer_environment)
        report["smoke_criteria_assertions"] = int(re.search(r"Smoke criteria assertions: (\d+)", criteria).group(1))
        flags = shlex.split(command(["pkg-config", "--cflags", "--libs", "egl", "glesv2", "gbm", "libdrm"], "smoke-flags"))
        command(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-g"] + includes +
                ["-I" + str(staging / "source/linux/include/uapi/drm"), str(KIT / "headless-smoke.c"),
                 "-o", str(output / "headless-smoke")] + flags, "smoke-link-only")
        # Validate the actual caller chain and preserve both execution gates.
        probe = (kernel / "asahi_m4.rs").read_text()
        drm = (kernel / "g16_drm.rs").read_text()
        runtime = (kernel / "g16.rs").read_text()
        platform = (kernel / "g16_platform.rs").read_text()
        profile = (kernel / "g16_profile.rs").read_text()
        device = (mesa / "agx_device.c").read_text()
        checks = {
            "probe_passes_selected_profile": "g16_drm::register(pdev, metadata)?" in probe,
            "drm_passes_profile_to_runtime": "Bootstrap::new(pdev, profile)?" in drm,
            "runtime_passes_profile_to_platform": "Platform::new(pdev.as_ref(), profile)?" in runtime,
            "platform_guard_before_device_inputs": platform.index("profile.initialization().ok_or(ENOTSUPP)?") < platform.index("dev.of_node()"),
            "runtime_guard_before_boot_resources": runtime.index("profile.initialization().ok_or(ENOTSUPP)?") < runtime.index("validate_boot_resources(pdev)?", runtime.index("impl Bootstrap")),
            "drm_guard_before_dma_setup": drm.index("profile.initialization().ok_or(ENOTSUPP)?") < drm.index("pdev.dma_set_mask_and_coherent"),
            "all_identity_fields_bound": all("device.topology." + name in drm for name in ["generation", "variant", "chip", "dies", "clusters", "slots_per_cluster", "core_masks"]),
            "t6040_startup_flag_stays_false": "normal_startup_implemented: false" in profile,
            "mesa_decodes_before_vm_creation": device.index("agx_g16_decode_device(") < device.index("DRM_IOCTL_ASAHI_VM_CREATE"),
            "mesa_refuses_layout_before_vm_creation": device.index("if (!agx_g16_layout_qualified(g16_model))") < device.index("DRM_IOCTL_ASAHI_VM_CREATE"),
        }
        if not all(checks.values()):
            raise ValueError("Caller/gate invariant failed: " + str(checks))
        report["source_invariants"] = checks
        for item in manifest["input_pins"]:
            actual = pin(item["path"])
            if actual["sha256"] != item["sha256"]:
                raise ValueError("Frozen source changed during qualification")
            report["input_pins"].append(actual)
        report["frozen_sources_unchanged"] = True
        for path in sorted(KIT.iterdir()):
            if path.is_file():
                report["input_pins"].append(pin(path))
        report["smoke_binary"] = pin(output / "headless-smoke")
        report["limitations"] = ["Pure profile/header and acceptance criteria were exercised; the full kernel module and Mesa were not compiled.",
                                  "The EGL/GBM harness was linked but not executed. No hardware renderer/fence/pixels or desktop presentation are qualified.",
                                  "T6040 initialization and G16S firmware/scene/shader layout gates remain closed."]
        report["passed"] = True
    except Exception as error:
        report["error"] = str(error)
    with (output / "qualification.json").open("x") as file:
        json.dump(report, file, indent=2); file.write("\n")
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("staging")
    parser.add_argument("output", help="New immutable qualification output directory")
    args = parser.parse_args()
    result = qualify(args.staging, args.output)
    print(json.dumps({key: result.get(key) for key in ["passed", "rust_tests", "mesa_assertions", "smoke_criteria_assertions", "error"]}))
    sys.exit(0 if result["passed"] else 1)
