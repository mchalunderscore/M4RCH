"""Build the fixed, separately enrolled m1n1/U-Boot object."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import struct
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib"))
import boot
from common import manifest_files, run, sha256, verify_manifest, write_json
from prepare_m1n1 import prepare as prepare_m1n1
from prepare_uboot import prepare as prepare_uboot

UBOOT = {"url": "https://github.com/AsahiLinux/u-boot.git", "revision": "8aa706b2daa49b64102e44067d8514de8a26dc42"}
NOIO_SHA = "7555aec41d86d6edb58a3e593199ed4b81b40be1316700c7c03ddf1d183963b5"


def validate_uboot_config(config, serial_makefile):
    """Check Kconfig's resolved result, including defaults absent from the recipe.

    This target deliberately has no UART mapping or driver. Requiring a serial
    console aborts before U-Boot can initialize its framebuffer console; enabling
    a UART instead would introduce unreviewed MMIO access.
    """
    settings = dict(line.split("=", 1) for line in config.read_text().splitlines()
                    if line.startswith("CONFIG_") and "=" in line)
    for symbol in ("SERIAL", "DM_SERIAL", "MMC_SDHCI_IO_ACCESSORS", "EFI_LOADER", "EFI_BINARY_EXEC",
                   "CMD_BOOTEFI", "CMD_BOOTEFI_BINARY", "EFI_VARIABLE_NO_STORE",
                   "EFI_PARTITION", "PARTITION_UUIDS", "OF_LIBFDT_OVERLAY",
                   "VIDEO", "VIDEO_SIMPLE", "VIDEO_ANSI", "DM_DEVICE_REMOVE"):
        if settings.get("CONFIG_" + symbol) != "y":
            raise ValueError(f"Fixed loader requires CONFIG_{symbol}=y")
    if settings.get("CONFIG_REQUIRE_SERIAL_CONSOLE", "n") != "n":
        raise ValueError("Framebuffer-only loader must disable CONFIG_REQUIRE_SERIAL_CONSOLE")
    if settings.get("CONFIG_PCI_INIT_R", "n") != "n":
        raise ValueError("Fixed loader must disable CONFIG_PCI_INIT_R until the console is ready")
    for symbol in ("MMC_WRITE", "MMC_HW_PARTITIONING", "MMC_SDHCI_SDMA",
                   "MMC_SDHCI_ADMA", "FAT_WRITE", "FAT_RENAME", "ENV_IS_IN_FAT",
                   "CMD_SAVEENV", "EFI_VARIABLE_FILE_STORE", "EFI_MM_COMM_TEE",
                   "EFI_BOOTMGR", "CMD_BOOTEFI_BOOTMGR", "EFI_CAPSULE_ON_DISK",
                   "EFI_RUNTIME_UPDATE_CAPSULE", "USB", "NVME", "IOMMU",
                   "MMC_UHS_SUPPORT", "MMC_HS200_SUPPORT", "MMC_HS400_SUPPORT",
                   "MMC_HS400_ES_SUPPORT"):
        if settings.get("CONFIG_" + symbol, "n") != "n":
            raise ValueError(f"Fixed UEFI bridge must disable CONFIG_{symbol}")
    # Derive the driver's configuration switches from the pinned upstream
    # Makefile rather than assuming S5P is the only driver a future config can
    # accidentally enable. PHASE_ is empty for this non-SPL U-Boot build.
    makefile = serial_makefile.read_text().replace("$(PHASE_)", "")
    drivers = re.findall(r"^obj-\$\((CONFIG_[A-Z0-9_]+)\)\s*\+=", makefile, re.M)
    if "CONFIG_S5P_SERIAL" not in drivers:
        raise ValueError("Pinned U-Boot serial driver list changed")
    enabled = sorted(name for name in set(drivers) if settings.get(name, "n") != "n")
    if enabled:
        raise ValueError("Fixed loader must not enable serial drivers: " + ", ".join(enabled))


def build_uboot(tree, jobs, env):
    run(["make", "apple_sdboot_defconfig"], cwd=tree, env=env)
    validate_uboot_config(tree / ".config", tree / "drivers/serial/Makefile")
    label = uboot_label(tree / "Makefile")
    run(["make", "UBOOTRELEASE=" + label, "LOCALVERSION=", "-j" + str(jobs)], cwd=tree, env=env)


def uboot_label(makefile):
    """Use U-Boot's pinned base version without Git or dirty suffixes."""
    text = Path(makefile).read_text()
    values = []
    for name in ("VERSION", "PATCHLEVEL", "SUBLEVEL"):
        matches = re.findall(r"^" + name + r"\s*=\s*([0-9]*)\s*$", text, re.MULTILINE)
        if len(matches) != 1 or (name != "SUBLEVEL" and not matches[0]):
            raise ValueError(f"Pinned U-Boot Makefile has no unambiguous {name}")
        if matches[0]:
            values.append(matches[0])
    return "u-boot-m4rch-" + ".".join(values)


