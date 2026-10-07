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


def validate_uboot_config(config, serial_makefile, *, internal=False):
    """Check Kconfig's resolved result, including defaults absent from the recipe.

    This target deliberately has no UART mapping or driver. Requiring a serial
    console aborts before U-Boot can initialize its framebuffer console; enabling
    a UART instead would introduce unreviewed MMIO access.
    """
    settings = dict(line.split("=", 1) for line in config.read_text().splitlines()
                    if line.startswith("CONFIG_") and "=" in line)
    for symbol in ("SERIAL", "DM_SERIAL", "EFI_LOADER", "EFI_BINARY_EXEC",
                   "CMD_BOOTEFI", "CMD_BOOTEFI_BINARY", "EFI_VARIABLE_NO_STORE",
                   "EFI_PARTITION", "PARTITION_UUIDS", "OF_LIBFDT_OVERLAY",
                   "VIDEO", "VIDEO_SIMPLE", "VIDEO_ANSI", "DM_DEVICE_REMOVE"):
        if settings.get("CONFIG_" + symbol) != "y":
            raise ValueError(f"Fixed loader requires CONFIG_{symbol}=y")
    for symbol in (("NVME", "NVME_APPLE", "DM_MAILBOX", "APPLE_MBOX", "DM_RESET", "POWER_DOMAIN", "APPLE_PMGR_POWER_DOMAIN", "PARTITION_TYPE_GUID") if internal else ("MMC_SDHCI_IO_ACCESSORS",)):
        if settings.get("CONFIG_" + symbol) != "y":
            raise ValueError(f"Loader requires CONFIG_{symbol}=y")
    if internal:
        for symbol in ("PCI", "MMC", "USB", "NVME_PCI"):
            if settings.get("CONFIG_" + symbol, "n") != "n":
                raise ValueError(f"Internal loader must disable CONFIG_{symbol}")
    if settings.get("CONFIG_REQUIRE_SERIAL_CONSOLE", "n") != "n":
        raise ValueError("Framebuffer-only loader must disable CONFIG_REQUIRE_SERIAL_CONSOLE")
    if settings.get("CONFIG_PCI_INIT_R", "n") != "n":
        raise ValueError("Fixed loader must disable CONFIG_PCI_INIT_R until the console is ready")
    for symbol in ("MMC_WRITE", "MMC_HW_PARTITIONING", "MMC_SDHCI_SDMA",
                   "MMC_SDHCI_ADMA", "FAT_WRITE", "FAT_RENAME", "ENV_IS_IN_FAT",
                   "CMD_SAVEENV", "EFI_VARIABLE_FILE_STORE", "EFI_MM_COMM_TEE",
                   "EFI_BOOTMGR", "CMD_BOOTEFI_BOOTMGR", "EFI_CAPSULE_ON_DISK",
                   "EFI_RUNTIME_UPDATE_CAPSULE", "USB", "IOMMU",
                   "MMC_UHS_SUPPORT", "MMC_HS200_SUPPORT", "MMC_HS400_SUPPORT",
                   "MMC_HS400_ES_SUPPORT"):
        if settings.get("CONFIG_" + symbol, "n") != "n":
            raise ValueError(f"Fixed UEFI bridge must disable CONFIG_{symbol}")
    if not internal and settings.get("CONFIG_NVME", "n") != "n":
        raise ValueError("SD loader must disable CONFIG_NVME")
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


def build_uboot(tree, jobs, env, *, internal=False):
    run(["make", "apple_sdboot_defconfig"], cwd=tree, env=env)
    validate_uboot_config(tree / ".config", tree / "drivers/serial/Makefile", internal=internal)
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


def inputs(project, lock, kernel_dir, *, nvme=False, internal=False):
    names = ("loader.py", "prepare_m1n1.py", "prepare_uboot.py", "sd_pcie.h", "sd_pci_handoff.h", "gl9755.h", "gl9755_pci.h", "gl9755_card.h", "archsd.c", "uboot.config", "uboot-noio.patch")
    result = {"uboot": UBOOT, "source_date_epoch": lock["source_date_epoch"],
            "toolchain_recipe": sha256(project / "sdboot/Containerfile"),
            "hardware_helpers": sha256(project / "lib/boot.py"),
            "m1n1": {k: lock[k] for k in ("m1n1", "wallace", "m1n1_pcie", "m1n1_smp")},
            "baseline_dtb": sha256(kernel_dir / "boot/t6040-j614s.dtb"),
            "recipe": {n: sha256(project / "sdboot" / n) for n in names}}
    if internal:
        result["internal_recipe"] = {n: sha256(project / "sdboot" / n) for n in ("prepare_nvme_uboot.py", "archnvme.c", "uboot-nvme.config", "uboot-nvme-sources.json")}
        result["internal_patches"] = {s["file"]: sha256(project / "patches" / s["file"]) for s in json.loads((project / "sdboot/uboot-nvme-sources.json").read_text())}
    if nvme:
        import nvme_handoff
        result["nvme_handoff"] = nvme_handoff.inputs(project, lock)
        result["nvme_recipe"] = sha256(project / "lib/nvme_handoff.py")
    return result



