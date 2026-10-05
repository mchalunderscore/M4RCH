"""Execute the prepared U-Boot clock/IOS functions against an SDHCI model."""
import ast
import errno
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


def extract_function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


HARNESS = r'''
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define BIT(n) (UINT32_C(1) << (n))
#define IS_ENABLED(x) 1
#define CONFIG_IS_ENABLED(x) 0
#define SDHCI_PRESENT_STATE 0x24
#define SDHCI_CMD_INHIBIT 1
#define SDHCI_DATA_INHIBIT 2
#define SDHCI_HOST_CONTROL 0x28
#define SDHCI_POWER_CONTROL 0x29
#define SDHCI_CLOCK_CONTROL 0x2c
#define SDHCI_HOST_CONTROL2 0x3e
#define SDHCI_DIVIDER_SHIFT 8
#define SDHCI_DIVIDER_HI_SHIFT 6
#define SDHCI_DIV_MASK 0xff
#define SDHCI_DIV_MASK_LEN 8
#define SDHCI_DIV_HI_MASK 0x300
#define SDHCI_PROG_CLOCK_MODE BIT(5)
#define SDHCI_CLOCK_PLL_EN BIT(3)
#define SDHCI_CLOCK_CARD_EN BIT(2)
#define SDHCI_CLOCK_INT_STABLE BIT(1)
#define SDHCI_CLOCK_INT_EN BIT(0)
#define SDHCI_SPEC_300 2
#define SDHCI_SPEC_410 4
#define SDHCI_CTRL_V4_MODE BIT(12)
#define SDHCI_MAX_DIV_SPEC_300 2046
#define SDHCI_MAX_DIV_SPEC_200 256
#define SDHCI_GET_VERSION(host) ((host)->version & 0xff)
#define SDHCI_CTRL_4BITBUS BIT(1)
#define SDHCI_CTRL_HISPD BIT(2)
#define SDHCI_CTRL_8BITBUS BIT(5)
#define SDHCI_QUIRK_NO_HISPD_BIT BIT(3)
#define SDHCI_QUIRK_BROKEN_HISPD_MODE BIT(5)
#define SDHCI_QUIRK_USE_WIDE8 BIT(8)
#define log_err printf
enum { MMC_LEGACY, MMC_HS, SD_HS, MMC_HS_52, MMC_DDR_52, MMC_HS_200,
       MMC_HS_400, MMC_HS_400_ES, UHS_SDR25, UHS_SDR50, UHS_SDR104, UHS_DDR50 };

struct sdhci_host;
struct sdhci_ops {
    int (*set_delay)(struct sdhci_host *);
    int (*config_dll)(struct sdhci_host *, unsigned, bool);
    void (*set_clock)(struct sdhci_host *, unsigned);
    void (*set_control_reg)(struct sdhci_host *);
    int (*set_ios_post)(struct sdhci_host *);
};
struct sdhci_host {
    const struct sdhci_ops *ops;
    unsigned max_clk, clk_mul, version, clock, quirks;
};
struct mmc {
    struct sdhci_host *priv;
    unsigned clock, bus_width, selected_mode;
    bool clk_disable;
};
struct udevice { struct mmc *mmc; };
static struct mmc *mmc_get_mmc_dev(struct udevice *dev) { return dev->mmc; }

static u16 clock_control, host_control2 = SDHCI_CTRL_V4_MODE;
static u8 host_control = 0xa0;
static unsigned elapsed, phase, phase_reads, timeout_phase, unreadable_phase;
static unsigned present_state, bus_writes, post_calls;

static void udelay(unsigned us) { elapsed += us; }
static u32 sdhci_readl(struct sdhci_host *host, int reg)
{
    (void)host;
    if (reg == SDHCI_PRESENT_STATE)
        return present_state;
    if (reg == SDHCI_CLOCK_CONTROL)
        return clock_control;
    exit(90);
}
static u16 sdhci_readw(struct sdhci_host *host, int reg)
{
    (void)host;
    if (reg == SDHCI_HOST_CONTROL2)
        return host_control2;
    if (reg != SDHCI_CLOCK_CONTROL)
        exit(91);
    if (phase == unreadable_phase && phase)
        return 0xffff;
    if (phase && phase < 3 && ++phase_reads >= 2 && phase != timeout_phase) {
        if (!(clock_control & SDHCI_CLOCK_INT_STABLE))
            printf("EVENT stable %u\n", phase);
        clock_control |= SDHCI_CLOCK_INT_STABLE;
    }
    return clock_control;
}
static u8 sdhci_readb(struct sdhci_host *host, int reg)
{
    (void)host;
    if (reg == SDHCI_HOST_CONTROL)
        return host_control;
    if (reg == SDHCI_POWER_CONTROL)
        return 0xbf;
    exit(92);
}
static void sdhci_writew(struct sdhci_host *host, u16 value, int reg)
{
    (void)host;
    if (reg != SDHCI_CLOCK_CONTROL)
        exit(93);
    printf("EVENT clock %u\n", value);
    clock_control = value;
    phase_reads = 0;
    phase = !value ? 0 : value & SDHCI_CLOCK_CARD_EN ? 3 :
            value & SDHCI_CLOCK_PLL_EN ? 2 : 1;
}
static void sdhci_writeb(struct sdhci_host *host, u8 value, int reg)
{
    (void)host;
    if (reg != SDHCI_HOST_CONTROL)
        exit(94);
    printf("EVENT bus %u\n", value);
    host_control = value;
    ++bus_writes;
}
static int post_ios(struct sdhci_host *host)
{
    (void)host;
    ++post_calls;
    return 0;
}

/* ACTUAL_CLOCK */
/* ACTUAL_IOS */

int main(int argc, char **argv)
{
    if (argc != 2)
        return 95;
    const char *scenario = argv[1];
    struct sdhci_ops ops = { .set_ios_post = post_ios };
    struct sdhci_host host = { .ops = &ops, .max_clk = 50000000, .version = 5 };
    struct mmc mmc = { .priv = &host, .clock = 400000, .bus_width = 1 };
    struct udevice dev = { .mmc = &mmc };
    if (strstr(scenario, "int-timeout"))
        timeout_phase = 1;
    if (strstr(scenario, "pll-timeout"))
        timeout_phase = 2;
    if (strstr(scenario, "pll-unreadable"))
        unreadable_phase = 2;
    if (strstr(scenario, "int-unreadable"))
        unreadable_phase = 1;
    if (!strcmp(scenario, "high-divider"))
        host.max_clk = 500000000;
    if (!strcmp(scenario, "spec-400"))
        host.version = 3;
    if (!strcmp(scenario, "spec-410"))
        host.version = 4;
    if (!strcmp(scenario, "v4-off"))
        host_control2 = 0;
    if (!strcmp(scenario, "off"))
        mmc.clock = 0;
    if (!strcmp(scenario, "ios-disable-busy")) {
        host.clock = mmc.clock;
        mmc.clk_disable = true;
        present_state = SDHCI_CMD_INHIBIT;
    }
    int result = !strncmp(scenario, "ios-", 4) ? sdhci_set_ios(&dev) :
                 sdhci_set_clock(&mmc, mmc.clock);
    printf("STATE %d %u %u %u %u\n", result, clock_control, elapsed,
           bus_writes, post_calls);
    return 0;
}
'''


