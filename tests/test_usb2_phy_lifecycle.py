"""Exercise the actual T6040 PHY callbacks against a host MMIO recorder.

The expected register operations follow the reviewed USB2 reset/host sequences.
These tests check ordering, delays, preservation and callback wiring; they do
not model analog PHY behavior or establish native USB device enumeration.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib"))
import hardware_profile as hardware

SOURCE = "drivers/phy/apple/t6040-usb2.c"
WALLACE_PATCH = "0001-phy-apple-add-experimental-T6040-USB2-only-slice.patch"
RESET_PATCH = "patches/experimental-usb2-phy-reset.patch"


def function(source, declaration):
    start = source.index(declaration)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


PRELUDE = r"""
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
#define BIT(n) (UINT32_C(1) << (n))
#define GENMASK(h, l) ((UINT32_MAX >> (31 - (h))) & (UINT32_MAX << (l)))
#define __iomem
#define THIS_MODULE NULL
enum phy_mode { PHY_MODE_INVALID, PHY_MODE_USB_HOST, PHY_MODE_USB_DEVICE };
struct device { int unused; };
struct mutex { bool held; };
struct phy { void *driver_data; };
struct phy_ops {
    void *owner;
    int (*init)(struct phy *);
    int (*exit)(struct phy *);
    int (*power_off)(struct phy *);
    int (*power_on)(struct phy *);
    int (*set_mode)(struct phy *, enum phy_mode, int);
};
static void require(bool condition, int code, const char *message) {
    if (!condition) { fprintf(stderr, "%s\n", message); exit(code); }
}
static struct mutex *active_lock;
struct lock_guard { struct mutex *lock; };
static struct lock_guard take_lock(struct mutex *lock) {
    require(!active_lock && !lock->held, 1, "nested PHY lock");
    lock->held = true;
    active_lock = lock;
    return (struct lock_guard) { lock };
}
static void release_lock(struct lock_guard *guard_value) {
    require(active_lock == guard_value->lock && active_lock->held, 1,
            "wrong PHY lock released");
    active_lock->held = false;
    active_lock = NULL;
}
#define guard(kind) struct lock_guard guard_value \
    __attribute__((cleanup(release_lock))) = take_lock
#define lockdep_assert_held(lock) \
    require(active_lock == (lock) && active_lock->held, 1, "helper lacks PHY lock")