def trace_nvme_handoff(tree):
    """Keep a visible breadcrumb before each checked shutdown operation."""
    path = tree / "src/nvme.c"
    source = path.read_text()
    start = source.index("static bool nvme_shutdown_checked(void)")
    end = source.index("\nbool nvme_prepare_handoff(void)", start)
    body = source[start:end]
    for anchor, label in (
        ("    cmd.opcode = NVME_ADMIN_CMD_DELETE_SQ;", "delete I/O SQ"),
        ("    cmd.opcode = NVME_ADMIN_CMD_DELETE_CQ;", "delete I/O CQ"),
        ("    if (!nvme_ctrl_shutdown()) {", "controller shutdown"),
        ("    if (!nvme_ctrl_disable()) {", "controller disable"),
        ("    if (!rtkit_sleep_checked(nvme_rtkit)) {", "RTKit sleep"),
        ('    int ans_reset = pmgr_reset(nvme_die, "ANS");', "ANS power-domain reset"),
        ("    rtkit_free(nvme_rtkit);", "release stopped firmware buffers"),
    ):
        if body.count(anchor) != 1:
            raise ValueError("NVMe handoff trace anchor changed: " + anchor)
        body = body.replace(anchor, '    printf("M4RCH ANS handoff: ' + label + '\\n");\n' + anchor)
    path.write_text(source[:start] + body + source[end:])



def trace_next_stage_cleanup(tree):
    """Internal diagnostic: preserve the final pre-U-Boot cleanup messages."""
    path = tree / "src/main.c"
    source = path.read_text()
    start = source.index('    printf("Preparing to run next stage at ')
    prefix, source = source[:start], source[start:]
    for anchor, label in (
        ("    nvme_shutdown();", "confirm ANS stopped"),
        ("    exception_shutdown();", "exception cleanup"),
        ("    usb_iodev_shutdown();", "USB iodev cleanup"),
        ("    display_shutdown(DCP_SLEEP_IF_EXTERNAL);", "display cleanup"),
        ("    fb_shutdown(next_stage.restore_logo);", "framebuffer release; MMU teardown and branch next"),
    ):
        if source.count(anchor) != 1:
            raise ValueError("Pinned next-stage cleanup changed: " + anchor)
        source = source.replace(anchor, '    printf("M4RCH next stage: ' + label + '\\n");\n' + anchor)
    path.write_text(prefix + source)
    path = tree / "src/fb.c"
    source = path.read_text()
    anchor = "    console.active = false;\n    fb_clear_console();"
    if source.count(anchor) != 1:
        raise ValueError("Pinned framebuffer shutdown changed")
    # Release buffers normally, but keep pixels visible when not restoring
    # Apple's logo. This does not leave the console or its allocation active.
    path.write_text(source.replace(anchor, "    console.active = false;\n    if (restore_logo)\n        fb_clear_console();"))


def bounded_nvme_shutdown(tree):
    """Service one RTKit message per SHST check, retaining shutdown guards.

    A register-only wait stalled at SHST=1 on hardware. Firmware may need its
    logging/management acknowledgements to progress. The ordinary recv drains
    indefinitely under a message flood; a dedicated one-message entry point
    lets us recheck the deadline between handlers. ASC sends already have a
    200 ms timeout, so a handler can extend the overall deadline slightly.
    Other RTKit callers retain their original receive behavior.
    """
    rtkit = tree / "src/rtkit.c"
    original = rtkit.read_text()
    signature = "int rtkit_recv(rtkit_dev_t *rtk, struct rtkit_message *msg)"
    start = original.index(signature)
    end = original.index("\nbool rtkit_start_ep(", start)
    body = original[start:end]
    anchor = "    while (asc_recv(rtk->asc, &asc_msg)) {"
    if body.count(anchor) != 1:
        raise ValueError("Pinned RTKit receive loop changed")
    body = body.replace(signature, "static int rtkit_recv_limit(rtkit_dev_t *rtk, struct rtkit_message *msg, unsigned budget)")
    body = body.replace(anchor, "    while (budget && asc_recv(rtk->asc, &asc_msg)) {\n        budget--;")
    body += "\n" + signature + "\n{\n    return rtkit_recv_limit(rtk, msg, ~0u);\n}\n"
    body += "\nint rtkit_recv_one(rtkit_dev_t *rtk, struct rtkit_message *msg)\n{\n    return rtkit_recv_limit(rtk, msg, 1);\n}\n"
    rtkit.write_text(original[:start] + body + original[end:])
    header = tree / "src/rtkit.h"
    text = header.read_text()
    declaration = signature + ";"
    if text.count(declaration) != 1:
        raise ValueError("Pinned RTKit receive declaration changed")
    header.write_text(text.replace(declaration, declaration + "\nint rtkit_recv_one(rtkit_dev_t *rtk, struct rtkit_message *msg);"))
    path = tree / "src/nvme.c"
    source = path.read_text()
    start = source.index("static bool nvme_ctrl_shutdown(void)")
    end = source.index("\nstatic bool nvme_exec_command(", start)
    source = source[:start] + r'''static bool nvme_ctrl_shutdown(void)
{
    u64 timeout = timeout_calculate(NVME_SHUTDOWN_TIMEOUT);
    u32 status, control;

    printf("M4RCH ANS SHN: reading initial controller registers\n");
    control = read32(nvme_base + NVME_CC);
    status = read32(nvme_base + NVME_CSTS);
    printf("M4RCH ANS SHN: before CC=%08x CSTS=%08x\n", control, status);
    printf("M4RCH ANS SHN: requesting normal shutdown\n");
    mask32(nvme_base + NVME_CC, NVME_CC_SHN,
           FIELD_PREP(NVME_CC_SHN, NVME_CC_SHN_NORMAL));
    printf("M4RCH ANS SHN: request written; reading CSTS\n");
    status = read32(nvme_base + NVME_CSTS);
    printf("M4RCH ANS SHN: first CSTS=%08x\n", status);
    while (FIELD_GET(NVME_CSTS_SHST, status) != NVME_CSTS_SHST_DONE &&
           !timeout_expired(timeout)) {
        struct rtkit_message message;
        if (rtkit_recv_one(nvme_rtkit, &message) < 0) {
            printf("M4RCH ANS SHN: firmware receive failed; refusing handoff\n");
            return false;
        }
        udelay(100);
        status = read32(nvme_base + NVME_CSTS);
    }
    printf("M4RCH ANS SHN: final CSTS=%08x\n", status);
    return FIELD_GET(NVME_CSTS_SHST, status) == NVME_CSTS_SHST_DONE;
}
''' + source[end:]
    path.write_text(source)


