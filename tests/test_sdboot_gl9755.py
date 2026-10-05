"""Execute the shipped GL9755 callbacks with recording PCI MMIO stubs."""
import ast
import errno
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
ENOMEDIUM = getattr(errno, "ENOMEDIUM", 123)

ACCESSOR_HARNESS = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
struct sdhci_host;
struct sdhci_ops {
    u32 (*read_l)(struct sdhci_host *, int);
    u16 (*read_w)(struct sdhci_host *, int);
    u8 (*read_b)(struct sdhci_host *, int);
    void (*write_l)(struct sdhci_host *, u32, int);
    void (*write_w)(struct sdhci_host *, u16, int);
    void (*write_b)(struct sdhci_host *, u8, int);
};
struct sdhci_host {
    void *ioaddr;
    const struct sdhci_ops *ops;
};

static union { u32 align[64]; u8 bytes[256]; } registers;
static unsigned read_count, last_offset, reset_model;

static u32 readl(const void *address)
{
    uintptr_t base = (uintptr_t)registers.bytes;
    uintptr_t addr = (uintptr_t)address;
    if (addr < base || addr > base + sizeof(registers.bytes) - 4 || (addr & 3)) {
        fputs("Unaligned or out-of-range PCI MMIO read\n", stderr);
        exit(90);
    }
    last_offset = (unsigned)(addr - base);
    ++read_count;
    if (reset_model) {
        if (last_offset != 0x2c)
            exit(91);
        if (read_count >= 3)
            registers.bytes[0x2f] = 0;
    }
    return (u32)registers.bytes[last_offset] |
           ((u32)registers.bytes[last_offset + 1] << 8) |
           ((u32)registers.bytes[last_offset + 2] << 16) |
           ((u32)registers.bytes[last_offset + 3] << 24);
}

/* Model the broken narrow PCI read independently from the 32-bit path. */
static u8 native_readb(const void *address)
{
    (void)address;
    return 0xff;
}

#include "gl9755.h"

