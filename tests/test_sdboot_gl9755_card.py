"""Execute the shipped GL9755 card-detect helper against timed MMIO samples."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#ifndef ENOMEDIUM
#define ENOMEDIUM 123
#endif
typedef uint32_t u32;
struct sdhci_host { int unused; };
#define SDHCI_PRESENT_STATE 0x24
#define SDHCI_CLOCK_CONTROL 0x2c
#define SDHCI_POWER_CONTROL 0x29
#define SDHCI_CARD_PRESENT (1U << 16)
#define SDHCI_CARD_STATE_STABLE (1U << 17)
#define SDHCI_CARD_DETECT_PIN_LEVEL (1U << 18)
#define PRESENT SDHCI_CARD_PRESENT
#define STABLE SDHCI_CARD_STATE_STABLE
#define PIN SDHCI_CARD_DETECT_PIN_LEVEL

static struct sdhci_host host;
static unsigned elapsed, delays, state_reads, clock_reads, power_reads;
static unsigned writes, log_calls;
static char log_text[512];
static struct { unsigned at; u32 state; } samples[8];
static unsigned count;

static void sample(unsigned at, u32 state)
{
    assert(count < sizeof(samples) / sizeof(samples[0]));
    assert(!count || at > samples[count - 1].at);
    samples[count].at = at;
    samples[count++].state = state;
}

static u32 sdhci_readl(struct sdhci_host *dev, unsigned offset)
{
    unsigned i = 0;
    assert(dev == &host);
    assert(offset == SDHCI_PRESENT_STATE);
    assert(count && samples[0].at == 0);
    state_reads++;
    while (i + 1 < count && samples[i + 1].at <= elapsed)
        i++;
    return samples[i].state;
}

static uint16_t sdhci_readw(struct sdhci_host *dev, unsigned offset)
{
    assert(dev == &host && offset == SDHCI_CLOCK_CONTROL);
    clock_reads++;
    return 0x000b;
}

static uint8_t sdhci_readb(struct sdhci_host *dev, unsigned offset)
{
    assert(dev == &host && offset == SDHCI_POWER_CONTROL);
    power_reads++;
    return 0x1f;
}

/* Any attempted write fails at execution, regardless of its width. */
#define sdhci_writel(...) (++writes, assert(!"unexpected MMIO write"))
#define sdhci_writew(...) (++writes, assert(!"unexpected MMIO write"))
#define sdhci_writeb(...) (++writes, assert(!"unexpected MMIO write"))

static void mdelay(unsigned ms)
{
    assert(ms == 1);
    assert(delays < 2000);
    delays++;
    elapsed += ms;
}

static int record_log(const char *format, ...)
{
    int ret;
    va_list args;
    log_calls++;
    va_start(args, format);
    ret = vsnprintf(log_text, sizeof(log_text), format, args);
    va_end(args);
    assert(ret > 0 && (unsigned)ret < sizeof(log_text));
    return ret;
}

#define printf record_log
#include "gl9755_card.h"
#undef printf

int main(int argc, char **argv)
{
    const char *scenario;
    unsigned expected_ms = 0;
    int expected = 0, get_cd = 0, ret;
    assert(argc == 2);
    scenario = argv[1];

    if (!strcmp(scenario, "present_high"))
        sample(0, PRESENT | STABLE | PIN | 1U);
    else if (!strcmp(scenario, "present_low"))
        sample(0, PRESENT | STABLE);
    else if (!strcmp(scenario, "absent_high") ||
             !strcmp(scenario, "absent_low")) {
        sample(0, STABLE | (!strcmp(scenario, "absent_high") ? PIN : 0));
        expected = -ENOMEDIUM; expected_ms = 2000;
    } else if (!strcmp(scenario, "delayed_insert")) {
        sample(0, STABLE); sample(350, PRESENT | STABLE);
        expected_ms = 350;
    } else if (!strcmp(scenario, "delayed_stable")) {
        sample(0, PRESENT | PIN); sample(375, PRESENT | STABLE | PIN);
        expected_ms = 375;
    } else if (!strcmp(scenario, "bounce")) {
        sample(0, STABLE); sample(10, PRESENT | PIN); sample(20, STABLE);
        sample(30, PRESENT); sample(400, PRESENT | STABLE);
        expected_ms = 400;
    } else if (!strcmp(scenario, "unstable_present") ||
               !strcmp(scenario, "unstable_absent")) {
        sample(0, !strcmp(scenario, "unstable_present") ? PRESENT | PIN : 0);
        expected = -ETIMEDOUT; expected_ms = 2000;
    } else if (!strcmp(scenario, "last_unstable")) {
        sample(0, STABLE); sample(2000, PRESENT);
        expected = -ETIMEDOUT; expected_ms = 2000;
    } else if (!strcmp(scenario, "last_absent")) {
        sample(0, PRESENT); sample(2000, STABLE);
        expected = -ENOMEDIUM; expected_ms = 2000;
    } else if (!strcmp(scenario, "all_ones_initial")) {
        sample(0, 0xffffffff);
        expected = -EIO;
    } else if (!strcmp(scenario, "all_ones_delayed")) {
        sample(0, STABLE); sample(100, 0xffffffff);
        expected = -EIO; expected_ms = 100;
    } else if (!strcmp(scenario, "deadline_present")) {
        sample(0, STABLE); sample(2000, PRESENT | STABLE);
        expected_ms = 2000;
    } else if (!strcmp(scenario, "after_deadline")) {
        sample(0, STABLE); sample(2001, PRESENT | STABLE);
        expected = -ENOMEDIUM; expected_ms = 2000;
    } else if (!strcmp(scenario, "deadline_all_ones")) {
        sample(0, STABLE); sample(2000, 0xffffffff);
        expected = -EIO; expected_ms = 2000;
    } else if (!strncmp(scenario, "get_cd_", 7)) {
        get_cd = 1;
        if (!strcmp(scenario, "get_cd_present_high")) {
            sample(0, PRESENT | STABLE | PIN); expected = 1;
        } else if (!strcmp(scenario, "get_cd_present_low")) {
            sample(0, PRESENT | STABLE); expected = 1;
        } else if (!strcmp(scenario, "get_cd_absent_high"))
            sample(0, STABLE | PIN);
        else if (!strcmp(scenario, "get_cd_absent_low"))
            sample(0, STABLE);
        else if (!strcmp(scenario, "get_cd_unstable_present"))
            sample(0, PRESENT | PIN);
        else if (!strcmp(scenario, "get_cd_unstable_absent"))
            sample(0, 0);
        else if (!strcmp(scenario, "get_cd_all_ones"))
            sample(0, 0xffffffff);
        else
            assert(!"unknown get_cd scenario");
    } else
        assert(!"unknown scenario");

    ret = get_cd ? gl9755_get_cd(&host) : gl9755_wait_card(&host);
    assert(ret == expected);
    assert(writes == 0);
    assert(elapsed == expected_ms && delays == expected_ms);
    assert(state_reads == expected_ms + 1);
    if (get_cd) {
        assert(clock_reads == 0 && power_reads == 0);
        assert(log_calls == (expected ? 0U : 1U));
        if (!expected)
            assert(strstr(log_text, "card detect rejected state="));
    } else {
        char timing[32];
        assert(clock_reads == 1 && power_reads == 1);
        assert(log_calls == 1);
        assert(strstr(log_text, "first=") && strstr(log_text, "last="));
        assert(strstr(log_text, "present=") && strstr(log_text, "stable="));
        assert(strstr(log_text, "pin="));
        assert(strstr(log_text, "clock=000b power=1f"));
        snprintf(timing, sizeof(timing), "elapsed=%ums", expected_ms);
        assert(strstr(log_text, timing));
    }
    printf("passed: %s\n", scenario);
    return 0;
}
'''


class Gl9755CardDetection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which("cc")
        if not cc:
            raise unittest.SkipTest("C compiler unavailable")
        cls.directory = tempfile.TemporaryDirectory(prefix="arch-m4-gli-card-")
        cls.addClassCleanup(cls.directory.cleanup)
        directory = Path(cls.directory.name)
        source = directory / "gl9755-card.c"
        source.write_text(HARNESS)
        cls.executable = directory / "gl9755-card"
        subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-I", str(PROJECT / "sdboot"), str(source),
                        "-o", str(cls.executable)], check=True, capture_output=True, text=True)

    def scenario(self, name):
        result = subprocess.run([str(self.executable), name], check=True,
                                capture_output=True, text=True)
        self.assertEqual(result.stdout, f"passed: {name}\n")

    def test_present_does_not_depend_on_raw_pin_level(self):
        for name in ("present_high", "present_low"):
            with self.subTest(name=name):
                self.scenario(name)

    def test_missing_card_is_bounded_and_never_forced_present(self):
        for name in ("absent_high", "absent_low"):
            with self.subTest(name=name):
                self.scenario(name)

    def test_initially_stable_absent_can_become_inserted(self):
        self.scenario("delayed_insert")

    def test_presence_waits_for_controller_stability(self):
        self.scenario("delayed_stable")

    def test_bouncing_unstable_samples_do_not_end_wait(self):
        self.scenario("bounce")

    def test_never_stable_is_distinct_from_missing_card(self):
        for name in ("unstable_present", "unstable_absent"):
            with self.subTest(name=name):
                self.scenario(name)

    def test_timeout_classification_uses_final_status(self):
        for name in ("last_unstable", "last_absent"):
            with self.subTest(name=name):
                self.scenario(name)

    def test_unreadable_mmio_is_immediate_error(self):
        for name in ("all_ones_initial", "all_ones_delayed", "deadline_all_ones"):
            with self.subTest(name=name):
                self.scenario(name)

    def test_inclusive_deadline_accepts_presence(self):
        self.scenario("deadline_present")

    def test_never_reads_past_deadline(self):
        self.scenario("after_deadline")

    def test_get_cd_uses_one_native_sample_and_no_delay(self):
        for state in ("present_high", "present_low", "absent_high", "absent_low",
                      "unstable_present", "unstable_absent", "all_ones"):
            with self.subTest(state=state):
                self.scenario(f"get_cd_{state}")


if __name__ == "__main__":
    unittest.main()
