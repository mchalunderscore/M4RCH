"""Exercise the real prepared PCI probe with banked vendor configuration."""
import ast
import importlib.util
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


HARNESS = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define BIT(n) (1U << (n))
#define GENMASK(h, l) ((~0U << (l)) & (~0U >> (31 - (h))))
#define IS_ENABLED(x) 1
#define PCI_VENDOR_ID 0
#define PCI_DEVICE_ID 2
#define PCI_COMMAND 4
#define PCI_COMMAND_MEMORY 2
#define PCI_COMMAND_MASTER 4
#define PCI_BASE_ADDRESS_0 0x10
#define PCI_BASE_ADDRESS_1 0x14
#define PCI_REGION_TYPE 3
#define PCI_REGION_MEM 0
#define SDHCI_CAPABILITIES 0x40
#define SDHCI_HOST_VERSION 0xfe
#define SDHCI_CLOCK_CONTROL 0x2c
#define SDHCI_QUIRK_NO_1_8_V BIT(9)
#define SDHCI_QUIRK_BROKEN_HISPD_MODE BIT(5)
#define MMC_MODE_4BIT BIT(2)
#define MMC_VDD_32_33 BIT(20)
#define MMC_VDD_33_34 BIT(21)

struct udevice { const char *name; };
struct sdhci_host;
struct sdhci_ops {
    u16 (*read_w)(struct sdhci_host *, int);
    u8 (*read_b)(struct sdhci_host *, int);
};
struct gpio_desc { int unused; };
struct mmc;
struct sdhci_host {
    void *ioaddr;
    const struct sdhci_ops *ops;
    const char *name;
    struct mmc *mmc;
    struct gpio_desc cd_gpio;
    unsigned quirks;
};
struct mmc_config { unsigned host_caps, voltages, f_max; };
struct mmc { struct udevice *dev; void *priv; };
struct mmc_uclass_priv { struct mmc *mmc; };
struct blk_desc { bool removable; };
struct pci_mmc_plat { struct mmc_config cfg; struct mmc mmc; };
struct pci_mmc_priv { struct sdhci_host host; void *base; struct gpio_desc cd_gpio; };

static struct udevice device = { .name = "sd-reader" };
static struct pci_mmc_plat plat;
static struct pci_mmc_priv priv;
static struct mmc_uclass_priv upriv;
static struct blk_desc block;
static union { u32 words[64]; u8 bytes[256]; } mmio;
static u32 wt = 0x200, peconf = 0x2402c1f3;
static unsigned post_init, vendor_reads_closed, vendor_reads_open, vendor_writes;
static unsigned verify_reads, post_wt_writes, init_calls;
static int init_error, fail_verify_read, fail_close, ignore_close, mismatch, verify_ones;
#define MMC_CAP_NONREMOVABLE BIT(16)