int main(int argc, char **argv)
{
    if (argc != 2)
        return 92;
    struct sdhci_host host = { .ioaddr = registers.bytes, .ops = &gl9755_ops };
    for (unsigned i = 0; i < sizeof(registers.bytes); ++i)
        registers.bytes[i] = (u8)(i * 37 + 13);

    if (!strcmp(argv[1], "byte-lanes")) {
        for (int reg = 0; reg < 256; ++reg) {
            read_count = 0;
            if (host.ops->read_b(&host, reg) != registers.bytes[reg] ||
                read_count != 1 || last_offset != ((unsigned)reg & ~3U))
                return 1;
        }
    } else if (!strcmp(argv[1], "word-lanes")) {
        for (int reg = 0; reg < 256; reg += 2) {
            read_count = 0;
            u16 expected = (u16)registers.bytes[reg] |
                           ((u16)registers.bytes[reg + 1] << 8);
            if (host.ops->read_w(&host, reg) != expected ||
                read_count != 1 || last_offset != ((unsigned)reg & ~3U))
                return 2;
        }
    } else if (!strcmp(argv[1], "reset-completion")) {
        registers.bytes[0x2c] = 3;    /* clock enabled and stable */
        registers.bytes[0x2d] = 0xa6;
        registers.bytes[0x2e] = 0x55; /* neighboring timeout control */
        registers.bytes[0x2f] = 1;    /* reset initially active */
        reset_model = 1;
        unsigned polls = 0;
        while (host.ops->read_b(&host, 0x2f) & 1) {
            if (++polls > 5)
                return 3;
        }
        if (read_count != 3 || polls != 2 ||
            !(native_readb(registers.bytes + 0x2f) & 1))
            return 4;
    } else if (!strcmp(argv[1], "named-registers")) {
        registers.bytes[0x2c] = 0x03;
        registers.bytes[0x2d] = 0xa5;
        registers.bytes[0x2e] = 0x87;
        registers.bytes[0x2f] = 0x04;
        registers.bytes[0xfc] = 0x21;
        registers.bytes[0xfd] = 0x43;
        registers.bytes[0xfe] = 0x04;
        registers.bytes[0xff] = 0x97;
        if (host.ops->read_w(&host, 0x2c) != 0xa503 ||
            host.ops->read_b(&host, 0x2f) != 4 ||
            host.ops->read_w(&host, 0xfe) != 0x9704)
            return 5;
    } else if (!strcmp(argv[1], "native-writes")) {
        if (host.ops->write_b || host.ops->write_w || host.ops->write_l ||
            host.ops->read_l || !host.ops->read_b || !host.ops->read_w)
            return 6;
        if (read_count)
            return 7;
    } else {
        return 93;
    }
    puts("GL9755 accessor checks passed");
    return 0;
}
'''


@unittest.skipUnless(shutil.which("cc"), "requires a host C compiler")
class Gl9755Accessors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name)
        source = directory / "gl9755-accessors.c"
        source.write_text(ACCESSOR_HARNESS)
        cls.executable = directory / "gl9755-accessors"
        subprocess.run([shutil.which("cc"), "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                        "-I", str(PROJECT / "sdboot"), str(source),
                        "-o", str(cls.executable)], check=True, capture_output=True, text=True)

    def check_scenario(self, scenario):
        result = subprocess.run([str(self.executable), scenario], check=True,
                                capture_output=True, text=True, timeout=5)
        self.assertIn("GL9755 accessor checks passed", result.stdout)

    def test_all_byte_lanes_use_one_aligned_dword_read(self):
        self.check_scenario("byte-lanes")

    def test_both_word_lanes_use_one_aligned_dword_read(self):
        self.check_scenario("word-lanes")

    def test_clock_reset_and_host_version_read_their_own_lanes(self):
        self.check_scenario("named-registers")

    def test_reset_completes_when_native_byte_reads_would_stay_set(self):
        self.check_scenario("reset-completion")

    def test_writes_keep_native_width_and_full_dword_reads_are_unchanged(self):
        self.check_scenario("native-writes")


RESET_HARNESS = r'''
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef ENOMEDIUM
#define ENOMEDIUM 123
#endif

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define BIT(n) (UINT32_C(1) << (n))
#define IS_ENABLED(x) 1
#define CONFIG_IS_ENABLED(x) 0
#define SDHCI_RESET_ALL 1
#define SDHCI_RESET_CMD 2
#define SDHCI_SOFTWARE_RESET 0x2f
#define SDHCI_CLOCK_CONTROL 0x2c
#define SDHCI_CLOCK_INT_EN 1
#define SDHCI_CLOCK_INT_STABLE 2
#define SDHCI_HOST_CONTROL2 0x3e
#define SDHCI_PRESENT_STATE 0x24
#define SDHCI_CARD_PRESENT BIT(16)
#define SDHCI_CARD_STATE_STABLE BIT(17)
#define SDHCI_CARD_DETECT_PIN_LEVEL BIT(18)
#define SDHCI_POWER_CONTROL 0x29
#define MMC_CAP_NONREMOVABLE BIT(16)
#define MMC_CAP_NEEDS_POLL BIT(17)
#define MMC_CAP_CD_ACTIVE_HIGH BIT(18)
#define SDHCI_QUIRK_32BIT_DMA_ADDR 1
#define SDHCI_INT_DATA_MASK 0x02ff0000
#define SDHCI_INT_CMD_MASK 0x000f0001
#define SDHCI_INT_ENABLE 0x34
#define SDHCI_SIGNAL_ENABLE 0x38
#define log_warning printf
#define log_err printf

