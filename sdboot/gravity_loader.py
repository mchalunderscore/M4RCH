"""Build a Gravity-based stage 2 without replacing the enrolled stage 1."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import boot
import loader
import nvme_handoff
from common import run, sha256, manifest_files, verify_manifest, write_json
from prepare_nvme_uboot import validate_power_map
from split_loader import ESP_UUID, stage2_payload


def profile_inputs(project):
    profile = json.loads((project / "profiles/gravity-loader.json").read_text())
    for spec in profile["sources"].values():
        if sha256(project / spec["patch"]) != spec["patch_sha256"]:
            raise ValueError("Gravity loader patch checksum differs: " + spec["patch"])
    return profile


def prepare_tree(project, name, spec, work):
    tree = boot.checkout("gravity-" + name, spec, work / name)
    run(["git", "-C", tree, "reset", "--hard", spec["revision"]])
    # Only remove generated files enumerated by this reviewed patch.
    for relative in spec["added_files"]:
        (tree / relative).unlink(missing_ok=True)
    patch = project / spec["patch"]
    run(["git", "-C", tree, "apply", "--check", patch])
    run(["git", "-C", tree, "apply", patch])
    for relative, digest in spec["result_files"].items():
        if sha256(tree / relative) != digest:
            raise ValueError("Gravity source result differs: " + relative)
    return tree


def build(project, out, config, lock, kernel_dir):
    profile = profile_inputs(project)
    proven = verify_manifest(out / "split-loader/loader-manifest.json")
    verify_manifest(out / "internal-loader/loader-manifest.json")
    if proven["inputs"]["esp_partuuid"] != ESP_UUID:
        raise ValueError("Existing split-loader ESP identity differs")
    target = out / "gravity-loader"
    target.mkdir(exist_ok=True)
    baseline = out / "internal-loader/loader/baseline.dtb"
    validate_power_map(baseline)
    inputs = {"profile": profile, "esp_partuuid": ESP_UUID,
              "stage1_sha256": sha256(out / "split-loader/loader.bin"),
              "baseline_dtb": sha256(baseline),
              "recipe": sha256(Path(__file__)),
              "handover": sha256(project / "HANDOVER.md"),
              "collector": sha256(project / "tools/boot/collect-alignment.sh"),
              "hardware_helpers": sha256(project / "lib/boot.py"),
              "container_recipe": sha256(project / "sdboot/Containerfile"),
              "validation_recipe": sha256(project / "sdboot/loader.py"),
              "packing_recipe": sha256(project / "sdboot/split_loader.py")}
    manifest = target / "loader-manifest.json"
    if manifest.exists() and verify_manifest(manifest).get("inputs") == inputs:
        print("Reusing verified Gravity stage 2.")
        return
    work = Path("/work/loader-gravity")
    work.mkdir(exist_ok=True)
    m1n1 = prepare_tree(project, "m1n1", profile["sources"]["m1n1"], work)
    uboot = prepare_tree(project, "uboot", profile["sources"]["uboot"], work)
    run(["git", "-C", m1n1, "submodule", "update", "--init", "--depth=1"])
    env = dict(os.environ, CARGO_HOME="/cache/cargo", SOURCE_DATE_EPOCH=str(lock["source_date_epoch"]),
               M1N1_VERSION_TAG=boot.M1N1_LABEL)
    if not shutil.which("magick"):
        bindir = work / "bin"; bindir.mkdir(exist_ok=True)
        (bindir / "magick").write_text('#!/bin/sh\nexec convert "$@"\n')
        (bindir / "magick").chmod(0o755)
        env["PATH"] = str(bindir) + os.pathsep + env["PATH"]
    run(["make", "-j" + str(config["jobs"]), "BUILDSTD=1", "RELEASE=1",
         "EXTRA_CFLAGS=-DFB_CONSOLE_ALWAYS", "CARGO_FLAGS=-Z build-std=alloc,core --locked"], cwd=m1n1, env=env)
    boot.check_m1n1(m1n1 / "build/m1n1.bin", ctrr_error=b"FDT: Could not reserve CTRR range")
    nvme_handoff.check_binary(m1n1 / "build/m1n1.bin", uefi=True)
    loader.build_uboot(uboot, config["jobs"], env, internal=True)
    components = target / "loader"; components.mkdir(exist_ok=True)
    for source, name in ((m1n1 / "build/m1n1.bin", "m1n1.bin"),
                         (uboot / "u-boot-nodtb.bin", "u-boot-nodtb.bin"),
                         (uboot / ".config", ".config"), (baseline, "baseline.dtb")):
        shutil.copyfile(source, components / name)
    if inputs["profile"] != profile_inputs(project):
        raise ValueError("Gravity profile changed during compilation")
    (target / "boot.bin").write_bytes(stage2_payload(components))
    shutil.copyfile(project / "HANDOVER.md", target / "HANDOVER.md")
    shutil.copyfile(project / "tools/boot/collect-alignment.sh", target / "collect.sh")
    shutil.copyfile(project / "profiles/gravity-loader.json", target / "profile.json")
    write_json(manifest, {"schema": 1, "kind": "j614s-gravity-stage2", "stage2_path": "boot.bin",
                         "boot_protocol": "m1n1-chainload", "inputs": inputs, "hardware_tested": False,
                         "build_labels": {"m1n1": boot.M1N1_LABEL, "u-boot": loader.uboot_label(uboot / "Makefile")},
                         "files": manifest_files(target, ["boot.bin", "HANDOVER.md", "collect.sh", "profile.json", *["loader/" + n for n in
                                  ("m1n1.bin", "u-boot-nodtb.bin", ".config", "baseline.dtb")]])})
    print("Built Gravity stage 2:", target / "boot.bin")
