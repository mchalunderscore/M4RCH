"""Execute PCI handoff and Linux enumeration code against recording fixtures."""
import ast
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


def extract_function(source, signature):
    start = source.index(signature)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def prepared_uboot(directory):
    """Prepare the exact pinned inputs, including the production handoff hook."""
    tree = directory / "uboot"
    module_ast = ast.parse((PROJECT / "sdboot/loader.py").read_text())
    revision = next(ast.literal_eval(node.value)["revision"] for node in module_ast.body
                    if isinstance(node, ast.Assign) and
                    any(isinstance(target, ast.Name) and target.id == "UBOOT"
                        for target in node.targets))
    files = ("arch/arm/Kconfig", "arch/arm/mach-apple/Kconfig",
             "arch/arm/mach-apple/board.c", "arch/arm/mach-apple/Makefile",
             "drivers/pci/pcie_apple.c", "drivers/mmc/pci_mmc.c", "drivers/mmc/Kconfig",
             "drivers/mmc/sdhci.c", "lib/efi_loader/efi_disk.c", "lib/efi_loader/efi_boottime.c")
    for name in files:
        path = tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(subprocess.run(
            ["git", "--git-dir=" + str(PROJECT / "cache/git/uboot.git"),
             "show", revision + ":" + name], check=True, capture_output=True).stdout)
    (tree / "configs").mkdir()
    subprocess.run(["git", "apply", str(PROJECT / "sdboot/uboot-noio.patch")],
                   cwd=tree, check=True, capture_output=True)
    spec = importlib.util.spec_from_file_location("pci_handoff_prepare", PROJECT / "sdboot/prepare_uboot.py")
    prepare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prepare)
    prepare.prepare(tree, PROJECT / "sdboot")
    return tree, revision


LINUX_HARNESS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define PCI_PRIMARY_BUS 0x18
#define PCI_SUBORDINATE_BUS 0x1a
#define PCI_PRIMARY_BUS_MASK 0xffU
#define PCI_SECONDARY_BUS_MASK 0xff00U
#define PCI_SUBORDINATE_BUS_MASK 0xff0000U
#define PCI_SEC_LATENCY_TIMER_MASK 0xff000000U
#define PCI_BRIDGE_CONTROL 0x3e
#define PCI_BRIDGE_CTL_MASTER_ABORT 0x20
#define PCI_STATUS 6
#define PCI_SEC_STATUS 0x1e
#define FIELD_GET(mask, value) (((value) & (mask)) >> __builtin_ctz(mask))
#define FIELD_PREP(mask, value) (((value) << __builtin_ctz(mask)) & (mask))
#define pci_dbg(...) ((void)0)
#define pci_info(...) ((void)0)
#define pci_warn(...) ((void)0)
#define scnprintf snprintf
struct device { int unused; };
struct pci_dev;
struct pci_bus {
    struct { int start, end; } busn_res;
    int number, primary, bridge_ctl;
    char name[32];
    struct pci_dev *bridge;
};
struct pci_dev {
    struct device dev;
    u32 buses;
    u16 control;
    struct pci_bus *subordinate;
};
static struct pci_bus children[9];
static bool allocated[9];
static void pm_runtime_get_sync(struct device *dev) { (void)dev; }
static void pm_runtime_put(struct device *dev) { (void)dev; }
static void pci_read_config_dword(struct pci_dev *dev, int reg, u32 *value)
{ assert(reg == PCI_PRIMARY_BUS); *value = dev->buses; }
static void pci_read_config_word(struct pci_dev *dev, int reg, u16 *value)
{ assert(reg == PCI_BRIDGE_CONTROL); *value = dev->control; }
static void pci_write_config_word(struct pci_dev *dev, int reg, u16 value)
{
    if (reg == PCI_BRIDGE_CONTROL) dev->control = value;
    else assert((reg == PCI_STATUS || reg == PCI_SEC_STATUS) && value == 0xffff);
}
static void pci_write_config_dword(struct pci_dev *dev, int reg, u32 value)
{ assert(reg == PCI_PRIMARY_BUS); dev->buses = value; }
static void pci_write_config_byte(struct pci_dev *dev, int reg, u8 value)
{ assert(reg == PCI_SUBORDINATE_BUS); dev->buses = (dev->buses & ~0xff0000U) | ((u32)value << 16); }
static bool pci_is_cardbus_bridge(struct pci_dev *dev) { (void)dev; return false; }
static int pci_cardbus_scan_bridge_extend(struct pci_bus *bus, struct pci_dev *dev,
                                         u32 buses, int max, unsigned available, int pass)
{ (void)bus; (void)dev; (void)buses; (void)max; (void)available; (void)pass; abort(); }
static bool pcibios_assign_all_busses(void) { return false; }
static int pci_domain_nr(struct pci_bus *bus) { (void)bus; return 0; }
static struct pci_bus *pci_find_bus(int domain, int number)
{ assert(domain == 0 && number > 0 && number < 9); return allocated[number] ? &children[number] : NULL; }
static struct pci_bus *pci_add_new_bus(struct pci_bus *parent, struct pci_dev *dev, int number)
{
    assert(number > 0 && number < 9 && !allocated[number]);
    allocated[number] = true;
    children[number] = (struct pci_bus) { .number = number, .primary = parent->number, .bridge = dev };
    return dev->subordinate = &children[number];
}
static void pci_bus_insert_busn_res(struct pci_bus *bus, int start, int end)
{ bus->busn_res.start = start; bus->busn_res.end = end; }
static int pci_scan_child_bus_extend(struct pci_bus *bus, unsigned available)
{ (void)available; return bus->number; }
static bool pci_ea_fixed_busnrs(struct pci_dev *dev, u8 *secondary, u8 *subordinate)
{ (void)dev; (void)secondary; (void)subordinate; return false; }
static void pci_bus_update_busn_res_end(struct pci_bus *bus, int end)
{ bus->busn_res.end = end; }
static void pbus_validate_busn(struct pci_bus *bus)
{ assert(bus->number == bus->busn_res.start && bus->busn_res.end >= bus->number); }

