"""Host-execute the UEFI bridge with the pinned libfdt and fake block/EFI APIs.

These cover bounded file loading, DT inheritance and EFI device-path handoff,
not native PCIe/SDHCI operation. No container or disk access is needed.
"""
import importlib.util
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / "cache/sdboot-src"


EFI_CONFIG = "".join(f"CONFIG_{symbol}=y\n" for symbol in (
    "MMC_SDHCI_IO_ACCESSORS",
    "EFI_LOADER", "EFI_BINARY_EXEC", "CMD_BOOTEFI", "CMD_BOOTEFI_BINARY",
    "EFI_VARIABLE_NO_STORE", "EFI_PARTITION", "PARTITION_UUIDS",
    "OF_LIBFDT_OVERLAY", "VIDEO", "VIDEO_SIMPLE", "VIDEO_ANSI", "DM_DEVICE_REMOVE"))


class LoaderConfiguration(unittest.TestCase):
    def test_resolved_config_rejects_serial_requirement_and_unmapped_drivers(self):
        sys.path.insert(0, str(PROJECT / "sdboot"))
        try:
            from loader import validate_uboot_config
        finally:
            sys.path.pop(0)
        # Model the resolved Kconfig defaults, not only entries the defconfig
        # explicitly supplies. The first fixture reproduces the native failure.
        framework = "CONFIG_SERIAL=y\nCONFIG_DM_SERIAL=y\n" + EFI_CONFIG
        safe = framework + "# CONFIG_REQUIRE_SERIAL_CONSOLE is not set\n"
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            config = tree / ".config"
            makefile = tree / "Makefile"
            makefile.write_text("obj-$(CONFIG_S5P_SERIAL) += serial_s5p.o\n"
                                "obj-$(CONFIG_PL01X_SERIAL) += serial_pl01x.o\n"
                                "obj-$(CONFIG_$(PHASE_)SYS_NS16550_SERIAL) += serial_ns16550.o\n")
            config.write_text(framework + "CONFIG_REQUIRE_SERIAL_CONSOLE=y\n")
            with self.assertRaisesRegex(ValueError, "REQUIRE_SERIAL_CONSOLE"):
                validate_uboot_config(config, makefile)
            config.write_text(safe)
            validate_uboot_config(config, makefile)
            config.write_text(safe + "CONFIG_PCI_INIT_R=y\n")
            with self.assertRaisesRegex(ValueError, "PCI_INIT_R"):
                validate_uboot_config(config, makefile)
            for driver in ("S5P_SERIAL", "PL01X_SERIAL", "SYS_NS16550_SERIAL"):
                with self.subTest(driver=driver):
                    config.write_text(safe + f"CONFIG_{driver}=y\n")
                    with self.assertRaisesRegex(ValueError, driver):
                        validate_uboot_config(config, makefile)

    def test_resolved_efi_config_requires_firmware_services_and_no_writes(self):
        sys.path.insert(0, str(PROJECT / "sdboot"))
        try:
            from loader import validate_uboot_config
        finally:
            sys.path.pop(0)
        safe = "CONFIG_SERIAL=y\nCONFIG_DM_SERIAL=y\n" + EFI_CONFIG
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            config = tree / ".config"
            makefile = tree / "Makefile"
            makefile.write_text("obj-$(CONFIG_S5P_SERIAL) += serial_s5p.o\n")
            for symbol in ("EFI_LOADER", "EFI_VARIABLE_NO_STORE", "CMD_BOOTEFI_BINARY",
                           "PARTITION_UUIDS", "OF_LIBFDT_OVERLAY", "VIDEO_SIMPLE", "MMC_SDHCI_IO_ACCESSORS", "DM_DEVICE_REMOVE"):
                with self.subTest(required=symbol):
                    config.write_text(safe.replace(f"CONFIG_{symbol}=y\n", ""))
                    with self.assertRaisesRegex(ValueError, symbol):
                        validate_uboot_config(config, makefile)
            for symbol in ("FAT_WRITE", "FAT_RENAME", "EFI_VARIABLE_FILE_STORE", "EFI_BOOTMGR",
                           "EFI_CAPSULE_ON_DISK", "EFI_RUNTIME_UPDATE_CAPSULE",
                           "MMC_WRITE", "MMC_SDHCI_ADMA", "MMC_SDHCI_SDMA",
                           "MMC_UHS_SUPPORT", "MMC_HS200_SUPPORT", "MMC_HS400_SUPPORT", "MMC_HS400_ES_SUPPORT"):
                with self.subTest(forbidden=symbol):
                    config.write_text(safe + f"CONFIG_{symbol}=y\n")
                    with self.assertRaisesRegex(ValueError, symbol):
                        validate_uboot_config(config, makefile)

    def test_uboot_build_checks_kconfig_defaults_before_compilation(self):
        sys.path.insert(0, str(PROJECT / "sdboot"))
        try:
            import loader
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            (tree / "Makefile").write_text("VERSION = 2025\nPATCHLEVEL = 10\nSUBLEVEL =\n")
            (tree / "drivers/serial").mkdir(parents=True)
            (tree / "drivers/serial/Makefile").write_text(
                "obj-$(CONFIG_S5P_SERIAL) += serial_s5p.o\n")
            for require_serial in (True, False):
                with self.subTest(require_serial=require_serial):
                    commands = []
                    def run_make(command, **kwargs):
                        commands.append(command)
                        if command == ["make", "apple_sdboot_defconfig"]:
                            (tree / ".config").write_text(
                                "CONFIG_SERIAL=y\nCONFIG_DM_SERIAL=y\n" + EFI_CONFIG +
                                ("CONFIG_REQUIRE_SERIAL_CONSOLE=y\n" if require_serial else
                                 "# CONFIG_REQUIRE_SERIAL_CONSOLE is not set\n"))
                    with patch.object(loader, "run", side_effect=run_make):
                        if require_serial:
                            with self.assertRaisesRegex(ValueError, "REQUIRE_SERIAL_CONSOLE"):
                                loader.build_uboot(tree, 3, {})
                        else:
                            loader.build_uboot(tree, 3, {})
                    expected = [["make", "apple_sdboot_defconfig"]]
                    if not require_serial:
                        expected.append(["make", "UBOOTRELEASE=u-boot-m4rch-2025.10", "LOCALVERSION=", "-j3"])
                    self.assertEqual(commands, expected)

    def test_build_label_uses_the_source_version_without_git_suffixes(self):
        sys.path.insert(0, str(PROJECT / "sdboot"))
        try:
            from loader import uboot_label
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as temporary:
            makefile = Path(temporary) / "Makefile"
            for sublevel, label in (("", "u-boot-m4rch-2025.10"), ("1", "u-boot-m4rch-2025.10.1")):
                makefile.write_text("VERSION = 2025\nPATCHLEVEL = 10\nSUBLEVEL = " + sublevel + "\nEXTRAVERSION = -dirty\n")
                self.assertEqual(uboot_label(makefile), label)
            makefile.write_text("VERSION = 2025\nPATCHLEVEL = bad\nSUBLEVEL =\n")
            with self.assertRaises(ValueError):
                uboot_label(makefile)

    def test_pack_pads_the_inline_uboot_memory_extent(self):
        sys.path.insert(0, str(PROJECT / "sdboot"))
        try:
            from loader import pack
        finally:
            sys.path.pop(0)
        prefix = b"m" * 16384
        dt = struct.pack(">II", 0xd00dfeed, 40) + bytes(32)
        payload = bytearray(80)
        payload[56:60] = b"ARM\x64"
        struct.pack_into("<QQ", payload, 8, 0, 4096)
        result = pack(prefix, dt, payload)
        self.assertEqual(result[:16384], prefix)
        self.assertEqual(result[16384:16424], dt)
        self.assertEqual(result[16424:16504], payload)
        self.assertEqual(result[16504:], bytes(len(result) - 16504))
        self.assertEqual(len(result) % 16384, 0)
        for broken_prefix, broken_dt, broken_image in (
            (prefix[:-1], dt, payload), (prefix, dt[:-1], payload),
            (prefix, dt, payload[:60]),
        ):
            with self.subTest(lengths=list(map(len, (broken_prefix, broken_dt, broken_image)))):
                with self.assertRaises(ValueError):
                    pack(broken_prefix, broken_dt, broken_image)
        for offset, size in ((0, 79), (1, 4096), (0, 32 * 1024**2 + 1)):
            struct.pack_into("<QQ", payload, 8, offset, size)
            with self.assertRaises(ValueError):
                pack(prefix, dt, payload)

    def test_loader_cannot_write_storage_or_restore_a_saved_environment(self):
        config = (PROJECT / "sdboot/uboot.config").read_text().splitlines()
        for symbol in ("MMC_WRITE", "MMC_HW_PARTITIONING", "MMC_SDHCI_SDMA",
                       "MMC_SDHCI_ADMA", "CMD_MMC", "CMD_GPT", "FAT_WRITE",
                       "ENV_IS_IN_FAT", "CMD_SAVEENV", "NVME", "USB", "IOMMU",
                       "EFI_VARIABLE_FILE_STORE", "EFI_BOOTMGR", "FAT_RENAME",
                       "EFI_CAPSULE_ON_DISK", "EFI_RUNTIME_UPDATE_CAPSULE"):
            with self.subTest(symbol=symbol):
                self.assertIn(f"# CONFIG_{symbol} is not set", config)
        self.assertIn("CONFIG_ENV_IS_NOWHERE=y", config)
        self.assertIn("CONFIG_EFI_VARIABLE_NO_STORE=y", config)
        self.assertIn("CONFIG_EFI_LOADER=y", config)

    def test_pinned_source_replacement_rejects_ambiguous_matches(self):
        spec = importlib.util.spec_from_file_location(
            "prepare_sd_uboot", PROJECT / "sdboot/prepare_uboot.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.c"
            path.write_text("anchor anchor")
            with self.assertRaises(ValueError):
                module.replace(path, "anchor", "replacement")
            self.assertEqual(path.read_text(), "anchor anchor")

    @unittest.skipUnless(shutil.which("cc"), "requires a C compiler")
    def test_smc_power_write_requires_exact_live_board_action(self):
        spec = importlib.util.spec_from_file_location(
            "prepare_sd_m1n1", PROJECT / "sdboot/prepare_m1n1.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            (tree / "src").mkdir()
            path = tree / "src/kboot.c"
            path.write_text("int kboot_boot(void *kernel)\n{\n    usb_init();\n    pcie_init();\n}\n")
            module.prepare(tree)
            patched = path.read_text()
            helper = patched[patched.index("static int sdboot_power_reader"):
                             patched.index("int kboot_boot")]
            self.assertLess(patched.index("if (sdboot_power_reader())"),
                            patched.index("    pcie_init();"))
            code = r'''
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
typedef uint32_t u32;
typedef int smc_dev_t;
#define T6040 0x6040
static int chip_id = T6040, scenario, writes, opened, closed;
static void *dt, *adt;
static int fdt_node_check_compatible(void *p, int node, const char *s) { return scenario == 1; }
static int adt_path_offset(void *p, const char *path) {
    return strstr(path, "smc-pmu") ? (scenario == 2 ? -1 : 2) : 1;
}
static const void *adt_getprop(void *p, int node, const char *name, u32 *len) {
    static u32 action[4];
    action[0] = scenario == 3 ? 0x125 : 0x126;
    action[1] = scenario == 4 ? 0 : 0x704b5734;
    action[2] = scenario == 5 ? 0x67503138 : 0x67503139;
    action[3] = scenario == 6 ? 1 : 0;
    *len = scenario == 7 ? 12 : sizeof(action);
    return action;
}
static int adt_getprop_copy(void *p, int node, const char *name, void *dest, u32 len) {
    *(u32 *)dest = scenario == 8 ? 0 : 0x126;
    return scenario == 9 ? -1 : 0;
}
static smc_dev_t *smc_init(void) { ++opened; return (smc_dev_t *)1; }
static int smc_write_u32(smc_dev_t *s, u32 key, u32 value) {
    if (key != 0x67503139 || value != 0x01000001) abort();
    ++writes; return scenario == 10 ? -1 : 0;
}
static void smc_shutdown(smc_dev_t *s) { ++closed; }
static void mdelay(int time) { if (time != 100) abort(); }
''' + helper + r'''
int main(int argc, char **argv) {
    scenario = atoi(argv[1]);
    int result = sdboot_power_reader();
    if (scenario == 0 || scenario == 10) {
        if (opened != 1 || closed != 1 || writes != 1) return 8;
    } else if (opened || closed || writes) return 8;
    return result ? 1 : 0;
}
'''
            (tree / "helper.c").write_text(code)
            subprocess.run([shutil.which("cc"), "-std=c11", str(tree / "helper.c"),
                            "-o", str(tree / "helper")], check=True, capture_output=True)
            for scenario in range(11):
                with self.subTest(scenario=scenario):
                    result = subprocess.run([str(tree / "helper"), str(scenario)], capture_output=True)
                    self.assertEqual(result.returncode, 0 if scenario == 0 else 1,
                                     result.stdout.decode())


@unittest.skipUnless(shutil.which("cc") and (SOURCE / "scripts/dtc/libfdt/fdt.c").is_file(),
                     "requires a C compiler and the pinned U-Boot source cache")
class LoaderEfiHandoff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        source = (PROJECT / "sdboot/archsd.c").read_text()
        body = source[source.index("#define EFI_LIMIT"):source.index("U_BOOT_CMD(")]
        prefix = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <libfdt.h>
typedef unsigned long ulong;
typedef long long loff_t;
#define SZ_64M (64U * 1024 * 1024)
#define SZ_2M (2U * 1024 * 1024)
#define CMD_RET_FAILURE 1
#define CMD_RET_SUCCESS 0
#define FS_TYPE_FAT 1
#define EFI_SUCCESS 0
struct cmd_tbl { int unused; };
struct global_data { void *fdt_blob; };
static struct global_data global, *gd = &global;
static unsigned char live[8192], original[8192], file_overlay[8192];
static unsigned char image[SZ_64M], handoff[SZ_2M], overlay[SZ_2M];
static int scenario, started, scanned, reads, selected, stage, env_cleared;
static void *registered;
static size_t registered_size;
static ulong env_get_hex(const char *name, ulong def) {
    if (!strcmp(name, "loadaddr")) return scenario == 1 ? 0 : (ulong)image;
    if (!strcmp(name, "fdt_addr_r")) return (ulong)handoff;
    if (!strcmp(name, "scriptaddr")) return (ulong)overlay;
    abort();
}
static int env_set(const char *name, const char *value) {
    if (strcmp(name, "bootargs") || value) abort();
    env_cleared = 1;
    return scenario == 14 ? -1 : 0;
}
static int puts_probe(const char *msg) {
    if (strstr(msg, "framebuffer console ready")) stage = 1;
    return puts(msg);
}
#define puts puts_probe
static void pci_init(void) {
    if (stage != 1) abort();
    scanned = 1;
}
static int fs_set_blk_dev(const char *dev, const char *part, int fs) {
    if (!scanned || strcmp(dev, "mmc") || strcmp(part, "0:1") || fs != FS_TYPE_FAT) abort();
    selected = 1;
    return scenario == 3 ? -1 : 0;
}
static int fs_size(const char *path, loff_t *len) {
    if (!selected) abort();
    selected = 0;
    if (!strcmp(path, "/dtbs/board.dtbo")) {
        if (scenario == 4) return -1;
        *len = scenario == 5 ? SZ_2M + 1 : fdt_totalsize(file_overlay);
    } else if (!strcmp(path, "/EFI/BOOT/BOOTAA64.EFI")) {
        if (scenario == 9) return -1;
        *len = scenario == 10 ? SZ_64M + 1 : 128;
    } else abort();
    return 0;
}
static int fs_read(const char *path, ulong addr, loff_t offset, loff_t len, loff_t *actual) {
    if (!selected || offset) abort();
    selected = 0;
    ++reads;
    *actual = len;
    if (!strcmp(path, "/dtbs/board.dtbo")) {
        if (len > SZ_2M || addr != (ulong)overlay) abort();
        memcpy((void *)addr, file_overlay, len);
        if (scenario == 6) --*actual;
        if (scenario == 7) overlay[0] = 0;
    } else {
        if (len > SZ_64M || addr != (ulong)image) abort();
        memset((void *)addr, 0xab, len);
        if (scenario == 11) --*actual;
    }
    return 0;
}
static int efi_check_pe(void *data, size_t len, void **nt) {
    if (data != image || len != 128 || nt) abort();
    return scenario == 12 ? -1 : 0;
}
static void efi_set_bootdev(const char *dev, const char *part, const char *path, void *data, size_t len) {
    if (strcmp(dev, "mmc") || strcmp(part, "0:1") || strcmp(path, "/EFI/BOOT/BOOTAA64.EFI") ||
        data != image || len != 128 || reads != 2) abort();
    registered = scenario == 13 ? NULL : data;
    registered_size = len;
}
static void efi_get_image_parameters(void **data, size_t *len) {
    *data = registered;
    *len = registered_size;
}
static int run_command(const char *command, int flag) {
    char expected[96];
    snprintf(expected, sizeof(expected), "bootefi %lx %lx", (ulong)image, (ulong)handoff);
    if (strcmp(command, expected) || flag || !env_cleared || registered != image) abort();
    ++started;
    int node = fdt_path_offset(handoff, "/chosen"), len;
    const fdt32_t *val = fdt_getprop(handoff, node, "firmware-live", &len);
    if (!val || len != 4 || fdt32_to_cpu(*val) != 0x12345678) abort();
    val = fdt_getprop(handoff, node, "overlay-applied", &len);
    if (!val || len != 4 || fdt32_to_cpu(*val) != 1) abort();
    return scenario == 15 ? -1 : 0;
}
'''
        suffix = r'''
int main(int argc, char **argv) {
    scenario = atoi(argv[1]);
    if (fdt_create_empty_tree(live, sizeof(live))) return 9;
    fdt_setprop_string(live, 0, "compatible", scenario == 2 ? "apple,j274" : "apple,j614s");
    int chosen = fdt_add_subnode(live, 0, "chosen");
    fdt_setprop_u32(live, chosen, "firmware-live", 0x12345678);
    memcpy(original, live, sizeof(live));
    global.fdt_blob = live;
    if (fdt_create_empty_tree(file_overlay, sizeof(file_overlay))) return 9;
    int fragment = fdt_add_subnode(file_overlay, 0, "fragment@0");
    fdt_setprop_string(file_overlay, fragment, "target-path", scenario == 8 ? "/missing" : "/chosen");
    int props = fdt_add_subnode(file_overlay, fragment, "__overlay__");
    fdt_setprop_u32(file_overlay, props, "overlay-applied", 1);
    if (fdt_pack(file_overlay)) return 9;
    int result = do_archsd(NULL, 0, 0, NULL);
    if (memcmp(live, original, sizeof(live))) return 8;
    if (scenario == 0 || scenario == 15) {
        if (started != 1 || !scanned || reads != 2) return 8;
    } else if (started) return 8;
    if ((scenario == 1 || scenario == 2) && scanned) return 8;
    return result;
}
'''
        (directory / "handoff.c").write_text(prefix + body + suffix)
        cls.executable = directory / "handoff"
        fdt = SOURCE / "scripts/dtc/libfdt"
        sources = [fdt / name for name in ("fdt.c", "fdt_ro.c", "fdt_rw.c",
                   "fdt_wip.c", "fdt_sw.c", "fdt_empty_tree.c", "fdt_strerror.c",
                   "fdt_overlay.c")]
        result = subprocess.run([shutil.which("cc"), "-std=c11",
                                 "-D_POSIX_C_SOURCE=200809L", "-I", str(fdt),
                                 str(directory / "handoff.c"), *map(str, sources),
                                 "-o", str(cls.executable)], text=True, capture_output=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    def test_efi_handoff_preserves_live_dt_and_real_boot_device(self):
        result = subprocess.run([str(self.executable), "0"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())

    def test_fail_closed_on_board_storage_overlay_image_and_handoff_errors(self):
        for case in range(1, 16):
            with self.subTest(case=case):
                result = subprocess.run([str(self.executable), str(case)], capture_output=True)
                self.assertEqual(result.returncode, 1, result.stdout.decode() + result.stderr.decode())

    def test_missing_card_is_reported_before_attempting_overlay(self):
        result = subprocess.run([str(self.executable), "3"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("SD card/ESP unavailable", result.stdout)
        self.assertNotIn("missing or invalid /dtbs/board.dtbo", result.stdout)


if __name__ == "__main__":
    unittest.main()