static void *dev_get_uclass_priv(struct udevice *dev) { assert(dev == &device); return &upriv; }
static void *dev_get_plat(struct udevice *dev) { assert(dev == &device); return &plat; }
static void *dev_get_priv(struct udevice *dev) { assert(dev == &device); return &priv; }
static struct blk_desc *mmc_get_blk_desc(struct mmc *mmc) { assert(mmc == &plat.mmc); return &block; }
static bool of_machine_is_compatible(const char *name) { return !strcmp(name, "apple,j614s"); }
static int mmc_of_parse(struct udevice *dev, struct mmc_config *cfg)
{
    assert(dev == &device && cfg == &plat.cfg);
    cfg->host_caps = MMC_MODE_4BIT;
    return 0;
}
static void *dm_pci_map_bar(struct udevice *dev, int bar, int offset, int length,
                          unsigned mask, unsigned flags)
{
    assert(dev == &device && bar == PCI_BASE_ADDRESS_0 && !offset && !length);
    assert(mask == PCI_REGION_TYPE && flags == PCI_REGION_MEM);
    return mmio.bytes;
}
static int dm_pci_read_config16(struct udevice *dev, int offset, u16 *value)
{
    assert(dev == &device);
    switch (offset) {
    case PCI_VENDOR_ID: *value = 0x17a0; break;
    case PCI_DEVICE_ID: *value = 0x9755; break;
    case PCI_COMMAND: *value = PCI_COMMAND_MEMORY; break;
    default: assert(!"unexpected PCI word read");
    }
    return 0;
}
static int dm_pci_read_config32(struct udevice *dev, int offset, u32 *value)
{
    assert(dev == &device);
    switch (offset) {
    case PCI_BASE_ADDRESS_0: *value = 0x80000000; return 0;
    case PCI_BASE_ADDRESS_1: *value = 0; return 0;
    case 0x800: *value = wt; return 0;
    case 0x44:
        if (post_init)
            ++verify_reads;
        if (!(wt & BIT(0))) {
            ++vendor_reads_closed;
            *value = 0; /* ordinary config bank, not the vendor PECONF */
            return 0;
        }
        ++vendor_reads_open;
        if (post_init && fail_verify_read)
            return -EIO;
        *value = post_init && verify_ones ? UINT32_MAX : peconf;
        return 0;
    default: assert(!"unexpected PCI dword read");
    }
    return -EIO;
}
static int dm_pci_write_config32(struct udevice *dev, int offset, u32 value)
{
    assert(dev == &device);
    if (offset == 0x800) {
        assert((value & ~BIT(0)) == 0x200);
        if (post_init)
            ++post_wt_writes;
        if (post_init && !(value & BIT(0)) && fail_close)
            return -EIO;
        if (!(post_init && !(value & BIT(0)) && ignore_close))
            wt = value;
        return 0;
    }
    assert(offset == 0x44 && (wt & BIT(0)));
    assert(!post_init); /* verification must never rewrite polarity */
    ++vendor_writes;
    peconf = value;
    return 0;
}
static u32 readl(const void *address)
{
    uintptr_t offset = (const u8 *)address - mmio.bytes;
    assert(offset <= 252 && !(offset & 3));
    if (offset == SDHCI_CAPABILITIES)
        return 0x396a3281;
    if (offset == (SDHCI_HOST_VERSION & ~3))
        return 0x00050000;
    if (offset == SDHCI_CLOCK_CONTROL)
        return 0;
    assert(!"unexpected MMIO read");
    return 0;
}
#include "gl9755.h"
#include "gl9755_pci.h"
static u32 sdhci_readl(struct sdhci_host *host, int offset)
{
    assert(host == &priv.host && host->ops == &gl9755_ops);
    return readl(host->ioaddr + offset);
}
static int sdhci_setup_cfg(struct mmc_config *cfg, struct sdhci_host *host,
                           unsigned f_max, unsigned f_min)
{
    assert(cfg == &plat.cfg && host == &priv.host && !f_max && !f_min);
    assert(host->ops == &gl9755_ops);
    return 0;
}
static int sdhci_probe(struct udevice *dev)
{
    assert(dev == &device && upriv.mmc == &plat.mmc);
    assert(plat.mmc.priv == &priv.host);
    assert(plat.cfg.host_caps == MMC_MODE_4BIT);
    assert(plat.cfg.voltages == (MMC_VDD_32_33 | MMC_VDD_33_34));
    assert(plat.cfg.f_max == 25000000);
    assert(!(wt & BIT(0)));
    ++init_calls;
    post_init = 1;
    if (mismatch)
        peconf &= ~BIT(30);
    return init_error;
}
/* ACTUAL_PROBE */
int main(int argc, char **argv)
{
    assert(argc == 2);
    const char *scenario = argv[1];
    if (strstr(scenario, "init-error"))
        init_error = -ETIMEDOUT;
    if (strstr(scenario, "mismatch"))
        mismatch = 1;
    if (strstr(scenario, "read-error"))
        fail_verify_read = 1;
    if (strstr(scenario, "all-ones"))
        verify_ones = 1;
    if (strstr(scenario, "close-error"))
        fail_close = 1;
    if (strstr(scenario, "close-ignored"))
        ignore_close = 1;
    int expected = init_error ? init_error :
                   mismatch || fail_verify_read || verify_ones || fail_close || ignore_close ? -EIO : 0;
    int result = pci_mmc_probe(&device);
    assert(result == expected);
    assert(init_calls == 1 && verify_reads == 1 && vendor_writes == 1);
    assert(vendor_reads_closed == 0 && vendor_reads_open == 3);
    assert(post_wt_writes == 2);
    assert(!!(wt & BIT(0)) == !!(fail_close || ignore_close));
    puts("Probe and gated verification passed");
    return 0;
}
'''


@unittest.skipUnless(shutil.which("cc") and (PROJECT / "cache/git/uboot.git").is_dir(),
                     "requires a host C compiler and the pinned U-Boot source cache")
class Gl9755Probe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name)
        tree = directory / "uboot"
        module_ast = ast.parse((PROJECT / "sdboot/loader.py").read_text())
        revision = next(ast.literal_eval(node.value)["revision"] for node in module_ast.body
                        if isinstance(node, ast.Assign) and
                        any(isinstance(target, ast.Name) and target.id == "UBOOT"
                            for target in node.targets))
        for name in ("arch/arm/Kconfig", "arch/arm/mach-apple/Kconfig",
                     "arch/arm/mach-apple/board.c", "arch/arm/mach-apple/Makefile",
                     "drivers/pci/pcie_apple.c", "drivers/mmc/pci_mmc.c", "drivers/mmc/Kconfig",
                     "drivers/mmc/sdhci.c", "lib/efi_loader/efi_disk.c", "lib/efi_loader/efi_boottime.c"):
            path = tree / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(subprocess.run(
                ["git", "--git-dir=" + str(PROJECT / "cache/git/uboot.git"),
                 "show", revision + ":" + name], check=True, capture_output=True).stdout)
        (tree / "configs").mkdir()
        subprocess.run(["git", "apply", str(PROJECT / "sdboot/uboot-noio.patch")],
                       cwd=tree, check=True, capture_output=True)
        spec = importlib.util.spec_from_file_location("probe_prepare", PROJECT / "sdboot/prepare_uboot.py")
        prepare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prepare)
        prepare.prepare(tree, PROJECT / "sdboot")
        source = (tree / "drivers/mmc/pci_mmc.c").read_text()
        harness = HARNESS.replace("/* ACTUAL_PROBE */", extract_function(source, "static int pci_mmc_probe("))
        path = directory / "gl9755-probe.c"
        path.write_text(harness)
        cls.executable = directory / "gl9755-probe"
        compiled = subprocess.run([shutil.which("cc"), "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                                   "-I", str(PROJECT / "sdboot"), str(path), "-o", str(cls.executable)],
                                  capture_output=True, text=True)
        if compiled.returncode:
            raise AssertionError(compiled.stderr)

    def check_scenario(self, scenario):
        result = subprocess.run([str(self.executable), scenario], capture_output=True,
                                text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Probe and gated verification passed", result.stdout)

    def test_good_probe_ignores_zero_in_the_closed_vendor_bank(self):
        self.check_scenario("success")

    def test_real_polarity_loss_and_unreadable_vendor_register_fail_probe(self):
        for scenario in ("mismatch", "read-error", "all-ones"):
            with self.subTest(scenario=scenario):
                self.check_scenario(scenario)

    def test_failure_to_close_vendor_gate_fails_probe(self):
        for scenario in ("close-error", "close-ignored"):
            with self.subTest(scenario=scenario):
                self.check_scenario(scenario)

    def test_original_sdhci_init_error_survives_diagnostic_failures(self):
        for scenario in ("init-error", "init-error-mismatch", "init-error-read-error",
                         "init-error-all-ones", "init-error-close-error", "init-error-close-ignored"):
            with self.subTest(scenario=scenario):
                self.check_scenario(scenario)


if __name__ == "__main__":
    unittest.main()
