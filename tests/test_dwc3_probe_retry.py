"""Compile the pinned Apple wrapper and check deferred core-probe retries.

The core-probe and devres adapters model allocations and group boundaries. They
expose retained MMIO reservations, dropped PHY references/readiness, and nested
resource groups; they do not execute Linux's core probe or prove native USB
enumeration. The wrapper being tested is extracted from authenticated source.
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

DWC3 = "drivers/usb/dwc3/dwc3-apple.c"
PATCH = "patches/experimental-dwc3-probe-retry.patch"
PATCH_SHA256 = "7b8aa8ca2f77159e19780904d4aa6942940166d3317ee282723f24eca985e5ff"
BASE_SHA256 = "f7df0c0c3e294656ee56f565585a6c723c7c96aac060d76a5d56a79f32eab52a"
RESULT_SHA256 = "8714bbccc22861f21ab7a31cec4e9950611ab0bd443c281487bb4d246260da23"


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
#define __iomem
#define GFP_KERNEL 0
#define DWC3_DEFAULT_PROPERTIES 0
#define lockdep_assert_held(lock) ((void)(lock))
#define WARN_ON_ONCE(condition) ((void)(condition))
struct device { void *driver_data; };
struct mutex { int unused; };
struct resource { int unused; };
struct reset_control { int unused; };
struct usb_role_switch { int unused; };
struct dwc3 {
    struct device *dev;
    void *regs, *ev_buf, *usb_psy, *edev, *ulpi;
    size_t regs_size;
    void *usb2_phy, *usb3_phy;
    void *usb2_generic_phy[2], *usb3_generic_phy[2];
    bool phys_ready, ulpi_ready;
    unsigned num_usb2_ports, num_usb3_ports;
};
/* ACTUAL_APPLE_TYPES */
struct dwc3_probe_data {
    struct dwc3 *dwc;
    struct resource *res;
    bool ignore_clocks_and_resets, skip_core_init_mode;
    int properties;
};
static void require(bool condition, int code, const char *message) {
    if (!condition) { fprintf(stderr, "%s\n", message); exit(code); }
}

/* A deliberately small devres model: open/close markers bracket resources.
 * Releasing an open outer group also consumes nested group markers. */
enum node_kind { RESOURCE, OPEN_GROUP, CLOSE_GROUP };
enum resource_kind { PERSISTENT, CORE_MMIO, CORE_PHY, CORE_EVENT };
struct group { struct device *dev; bool active, closed; };
struct node { enum node_kind kind; unsigned value; struct group *group; };
static struct node nodes[128];
static struct group groups[32];
static unsigned node_count, group_count, live[4];
static unsigned group_opens, group_closes, group_removes, group_releases;
static bool fail_group_alloc;
static void add_resource(enum resource_kind kind) {
    require(node_count < 128, 1, "resource model overflow");
    nodes[node_count++] = (struct node){ .kind = RESOURCE, .value = kind };
    ++live[kind];
}
static inline void *devres_open_group(struct device *dev, void *id, int flags) {
    require(!id && flags == GFP_KERNEL, 1, "unexpected group options");
    ++group_opens;
    if (fail_group_alloc) return NULL;
    require(group_count < 32 && node_count < 128, 1, "group model overflow");
    struct group *group = &groups[group_count++];
    *group = (struct group){ .dev = dev, .active = true };
    nodes[node_count++] = (struct node){ .kind = OPEN_GROUP, .group = group };
    return group;
}
static inline void devres_close_group(struct device *dev, void *id) {
    struct group *group = id;
    require(group && group->active && !group->closed && group->dev == dev,
            1, "wrong group closed");
    group->closed = true;
    nodes[node_count++] = (struct node){ .kind = CLOSE_GROUP, .group = group };
    ++group_closes;
}
static inline __attribute__((unused)) void devres_remove_group(struct device *dev, void *id) {
    struct group *group = id;
    require(group && group->active && group->closed && group->dev == dev,
            1, "wrong group removed");
    unsigned out = 0;
    for (unsigned i = 0; i < node_count; ++i)
        if (nodes[i].group != group) nodes[out++] = nodes[i];
    node_count = out;
    group->active = false;
    ++group_removes;
}
static inline __attribute__((unused)) int devres_release_group(struct device *dev, void *id) {
    struct group *group = id;
    require(group && group->active && group->dev == dev, 1, "wrong group released");
    unsigned start = node_count, end = node_count;
    for (unsigned i = 0; i < node_count; ++i) {
        if (nodes[i].group != group) continue;
        if (nodes[i].kind == OPEN_GROUP) start = i;
        if (nodes[i].kind == CLOSE_GROUP) end = i + 1;
    }
    require(start < end, 1, "missing open group");
    int released = 0;
    for (unsigned i = end; i-- > start;) {
        struct node *node = &nodes[i];
        if (node->kind == RESOURCE) {
            require(live[node->value] > 0, 1, "double resource release");
            --live[node->value];
            ++released;
        } else {
            node->group->active = false;
        }
    }
    memmove(nodes + start, nodes + end, (node_count - end) * sizeof(*nodes));
    node_count -= end - start;
    ++group_releases;
    return released;
}
static unsigned active_groups(void) {
    unsigned count = 0;
    for (unsigned i = 0; i < group_count; ++i) count += groups[i].active;
    return count;
}
static unsigned core_probes, phy_gets, ulpi_inits, runtime_unwinds;
static int first_probe_error;
static bool fail_before_phy, fail_at_mmio, use_nested_group;
static int core_regs, generic_phy, legacy_phy, event_buffer, supply, extcon, ulpi;
static int dwc3_core_probe(struct dwc3_probe_data *data) {
    struct dwc3 *dwc = data->dwc;
    ++core_probes;
    require(data->ignore_clocks_and_resets && data->skip_core_init_mode,
            1, "wrapper changed core options");
    if (fail_at_mmio || live[CORE_MMIO]) return -EBUSY;
    add_resource(CORE_MMIO);
    dwc->regs = &core_regs;
    dwc->regs_size = 0x1000;
    dwc->usb_psy = &supply;
    if (fail_before_phy && first_probe_error) return first_probe_error;
    ++dwc->num_usb2_ports;
    ++dwc->num_usb3_ports;
    add_resource(CORE_EVENT);
    dwc->ev_buf = &event_buffer;
    dwc->edev = &extcon;
    if (!dwc->ulpi_ready) {
        ++ulpi_inits;
        dwc->ulpi_ready = true;
        dwc->ulpi = &ulpi;
    }
    if (!dwc->phys_ready) {
        ++phy_gets;
        add_resource(CORE_PHY);
        dwc->usb2_phy = dwc->usb3_phy = &legacy_phy;
        for (unsigned i = 0; i < 2; ++i)
            dwc->usb2_generic_phy[i] = dwc->usb3_generic_phy[i] = &generic_phy;
        dwc->phys_ready = true;
    }
    if (use_nested_group) {
        void *nested = devres_open_group(dwc->dev, NULL, GFP_KERNEL);
        require(nested != NULL, 1, "nested allocation failed unexpectedly");
        add_resource(CORE_EVENT);
        devres_close_group(dwc->dev, nested);
    }
    if (first_probe_error) {
        /* The real core already unwinds PM/non-managed buffers at this point.
         * Retained managed resources and readiness state are intentionally
         * left for the real Apple wrapper under test to handle. */
        ++runtime_unwinds;
        return first_probe_error;
    }
    dwc->dev->driver_data = dwc;
    return 0;
}
"""