struct sdhci_host;
struct sdhci_ops {
    u16 (*read_w)(struct sdhci_host *, int);
    u8 (*read_b)(struct sdhci_host *, int);
    int (*get_cd)(struct sdhci_host *);
};
struct sdhci_host {
    void *ioaddr;
    const struct sdhci_ops *ops;
    unsigned clock, quirks;
    void *align_buffer;
};
struct mmc_config { unsigned voltages, host_caps; };
struct mmc { struct sdhci_host *priv; struct mmc_config *cfg; };
struct udevice { struct mmc *mmc; };
static struct mmc *mmc_get_mmc_dev(struct udevice *dev) { return dev->mmc; }
static int fake_fls(unsigned n) { return n ? 32 - __builtin_clz(n) : 0; }
#define fls fake_fls
static void *memalign(unsigned alignment, unsigned size)
{
    (void)alignment;
    (void)size;
    fputs("Unexpected DMA allocation\n", stderr);
    exit(90);
}

static union { u32 align[64]; u8 bytes[256]; } registers;
static unsigned clock_reads, reset_reads, reset_started, elapsed, power_calls;
static unsigned clock_timeout, reset_timeout, unreadable;
static unsigned card_mode, card_delay, reset_completed_at, card_ready_logged;

static u32 card_state(void)
{
    switch (card_mode) {
    case 1: return SDHCI_CARD_STATE_STABLE; /* stable, absent */
    case 2: return 0; /* still debouncing */
    case 3: return UINT32_MAX; /* disconnected register window */
    case 4:
        if (elapsed - reset_completed_at < card_delay)
            return SDHCI_CARD_DETECT_PIN_LEVEL; /* raw pin is not enough */
        if (!card_ready_logged++)
            printf("EVENT card-ready %u\n", elapsed);
        break;
    case 5: return SDHCI_CARD_PRESENT; /* inserted bit without stability */
    case 6: return SDHCI_CARD_DETECT_PIN_LEVEL | SDHCI_CARD_STATE_STABLE;
    }
    return SDHCI_CARD_PRESENT | SDHCI_CARD_STATE_STABLE;
}

static u32 readl(const void *address)
{
    uintptr_t base = (uintptr_t)registers.bytes, addr = (uintptr_t)address;
    if (addr < base || addr > base + 252 || (addr & 3))
        exit(91);
    unsigned reg = (unsigned)(addr - base);
    if (reg == SDHCI_PRESENT_STATE)
        return card_state();
    if (reg == SDHCI_CLOCK_CONTROL) {
        if (unreadable)
            return UINT32_MAX;
        if (reset_started) {
            if (++reset_reads >= 3 && !reset_timeout) {
                if (registers.bytes[SDHCI_SOFTWARE_RESET])
                    reset_completed_at = elapsed;
                registers.bytes[SDHCI_SOFTWARE_RESET] = 0;
            }
        } else if (++clock_reads >= 2 && !clock_timeout) {
            registers.bytes[SDHCI_CLOCK_CONTROL] |= SDHCI_CLOCK_INT_STABLE;
        }
    }
    return (u32)registers.bytes[reg] | ((u32)registers.bytes[reg + 1] << 8) |
           ((u32)registers.bytes[reg + 2] << 16) | ((u32)registers.bytes[reg + 3] << 24);
}

#include "gl9755.h"

static u32 sdhci_readl(struct sdhci_host *host, int reg) { return readl(host->ioaddr + reg); }
static u16 sdhci_readw(struct sdhci_host *host, int reg) { return host->ops->read_w(host, reg); }
static u8 sdhci_readb(struct sdhci_host *host, int reg) { return host->ops->read_b(host, reg); }

static void sdhci_writew(struct sdhci_host *host, u16 value, int reg)
{
    (void)host;
    if (reg != SDHCI_CLOCK_CONTROL && reg != SDHCI_HOST_CONTROL2)
        exit(92);
    printf("EVENT writew %u %u\n", reg, value);
    registers.bytes[reg] = value;
    registers.bytes[reg + 1] = value >> 8;
}