def pack(prefix, dtb, uboot):
    if not prefix or len(prefix) % 16384:
        raise ValueError("m1n1 prefix must be 16 KiB aligned")
    if len(dtb) < 40 or struct.unpack_from(">II", dtb) != (0xd00dfeed, len(dtb)):
        raise ValueError("Invalid baseline DT")
    if len(uboot) < 64 or uboot[56:60] != b"ARM\x64":
        raise ValueError("U-Boot has no ARM64 Image header")
    offset, extent = struct.unpack_from("<QQ", uboot, 8)
    if offset or not len(uboot) <= extent <= 32 * 1024**2:
        raise ValueError("Invalid U-Boot memory footprint")
    result = prefix + dtb + uboot + bytes(extent - len(uboot))
    return result + bytes(-len(result) % 16384)


def inputs(project, lock, kernel_dir, *, nvme=False):
    names = ("loader.py", "prepare_m1n1.py", "prepare_uboot.py", "sd_pcie.h", "sd_pci_handoff.h", "gl9755.h", "gl9755_pci.h", "gl9755_card.h", "archsd.c", "uboot.config", "uboot-noio.patch")
    result = {"uboot": UBOOT, "source_date_epoch": lock["source_date_epoch"],
            "toolchain_recipe": sha256(project / "sdboot/Containerfile"),
            "hardware_helpers": sha256(project / "lib/boot.py"),
            "m1n1": {k: lock[k] for k in ("m1n1", "wallace", "m1n1_pcie", "m1n1_smp")},
            "baseline_dtb": sha256(kernel_dir / "boot/t6040-j614s.dtb"),
            "recipe": {n: sha256(project / "sdboot" / n) for n in names}}
    if nvme:
        import nvme_handoff
        result["nvme_handoff"] = nvme_handoff.inputs(project, lock)
        result["nvme_recipe"] = sha256(project / "lib/nvme_handoff.py")
    return result