MAIN = r"""
int main(int argc, char **argv) {
    require(argc == 2, 1, "missing test case");
    const char *name = argv[1];
    struct device dev = {};
    struct resource resource = {};
    struct reset_control reset = {};
    int apple_regs;
    struct dwc3_apple apple = {
        .dev = &dev, .mmio_resource = &resource, .apple_regs = &apple_regs,
        .reset = &reset, .state = DWC3_APPLE_PROBE_PENDING,
    };
    apple.dwc.dev = &dev;
    dev.driver_data = &apple.dwc;
    add_resource(PERSISTENT);
    add_resource(PERSISTENT);
    if (!strcmp(name, "group-oom")) {
        fail_group_alloc = true;
        int ret = dwc3_apple_core_probe(&apple);
        require(ret == -ENOMEM && !core_probes && !group_releases &&
                apple.state == DWC3_APPLE_PROBE_PENDING && live[PERSISTENT] == 2,
                10, "group OOM did not stop before core probe");
    } else if (!strcmp(name, "success")) {
        require(!dwc3_apple_core_probe(&apple), 11, "core success failed");
        require(apple.state == DWC3_APPLE_NO_CABLE && group_closes == 1 &&
                group_removes == 1 && !group_releases && !active_groups() &&
                live[CORE_MMIO] == 1 && live[CORE_PHY] == 1 &&
                apple.dwc.regs == &core_regs && apple.dwc.phys_ready,
                12, "successful group did not retain core resources");
    } else {
        first_probe_error = -ETIMEDOUT;
        fail_before_phy = !strcmp(name, "early-error");
        fail_at_mmio = !strcmp(name, "mmio-error");
        use_nested_group = !strcmp(name, "nested-error");
        int ret = dwc3_apple_core_probe(&apple);
        require(ret == (fail_at_mmio ? -EBUSY : -ETIMEDOUT), 13,
                "first probe error changed");
        require(apple.state == DWC3_APPLE_PROBE_PENDING &&
                live[PERSISTENT] == 2 && !live[CORE_MMIO] && !live[CORE_PHY] &&
                !live[CORE_EVENT] && !active_groups() && group_releases == 1,
                14, "failed probe retained managed core resources");
        require(apple.dwc.dev == &dev && !apple.dwc.regs && !apple.dwc.regs_size &&
                !apple.dwc.ev_buf && !apple.dwc.usb_psy && !apple.dwc.edev &&
                !apple.dwc.usb2_phy && !apple.dwc.usb3_phy &&
                !apple.dwc.phys_ready && !apple.dwc.ulpi_ready && !apple.dwc.ulpi &&
                !apple.dwc.num_usb2_ports && !apple.dwc.num_usb3_ports,
                15, "failed probe retained dangling pointers or readiness/count state");
        for (unsigned i = 0; i < 2; ++i)
            require(!apple.dwc.usb2_generic_phy[i] && !apple.dwc.usb3_generic_phy[i],
                    16, "failed probe retained generic PHY reference");
        require(dev.driver_data == &apple.dwc && apple.dev == &dev &&
                apple.mmio_resource == &resource && apple.apple_regs == &apple_regs &&
                apple.reset == &reset, 17, "failed probe damaged persistent glue");
        unsigned previous_phy_gets = phy_gets;
        unsigned previous_ulpi_inits = ulpi_inits;
        first_probe_error = 0;
        fail_at_mmio = false;
        use_nested_group = false;
        require(!dwc3_apple_core_probe(&apple), 18, "retry could not reserve core MMIO");
        require(apple.state == DWC3_APPLE_NO_CABLE && core_probes == 2 &&
                phy_gets == previous_phy_gets + 1 && ulpi_inits == previous_ulpi_inits + 1 &&
                apple.dwc.num_usb2_ports == 1 && apple.dwc.num_usb3_ports == 1 &&
                live[CORE_MMIO] == 1 && live[CORE_PHY] == 1 && live[PERSISTENT] == 2 &&
                !active_groups(), 19, "retry did not reacquire PHYs as a fresh core probe");
        require(runtime_unwinds == (fail_before_phy || !strcmp(name, "mmio-error") ? 0 : 1),
                20, "wrapper interfered with modeled core error cleanup");
    }
    puts("DWC3 deferred probe retry checks passed");
    return 0;
}
"""