/* ACTUAL_LINUX_SCAN_BRIDGE */

int main(int argc, char **argv)
{
    assert(argc == 2);
    int inherited_sd_bus = atoi(argv[1]);
    assert(inherited_sd_bus >= 0 && inherited_sd_bus <= 2);
    struct pci_bus root = { .number = 0, .busn_res = {0, 8} };
    struct pci_dev ports[2] = {{0}, {0}};
    ports[1].buses = 0xa5000000U | ((u32)inherited_sd_bus << 8) | ((u32)inherited_sd_bus << 16);
    int max = 0;
    /* pci_scan_child_bus_extend uses physical root-port order for each
     * pass: configured firmware bridges first, then unconfigured bridges. */
    for (int pass = 0; pass < 2; pass++)
        for (int port = 0; port < 2; port++)
            max = pci_scan_bridge_extend(&root, &ports[port], max, 0, pass);
    assert(ports[0].subordinate && ports[1].subordinate);
    assert((ports[1].buses & PCI_SEC_LATENCY_TIMER_MASK) == 0xa5000000U);
    printf("wifi=%d sd=%d max=%d\n", ports[0].subordinate->number,
           ports[1].subordinate->number, max);
    return 0;
}
'''


HANDOFF_HARNESS = r'''
#include <assert.h>
#include <errno.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint32_t u32;
typedef uint32_t fdt32_t;
typedef unsigned long ulong;
typedef uint32_t pci_dev_t;
typedef int ofnode;
#define PCI_BDF(bus, dev, func) (((bus) << 16) | ((dev) << 11) | ((func) << 8))
#define PCI_VENDOR_ID 0
#define PCI_HEADER_TYPE 0xe
#define PCI_PRIMARY_BUS 0x18
#define PCI_VENDOR_ID_APPLE 0x106b
#define PCI_HEADER_TYPE_BRIDGE 1
#define PCI_SIZE_8 0
#define PCI_SIZE_16 1
#define PCI_SIZE_32 2
#define IS_ENABLED(option) app_noio
static int app_noio = 1;
static const char *scenario;
static bool is(const char *name) { return !strcmp(scenario, name); }
struct udevice { int seq; };
struct apple_pcie_priv { int ports; };
struct apple_pcie_port { int reset; };
static struct udevice device;
static struct apple_pcie_priv private;
static unsigned reads, writes;
static u32 bus_register = 0xa5010100;
static fdt32_t range[2];
static jmp_buf failure;
static int panic_error;
#define list_for_each_entry_safe(port, tmp, head, entry) \
    for ((void)(head), (tmp) = NULL, (port) = NULL; (port); (port) = (tmp))