static void sdhci_writeb(struct sdhci_host *host, u8 value, int reg)
{
    (void)host;
    if (reg != SDHCI_SOFTWARE_RESET)
        exit(93);
    printf("EVENT writeb %u %u\n", reg, value);
    registers.bytes[reg] = value;
    reset_started = 1;
    if (value & SDHCI_RESET_ALL) {
        registers.bytes[SDHCI_HOST_CONTROL2] = 0;
        registers.bytes[SDHCI_HOST_CONTROL2 + 1] = 0;
    }
}

static void sdhci_writel(struct sdhci_host *host, u32 value, int reg)
{
    (void)host;
    if (reg != SDHCI_INT_ENABLE && reg != SDHCI_SIGNAL_ENABLE)
        exit(94);
    printf("EVENT writel %u %u\n", reg, value);
}

static void sdhci_set_power(struct sdhci_host *host, unsigned vdd)
{
    (void)host;
    if (card_state() != (SDHCI_CARD_PRESENT | SDHCI_CARD_STATE_STABLE)) {
        fputs("Card power enabled before debounced presence\n", stderr);
        exit(96);
    }
    ++power_calls;
    printf("EVENT power %u\n", vdd);
}
static void udelay(unsigned us) { elapsed += us; }
static void mdelay(unsigned ms) { elapsed += ms * 1000; }

#include "gl9755_card.h"

/* ACTUAL_RESET */
/* ACTUAL_INIT */
/* ACTUAL_PROBE */
/* ACTUAL_GET_CD */

