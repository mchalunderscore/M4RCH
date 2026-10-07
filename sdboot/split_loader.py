"""Build the enrolled chainloader and its independently replaceable ESP image."""
from pathlib import Path
import gzip
import os
import shutil
import boot
import loader
import nvme_handoff
from common import run, sha256, manifest_files, verify_manifest, write_json

ESP_UUID = "5fdb35c6-3a66-416d-8358-6555fd99fcc5"


def stage1_payload(prefix):
    if not prefix or len(prefix) % 16384:
        raise ValueError("Stage 1 prefix must be 16 KiB aligned")
    variables = (f"chainload={ESP_UUID};boot.bin\n"
                 f"chosen.asahi,efi-system-partition={ESP_UUID}\n").encode()
    data = prefix + variables + bytes(4)
    return data + bytes((-len(data)) % 16384)


def stage2_payload(directory):
    # A compressed Image is self-delimiting: stage 1 appends chosen variables
    # after it, which stage 2 must parse rather than stopping at raw Image data.
    prefix = (directory / "m1n1.bin").read_bytes()
    dtb = (directory / "baseline.dtb").read_bytes()
    image = (directory / "u-boot-nodtb.bin").read_bytes()
    loader.pack(prefix, dtb, image)  # Validate each component's existing contract.
    return prefix + dtb + gzip.compress(image, compresslevel=9, mtime=0)


def build(project, out, config, lock, kernel_dir):
    loader.build(project, out / "internal-loader", config, lock, kernel_dir,
                 nvme=True, internal=True)
    verified = verify_manifest(out / "internal-loader/loader-manifest.json")
    target = out / "split-loader"
    target.mkdir(exist_ok=True)
    inputs = {"stage2": verified["files"], "recipe": sha256(Path(__file__)),
              "loader_recipe": sha256(project / "sdboot/loader.py"),
              "nvme_handoff": nvme_handoff.inputs(project, lock), "esp_partuuid": ESP_UUID}
    manifest = target / "loader-manifest.json"
    if manifest.exists() and verify_manifest(manifest).get("inputs") == inputs:
        print("Reusing verified split loader.")
        return
    work = Path("/work/loader-stage1")
    m1n1 = boot.checkout("m1n1", lock["m1n1"], work / "m1n1")
    wallace = boot.checkout("wallace", lock["wallace"], work / "wallace")
    run(["git", "-C", m1n1, "reset", "--hard", lock["m1n1"]["revision"]])
    for patch in (wallace / "patches/m1n1-fb-console-always.patch", boot.pcie_patch(lock)):
        run(["git", "-C", m1n1, "apply", "--check", patch])
        run(["git", "-C", m1n1, "apply", patch])
    boot.apply_smp_patch(m1n1, lock["m1n1_smp"], boot.smp_patch(lock, "m1n1_smp"))
    nvme_handoff.prepare(m1n1, wallace / "patches")
    loader.bounded_nvme_shutdown(m1n1)
    # CHAINLOADING enables upstream's optional USB proxy window by default.
    # Keep the same direct, untethered startup contract as the working loader.
    header = m1n1 / "config.h"
    header.write_text(header.read_text() + "\n#undef EARLY_PROXY_TIMEOUT\n")
    run(["git", "-C", m1n1, "submodule", "update", "--init", "--depth=1"])
    env = dict(os.environ, CARGO_HOME="/cache/cargo",
               SOURCE_DATE_EPOCH=str(lock["source_date_epoch"]), M1N1_VERSION_TAG=boot.M1N1_LABEL)
    if not shutil.which("magick"):
        bindir = work / "bin"; bindir.mkdir(exist_ok=True)
        (bindir / "magick").write_text('#!/bin/sh\nexec convert "$@"\n')
        (bindir / "magick").chmod(0o755)
        env["PATH"] = str(bindir) + os.pathsep + env["PATH"]
    run(["make", "-j" + str(config["jobs"]), "CHAINLOADING=1", "BUILDSTD=1", "RELEASE=1",
         "EXTRA_CFLAGS=-DFB_CONSOLE_ALWAYS", "CARGO_FLAGS=-Z build-std=alloc,core --locked --features chainload"],
        cwd=m1n1, env=env)
    binary = m1n1 / "build/m1n1.bin"
    boot.check_m1n1(binary)
    if b"Chainloading " not in binary.read_bytes():
        raise ValueError("Stage 1 lacks the Rust file chainloader")
    (target / "loader.bin").write_bytes(stage1_payload(binary.read_bytes()))
    (target / "boot.bin").write_bytes(stage2_payload(out / "internal-loader/loader"))
    write_json(manifest, {"schema": 1, "kind": "j614s-stage1-loader", "boot_protocol": "m1n1-chainload",
                         "inputs": inputs, "stage2_path": "boot.bin", "hardware_tested": False,
                         "files": manifest_files(target, ["loader.bin", "boot.bin"])})