class Dwc3ProbeRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("cc", "git"):
            if not shutil.which(tool):
                raise unittest.SkipTest("DWC3 retry C harness requires " + tool)
        lock = json.loads((PROJECT / "sources.lock.json").read_text())
        caches = {name: PROJECT / "cache/git" / (name + ".git")
                  for name in ("linux", "wallace")}
        if not all(path.is_dir() for path in caches.values()):
            raise unittest.SkipTest("DWC3 retry C harness requires pinned cached sources")
        temporary = tempfile.TemporaryDirectory(prefix="arch-m4-dwc3-retry-test-")
        cls.addClassCleanup(temporary.cleanup)
        tree = Path(temporary.name)

        def cached(name, path):
            return subprocess.check_output([
                "git", "--git-dir=" + str(caches[name]), "show",
                lock[name]["revision"] + ":" + path], timeout=15)

        source = tree / DWC3
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(cached("linux", DWC3))
        force_name = "t6040-dwc3-apple-force-host.patch"
        force = cached("wallace", "patches/" + force_name)
        if hashlib.sha256(force).hexdigest() != hardware.PATCHES[force_name]:
            raise AssertionError("cached Wallace force-host patch digest changed")
        subprocess.run(["git", "apply", "-"], input=force,
                       cwd=tree, check=True, timeout=15)
        lifecycle = next(item for item in hardware.USB_CABLE_FIXES
                         if item["path"] == "patches/experimental-dwc3-cable-lifecycle.patch")
        retry = next(item for item in hardware.USB_CABLE_FIXES
                     if item["path"] == PATCH)
        if (retry["sha256"], retry["base_source_sha256"], retry["result_source_sha256"]) != (
                PATCH_SHA256, BASE_SHA256, RESULT_SHA256):
            raise AssertionError("DWC3 retry profile no longer matches reviewed harness source")
        for metadata in (lifecycle, retry):
            if hashlib.sha256(source.read_bytes()).hexdigest() != metadata["base_source_sha256"]:
                raise AssertionError("DWC3 patch base does not match pinned digest")
            patch = PROJECT / metadata["path"]
            if hashlib.sha256(patch.read_bytes()).hexdigest() != metadata["sha256"]:
                raise AssertionError("DWC3 patch does not match pinned digest")
            if metadata["path"] == PATCH:
                original = source.read_text()
            subprocess.run(["git", "apply", "--check", str(patch)],
                           cwd=tree, check=True, timeout=15)
            subprocess.run(["git", "apply", str(patch)], cwd=tree, check=True, timeout=15)
            if hashlib.sha256(source.read_bytes()).hexdigest() != metadata["result_source_sha256"]:
                raise AssertionError("patched DWC3 source does not match pinned digest")

        patched = source.read_text()
        release_only = patched.replace(
            "\t\tmemset(&appledwc->dwc, 0, sizeof(appledwc->dwc));\n", "", 1)
        if release_only == patched:
            raise AssertionError("retry negative control did not remove embedded core reset")
        cls.binaries = {}
        for label, body in (("original", original), ("release-only", release_only),
                            ("patched", patched)):
            types = "\n".join(re.search(
                kind + r" \{.*?\n\};", body, re.S).group()
                for kind in ("enum dwc3_apple_state", "struct dwc3_apple"))
            actual = function(body, "static int dwc3_apple_core_probe(")
            harness = tree / (label + ".c")
            harness.write_text(PRELUDE.replace("/* ACTUAL_APPLE_TYPES */", types) + actual + MAIN)
            cls.binaries[label] = tree / label
            result = subprocess.run([
                shutil.which("cc"), "-std=gnu11", "-O0", "-Wall", "-Wextra", "-Werror",
                str(harness), "-o", str(cls.binaries[label]),
            ], capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise AssertionError("DWC3 retry harness compilation failed: " + result.stderr)

    def run_case(self, label, case):
        return subprocess.run([str(self.binaries[label]), case],
                              capture_output=True, text=True, timeout=5)

    def assert_case_passes(self, case):
        result = self.run_case("patched", case)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_timeout_releases_mmio_and_reacquires_phy_on_retry(self):
        old = self.run_case("original", "timeout")
        self.assertEqual(old.returncode, 14, old.stdout + old.stderr)
        self.assertIn("retained managed core resources", old.stderr)
        self.assert_case_passes("timeout")

    def test_releasing_resources_without_resetting_readiness_is_detected(self):
        old = self.run_case("release-only", "timeout")
        self.assertEqual(old.returncode, 15, old.stdout + old.stderr)
        self.assertIn("dangling pointers or readiness/count state", old.stderr)
        self.assert_case_passes("timeout")

    def test_failure_before_phy_acquisition_cleans_partial_probe(self):
        self.assert_case_passes("early-error")

    def test_mmio_failure_retries_without_damaging_persistent_glue(self):
        self.assert_case_passes("mmio-error")

    def test_nested_managed_group_is_released_with_probe_group(self):
        self.assert_case_passes("nested-error")

    def test_group_allocation_failure_prevents_core_probe(self):
        self.assert_case_passes("group-oom")

    def test_success_retains_managed_resources_and_removes_group_markers(self):
        self.assert_case_passes("success")


if __name__ == "__main__":
    unittest.main()