int main(int argc, char **argv)
{
    if (argc != 2)
        return 95;
    const char *scenario = argv[1];
    struct sdhci_host host = {
        .ioaddr = registers.bytes, .ops = &gl9755_ops, .clock = 25000000
    };
    struct mmc_config cfg = { .voltages = BIT(20) | BIT(21) };
    struct mmc mmc = { .priv = &host, .cfg = &cfg };
    struct udevice dev = { .mmc = &mmc };
    registers.bytes[SDHCI_HOST_CONTROL2 + 1] = 0x10;
    clock_timeout = strstr(scenario, "clock-timeout") != NULL;
    reset_timeout = strstr(scenario, "reset-timeout") != NULL;
    unreadable = strstr(scenario, "unreadable") != NULL && !strstr(scenario, "card");
    if (strstr(scenario, "card-absent"))
        card_mode = 1;
    if (strstr(scenario, "card-unstable"))
        card_mode = 2;
    if (strstr(scenario, "card-unreadable"))
        card_mode = 3;
    if (strstr(scenario, "card-delayed")) {
        card_mode = 4;
        card_delay = 300000;
    }
    if (strstr(scenario, "card-deadline")) {
        card_mode = 4;
        card_delay = 2000000;
    }
    if (strstr(scenario, "card-too-late")) {
        card_mode = 4;
        card_delay = 2001000;
    }
    if (strstr(scenario, "card-present-unstable"))
        card_mode = 5;
    if (strstr(scenario, "card-raw-pin"))
        card_mode = 6;
    if (strstr(scenario, "force-caps"))
        cfg.host_caps = MMC_CAP_NONREMOVABLE | MMC_CAP_NEEDS_POLL | MMC_CAP_CD_ACTIVE_HIGH;
    int result;
    if (!strncmp(scenario, "probe", 5))
        result = sdhci_probe(&dev);
    else if (!strncmp(scenario, "getcd", 5))
        result = sdhci_get_cd(&dev);
    else
        result = sdhci_reset(&host, !strcmp(scenario, "command") ? SDHCI_RESET_CMD : SDHCI_RESET_ALL);
    printf("STATE %d %u %u %u %u\n", result, host.clock,
           (unsigned)registers.bytes[SDHCI_HOST_CONTROL2] |
           ((unsigned)registers.bytes[SDHCI_HOST_CONTROL2 + 1] << 8), elapsed, power_calls);
    return 0;
}
'''


def extract_function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


@unittest.skipUnless(shutil.which("cc") and (PROJECT / "cache/git/uboot.git").is_dir(),
                     "requires a host C compiler and the pinned U-Boot source cache")
class Gl9755Reset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name)
        tree = directory / "uboot"
        # Read the pin from the actual recipe without importing its builder or
        # accessing the network. All source reconstruction remains temporary.
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
            content = subprocess.run(["git", "--git-dir=" + str(PROJECT / "cache/git/uboot.git"),
                                      "show", revision + ":" + name],
                                     check=True, capture_output=True).stdout
            path.write_bytes(content)
        (tree / "configs").mkdir()
        subprocess.run(["git", "apply", str(PROJECT / "sdboot/uboot-noio.patch")],
                       cwd=tree, check=True, capture_output=True)
        spec = importlib.util.spec_from_file_location("gl9755_prepare_uboot", PROJECT / "sdboot/prepare_uboot.py")
        prepare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prepare)
        prepare.prepare(tree, PROJECT / "sdboot")
        cls.mmc_source = (tree / "drivers/mmc/pci_mmc.c").read_text()
        source = (tree / "drivers/mmc/sdhci.c").read_text()
        cls.sdhci_source = source
        harness = RESET_HARNESS
        for marker, signature in (("RESET", "static int sdhci_reset("),
                                  ("INIT", "static int sdhci_init("),
                                  ("PROBE", "int sdhci_probe("),
                                  ("GET_CD", "static int sdhci_get_cd(")):
            harness = harness.replace("/* ACTUAL_" + marker + " */", extract_function(source, signature))
        path = directory / "gl9755-reset.c"
        path.write_text(harness)
        cls.executable = directory / "gl9755-reset"
        compiled = subprocess.run([shutil.which("cc"), "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                                   "-I", str(PROJECT / "sdboot"), str(path), "-o", str(cls.executable)],
                                  capture_output=True, text=True)
        if compiled.returncode:
            raise AssertionError(compiled.stderr)

    def execute(self, scenario):
        run = subprocess.run([str(self.executable), scenario], check=True,
                             capture_output=True, text=True, timeout=5)
        lines = run.stdout.splitlines()
        state = tuple(map(int, next(line.split()[1:] for line in lines if line.startswith("STATE "))))
        events = [line.removeprefix("EVENT ") for line in lines if line.startswith("EVENT ")]
        return state, events

    def test_accessor_ops_installed_before_first_host_register_access(self):
        probe = extract_function(self.mmc_source, "static int pci_mmc_probe(")
        start = probe.index("host->ops = &gl9755_ops;")
        for operation in ("sdhci_readl(", "sdhci_setup_cfg(", "sdhci_probe("):
            self.assertLess(start, probe.index(operation))

    def test_full_reset_enables_clock_before_reset_and_restores_v4_afterwards(self):
        state, events = self.execute("reset")
        self.assertEqual(state, (0, 0, 4096, 2010, 0))
        self.assertEqual(events, ["writew 44 1", "writew 62 4096", "writeb 47 1", "writew 62 4096"])

    def test_command_only_reset_does_not_reconfigure_clock_or_mode(self):
        state, events = self.execute("command")
        self.assertEqual(state, (0, 25000000, 4096, 2000, 0))
        self.assertEqual(events, ["writeb 47 2"])

    def test_clock_failures_stop_before_reset(self):
        for scenario, error, elapsed in (("clock-timeout", errno.ETIMEDOUT, 20000),
                                         ("unreadable", errno.EIO, 0)):
            with self.subTest(scenario=scenario):
                state, events = self.execute(scenario)
                self.assertEqual(state, (-error, 25000000, 4096, elapsed, 0))
                self.assertEqual(events, ["writew 44 1"])

    def test_reset_timeout_is_bounded_and_does_not_claim_reinitialization(self):
        state, events = self.execute("reset-timeout")
        self.assertEqual(state, (-errno.ETIMEDOUT, 25000000, 0, 100010, 0))
        self.assertEqual(events, ["writew 44 1", "writew 62 4096", "writeb 47 1"])

    def test_probe_propagates_every_reset_failure_before_card_power_or_interrupts(self):
        for scenario, error in (("probe-clock-timeout", errno.ETIMEDOUT),
                                ("probe-unreadable", errno.EIO),
                                ("probe-reset-timeout", errno.ETIMEDOUT)):
            with self.subTest(scenario=scenario):
                state, events = self.execute(scenario)
                self.assertEqual(state[0], -error)
                self.assertEqual(state[4], 0)
                self.assertFalse(any(event.startswith(("power ", "writel ")) for event in events))

    def test_probe_powers_card_only_after_successful_reset(self):
        state, events = self.execute("probe")
        self.assertEqual(state, (0, 0, 4096, 2010, 1))
        self.assertEqual(events[:5], ["writew 44 1", "writew 62 4096", "writeb 47 1",
                                      "writew 62 4096", "power 21"])
        self.assertEqual(events[5:], [f"writel 52 {0x02ff0000 | 0x000f0001}", "writel 56 0"])

    def test_probe_waits_for_debounced_insertion_before_power(self):
        state, events = self.execute("probe-card-delayed")
        self.assertEqual(state, (0, 0, 4096, 302010, 1))
        ready = events.index("card-ready 302010")
        self.assertGreater(ready, events.index("writew 62 4096", 2))
        self.assertEqual(events[ready + 1:], ["power 21",
                         f"writel 52 {0x02ff0000 | 0x000f0001}", "writel 56 0"])

    def test_probe_accepts_presence_at_the_deadline_without_an_extra_delay(self):
        state, events = self.execute("probe-card-deadline")
        self.assertEqual(state, (0, 0, 4096, 2002010, 1))
        self.assertIn("card-ready 2002010", events)

    def test_probe_card_failures_stop_before_power_or_interrupts(self):
        for scenario, error, elapsed in (
                ("probe-card-absent", ENOMEDIUM, 2002010),
                ("probe-card-raw-pin", ENOMEDIUM, 2002010),
                ("probe-card-unstable", errno.ETIMEDOUT, 2002010),
                ("probe-card-present-unstable", errno.ETIMEDOUT, 2002010),
                ("probe-card-too-late", errno.ETIMEDOUT, 2002010),
                ("probe-card-unreadable", errno.EIO, 2010)):
            with self.subTest(scenario=scenario):
                state, events = self.execute(scenario)
                self.assertEqual(state, (-error, 0, 4096, elapsed, 0))
                self.assertEqual(events, ["writew 44 1", "writew 62 4096",
                                          "writeb 47 1", "writew 62 4096"])

    def test_actual_get_cd_requires_debounced_presence_and_rejects_all_ones(self):
        for scenario, present in (("getcd", 1), ("getcd-card-absent", 0),
                                  ("getcd-card-raw-pin", 0), ("getcd-card-unstable", 0),
                                  ("getcd-card-present-unstable", 0),
                                  ("getcd-card-unreadable", 0),
                                  ("getcd-card-absent-force-caps", 0),
                                  ("getcd-card-unreadable-force-caps", 0)):
            with self.subTest(scenario=scenario):
                state, events = self.execute(scenario)
                self.assertEqual(state, (present, 25000000, 4096, 0, 0))
                self.assertEqual(events, [])

    def test_native_get_cd_dispatches_before_generic_gpio_and_forced_presence(self):
        function = extract_function(self.sdhci_source, "static int sdhci_get_cd(")
        callback = function.index("return gl9755_get_cd(host);")
        for fallback in ("MMC_CAP_NONREMOVABLE", "MMC_CAP_NEEDS_POLL", "dm_gpio_get_value("):
            self.assertLess(callback, function.index(fallback))


if __name__ == "__main__":
    unittest.main()