COMMAND_HARNESS = r'''
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef unsigned long ulong;
#ifndef ECOMM
#define ECOMM 70
#endif
#define BIT(n) (UINT32_C(1) << (n))
#define IS_ENABLED(x) 1
#define CONFIG_IS_ENABLED(x) 0
#define log_warning printf
/* ACTUAL_REGISTER_CONSTANTS */
#define MMC_CMD_STOP_TRANSMISSION 12
#define MMC_CMD_SEND_TUNING_BLOCK 19
#define MMC_CMD_SEND_TUNING_BLOCK_HS200 21
#define MMC_RSP_PRESENT BIT(0)
#define MMC_RSP_136 BIT(1)
#define MMC_RSP_CRC BIT(2)
#define MMC_RSP_BUSY BIT(3)
#define MMC_RSP_OPCODE BIT(4)
#define MMC_DATA_READ 1
#define USE_DMA 1
#define SDHCI_CMD_DEFAULT_TIMEOUT 100
#define SDHCI_CMD_MAX_TIMEOUT 3200
#define SDHCI_READ_STATUS_TIMEOUT 1000
struct sdhci_host { unsigned start_addr, quirks, flags; void *align_buffer; };
struct mmc { struct sdhci_host *priv; };
struct mmc_cmd { unsigned cmdidx, cmdarg, resp_type; };
struct mmc_data { unsigned blocks, blocksize, flags; void *dest; };
struct blk_desc { int devnum; };
static struct blk_desc block = { .devnum = 0 };
static struct blk_desc *mmc_get_blk_desc(struct mmc *mmc) { (void)mmc; return &block; }
static unsigned present, status_reads, commands, reset_calls, reset_failure, done_calls;
static unsigned status_success, milliseconds;
static ulong get_timer(ulong start) { milliseconds += 100; return milliseconds - start; }
static void udelay(unsigned us) { milliseconds += us / 1000; }
static u32 sdhci_readl(struct sdhci_host *host, int reg)
{
    (void)host;
    if (reg == SDHCI_PRESENT_STATE)
        return present;
    if (reg == SDHCI_INT_ENABLE)
        return SDHCI_INT_RESPONSE;
    if (reg == SDHCI_INT_STATUS) {
        if (++status_reads > 30)
            exit(90);
        return status_success ? SDHCI_INT_RESPONSE : 0;
    }
    exit(91);
}
static u16 sdhci_readw(struct sdhci_host *host, int reg)
{
    (void)host;
    if (reg == SDHCI_CLOCK_CONTROL)
        return 0x3f0f;
    if (reg == SDHCI_HOST_CONTROL2)
        return BIT(12);
    exit(92);
}
static u8 sdhci_readb(struct sdhci_host *host, int reg)
{
    (void)host;
    if (reg != SDHCI_POWER_CONTROL)
        exit(93);
    return 0xbf;
}
static void sdhci_writel(struct sdhci_host *host, u32 value, int reg)
{
    (void)host;
    (void)value;
    if (reg != SDHCI_INT_STATUS && reg != SDHCI_ARGUMENT)
        exit(94);
}
static void sdhci_writew(struct sdhci_host *host, u16 value, int reg)
{
    (void)host;
    if (reg != SDHCI_COMMAND)
        exit(95);
    printf("EVENT command %u\n", SDHCI_GET_CMD(value));
    ++commands;
    present |= SDHCI_CMD_INHIBIT;
}
static void sdhci_writeb(struct sdhci_host *host, u8 value, int reg)
{
    (void)host; (void)value; (void)reg;
    exit(96);
}
static int sdhci_reset(struct sdhci_host *host, u8 mask)
{
    (void)host;
    printf("EVENT reset %u\n", mask);
    if (++reset_calls == reset_failure)
        return -EIO;
    if (mask & SDHCI_RESET_CMD)
        present &= ~SDHCI_CMD_INHIBIT;
    if (mask & SDHCI_RESET_DATA)
        present &= ~SDHCI_DATA_INHIBIT;
    return 0;
}
static void sdhci_prepare_dma(struct sdhci_host *host, struct mmc_data *data,
                              int *aligned, int bytes)
{
    (void)host; (void)data; (void)aligned; (void)bytes; exit(97);
}
static void sdhci_cmd_done(struct sdhci_host *host, struct mmc_cmd *cmd)
{
    (void)host; (void)cmd; ++done_calls; present = 0;
}
static int sdhci_transfer_data(struct sdhci_host *host, struct mmc_data *data)
{
    (void)host; (void)data; exit(98);
}
/* ACTUAL_COMMAND */
int main(int argc, char **argv)
{
    if (argc != 2)
        return 99;
    struct sdhci_host host = {0};
    struct mmc mmc = {.priv = &host};
    struct mmc_cmd cmd = {.cmdidx = 0, .cmdarg = 0};
    if (!strcmp(argv[1], "cmd-reset-failure"))
        reset_failure = 1;
    if (!strcmp(argv[1], "data-reset-failure"))
        reset_failure = 2;
    if (!strcmp(argv[1], "success"))
        status_success = 1;
    int result = sdhci_send_command(&mmc, &cmd, NULL), second = 999;
    if (!strcmp(argv[1], "retry")) {
        status_success = 1;
        second = sdhci_send_command(&mmc, &cmd, NULL);
    }
    printf("STATE %d %u %u %u %d\n", result, commands, reset_calls, done_calls, second);
    return 0;
}
'''


