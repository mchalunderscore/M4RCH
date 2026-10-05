"""Exercise the shipped GL9755 PCI setup against a fault-injected config space."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint32_t u32;
struct udevice { int unused; };
#define BIT(n) (1U << (n))
#define GENMASK(h, l) ((~0U << (l)) & (~0U >> (31 - (h))))

static u32 wt, peconf, entry_wt, entry_peconf;
static unsigned reads[2], writes[2], total_writes;
static int fail_read_reg = -1, fail_write_reg = -1, ones_reg = -1;
static unsigned fail_read_n, fail_write_n, ones_n;
static int mismatch, ignore_close, side_effect_error;
static int read_error = -EIO, write_error = -EIO;
static int verify;

static unsigned index_of(unsigned offset)
{
    assert(offset == 0x800 || offset == 0x44);
    return offset == 0x800 ? 0 : 1;
}

static int dm_pci_read_config32(struct udevice *dev, unsigned offset, u32 *value)
{
    unsigned i = index_of(offset);
    (void)dev;
    reads[i]++;
    if ((int)i == fail_read_reg && reads[i] == fail_read_n)
        return read_error;
    /* Vendor registers are hidden while WT is closed. Ordinary PCI config
     * access still succeeds, but the apparent value is zero.
     */
    *value = i == 0 ? wt : (wt & BIT(0)) ? peconf : 0;
    if ((int)i == ones_reg && reads[i] == ones_n)
        *value = 0xffffffff;
    if (i == 1 && reads[i] == 2 && mismatch)
        *value ^= BIT(30);
    return 0;
}

static int dm_pci_write_config32(struct udevice *dev, unsigned offset, u32 value)
{
    const u32 allowed = BIT(30) | BIT(31) | GENMASK(14, 12) | BIT(29);
    unsigned i = index_of(offset);
    int fail;
    (void)dev;
    total_writes++;
    writes[i]++;
    if (i == 0)
        assert((value & ~BIT(0)) == (entry_wt & ~BIT(0)));
    else {
        assert(!verify);
        assert(wt & BIT(0));
        assert((value & ~allowed) == (entry_peconf & ~allowed));
        assert((value & allowed) == (BIT(30) | BIT(31)));
    }
    fail = (int)i == fail_write_reg && writes[i] == fail_write_n;
    if (!fail || side_effect_error) {
        if (i == 0) {
            if (!ignore_close || (value & BIT(0)))
                wt = value;
        } else
            peconf = value;
    }
    return fail ? write_error : 0;
}

#include "gl9755_pci.h"

int main(int argc, char **argv)
{
    struct udevice dev = {0};
    const char *scenario;
    int expected = -EIO, expect_open = 0, ret;
    assert(argc == 2);
    entry_wt = wt = 0xa4a40020;
    entry_peconf = peconf = 0x21237654;
    scenario = argv[1];
    verify = !strncmp(scenario, "verify_", 7);
    if (verify) {
        scenario += 7;
        entry_peconf = peconf = (entry_peconf | BIT(30) | BIT(31)) &
                               ~(GENMASK(14, 12) | BIT(29));
    }

    if (!strcmp(scenario, "success")) {
        expected = 0;
        if (verify) {
            u32 hidden;
            assert(!dm_pci_read_config32(&dev, 0x44, &hidden));
            assert(hidden == 0 && peconf != 0);
            reads[1] = 0;
        }
    } else if (!strcmp(scenario, "already_open")) {
        entry_wt = wt |= BIT(0);
        expected = 0;
    } else if (!strcmp(scenario, "initial_read_error")) {
        fail_read_reg = 0; fail_read_n = 1;
    } else if (!strcmp(scenario, "initial_all_ones")) {
        ones_reg = 0; ones_n = 1;
    } else if (!strcmp(scenario, "unlock_write_error")) {
        fail_write_reg = 0; fail_write_n = 1;
        side_effect_error = 1;
    } else if (!strcmp(scenario, "unlock_read_error")) {
        fail_read_reg = 0; fail_read_n = 2;
    } else if (!strcmp(scenario, "unlock_all_ones")) {
        ones_reg = 0; ones_n = 2;
    } else if (!strcmp(scenario, "peconf_read_error")) {
        fail_read_reg = 1; fail_read_n = 1;
    } else if (!strcmp(scenario, "peconf_all_ones")) {
        ones_reg = 1; ones_n = 1;
    } else if (!strcmp(scenario, "peconf_write_error")) {
        fail_write_reg = 1; fail_write_n = 1;
        side_effect_error = 1;
    } else if (!strcmp(scenario, "readback_error")) {
        fail_read_reg = 1; fail_read_n = 2;
    } else if (!strcmp(scenario, "readback_all_ones")) {
        ones_reg = 1; ones_n = 2;
    } else if (!strcmp(scenario, "readback_mismatch"))
        mismatch = 1;
    else if (!strcmp(scenario, "close_write_error")) {
        fail_write_reg = 0; fail_write_n = 2;
        expect_open = 1;
    } else if (!strcmp(scenario, "close_read_error")) {
        fail_read_reg = 0; fail_read_n = 3;
    } else if (!strcmp(scenario, "close_all_ones")) {
        ones_reg = 0; ones_n = 3;
    } else if (!strcmp(scenario, "close_ignored")) {
        ignore_close = expect_open = 1;
    } else if (!strcmp(scenario, "wrong_cd"))
        entry_peconf = peconf ^= BIT(30);
    else if (!strcmp(scenario, "wrong_wp"))
        entry_peconf = peconf ^= BIT(31);
    else if (!strcmp(scenario, "wrong_lfclk"))
        entry_peconf = peconf |= BIT(12);
    else if (!strcmp(scenario, "wrong_dmaclk"))
        entry_peconf = peconf |= BIT(29);
    else if (!strcmp(scenario, "real_zero"))
        entry_peconf = peconf = 0;
    else if (!strcmp(scenario, "initial_read_errno")) {
        fail_read_reg = 0; fail_read_n = 1;
        expected = read_error = -ENODEV;
    } else if (!strcmp(scenario, "unlock_write_errno")) {
        fail_write_reg = 0; fail_write_n = 1;
        expected = write_error = -EACCES;
        side_effect_error = 1;
    } else if (!strcmp(scenario, "peconf_read_and_close_error")) {
        fail_read_reg = 1; fail_read_n = 1;
        expected = read_error = -EACCES;
        fail_write_reg = 0; fail_write_n = 2;
        write_error = -EBUSY;
        expect_open = 1;
    } else if (!strcmp(scenario, "close_write_errno")) {
        fail_write_reg = 0; fail_write_n = 2;
        expected = write_error = -EBUSY;
        expect_open = 1;
    } else
        assert(!"unknown scenario");

    ret = verify ? gl9755_pci_verify(&dev) : gl9755_pci_init(&dev);
    assert(ret == expected);
    assert(!!(wt & BIT(0)) == expect_open);
    assert((wt & ~BIT(0)) == (entry_wt & ~BIT(0)));
    if (!strncmp(scenario, "initial_", 8))
        assert(total_writes == 0);
    else
        assert(writes[0] >= 1);
    if (verify) {
        assert(writes[1] == 0);
        assert(peconf == entry_peconf);
        if (!expected) {
            assert(reads[1] == 1);
            assert(writes[0] == (!strcmp(scenario, "already_open") ? 1U : 2U));
        }
    } else if (!expected) {
        assert(peconf == ((entry_peconf | BIT(30) | BIT(31)) &
                         ~(GENMASK(14, 12) | BIT(29))));
        assert(writes[1] == 1);
    }
    printf("passed: %s\n", argv[1]);
    return 0;
}
'''


class Gl9755PciConfiguration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which("cc")
        if not cc:
            raise unittest.SkipTest("C compiler unavailable")
        cls.directory = tempfile.TemporaryDirectory(prefix="arch-m4-gli-pci-")
        cls.addClassCleanup(cls.directory.cleanup)
        directory = Path(cls.directory.name)
        source = directory / "gl9755-pci.c"
        source.write_text(HARNESS)
        cls.executable = directory / "gl9755-pci"
        subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-I", str(PROJECT / "sdboot"), str(source),
                        "-o", str(cls.executable)], check=True, capture_output=True, text=True)

    def check_case(self, case):
        result = subprocess.run([str(self.executable), case], check=True,
                                capture_output=True, text=True)
        self.assertIn(f"passed: {case}", result.stdout)
        if case.startswith("verify_"):
            self.assertIn("gated post-reset PECONF", result.stdout)
            self.assertIn("status=", result.stdout)
            self.assertIn("gate cleanup=", result.stdout)

    def test_preserves_unrelated_bits_and_sets_hardware_polarity(self):
        self.check_case("success")

    def test_closes_an_initially_open_gate(self):
        self.check_case("already_open")

    def test_unreadable_initial_gate_never_writes(self):
        for case in ("initial_read_error", "initial_all_ones"):
            with self.subTest(case=case):
                self.check_case(case)

    def test_failed_unlock_still_closes_gate(self):
        for case in ("unlock_write_error", "unlock_read_error", "unlock_all_ones"):
            with self.subTest(case=case):
                self.check_case(case)

    def test_peconf_failures_close_gate(self):
        for case in ("peconf_read_error", "peconf_all_ones", "peconf_write_error"):
            with self.subTest(case=case):
                self.check_case(case)

    def test_peconf_readback_must_match(self):
        for case in ("readback_error", "readback_all_ones", "readback_mismatch"):
            with self.subTest(case=case):
                self.check_case(case)

    def test_cleanup_failures_are_reported(self):
        for case in ("close_write_error", "close_read_error", "close_all_ones", "close_ignored"):
            with self.subTest(case=case):
                self.check_case(case)

    def test_verification_opens_hidden_register_window_without_reconfiguring(self):
        self.check_case("verify_success")

    def test_verification_closes_initially_open_gate(self):
        self.check_case("verify_already_open")

    def test_verification_rejects_real_configuration_mismatch(self):
        for case in ("wrong_cd", "wrong_wp", "wrong_lfclk", "wrong_dmaclk", "real_zero"):
            with self.subTest(case=case):
                self.check_case(f"verify_{case}")

    def test_verification_rejects_unreadable_gate_or_value(self):
        for case in ("initial_read_error", "initial_all_ones", "unlock_read_error",
                     "unlock_all_ones", "peconf_read_error", "peconf_all_ones"):
            with self.subTest(case=case):
                self.check_case(f"verify_{case}")

    def test_verification_cleans_up_after_ambiguous_unlock_error(self):
        self.check_case("verify_unlock_write_error")

    def test_verification_cleanup_is_required_for_success(self):
        for case in ("close_write_error", "close_read_error", "close_all_ones", "close_ignored"):
            with self.subTest(case=case):
                self.check_case(f"verify_{case}")

    def test_verification_preserves_primary_and_cleanup_error_codes(self):
        for case in ("initial_read_errno", "unlock_write_errno", "peconf_read_and_close_error",
                     "close_write_errno"):
            with self.subTest(case=case):
                self.check_case(f"verify_{case}")


if __name__ == "__main__":
    unittest.main()