def build(project, out, config, lock, kernel_dir, *, nvme=False, internal=False):
    if internal and not nvme:
        raise ValueError("Internal bridge requires the NVMe-aware m1n1 handoff")
    recipe = project / "sdboot"
    out.mkdir(parents=True, exist_ok=True)
    expected = inputs(project, lock, kernel_dir, nvme=nvme, internal=internal)
    manifest_path = out / "loader-manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text()).get("inputs") == expected:
        verify_manifest(manifest_path)
        print("Reusing verified fixed SD loader.")
        return
    directory = out / "loader"
    directory.mkdir(exist_ok=True)
    work = Path("/work/loader-internal" if internal else ("/work/loader-nvme" if nvme else "/work/loader"))
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
    # Retain the proven J614s SMC/reader supply setup even with an empty
    # slot. It does not probe a card; U-Boot internal mode has no MMC/PCI.
    prepare_m1n1(m1n1)
    if nvme:
        import nvme_handoff
        nvme_handoff.prepare(m1n1, wallace / "patches")
        nvme_handoff.prepare_uefi(m1n1)
        if internal:
            trace_nvme_handoff(m1n1)
            bounded_nvme_shutdown(m1n1)
            trace_next_stage_cleanup(m1n1)
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
    if internal:
        from prepare_nvme_uboot import prepare, validate_power_map
        validate_power_map(kernel_dir / "boot/t6040-j614s.dtb")
        prepare(uboot, recipe)
    else:
        prepare_uboot(uboot, recipe)
    build_uboot(uboot, config["jobs"], env, internal=internal)
    for source, name in ((m1n1 / "build/m1n1.bin", "m1n1.bin"),
                         (uboot / "u-boot-nodtb.bin", "u-boot-nodtb.bin"),
                         (uboot / "tools/mkimage", "mkimage"),
                         (uboot / ".config", ".config"),
                         (kernel_dir / "boot/t6040-j614s.dtb", "baseline.dtb")):
        shutil.copy2(source, directory / name)
    # Older cached kernels contain the retired bracketed board-label suffix.
    # Normalize only this loader's copy; never modify installed kernel inputs.
    baseline = directory / "baseline.dtb"
    model = boot.read_fdt(baseline)["/"].get("model", b"").rstrip(b"\0").decode()
    clean_model = model.partition(" [")[0]
    if clean_model != model:
        run(["fdtput", "-t", "s", baseline, "/", "model", clean_model])
    if inputs(project, lock, kernel_dir, nvme=nvme, internal=internal) != expected:
        raise ValueError("Loader sources changed during compilation; rerun make loader")
    data = pack(*[(directory / n).read_bytes() for n in ("m1n1.bin", "baseline.dtb", "u-boot-nodtb.bin")])
    temporary = out / ".loader.bin.partial"
    temporary.write_bytes(data)
    temporary.replace(out / "loader.bin")
    write_json(manifest_path, {"schema": 1, "kind": "j614s-internal-loader" if internal else "j614s-sd-loader", "boot_protocol": "uefi-arm64", "inputs": expected,
                              "build_labels": {"m1n1": boot.M1N1_LABEL, "u-boot": uboot_label(uboot / "Makefile")},
                              "m1n1_upstream_base": boot.M1N1_BASE, "hardware_tested": False,
                              "files": manifest_files(out, ["loader.bin", *["loader/" + n for n in ("m1n1.bin", "baseline.dtb", "u-boot-nodtb.bin", "mkimage", ".config")]])})