@unittest.skipUnless(shutil.which("cc") and (PROJECT / "cache/git/uboot.git").is_dir(),
                     "requires a host C compiler and the pinned U-Boot source cache")
class Gl9755Clock(unittest.TestCase):
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
        spec = importlib.util.spec_from_file_location("clock_prepare", PROJECT / "sdboot/prepare_uboot.py")
        prepare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prepare)
        prepare.prepare(tree, PROJECT / "sdboot")
        source = (tree / "drivers/mmc/sdhci.c").read_text()
        # Select the DM declaration, just as this project's U-Boot config does.
        source = source.replace("#else\nstatic int sdhci_set_ios(struct mmc *mmc)\n{\n#endif", "#endif")
        harness = HARNESS.replace("/* ACTUAL_CLOCK */", extract_function(source, "int sdhci_set_clock("))
        harness = harness.replace("/* ACTUAL_IOS */", extract_function(source, "static int sdhci_set_ios(struct udevice *dev)"))
        # The extraction starts after the opening #ifdef CONFIG_DM_MMC.
        harness = harness.replace("struct mmc *mmc = mmc_get_mmc_dev(dev);\n#endif", "struct mmc *mmc = mmc_get_mmc_dev(dev);")
        path = directory / "gl9755-clock.c"
        path.write_text(harness)
        cls.executable = directory / "gl9755-clock"
        compiled = subprocess.run([shutil.which("cc"), "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                                   str(path), "-o", str(cls.executable)], capture_output=True, text=True)
        if compiled.returncode:
            raise AssertionError(compiled.stderr)
        header = subprocess.run(["git", "--git-dir=" + str(PROJECT / "cache/git/uboot.git"),
                                 "show", revision + ":include/sdhci.h"],
                                check=True, capture_output=True, text=True).stdout
        constants = "\n".join(re.findall(r"^#define\s+SDHCI_[^\n]*", header.replace("\\\n", " "), re.M))
        command = extract_function(source, "static int sdhci_send_command(struct mmc *mmc,")
        command = command.replace("#endif\n", "", 1)
        harness = COMMAND_HARNESS.replace("/* ACTUAL_REGISTER_CONSTANTS */", constants)
        harness = harness.replace("/* ACTUAL_COMMAND */", command)
        path = directory / "gl9755-command.c"
        path.write_text(harness)
        cls.command_executable = directory / "gl9755-command"
        compiled = subprocess.run([shutil.which("cc"), "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                                   str(path), "-o", str(cls.command_executable)], capture_output=True, text=True)
        if compiled.returncode:
            raise AssertionError(compiled.stderr)

    def execute(self, scenario, *, command=False):
        executable = self.command_executable if command else self.executable
        run = subprocess.run([str(executable), scenario], check=True,
                             capture_output=True, text=True, timeout=5)
        lines = run.stdout.splitlines()
        state = tuple(map(int, next(line.split()[1:] for line in lines if line.startswith("STATE "))))
        events = [line.removeprefix("EVENT ") for line in lines if line.startswith("EVENT ")]
        return state, events

    def test_v4_waits_for_both_handshakes_before_card_clock(self):
        state, events = self.execute("normal")
        self.assertEqual(state, (0, 0x3f0f, 1010, 0, 0))
        self.assertEqual(events, ["clock 0", f"clock {0x3f01}", "stable 1",
                                  f"clock {0x3f09}", "stable 2", f"clock {0x3f0f}"])

    def test_split_divider_bits_survive_both_handshakes(self):
        state, events = self.execute("high-divider")
        self.assertEqual(state[0:2], (0, 0x718f))
        self.assertEqual(events, ["clock 0", f"clock {0x7181}", "stable 1",
                                  f"clock {0x7189}", "stable 2", f"clock {0x718f}"])

    def test_pll_applies_to_spec410_and_requires_v4_mode(self):
        state, events = self.execute("spec-410")
        self.assertEqual(state[0:2], (0, 0x3f0f))
        self.assertIn("stable 2", events)
        for scenario in ("spec-400", "v4-off"):
            with self.subTest(scenario=scenario):
                state, events = self.execute(scenario)
                self.assertEqual(state, (0, 0x3f07, 1000, 0, 0))
                self.assertEqual(events, ["clock 0", f"clock {0x3f01}", "stable 1", f"clock {0x3f07}"])

    def test_pll_timeout_is_bounded_and_never_enables_card_clock(self):
        state, events = self.execute("pll-timeout")
        self.assertEqual(state, (-errno.ETIMEDOUT, 0x3f09, 151000, 0, 0))
        self.assertEqual(events, ["clock 0", f"clock {0x3f01}", "stable 1", f"clock {0x3f09}"])

    def test_unreadable_pll_status_fails_without_enabling_card_clock(self):
        state, events = self.execute("pll-unreadable")
        self.assertEqual(state, (-errno.EIO, 0x3f09, 1000, 0, 0))
        self.assertEqual(events, ["clock 0", f"clock {0x3f01}", "stable 1", f"clock {0x3f09}"])

    def test_internal_clock_timeout_never_starts_pll_or_card_clock(self):
        state, events = self.execute("int-timeout")
        self.assertEqual(state, (-errno.EBUSY, 0x3f01, 20000, 0, 0))
        self.assertEqual(events, ["clock 0", f"clock {0x3f01}"])

    def test_initial_all_ones_status_does_not_masquerade_as_clock_stable(self):
        state, events = self.execute("int-unreadable")
        self.assertEqual(state, (-errno.EIO, 0x3f01, 0, 0, 0))
        self.assertEqual(events, ["clock 0", f"clock {0x3f01}"])

    def test_disable_clock_needs_neither_handshake(self):
        state, events = self.execute("off")
        self.assertEqual(state, (0, 0, 0, 0, 0))
        self.assertEqual(events, ["clock 0"])

    def test_ios_clock_failures_propagate_before_bus_configuration_or_post_hook(self):
        for scenario, error in (("ios-pll-timeout", errno.ETIMEDOUT),
                                ("ios-pll-unreadable", errno.EIO),
                                ("ios-int-timeout", errno.EBUSY),
                                ("ios-int-unreadable", errno.EIO),
                                ("ios-disable-busy", errno.EBUSY)):
            with self.subTest(scenario=scenario):
                state, events = self.execute(scenario)
                self.assertEqual(state[0], -error)
                self.assertEqual(state[3:], (0, 0))
                self.assertFalse(any(event.startswith("bus ") for event in events))

    def test_ios_success_configures_bus_only_after_card_clock(self):
        state, events = self.execute("ios-normal")
        self.assertEqual(state, (0, 0x3f0f, 1010, 1, 1))
        self.assertEqual(events[-2:], [f"clock {0x3f0f}", "bus 128"])

    def test_command_timeout_cleans_up_both_engines_and_preserves_timeout_result(self):
        state, events = self.execute("timeout", command=True)
        self.assertEqual(state, (-errno.ETIMEDOUT, 1, 2, 0, 999))
        self.assertEqual(events, ["command 0", "reset 2", "reset 4"])

    def test_command_cleanup_failure_is_propagated(self):
        for scenario, resets in (("cmd-reset-failure", 1), ("data-reset-failure", 2)):
            with self.subTest(scenario=scenario):
                state, events = self.execute(scenario, command=True)
                self.assertEqual(state, (-errno.EIO, 1, resets, 0, 999))
                self.assertEqual(events, ["command 0", "reset 2", "reset 4"][:resets + 1])

    def test_successful_command_needs_no_reset(self):
        state, events = self.execute("success", command=True)
        self.assertEqual(state, (0, 1, 0, 1, 999))
        self.assertEqual(events, ["command 0"])

    def test_retry_after_timeout_does_not_encounter_stale_command_inhibit(self):
        state, events = self.execute("retry", command=True)
        self.assertEqual(state, (-errno.ETIMEDOUT, 2, 2, 1, 0))
        self.assertEqual(events, ["command 0", "reset 2", "reset 4", "command 0"])


if __name__ == "__main__":
    unittest.main()