static void *dev_get_priv(struct udevice *dev) { assert(dev == &device); return &private; }
static void gpio_free_list_nodev(int *reset, int count) { (void)reset; (void)count; abort(); }
static void panic(const char *format, ...)
{
    assert(strstr(format, "SD PCI bus handoff"));
    if (strstr(format, "failed")) {
        va_list args;
        va_start(args, format);
        panic_error = va_arg(args, int);
        va_end(args);
    } else {
        assert(strstr(format, "did not complete"));
        panic_error = -ENXIO;
    }
    longjmp(failure, 1);
}
static bool of_machine_is_compatible(const char *name)
{ assert(!strcmp(name, "apple,j614s")); return !is("machine"); }
static int dev_seq(struct udevice *dev) { assert(dev == &device); return dev->seq; }
static ofnode dev_ofnode(struct udevice *dev) { assert(dev == &device); return 1; }
static bool ofnode_device_is_compatible(ofnode node, const char *name)
{ assert(node == 1 && !strcmp(name, "apple,t6040-pcie")); return !is("compatible"); }
static uint64_t dev_read_addr_index(struct udevice *dev, int index)
{ assert(dev == &device && index == 0); return is("ecam") ? 0 : 0x1cb0000000ULL; }
static ofnode ofnode_find_subnode(ofnode node, const char *name)
{ assert(node == 1 && !strcmp(name, "pci@1,0")); return is("missing-port") ? 0 : 2; }
static bool ofnode_valid(ofnode node) { return node == 2; }
static bool ofnode_is_enabled(ofnode node) { assert(node == 2); return !is("disabled-port"); }
static int ofnode_read_u32_index(ofnode node, const char *name, int index, u32 *value)
{
    assert(node == 2 && !strcmp(name, "reg") && index == 0);
    *value = is("wrong-port-reg") ? 0 : 0x800;
    return is("missing-port-reg") ? -EINVAL : 0;
}
static const void *ofnode_get_property(ofnode node, const char *name, int *length)
{
    assert(node == 2 && !strcmp(name, "bus-range"));
    *length = is("short-range") ? 4 : is("long-range") ? 12 : 8;
    return is("missing-range") ? NULL : range;
}
static u32 fdt32_to_cpu(fdt32_t value) { return __builtin_bswap32(value); }
static int apple_pcie_read_config(struct udevice *dev, pci_dev_t bdf,
                                  unsigned offset, ulong *value, int size)
{
    /* Every access must target the SD root port, never Wi-Fi or endpoint. */
    assert(dev == &device && bdf == PCI_BDF(0, 1, 0));
    reads++;
    if (offset == PCI_VENDOR_ID) {
        assert(size == PCI_SIZE_16);
        *value = is("vendor") ? 0x17a0 : PCI_VENDOR_ID_APPLE;
        return is("vendor-read") ? -EACCES : 0;
    }
    if (offset == PCI_HEADER_TYPE) {
        assert(size == PCI_SIZE_8);
        *value = is("header") ? 0 : is("multifunction") ? 0x81 : PCI_HEADER_TYPE_BRIDGE;
        return is("header-read") ? -EACCES : 0;
    }
    assert(offset == PCI_PRIMARY_BUS && size == PCI_SIZE_32);
    *value = (is("readback-mismatch") && writes) ? 0xa5000100 : bus_register;
    if (is("bus-read") || (is("readback-error") && writes)) return -EACCES;
    return 0;
}
static int apple_pcie_write_config(struct udevice *dev, pci_dev_t bdf,
                                   unsigned offset, ulong value, int size)
{
    assert(dev == &device && bdf == PCI_BDF(0, 1, 0));
    assert(offset == PCI_PRIMARY_BUS && size == PCI_SIZE_32);
    assert(value == (bus_register & 0xff000000U));
    writes++;
    if (is("write-error")) return -EACCES;
    bus_register = value;
    return 0;
}

#include "arch_m4_sd_pci_handoff.h"

/* ACTUAL_UBOOT_REMOVE */