static void *phy_get_drvdata(struct phy *phy) { return phy->driver_data; }
static void report(struct device *dev, const char *fmt, ...) {
    (void)dev; (void)fmt;
}
#define dev_info report
/* ACTUAL_PHY_DEFINITIONS */
static u32 bank0[32], bank1[32], before0[32], before1[32], want0[32], want1[32];
struct event { char kind; int bank; unsigned offset; u32 value; };
static struct event events[128], expected[128];
static unsigned event_count, expected_count, read_count;
static void record(char kind, int bank, unsigned offset, u32 value) {
    require(active_lock && active_lock->held, 1,
            "PHY MMIO or delay executed outside the PHY lock");
    require(event_count < 128, 1, "PHY event recorder overflow");
    events[event_count++] = (struct event) { kind, bank, offset, value };
}
static u32 *register_pointer(const void *address, int *bank, unsigned *offset) {
    uintptr_t target = (uintptr_t)address;
    uintptr_t base0 = (uintptr_t)bank0, base1 = (uintptr_t)bank1;
    require(active_lock && active_lock->held, 1, "PHY read outside the PHY lock");
    if (target >= base0 && target < base0 + sizeof(bank0)) {
        *bank = 0; *offset = (unsigned)(target - base0);
    } else if (target >= base1 && target < base1 + sizeof(bank1)) {
        *bank = 1; *offset = (unsigned)(target - base1);
    } else {
        require(false, 1, "PHY accessed an unreviewed register bank");
    }
    require(!(*offset & 3), 1, "unaligned PHY register access");
    return (u32 *)address;
}
static u32 readl(const void *address) {
    int bank; unsigned offset;
    u32 *reg = register_pointer(address, &bank, &offset);
    ++read_count;
    return *reg;
}
static void writel(u32 value, void *address) {
    int bank; unsigned offset;
    u32 *reg = register_pointer(address, &bank, &offset);
    record('w', bank, offset, value);
    *reg = value;
}
static void msleep(unsigned value) { record('m', -1, 0, value); }
static void udelay(unsigned value) { record('u', -1, 0, value); }
static void __attribute__((unused)) ndelay(unsigned value) { record('n', -1, 0, value); }
"""

MAIN = r"""
static void initialize(bool port_reset) {
    require(!active_lock, 1, "previous callback retained the PHY lock");
    for (unsigned i = 0; i < 32; ++i) {
        bank0[i] = UINT32_C(0x12340000) + i;
        bank1[i] = UINT32_C(0x56780000) + i;
    }
    bank0[0] = UINT32_C(0x91000105); /* Inherited mode; preserve unrelated bits. */
    bank0[1] = UINT32_C(0x810040a4) | (port_reset ? BIT(1) : 0);
    bank0[2] = UINT32_C(0x91010040);
    bank0[7] = UINT32_C(0x00231000);
    bank1[0] = UINT32_C(0x40000300);
    bank1[8] = 1;
    event_count = expected_count = read_count = 0;
}
static void snapshot(void) {
    memcpy(before0, bank0, sizeof(bank0));
    memcpy(before1, bank1, sizeof(bank1));
    memcpy(want0, bank0, sizeof(bank0));
    memcpy(want1, bank1, sizeof(bank1));
    event_count = expected_count = read_count = 0;
}
static void expect(char kind, int bank, unsigned offset, u32 value) {
    require(expected_count < 128, 1, "expected PHY trace overflow");
    expected[expected_count++] = (struct event) { kind, bank, offset, value };
    if (kind == 'w')
        (bank ? want1 : want0)[offset / sizeof(u32)] = value;
}
static void compare_events(int code) {
    require(!active_lock, 1, "callback did not release the PHY lock");
    if (event_count != expected_count) {
        fprintf(stderr, "PHY event count: got %u, expected %u\n",
                event_count, expected_count);
        exit(code);
    }
    for (unsigned i = 0; i < event_count; ++i) {
        struct event got = events[i], want = expected[i];
        if (got.kind != want.kind || got.bank != want.bank ||
            got.offset != want.offset || got.value != want.value) {
            fprintf(stderr, "PHY event %u: got %c bank=%d offset=%#x value=%#x; "
                    "expected %c bank=%d offset=%#x value=%#x\n", i,
                    got.kind, got.bank, got.offset, got.value,
                    want.kind, want.bank, want.offset, want.value);
            exit(code);
        }
    }
    require(!memcmp(bank0, want0, sizeof(bank0)) &&
            !memcmp(bank1, want1, sizeof(bank1)), code,
            "PHY register state differs from reviewed trace");
}
static void expected_reset(void) {
    u32 ctl = want0[1], misc = want0[7];
    if (!(ctl & BIT(1))) {
        ctl |= BIT(1);
        expect('w', 0, 0x04, ctl);
        expect('m', -1, 0, 5);
    }
    expect('w', 0, 0x00, (want0[0] & ~UINT32_C(7)) | UINT32_C(4));
    ctl |= BIT(3);
    expect('w', 0, 0x04, ctl);
    ctl |= BIT(0);
    expect('w', 0, 0x04, ctl);
    misc |= BIT(29);
    expect('w', 0, 0x1c, misc);
    misc |= BIT(30);
    expect('w', 0, 0x1c, misc);
    expect('n', -1, 0, 500);
}
static void expected_host(void) {
    u32 sig = want0[2], ctl = want0[1], misc = want0[7];
    const unsigned signal_bits[] = { 14, 13, 12, 0, 1 };
    for (unsigned i = 0; i < 5; ++i) {
        sig |= BIT(signal_bits[i]);
        expect('w', 0, 0x08, sig);
    }
    expect('m', -1, 0, 10);
    ctl &= ~BIT(3);
    expect('w', 0, 0x04, ctl);
    expect('u', -1, 0, 10);
    ctl &= ~BIT(0);
    expect('w', 0, 0x04, ctl);
    ctl &= ~BIT(1);
    expect('w', 0, 0x04, ctl);
    expect('w', 1, 0x00, want1[0] | UINT32_C(9));
    ctl |= BIT(2);
    expect('w', 0, 0x04, ctl);
    misc &= ~BIT(29);
    expect('w', 0, 0x1c, misc);
    misc &= ~BIT(30);
    expect('w', 0, 0x1c, misc);
    expect('u', -1, 0, 30);
    expect('m', -1, 0, 5);
    expect('w', 0, 0x00, (want0[0] & ~UINT32_C(7)) | UINT32_C(2));
}
static void hardware_active(struct t6040_usb2_phy *tphy, bool expected_active) {
#ifdef HAVE_HW_ACTIVE
    require(tphy->hw_active == expected_active, 31,
            "PHY software state does not match hardware activation");
#else
    (void)tphy; (void)expected_active;
#endif
}
static void reset_state(struct t6040_usb2_phy *tphy) {
    require((bank0[0] & 7) == 4, 11, "reset did not select isolation mode");
    require((bank0[1] & 0xb) == 0xb, 11,
            "reset did not assert SIDDQ, RESET and PORT_RESET");
    require((bank0[7] & UINT32_C(0x60000000)) == UINT32_C(0x60000000), 11,
            "reset did not gate both PHY clocks");
    require((bank0[0] & ~UINT32_C(7)) == (before0[0] & ~UINT32_C(7)) &&
            (bank0[1] & ~UINT32_C(0xb)) == (before0[1] & ~UINT32_C(0xb)) &&
            (bank0[7] & ~UINT32_C(0x60000000)) ==
                (before0[7] & ~UINT32_C(0x60000000)), 12,
            "reset modified unrelated register bits");
    for (unsigned i = 0; i < 32; ++i) {
        require(bank1[i] == before1[i], 13, "reset modified the event bank");
        if (i != 0 && i != 1 && i != 7)
            require(bank0[i] == before0[i], 13,
                    "reset modified signal or unreviewed register");
    }
    hardware_active(tphy, false);
}
static void host_state(struct t6040_usb2_phy *tphy) {
    require((bank0[0] & 7) == 2, 21, "host mode was not selected");
    require((bank0[1] & 0xf) == 4, 21,
            "host did not release all resets/SIDDQ and set APB_RESET_N");
    require(!(bank0[7] & UINT32_C(0x60000000)), 21,
            "host did not ungate both PHY clocks");
    require((bank0[2] & UINT32_C(0x7003)) == UINT32_C(0x7003), 21,
            "host signal forcing was not restored");
    require((bank1[0] & 9) == 9, 21, "host event controls were not enabled");
    require((bank0[0] & ~UINT32_C(7)) == (before0[0] & ~UINT32_C(7)) &&
            (bank0[1] & ~UINT32_C(0xf)) == (before0[1] & ~UINT32_C(0xf)) &&
            (bank0[2] & ~UINT32_C(0x7003)) ==
                (before0[2] & ~UINT32_C(0x7003)) &&
            (bank0[7] & ~UINT32_C(0x60000000)) ==
                (before0[7] & ~UINT32_C(0x60000000)) &&
            (bank1[0] & ~UINT32_C(9)) == (before1[0] & ~UINT32_C(9)), 22,
            "host modified unrelated register bits");
    for (unsigned i = 0; i < 32; ++i) {
        if (i != 0)
            require(bank1[i] == before1[i], 23,
                    "host modified an unreviewed event register");
        if (i != 0 && i != 1 && i != 2 && i != 7)
            require(bank0[i] == before0[i], 23,
                    "host modified an unreviewed PHY register");
    }
    hardware_active(tphy, true);
}
static int callback(int (*method)(struct phy *), struct phy *phy) {
    /* Replay-only source has no init, exit or power_off: actual no-ops. */
    return method ? method(phy) : 0;
}
static void do_init(struct phy *phy) {
    snapshot();
    expected_reset();
    expected_host();
    require(!callback(t6040_usb2_phy_ops.init, phy), 10, "PHY init failed");
    compare_events(10);
    host_state(phy_get_drvdata(phy));
}
static void do_stop(struct phy *phy, bool exiting) {
    snapshot();
    expected_reset();
    require(!callback(exiting ? t6040_usb2_phy_ops.exit :
                               t6040_usb2_phy_ops.power_off, phy), 10,
            "PHY shutdown callback failed");
    compare_events(10);
    reset_state(phy_get_drvdata(phy));
}
static void do_start(struct phy *phy) {
    snapshot();
    expected_host();
    require(!t6040_usb2_phy_ops.power_on(phy), 20, "host replay failed");
    compare_events(20);
    host_state(phy_get_drvdata(phy));
}
static void no_transition(struct phy *phy, int (*method)(struct phy *)) {
    snapshot();
    require(!callback(method, phy), 32, "idempotent PHY callback failed");
    require(!read_count, 32, "idempotent PHY callback read MMIO");
    compare_events(32);
}
static int modeled_dwc3_soft_reset(void) {
    /* core.c resets DWC3 after phy_init but BEFORE phy_power_on. */
    return ((bank0[1] & 0xb) || (bank0[7] & UINT32_C(0x60000000))) ?
           -ETIMEDOUT : 0;
}
int main(int argc, char **argv) {
    require(argc == 2, 1, "missing PHY scenario");
    const char *name = argv[1];
    struct device dev = { 0 };
    struct t6040_usb2_phy tphy = {
        .dev = &dev, .usb2 = bank0, .evt = bank1, .mode = PHY_MODE_USB_HOST,
    };
    struct phy phy = { .driver_data = &tphy };
    initialize(strstr(name, "preasserted") != NULL);
    if (!strcmp(name, "ops-wiring")) {
        require(t6040_usb2_phy_ops.init && t6040_usb2_phy_ops.exit &&
                t6040_usb2_phy_ops.power_off &&
                t6040_usb2_phy_ops.exit == t6040_usb2_phy_ops.power_off &&
                t6040_usb2_phy_ops.init != t6040_usb2_phy_ops.power_off, 30,
                "init and balanced shutdown callbacks are not wired");
        require(t6040_usb2_phy_ops.power_on == t6040_usb2_power_on &&
                t6040_usb2_phy_ops.set_mode == t6040_usb2_set_mode, 30,
                "existing public host callbacks were replaced");
    } else if (!strncmp(name, "reset-", 6)) {
#ifdef HAVE_HW_ACTIVE
        /* Direct active state tests both inherited PORT_RESET states. */
        tphy.hw_active = true;
#endif
        do_stop(&phy, false);
    } else if (!strncmp(name, "init-", 5)) {
        do_init(&phy);
    } else if (!strcmp(name, "dwc3-init")) {
        snapshot();
        expected_reset();
        expected_host();
        require(!callback(t6040_usb2_phy_ops.init, &phy), 10, "PHY init failed");
        require(!modeled_dwc3_soft_reset(), 50,
                "DWC3 soft reset sees gated clocks or asserted PHY resets after init");
        compare_events(10);
        host_state(&tphy);
        no_transition(&phy, t6040_usb2_phy_ops.power_on);
        host_state(&tphy);
    } else if (!strcmp(name, "init-failure-exit")) {
        do_init(&phy);
        /* A later controller reset/setup failure unwinds via phy_exit only. */
        do_stop(&phy, true);
        no_transition(&phy, t6040_usb2_phy_ops.exit);
        reset_state(&tphy);
    } else if (!strcmp(name, "success-teardown")) {
        do_init(&phy);
        no_transition(&phy, t6040_usb2_phy_ops.power_on);
        do_stop(&phy, false);
        no_transition(&phy, t6040_usb2_phy_ops.exit);
        no_transition(&phy, t6040_usb2_phy_ops.power_off);
        reset_state(&tphy);
    } else if (!strcmp(name, "runtime-cycle")) {
        do_init(&phy);
        no_transition(&phy, t6040_usb2_phy_ops.power_on);
        do_stop(&phy, false);
        do_start(&phy);
        no_transition(&phy, t6040_usb2_phy_ops.power_on);
        do_stop(&phy, false);
        no_transition(&phy, t6040_usb2_phy_ops.exit);
    } else if (!strcmp(name, "host-recovery")) {
#ifdef HAVE_HW_ACTIVE
        tphy.hw_active = true;
#endif
        do_stop(&phy, false);
        do_start(&phy);
    } else if (!strcmp(name, "repeated-cables")) {
        for (unsigned i = 0; i < 3; ++i) {
            /* Event status zero is informational and must not suppress init. */
            bank1[8] = i == 0 ? 1 : 0;
            do_init(&phy);
            require(!modeled_dwc3_soft_reset(), 50,
                    "reattachment leaves the PHY unavailable for DWC3 reset");
            no_transition(&phy, t6040_usb2_phy_ops.power_on);
            do_stop(&phy, false);
            no_transition(&phy, t6040_usb2_phy_ops.exit);
        }
    } else if (!strcmp(name, "reject-non-host")) {
        snapshot();
        require(t6040_usb2_phy_ops.set_mode(&phy, PHY_MODE_USB_DEVICE, 0) ==
                -EOPNOTSUPP, 40, "PHY accepted unsupported device mode");
        require(tphy.mode == PHY_MODE_USB_HOST && !read_count, 40,
                "unsupported mode changed state or read MMIO");
        compare_events(40);
        const enum phy_mode invalid_modes[] = { PHY_MODE_USB_DEVICE, PHY_MODE_INVALID };
        for (unsigned i = 0; i < 2; ++i) {
            tphy.mode = invalid_modes[i];
#ifdef HAVE_HW_ACTIVE
            tphy.hw_active = i != 0;
#endif
            bool was_active = i != 0;
            (void)was_active;
            require(t6040_usb2_phy_ops.power_on(&phy) == -EINVAL, 41,
                    "PHY powered on in unsupported mode");
            if (t6040_usb2_phy_ops.init) {
                require(callback(t6040_usb2_phy_ops.init, &phy) == -EINVAL &&
                        callback(t6040_usb2_phy_ops.power_off, &phy) == -EINVAL &&
                        callback(t6040_usb2_phy_ops.exit, &phy) == -EINVAL, 43,
                        "PHY init/shutdown accepted unsupported mode");
            }
            require(!read_count, 43, "unsupported callback read MMIO");
            compare_events(43);
            hardware_active(&tphy, was_active);
        }
    } else if (!strcmp(name, "host-mode-no-mmio")) {
        snapshot();
        require(!t6040_usb2_phy_ops.set_mode(&phy, PHY_MODE_USB_HOST, 0), 42,
                "PHY rejected its supported host mode");
        require(!read_count && tphy.mode == PHY_MODE_USB_HOST, 42,
                "host mode selection touched MMIO or lost the selected mode");
        compare_events(42);
    } else {
        require(false, 1, "unknown PHY scenario");
    }
    puts("T6040 USB2 reset/host lifecycle checks passed");
    return 0;
}
"""


class Usb2PhyLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("cc", "git"):
            if not shutil.which(tool):
                raise unittest.SkipTest("USB2 PHY C harness requires " + tool)
        cache = PROJECT / "cache/git/wallace.git"
        if not cache.is_dir():
            raise unittest.SkipTest("USB2 PHY C harness requires pinned cached Wallace source")
        lock = json.loads((PROJECT / "sources.lock.json").read_text())
        if lock["wallace"]["revision"] != hardware.WALLACE_REVISION:
            raise AssertionError("Wallace cache revision differs from reviewed PHY revision")
        linux_cache = PROJECT / "cache/git/linux.git"
        if not linux_cache.is_dir():
            raise unittest.SkipTest("USB2 lifecycle harness requires pinned cached Linux source")
        if lock["linux"]["revision"] != hardware.TIPD_CONNECTOR_FIX["base_linux_revision"]:
            raise AssertionError("Linux revision differs from reviewed DWC3 call order")
        core = subprocess.check_output([
            "git", "--git-dir=" + str(linux_cache), "show",
            lock["linux"]["revision"] + ":drivers/usb/dwc3/core.c",
        ], timeout=15).decode()
        cls.dwc3_core_init = function(core, "int dwc3_core_init(")
        temporary = tempfile.TemporaryDirectory(prefix="arch-m4-usb2-phy-test-")
        cls.addClassCleanup(temporary.cleanup)
        tree = Path(temporary.name)
        original_patch = subprocess.check_output([
            "git", "--git-dir=" + str(cache), "show",
            lock["wallace"]["revision"] + ":patches/" + WALLACE_PATCH,
        ], timeout=15)
        if hashlib.sha256(original_patch).hexdigest() != hardware.PATCHES[WALLACE_PATCH]:
            raise AssertionError("cached Wallace PHY patch digest changed")
        subprocess.run(["git", "apply", "--include=" + SOURCE, "-"],
                       input=original_patch, cwd=tree, check=True, timeout=15)
        source = tree / SOURCE
        cls.bodies = {}
        metadata = [item for item in hardware.USB_CABLE_FIXES if item["source"] == SOURCE]
        if [item["path"] for item in metadata] != [
                "patches/experimental-usb2-phy-replay.patch", RESET_PATCH]:
            raise AssertionError("PHY harness requires the ordered replay and reset patches")
        for item in metadata:
            if hashlib.sha256(source.read_bytes()).hexdigest() != item["base_source_sha256"]:
                raise AssertionError("PHY patch base differs from pinned digest: " + item["path"])
            patch = PROJECT / item["path"]
            if hashlib.sha256(patch.read_bytes()).hexdigest() != item["sha256"]:
                raise AssertionError("PHY patch differs from pinned digest: " + item["path"])
            subprocess.run(["git", "apply", "--check", str(patch)],
                           cwd=tree, check=True, timeout=15)
            subprocess.run(["git", "apply", str(patch)], cwd=tree, check=True, timeout=15)
            if hashlib.sha256(source.read_bytes()).hexdigest() != item["result_source_sha256"]:
                raise AssertionError("patched PHY source differs from pinned digest: " + item["path"])
            label = "replay" if item["path"] != RESET_PATCH else "patched"
            cls.bodies[label] = source.read_text()

        # Reproduce the native regression without depending on an output artifact:
        # the old .init left reset asserted and clocks gated before DWC3 reset.
        init = function(cls.bodies["patched"], "static int t6040_usb2_init(")
        if init.count("t6040_usb2_start_locked(tphy);") != 1:
            raise AssertionError("reset-only negative control requires one init host release")
        cls.bodies["reset-only"] = cls.bodies["patched"].replace(
            init, init.replace("\tt6040_usb2_start_locked(tphy);\n", ""), 1)

        cls.binaries = {}
        for label, body in cls.bodies.items():
            defines = "\n".join(re.findall(r"^#define T6040_USB2_.*$", body, re.M))
            actual_types = re.search(r"struct t6040_usb2_phy \{.*?\n\};", body, re.S).group()
            declarations = [
                "static inline void t6040_usb2_mask32(",
                "static inline void t6040_usb2_set32(",
                "static inline void t6040_usb2_clear32(",
                "static int t6040_usb2_set_mode(",
            ]
            if label != "replay":
                declarations.extend([
                    "static void t6040_usb2_stop_locked(",
                    "static void t6040_usb2_start_locked(",
                    "static int t6040_usb2_init(",
                ])
            declarations.append("static int t6040_usb2_power_on(")
            if label != "replay":
                declarations.append("static int t6040_usb2_power_off(")
            actual = "\n".join(function(body, declaration) for declaration in declarations)
            actual_ops = re.search(
                r"static const struct phy_ops t6040_usb2_phy_ops = \{.*?\n\};",
                body, re.S).group()
            harness = tree / (label + ".c")
            fixture_flags = "#define HAVE_HW_ACTIVE 1\n" if label != "replay" else ""
            harness.write_text(fixture_flags + PRELUDE.replace(
                "/* ACTUAL_PHY_DEFINITIONS */", defines + "\n" + actual_types)
                + actual + "\n" + actual_ops + MAIN)
            cls.binaries[label] = tree / label
            result = subprocess.run([
                shutil.which("cc"), "-std=gnu11", "-O0", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", str(harness), "-o", str(cls.binaries[label]),
            ], capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise AssertionError("USB2 PHY harness compilation failed: " + result.stderr)

    def run_case(self, label, case):
        return subprocess.run([str(self.binaries[label]), case],
                              capture_output=True, text=True, timeout=5)

    def assert_case_passes(self, case):
        result = self.run_case("patched", case)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reset_write_and_delay_order_when_port_reset_is_clear(self):
        self.assert_case_passes("reset-clear")

    def test_reset_skips_port_reset_write_and_delay_when_already_asserted(self):
        self.assert_case_passes("reset-preasserted")

    def test_init_resets_then_releases_host_for_both_initial_states(self):
        for case in ("init-clear", "init-preasserted"):
            with self.subTest(case=case):
                self.assert_case_passes(case)

    def test_reset_then_host_releases_isolation_resets_and_clock_gates(self):
        self.assert_case_passes("host-recovery")

    def test_modeled_reset_order_matches_the_pinned_dwc3_consumer(self):
        calls = re.findall(r"ret = (dwc3_phy_init|dwc3_core_soft_reset|dwc3_phy_power_on)\(dwc\);",
                           self.dwc3_core_init)
        self.assertEqual(calls, ["dwc3_phy_init", "dwc3_core_soft_reset", "dwc3_phy_power_on"])

    def test_dwc3_soft_reset_has_clocks_before_the_later_power_on(self):
        self.assert_case_passes("dwc3-init")

    def test_failed_controller_initialization_exit_shuts_down_the_active_phy(self):
        self.assert_case_passes("init-failure-exit")

    def test_successful_teardown_shuts_down_only_once_before_exit(self):
        self.assert_case_passes("success-teardown")

    def test_runtime_power_off_and_on_replays_host_without_duplicate_activation(self):
        self.assert_case_passes("runtime-cycle")

    def test_three_cable_cycles_preserve_shutdown_and_host_order(self):
        self.assert_case_passes("repeated-cables")

    def test_non_host_requests_do_not_read_or_write_phy_registers(self):
        for label in ("replay", "patched", "reset-only"):
            with self.subTest(label=label):
                result = self.run_case(label, "reject-non-host")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_supported_mode_selection_has_no_mmio_side_effects(self):
        self.assert_case_passes("host-mode-no-mmio")

    def test_initialization_and_balanced_shutdown_callbacks_are_wired(self):
        old = self.run_case("replay", "ops-wiring")
        self.assertEqual(old.returncode, 30, old.stdout + old.stderr)
        self.assertIn("init and balanced shutdown callbacks are not wired", old.stderr)
        self.assert_case_passes("ops-wiring")

    def test_replay_only_source_does_not_establish_reset_state(self):
        for case in ("init-clear", "reset-clear", "host-recovery"):
            with self.subTest(case=case):
                old = self.run_case("replay", case)
                self.assertEqual(old.returncode, 10, old.stdout + old.stderr)
                self.assertIn("PHY event count", old.stderr)

    def test_reset_only_init_reproduces_the_native_controller_clock_failure(self):
        old = self.run_case("reset-only", "dwc3-init")
        self.assertEqual(old.returncode, 50, old.stdout + old.stderr)
        self.assertIn("DWC3 soft reset sees gated clocks or asserted PHY resets", old.stderr)


if __name__ == "__main__":
    unittest.main()
