"""Execute the actual SD link helper against an allowlisted fake MMIO map.

These tests exercise handoff validation and write ordering, not physical link
training. The host harness supplies only U-Boot's MMIO/delay/poll primitives.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint32_t u32;
#define __iomem
#define BIT(n) (UINT32_C(1) << (n))
#define GENMASK(hi, lo) ((UINT32_MAX << (lo)) & (UINT32_MAX >> (31 - (hi))))
/* Register definitions from the pinned U-Boot Apple PCIe driver. */
#define PORT_LTSSMCTL 0x80
#define PORT_LTSSMCTL_START BIT(0)
#define PORT_LINKSTS 0x208
#define PORT_LINKSTS_UP BIT(0)
#define PORT_LINKSTS_BUSY BIT(2)
#define PORT_APPCLK 0x800
#define PORT_APPCLK_EN BIT(0)
#define PORT_APPCLK_CGDIS BIT(8)
#define PORT_STATUS 0x804
#define PORT_STATUS_READY BIT(0)
#define PORT_T602X_PERST 0x82c
#define PORT_PERST_OFF BIT(0)

static u32 port[0x1000 / 4], phy[0x4000 / 4], gpio[0x4000 / 4];
static unsigned reads[8], in_poll, poll_slept, poll_reads, link_after = 3;
static unsigned training;
static const char *const names[] = {
    "link", "phy", "appclk", "ready", "perst", "ltssm", "gpio5", "clkreq1"
};

/* Any shared PHY, other port, other GPIO, or undeclared register fails the
 * executable, including reads. This catches an accidentally broadened helper.
 */
static unsigned register_index(const void *addr)
{
    const void *allowed[] = {
        &port[PORT_LINKSTS / 4], &phy[0], &port[PORT_APPCLK / 4],
        &port[PORT_STATUS / 4], &port[PORT_T602X_PERST / 4],
        &port[PORT_LTSSMCTL / 4], &gpio[5], &gpio[1]
    };
    for (unsigned i = 0; i < 8; ++i)
        if (addr == allowed[i])
            return i;
    fputs("MMIO outside the SD register allowlist\n", stderr);
    exit(90);
}

static u32 readl(const void *addr)
{
    unsigned index = register_index(addr);
    ++reads[index];
    if (index == 0 && in_poll) {
        ++poll_reads;
        if (training && link_after && poll_reads >= link_after)
            port[PORT_LINKSTS / 4] |= PORT_LINKSTS_UP;
    }
    return *(const u32 *)addr;
}

static void writel(u32 value, void *addr)
{
    unsigned index = register_index(addr);
    printf("EVENT write %s %u\n", names[index], value);
    *(u32 *)addr = value;
    if (index == 5)
        training = value & PORT_LTSSMCTL_START;
}

static void udelay(unsigned time)
{
    if (in_poll)
        poll_slept += time;
    else
        printf("EVENT us %u\n", time);
}

static void mdelay(unsigned time)
{
    if (in_poll) {
        fputs("Unexpected millisecond delay inside polling\n", stderr);
        exit(91);
    }
    printf("EVENT ms %u\n", time);
}

/* Honor the caller's interval and deadline rather than substituting an
 * immediate success/failure. All MMIO still passes through readl above.
 */
#define readl_poll_sleep_timeout(addr, value, condition, interval, timeout) ({ \
    unsigned poll_interval = (interval), poll_timeout = (timeout); \
    int poll_result = -ETIMEDOUT; \
    if (!poll_interval || poll_timeout > 1000000) exit(92); \
    printf("EVENT poll %s %u %u\n", names[register_index(addr)], \
           poll_interval, poll_timeout); \
    in_poll = 1; \
    for (;;) { \
        (value) = readl(addr); \
        if (condition) { poll_result = 0; break; } \
        if (poll_slept >= poll_timeout) break; \
        udelay(poll_interval); \
    } \
    in_poll = 0; \
    poll_result; \
})

#include "sd_pcie.h"

int main(int argc, char **argv)
{
    if (argc != 2)
        return 93;
    const char *scenario = argv[1];
    /* State produced by m1n1. Preserve unrelated bits so tests detect
     * destructive whole-register writes in the endpoint completion path.
     */
    phy[0] = 0x2000060f;
    port[PORT_APPCLK / 4] = 0x100101;
    port[PORT_STATUS / 4] = PORT_STATUS_READY;
    port[PORT_T602X_PERST / 4] = PORT_PERST_OFF;
    gpio[1] = 0x76a21;
    gpio[5] = 0x87aa6d;

    if (!strcmp(scenario, "already-up")) {
        port[PORT_LINKSTS / 4] = PORT_LINKSTS_UP;
        phy[0] = port[PORT_APPCLK / 4] = port[PORT_STATUS / 4] = 0;
        port[PORT_T602X_PERST / 4] = gpio[1] = 0;
        port[PORT_LTSSMCTL / 4] = PORT_LTSSMCTL_START;
    } else if (!strncmp(scenario, "missing-phy-bit-", 16)) {
        unsigned bit = (unsigned)atoi(scenario + 16);
        if (bit >= 32)
            return 94;
        phy[0] &= ~BIT(bit);
    } else if (!strcmp(scenario, "phy-reset")) {
        phy[0] |= BIT(4);
    } else if (!strcmp(scenario, "appclk-off")) {
        port[PORT_APPCLK / 4] &= ~PORT_APPCLK_EN;
    } else if (!strcmp(scenario, "not-ready")) {
        port[PORT_STATUS / 4] &= ~PORT_STATUS_READY;
    } else if (!strcmp(scenario, "controller-reset")) {
        port[PORT_T602X_PERST / 4] &= ~PORT_PERST_OFF;
    } else if (!strcmp(scenario, "already-training")) {
        port[PORT_LTSSMCTL / 4] = PORT_LTSSMCTL_START;
    } else if (!strcmp(scenario, "link-busy")) {
        port[PORT_LINKSTS / 4] = PORT_LINKSTS_BUSY;
    } else if (!strcmp(scenario, "clkreq-gpio")) {
        gpio[1] &= ~GENMASK(6, 5);
    } else if (!strcmp(scenario, "clkreq-function2")) {
        gpio[1] = (gpio[1] & ~GENMASK(6, 5)) | BIT(6);
    } else if (!strcmp(scenario, "clkreq-output")) {
        gpio[1] |= BIT(1);
    } else if (!strcmp(scenario, "timeout")) {
        link_after = 0;
    } else if (!strcmp(scenario, "last-poll")) {
        link_after = 5001;
    } else if (!strcmp(scenario, "first-poll")) {
        link_after = 1;
    } else if (strcmp(scenario, "train")) {
        return 95;
    }

    int result = apple_sd_pcie_train(port, phy, gpio);
    printf("RESULT %d\n", result);
    printf("POLL %u %u\n", poll_reads, poll_slept);
    for (unsigned i = 0; i < 8; ++i)
        printf("READ %s %u\n", names[i], reads[i]);
    return 0;
}
'''


@unittest.skipUnless(shutil.which("cc"), "requires a host C compiler")
class SdPcieHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name)
        source = directory / "sd-pcie-harness.c"
        source.write_text(HARNESS)
        cls.executable = directory / "sd-pcie-harness"
        # Include the implementation itself: changes in the shipped header
        # automatically alter these tests' executed machine code.
        subprocess.run([shutil.which("cc"), "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                        "-I", str(PROJECT / "sdboot"), str(source),
                        "-o", str(cls.executable)], check=True, capture_output=True, text=True)

    def execute(self, scenario):
        run = subprocess.run([str(self.executable), scenario], check=True,
                             capture_output=True, text=True, timeout=5)
        lines = run.stdout.splitlines()
        events = [line.removeprefix("EVENT ") for line in lines if line.startswith("EVENT ")]
        result = int(next(line.split()[1] for line in lines if line.startswith("RESULT ")))
        poll = tuple(map(int, next(line.split()[1:] for line in lines if line.startswith("POLL "))))
        reads = {line.split()[1]: int(line.split()[2]) for line in lines if line.startswith("READ ")}
        return result, events, poll, reads

    @staticmethod
    def expected_training_events():
        asserted = (0x87aa6d & ~0x6f) | 2
        return [f"write gpio5 {asserted}", "us 100", f"write gpio5 {asserted | 1}",
                "ms 100", f"write phy {0x2000060f | 0xc0000000}",
                f"write appclk {0x100101 & ~0x100}", "write ltssm 1",
                "poll link 100 500000"]

    def test_already_up_link_is_inherited_without_writes_or_delays(self):
        result, events, poll, reads = self.execute("already-up")
        self.assertEqual(result, 0)
        self.assertEqual(events, [])
        self.assertEqual(poll, (0, 0))
        self.assertTrue(all(count == 1 for count in reads.values()))

    def test_m1n1_handoff_completes_only_port1_in_linux_order(self):
        result, events, poll, reads = self.execute("train")
        self.assertEqual(result, 0)
        self.assertEqual(events, self.expected_training_events())
        self.assertEqual(poll, (3, 200))
        self.assertEqual(reads["link"], 4)
        self.assertTrue(all(count == 1 for name, count in reads.items() if name != "link"))

    def test_each_missing_refclk_request_ack_or_enable_rejects_before_writes(self):
        for bit in (0, 1, 2, 3, 9, 10):
            with self.subTest(bit=bit):
                result, events, poll, _ = self.execute(f"missing-phy-bit-{bit}")
                self.assertLess(result, 0)
                self.assertEqual(events, [])
                self.assertEqual(poll, (0, 0))

    def test_invalid_controller_or_clkreq_state_never_resets_endpoint(self):
        for scenario in ("phy-reset", "appclk-off", "not-ready", "controller-reset",
                         "already-training", "link-busy", "clkreq-gpio",
                         "clkreq-function2", "clkreq-output"):
            with self.subTest(scenario=scenario):
                result, events, poll, _ = self.execute(scenario)
                self.assertLess(result, 0)
                self.assertEqual(events, [])
                self.assertEqual(poll, (0, 0))

    def test_link_timeout_is_bounded_and_does_not_retry_or_reset_again(self):
        result, events, poll, reads = self.execute("timeout")
        self.assertLess(result, 0)
        self.assertEqual(events, self.expected_training_events())
        self.assertEqual(poll, (5001, 500000))
        self.assertEqual(reads["link"], 5002)
        self.assertEqual(reads["ready"], 2)
        self.assertEqual(reads["ltssm"], 2)

    def test_polling_accepts_success_at_either_deadline_boundary(self):
        for scenario, expected in (("first-poll", (1, 0)), ("last-poll", (5001, 500000))):
            with self.subTest(scenario=scenario):
                result, events, poll, _ = self.execute(scenario)
                self.assertEqual(result, 0)
                self.assertEqual(events, self.expected_training_events())
                self.assertEqual(poll, expected)


if __name__ == "__main__":
    unittest.main()