int main(int argc, char **argv)
{
    assert(argc == 2);
    scenario = argv[1];
    if (is("guard-unarmed")) {
        apple_sd_pci_handoff_check();
        assert(!reads && !writes && !panic_error);
        puts("handoff verified: guard-unarmed");
        return 0;
    }
    apple_sd_pci_handoff_arm();
    assert(apple_sd_pci_handoff_required && !apple_sd_pci_handoff_complete);
    if (is("guard-skipped")) {
        if (!setjmp(failure)) { apple_sd_pci_handoff_check(); abort(); }
        assert(panic_error == -ENXIO && !reads && !writes);
        puts("handoff verified: guard-skipped");
        return 0;
    }
    range[0] = __builtin_bswap32(is("range-start") ? 1U : 2U);
    range[1] = __builtin_bswap32(is("range-end") ? 3U : 2U);
    device.seq = is("root-sequence") ? 1 : 0;
    if (is("already-clear")) bus_register = 0xa5000000;
    if (is("all-ones")) bus_register = 0xffffffff;
    if (is("primary")) bus_register = 0xa5010101;
    if (is("secondary-zero")) bus_register = 0xa5010000;
    if (is("subordinate-zero")) bus_register = 0xa5000100;
    if (is("subordinate-before-secondary")) bus_register = 0xa5010200;
    if (is("bus-two")) bus_register = 0xa5020200;
    if (is("subordinate-range")) bus_register = 0xa5080100;
    if (is("latency-ff")) bus_register = 0xff010100;
    if (is("generic")) app_noio = 0;
    u32 original = bus_register;
    bool success = is("good") || is("already-clear") || is("bus-two") || is("guard-rearm") ||
                   is("subordinate-range") || is("latency-ff") || is("multifunction") || is("generic");
    bool late_error = is("write-error") || is("readback-error") || is("readback-mismatch");
    bool early_error = is("machine") || is("root-sequence") || is("compatible") ||
                       is("ecam") || is("missing-port") || is("disabled-port") ||
                       is("wrong-port-reg") || is("missing-port-reg") ||
                       is("short-range") || is("long-range") || is("missing-range") ||
                       is("range-start") || is("range-end");
    int result = -999;
    if (!setjmp(failure)) result = apple_pcie_remove(&device);
    if (success) {
        assert(result == 0 && panic_error == 0);
        assert(bus_register == (is("generic") ? original : original & 0xff000000U));
        assert(writes == ((is("already-clear") || is("generic")) ? 0U : 1U));
        if (!is("generic")) {
            assert(apple_sd_pci_handoff_complete);
            apple_sd_pci_handoff_check();
        }
        if (is("guard-rearm")) {
            apple_sd_pci_handoff_arm();
            assert(!apple_sd_pci_handoff_complete);
            if (!setjmp(failure)) { apple_sd_pci_handoff_check(); abort(); }
            assert(panic_error == -ENXIO);
        }
    } else {
        assert(result == -999 && panic_error < 0);
        assert(writes == (late_error ? 1U : 0U));
        if (!late_error || is("write-error")) assert(bus_register == original);
    }
    if (early_error || is("generic")) assert(reads == 0);
    printf("handoff verified: %s reads=%u writes=%u panic=%d\n", scenario, reads, writes, panic_error);
    return 0;
}
'''


@unittest.skipUnless(shutil.which("cc") and (PROJECT / "cache/git/uboot.git").is_dir(),
                     "requires a C compiler and the pinned U-Boot source cache")
class SdPciHandoff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name)
        cls.tree, cls.revision = prepared_uboot(directory)
        cls.source = (cls.tree / "drivers/pci/pcie_apple.c").read_text()
        path = directory / "pci-handoff.c"
        path.write_text(HANDOFF_HARNESS.replace("/* ACTUAL_UBOOT_REMOVE */",
                        extract_function(cls.source, "static int apple_pcie_remove(")))
        cls.executable = directory / "pci-handoff"
        result = subprocess.run([shutil.which("cc"), "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                                 "-I", str(cls.tree / "drivers/pci"), str(path), "-o", str(cls.executable)],
                                capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    def check_scenarios(self, scenarios):
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                result = subprocess.run([str(self.executable), scenario], capture_output=True,
                                        text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("handoff verified: " + scenario, result.stdout)

    def test_clear_bus_numbers_preserving_latency_byte_and_only_accessing_sd_port(self):
        self.check_scenarios(("good", "bus-two", "subordinate-range", "latency-ff", "multifunction"))

    def test_already_cleared_bridge_is_idempotent(self):
        self.check_scenarios(("already-clear",))

    def test_other_apple_driver_builds_do_not_run_sd_handoff(self):
        self.check_scenarios(("generic",))

    def test_unexpected_hardware_and_dt_fail_before_any_pci_access(self):
        self.check_scenarios(("machine", "root-sequence", "compatible", "ecam", "missing-port",
                              "disabled-port", "wrong-port-reg", "missing-port-reg", "short-range",
                              "long-range", "missing-range", "range-start", "range-end"))

    def test_unexpected_pci_identity_or_bus_configuration_fails_before_writes(self):
        self.check_scenarios(("vendor", "header", "all-ones", "primary", "secondary-zero",
                              "subordinate-zero", "subordinate-before-secondary"))

    def test_config_io_and_readback_failures_stop_os_handoff(self):
        self.check_scenarios(("vendor-read", "header-read", "bus-read", "write-error",
                              "readback-error", "readback-mismatch"))

    def test_completion_guard_blocks_skipped_cleanup_and_resets_on_reprobe(self):
        self.check_scenarios(("guard-unarmed", "guard-skipped", "guard-rearm"))

    def test_handoff_is_attached_to_os_teardown_and_mmc_cleanup(self):
        declaration = self.source[self.source.index("U_BOOT_DRIVER(apple_pcie)"):]
        self.assertIn(".remove = apple_pcie_remove", declaration)
        self.assertIn(".flags = IS_ENABLED(CONFIG_APPLE_NOIO) ? DM_FLAG_OS_PREPARE : 0", declaration)
        mmc = (self.tree / "drivers/mmc/pci_mmc.c").read_text()
        mmc_declaration = mmc[mmc.index("U_BOOT_DRIVER(pci_mmc)"):]
        self.assertIn(".flags = IS_ENABLED(CONFIG_APPLE_NOIO) ? DM_FLAG_OS_PREPARE : 0", mmc_declaration)
        probe = extract_function(self.source, "static int apple_pcie_probe(")
        self.assertNotIn("apple_sd_pci_handoff(dev)", probe)
        self.assertIn("apple_sd_pci_handoff_arm()", probe)
        self.assertNotIn("apple_sd_pci_handoff", (PROJECT / "sdboot/archsd.c").read_text())
        efi = (self.tree / "lib/efi_loader/efi_boottime.c").read_text()
        exit_services = extract_function(efi, "static efi_status_t EFIAPI efi_exit_boot_services(")
        self.assertGreater(exit_services.index("apple_sd_pci_handoff_check();"),
                           exit_services.index("dm_remove_devices_active();"))


@unittest.skipUnless(shutil.which("cc") and (PROJECT / "cache/git/linux.git").is_dir(),
                     "requires a C compiler and the pinned Linux source cache")
class LinuxPciHandoffEnumeration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name)
        revision = json.loads((PROJECT / "sources.lock.json").read_text())["linux"]["revision"]
        source = subprocess.run(
            ["git", "--git-dir=" + str(PROJECT / "cache/git/linux.git"),
             "show", revision + ":drivers/pci/probe.c"],
            check=True, capture_output=True, text=True).stdout
        path = directory / "linux-pci-enumeration.c"
        path.write_text(LINUX_HARNESS.replace("/* ACTUAL_LINUX_SCAN_BRIDGE */",
                        extract_function(source, "static int pci_scan_bridge_extend(")))
        cls.executable = directory / "linux-pci-enumeration"
        result = subprocess.run([shutil.which("cc"), "-std=gnu11", "-Wall", "-Wextra",
                                 "-Werror", str(path), "-o", str(cls.executable)],
                                capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    def enumeration(self, inherited_sd_bus):
        result = subprocess.run([str(self.executable), str(inherited_sd_bus)],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def test_existing_loader_swaps_linux_bus_to_dart_association(self):
        self.assertEqual(self.enumeration(1), "wifi=2 sd=1 max=2")

    def test_reserving_sd_bus_two_alone_does_not_restore_wifi_bus_one(self):
        self.assertEqual(self.enumeration(2), "wifi=3 sd=2 max=3")

    def test_cleared_sd_bus_configuration_restores_the_pinned_dt_mapping(self):
        self.assertEqual(self.enumeration(0), "wifi=1 sd=2 max=2")


if __name__ == "__main__":
    unittest.main()