def build(project, out, config, lock, kernel_dir, *, nvme=False):
    recipe = project / "sdboot"
    out.mkdir(parents=True, exist_ok=True)
    expected = inputs(project, lock, kernel_dir, nvme=nvme)
    manifest_path = out / "loader-manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text()).get("inputs") == expected:
        verify_manifest(manifest_path)
        print("Reusing verified fixed SD loader.")
        return
    directory = out / "loader"
    directory.mkdir(exist_ok=True)
    work = Path("/work/loader-nvme" if nvme else "/work/loader")
    work.mkdir(exist_ok=True)
    wallace = boot.checkout("wallace", lock["wallace"], work / "wallace")
    m1n1 = boot.checkout("m1n1", lock["m1n1"], work / "m1n1")
    uboot = boot.checkout("uboot", UBOOT, work / "uboot")
    for tree, revision in ((m1n1, lock["m1n1"]["revision"]), (uboot, UBOOT["revision"])):
        run(["git", "-C", tree, "reset", "--hard", revision])
    # The pinned patch adds this untracked file; reset does not remove it on
    # subsequent builds. Remove only our generated source, preserving objects.
    (uboot / "configs/apple_t6040_noio_defconfig").unlink(missing_ok=True)
    for patch in (wallace / "patches/m1n1-fb-console-always.patch", boot.pcie_patch(lock)):
        run(["git", "-C", m1n1, "apply", "--check", patch])
        run(["git", "-C", m1n1, "apply", patch])
    boot.apply_smp_patch(m1n1, lock["m1n1_smp"], boot.smp_patch(lock, "m1n1_smp"))
    prepare_m1n1(m1n1)
    if nvme:
        import nvme_handoff
        nvme_handoff.prepare(m1n1, wallace / "patches")
        nvme_handoff.prepare_uefi(m1n1)
    run(["git", "-C", m1n1, "submodule", "update", "--init", "--depth=1"])
    env = dict(os.environ, CARGO_HOME="/cache/cargo", SOURCE_DATE_EPOCH=str(lock["source_date_epoch"]),
               M1N1_VERSION_TAG=boot.M1N1_LABEL)
    if not shutil.which("magick"):
        bindir = work / "bin"
        bindir.mkdir(exist_ok=True)
        (bindir / "magick").write_text('#!/bin/sh\nexec convert "$@"\n')
        (bindir / "magick").chmod(0o755)
        env["PATH"] = str(bindir) + os.pathsep + env["PATH"]
    run(["make", "-j" + str(config["jobs"]), "BUILDSTD=1", "RELEASE=1", "EXTRA_CFLAGS=-DFB_CONSOLE_ALWAYS", "CARGO_FLAGS=-Z build-std=alloc,core --locked"], cwd=m1n1, env=env)
    boot.check_m1n1(m1n1 / "build/m1n1.bin")
    if nvme:
        nvme_handoff.check_binary(m1n1 / "build/m1n1.bin", uefi=True)
    if b"SDBOOT: J614s SD supply enabled" not in (m1n1 / "build/m1n1.bin").read_bytes():
        raise ValueError("SD power helper is missing from m1n1")
    patch = recipe / "uboot-noio.patch"
    if sha256(patch) != NOIO_SHA:
        raise ValueError("Wallace no-I/O patch checksum changed")
    run(["git", "-C", uboot, "apply", "--check", patch])
    run(["git", "-C", uboot, "apply", patch])
    prepare_uboot(uboot, recipe)
    build_uboot(uboot, config["jobs"], env)
    for source, name in ((m1n1 / "build/m1n1.bin", "m1n1.bin"),
                         (uboot / "u-boot-nodtb.bin", "u-boot-nodtb.bin"),
                         (uboot / "tools/mkimage", "mkimage"),
                         (uboot / ".config", ".config"),
                         (kernel_dir / "boot/t6040-j614s.dtb", "baseline.dtb")):
        shutil.copy2(source, directory / name)
    if inputs(project, lock, kernel_dir, nvme=nvme) != expected:
        raise ValueError("Loader sources changed during compilation; rerun make loader")
    data = pack(*[(directory / n).read_bytes() for n in ("m1n1.bin", "baseline.dtb", "u-boot-nodtb.bin")])
    temporary = out / ".loader.bin.partial"
    temporary.write_bytes(data)
    temporary.replace(out / "loader.bin")
    write_json(manifest_path, {"schema": 1, "kind": "j614s-sd-loader", "boot_protocol": "uefi-arm64", "inputs": expected,
                              "build_labels": {"m1n1": boot.M1N1_LABEL, "u-boot": uboot_label(uboot / "Makefile")},
                              "m1n1_upstream_base": boot.M1N1_BASE, "hardware_tested": False,
                              "files": manifest_files(out, ["loader.bin", *["loader/" + n for n in ("m1n1.bin", "baseline.dtb", "u-boot-nodtb.bin", "mkimage", ".config")]])})
