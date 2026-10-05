"""Exercise pinned DWC3 cable lifecycle functions with observable core/PHY calls.

The old-source controls expose early forced-host initialization, missing pending
probe drvdata, and teardown before rejecting a fixed-host device-role request.
These host-compiled checks do not claim native USB device enumeration.
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
FORCE_HOST = "t6040-dwc3-apple-force-host.patch"


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
enum usb_role { USB_ROLE_NONE, USB_ROLE_HOST, USB_ROLE_DEVICE };
enum usb_dr_mode { USB_DR_MODE_UNKNOWN, USB_DR_MODE_HOST,
                   USB_DR_MODE_PERIPHERAL, USB_DR_MODE_OTG };
enum phy_mode { PHY_MODE_USB_HOST, PHY_MODE_USB_DEVICE };
struct mutex { int unused; };
struct resource { int unused; };
struct reset_control { int unused; };
struct fwnode_handle { int unused; };
struct device {
    void *driver_data;
    bool force_host, force_device, wait_cable;
    enum usb_dr_mode dr_mode;
};
struct platform_device { struct device dev; };
struct dwc3 {
    struct device *dev;
    void *usb2_generic_phy[1], *usb3_generic_phy[1];
    enum usb_dr_mode dr_mode;
};
struct usb_role_switch {
    void *driver_data;
    int (*set)(struct usb_role_switch *, enum usb_role);
    enum usb_role (*get)(struct usb_role_switch *);
};
struct usb_role_switch_desc {
    struct fwnode_handle *fwnode;
    int (*set)(struct usb_role_switch *, enum usb_role);
    enum usb_role (*get)(struct usb_role_switch *);
    void *driver_data;
};
struct dwc3_probe_data {
    struct dwc3 *dwc;
    struct resource *res;
    bool ignore_clocks_and_resets, skip_core_init_mode;
    int properties;
};
#define __iomem
/* ACTUAL_APPLE_TYPES */
#define container_of(p,t,m) ((t *)((char *)(p) - offsetof(t,m)))
#define to_dwc3_apple(d) container_of((d), struct dwc3_apple, dwc)
#define guard(kind) ignore_lock
static void ignore_lock(void *lock) { (void)lock; }
#define mutex_init(p) ((void)(p))
#define mutex_lock(p) ((void)(p))
#define mutex_unlock(p) ((void)(p))
#define lockdep_assert_held(p) ((void)(p))
#define WARN_ON_ONCE(condition) ((void)(condition))
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define GFP_KERNEL 0
#define IORESOURCE_MEM 0
#define DWC3_DEFAULT_PROPERTIES 0
#define DWC3_GCTL_PRTCAP_HOST 1
#define DWC3_GCTL_PRTCAP_DEVICE 2
#define usb_get_dr_mode(dev) ((dev)->dr_mode)
#define dev_fwnode(dev) ((void)(dev), (struct fwnode_handle *)NULL)
static void report(struct device *dev, const char *fmt, ...) {
    (void)dev; (void)fmt;
}
#define dev_info report
#define dev_warn report
#define dev_err report
static int dev_err_probe(struct device *dev, int error, const char *fmt, ...) {
    (void)dev; (void)fmt; return error;
}
static void require(bool condition, int code, const char *message) {
    if (!condition) { fprintf(stderr, "%s\n", message); exit(code); }
}
static unsigned core_probes, core_inits, core_exits, core_removes;
static unsigned host_inits, host_exits, gadget_inits, gadget_exits;
static unsigned reset_asserts, reset_deasserts, role_unregistrations;
static unsigned phy_modes, setup_calls;
static int core_probe_error, core_init_error, host_init_error;
static int reset_assert_error, reset_deassert_error;
static struct dwc3_apple allocated;
static struct reset_control reset;
static struct resource resource;
static struct usb_role_switch registered;
static int usb2_phy, usb3_phy, apple_regs;
#define platform_set_drvdata(pdev, data) ((pdev)->dev.driver_data = (data))
static void *platform_get_drvdata(struct platform_device *pdev) {
    return pdev->dev.driver_data;
}
static void *devm_kzalloc(struct device *dev, size_t size, int flags) {
    (void)dev; (void)flags;
    require(size == sizeof(allocated), 1, "unexpected glue allocation size");
    memset(&allocated, 0, sizeof(allocated));
    return &allocated;
}
static struct reset_control *devm_reset_control_get_optional_exclusive(
        struct device *dev, const char *name) {
    (void)dev; (void)name; return &reset;
}
static int reset_control_assert(struct reset_control *control) {
    (void)control; ++reset_asserts; return reset_assert_error;
}
static int reset_control_deassert(struct reset_control *control) {
    (void)control; ++reset_deasserts; return reset_deassert_error;
}
static struct resource *platform_get_resource_byname(
        struct platform_device *pdev, int type, const char *name) {
    (void)pdev; (void)type; (void)name; return &resource;
}
static void *devm_platform_ioremap_resource_byname(
        struct platform_device *pdev, const char *name) {
    (void)pdev; (void)name; return &apple_regs;
}
static bool device_property_read_bool(struct device *dev, const char *name) {
    if (!strcmp(name, "apple,force-host-mode")) return dev->force_host;
    if (!strcmp(name, "apple,force-device-mode")) return dev->force_device;
    if (!strcmp(name, "arch-m4,usb-wait-for-cable")) return dev->wait_cable;
    require(false, 1, "unexpected probe property");
    return false;
}
static void *usb_role_switch_get_drvdata(struct usb_role_switch *sw) {
    return sw->driver_data;
}
static struct usb_role_switch *usb_role_switch_register(
        struct device *dev, struct usb_role_switch_desc *desc) {
    (void)dev;
    registered.driver_data = desc->driver_data;
    registered.set = desc->set;
    registered.get = desc->get;
    return &registered;
}
static void usb_role_switch_unregister(struct usb_role_switch *sw) {
    require(sw == &registered, 1, "wrong role switch removed");
    ++role_unregistrations;
}
static int phy_set_mode(void *phy, enum phy_mode mode) {
    (void)phy; (void)mode; ++phy_modes; return 0;
}
/* Group allocation/resource release itself is exercised in the dedicated
 * retry fixture; these adapters keep lifecycle tests on the final glue source. */
static inline __attribute__((unused)) void *devres_open_group(
        struct device *dev, void *id, int flags) {
    require(!id && flags == GFP_KERNEL, 1, "unexpected devres group options");
    return dev;
}
static inline __attribute__((unused)) void devres_close_group(
        struct device *dev, void *id) {
    require(id == dev, 1, "wrong group closed");
}
static inline __attribute__((unused)) void devres_remove_group(
        struct device *dev, void *id) {
    require(id == dev, 1, "wrong group removed");
}
static inline __attribute__((unused)) int devres_release_group(
        struct device *dev, void *id) {
    require(id == dev, 1, "wrong group released");
    return 0;
}
static int dwc3_core_probe(struct dwc3_probe_data *probe) {
    ++core_probes;
    if (core_probe_error) return core_probe_error;
    probe->dwc->dev->driver_data = probe->dwc;
    probe->dwc->usb2_generic_phy[0] = &usb2_phy;
    probe->dwc->usb3_generic_phy[0] = &usb3_phy;
    return 0;
}
static int dwc3_core_init(struct dwc3 *dwc) {
    (void)dwc; ++core_inits; return core_init_error;
}
static void dwc3_core_exit(struct dwc3 *dwc) { (void)dwc; ++core_exits; }
/* Observe the glue call only; this stub does not exercise core_remove's own
 * teardown and therefore cannot validate native active-controller removal. */
static void dwc3_core_remove(struct dwc3 *dwc) { (void)dwc; ++core_removes; }
static int dwc3_host_init(struct dwc3 *dwc) {
    (void)dwc; ++host_inits; return host_init_error;
}
static void dwc3_host_exit(struct dwc3 *dwc) { (void)dwc; ++host_exits; }
static int dwc3_gadget_init(struct dwc3 *dwc) { (void)dwc; ++gadget_inits; return 0; }
static void dwc3_gadget_exit(struct dwc3 *dwc) { (void)dwc; ++gadget_exits; }
static void dwc3_enable_susphy(struct dwc3 *dwc, bool enabled) {
    (void)dwc; (void)enabled;
}
static void dwc3_apple_setup_cio(struct dwc3_apple *apple) { (void)apple; ++setup_calls; }
static void dwc3_apple_set_ptrcap(struct dwc3_apple *apple, unsigned mode) {
    (void)apple; (void)mode;
}
"""

MAIN = r"""
int main(int argc, char **argv) {
    require(argc == 2, 1, "missing test case");
    const char *name = argv[1];
    struct platform_device pdev = { .dev = { .dr_mode = USB_DR_MODE_HOST } };
    struct dwc3_apple apple = {
        .dev = &pdev.dev, .reset = &reset, .state = DWC3_APPLE_PROBE_PENDING,
    };
    struct usb_role_switch sw = { .driver_data = &apple };
    apple.dwc.dev = &pdev.dev;
    apple.dwc.usb2_generic_phy[0] = &usb2_phy;
    apple.dwc.usb3_generic_phy[0] = &usb3_phy;
    int ret;

    if (!strncmp(name, "probe-", 6)) {
        pdev.dev.wait_cable = strcmp(name, "probe-legacy") != 0;
        pdev.dev.force_host = strcmp(name, "probe-pending-remove") != 0;
        require(!dwc3_apple_probe(&pdev), 2, "glue probe failed");
        if (!strcmp(name, "probe-legacy")) {
            require(allocated.state == DWC3_APPLE_HOST && host_inits == 1 &&
                    core_probes == 1, 52, "legacy fixed host no longer initializes");
        } else {
            require(allocated.state == DWC3_APPLE_PROBE_PENDING &&
                    !host_inits && !core_probes && !reset_deasserts, 50,
                    "wait-for-cable marker did not suppress forced-host init");
            require(platform_get_drvdata(&pdev) == &allocated.dwc, 51,
                    "pending probe has no glue drvdata for safe removal");
        }
        dwc3_apple_remove(&pdev);
        require(role_unregistrations == 1, 53, "removal did not unregister role switch");
        if (pdev.dev.wait_cable) {
            require(!host_exits && !gadget_exits && !core_exits && !core_removes &&
                    reset_asserts == 1, 54, "pending removal touched unprobed core");
        } else {
            require(host_exits == 1 && core_exits == 1 && core_removes == 1, 55,
                    "legacy host removal changed its glue teardown calls");
        }
    } else if (!strcmp(name, "host-cycle")) {
        require(!dwc3_usb_role_switch_set(&sw, USB_ROLE_NONE) && !core_probes &&
                !core_exits && !reset_asserts, 20, "NONE touched pending core");
        require(!dwc3_usb_role_switch_set(&sw, USB_ROLE_HOST), 21, "first host init failed");
        require(apple.state == DWC3_APPLE_HOST && core_probes == 1 && !core_inits &&
                host_inits == 1 && !host_exits, 22, "HOST did not initialize pending core");
        require(!dwc3_usb_role_switch_set(&sw, USB_ROLE_HOST), 23, "duplicate HOST failed");
        require(host_inits == 1 && !host_exits && !core_exits && !reset_asserts, 24,
                "duplicate HOST restarted controller");
        require(!dwc3_usb_role_switch_set(&sw, USB_ROLE_NONE), 25, "detach failed");
        require(apple.state == DWC3_APPLE_NO_CABLE && host_exits == 1 &&
                core_exits == 1 && reset_asserts == 1, 26, "detach did not tear down host");
        require(!dwc3_usb_role_switch_set(&sw, USB_ROLE_NONE) && host_exits == 1 &&
                core_exits == 1, 27, "duplicate detach repeated teardown");
        require(!dwc3_usb_role_switch_set(&sw, USB_ROLE_HOST), 28, "reattach failed");
        require(apple.state == DWC3_APPLE_HOST && core_probes == 1 && core_inits == 1 &&
                host_inits == 2 && phy_modes == 4 && setup_calls == 2, 29,
                "reattach did not replay initialized core and PHY lifecycle");
    } else if (!strcmp(name, "reject-device")) {
        apple.state = DWC3_APPLE_HOST;
        ret = dwc3_usb_role_switch_set(&sw, USB_ROLE_DEVICE);
        require(apple.state == DWC3_APPLE_HOST && !host_exits && !core_exits &&
                !reset_asserts && !reset_deasserts && !gadget_inits, 10,
                "fixed-host DEVICE request tore down active host");
        require(ret == -EOPNOTSUPP, 11, "fixed-host DEVICE request was not rejected");
    } else if (!strcmp(name, "otg-device")) {
        pdev.dev.dr_mode = USB_DR_MODE_OTG;
        require(!dwc3_usb_role_switch_set(&sw, USB_ROLE_DEVICE) &&
                apple.state == DWC3_APPLE_DEVICE && gadget_inits == 1, 12,
                "device restriction leaked into an OTG controller");
    } else if (!strcmp(name, "probe-init-error")) {
        core_probe_error = -EIO;
        ret = dwc3_usb_role_switch_set(&sw, USB_ROLE_HOST);
        require(ret == -EIO && apple.state == DWC3_APPLE_PROBE_PENDING &&
                core_probes == 1 && !host_inits && reset_asserts == 1, 30,
                "initial core probe error was not returned with reset asserted");
    } else if (!strcmp(name, "resume-init-error")) {
        apple.state = DWC3_APPLE_NO_CABLE;
        core_init_error = -ETIMEDOUT;
        ret = dwc3_usb_role_switch_set(&sw, USB_ROLE_HOST);
        require(ret == -ETIMEDOUT && apple.state == DWC3_APPLE_NO_CABLE &&
                core_inits == 1 && !core_probes && !host_inits && reset_asserts == 1, 31,
                "reattach core init error was not returned with reset asserted");
    } else if (!strcmp(name, "host-init-error")) {
        host_init_error = -ENODEV;
        ret = dwc3_usb_role_switch_set(&sw, USB_ROLE_HOST);
        require(ret == -ENODEV && apple.state == DWC3_APPLE_NO_CABLE &&
                host_inits == 1 && core_exits == 1 && reset_asserts == 1, 32,
                "host init failure did not unwind core and propagate error");
    } else if (!strcmp(name, "reset-deassert-error")) {
        reset_deassert_error = -EIO;
        ret = dwc3_usb_role_switch_set(&sw, USB_ROLE_HOST);
        require(ret == -EIO && apple.state == DWC3_APPLE_PROBE_PENDING &&
                !core_probes && !host_inits, 33, "reset error did not stop host init");
    } else if (!strcmp(name, "detach-reset-error")) {
        apple.state = DWC3_APPLE_HOST;
        reset_assert_error = -EIO;
        ret = dwc3_usb_role_switch_set(&sw, USB_ROLE_NONE);
        require(ret == -EIO && apple.state == DWC3_APPLE_NO_CABLE &&
                host_exits == 1 && core_exits == 1 && !host_inits, 34,
                "detach reset error did not propagate after teardown");
    } else {
        require(false, 1, "unknown test case");
    }
    puts("DWC3 cable lifecycle checks passed");
    return 0;
}
"""


class UsbCableLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("cc", "git"):
            if not shutil.which(tool):
                raise unittest.SkipTest("USB cable C harness requires " + tool)
        lock = json.loads((PROJECT / "sources.lock.json").read_text())
        caches = {name: PROJECT / "cache/git" / (name + ".git")
                  for name in ("linux", "wallace")}
        if not all(path.is_dir() for path in caches.values()):
            raise unittest.SkipTest("USB cable C harness requires pinned cached sources")
        temporary = tempfile.TemporaryDirectory(prefix="arch-m4-usb-cable-test-")
        cls.addClassCleanup(temporary.cleanup)
        tree = Path(temporary.name)

        def cached(name, path):
            return subprocess.check_output([
                "git", "--git-dir=" + str(caches[name]), "show",
                lock[name]["revision"] + ":" + path], timeout=15)

        source = tree / DWC3
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(cached("linux", DWC3))
        force_host = cached("wallace", "patches/" + FORCE_HOST)
        if hashlib.sha256(force_host).hexdigest() != hardware.PATCHES[FORCE_HOST]:
            raise AssertionError("cached Wallace force-host patch digest changed")
        subprocess.run(["git", "apply", "-"], input=force_host,
                       cwd=tree, check=True, timeout=15)
        original = source.read_text()
        for metadata in (item for item in hardware.USB_CABLE_FIXES if item["source"] == DWC3):
            if hashlib.sha256(source.read_bytes()).hexdigest() != metadata["base_source_sha256"]:
                raise AssertionError("DWC3 patch base does not match pinned digest")
            patch = PROJECT / metadata["path"]
            if hashlib.sha256(patch.read_bytes()).hexdigest() != metadata["sha256"]:
                raise AssertionError("DWC3 patch does not match pinned digest")
            subprocess.run(["git", "apply", "--check", str(patch)],
                           cwd=tree, check=True, timeout=15)
            subprocess.run(["git", "apply", str(patch)], cwd=tree, check=True, timeout=15)
            if hashlib.sha256(source.read_bytes()).hexdigest() != metadata["result_source_sha256"]:
                raise AssertionError("patched DWC3 source does not match pinned digest")

        cls.binaries = {}
        for label, body in (("original", original), ("patched", source.read_text())):
            types = "\n".join(re.search(
                kind + r" \{.*?\n\};", body, re.S).group()
                for kind in ("enum dwc3_apple_state", "struct dwc3_apple"))
            actual = "\n".join(function(body, declaration) for declaration in (
                "static int dwc3_apple_core_probe(", "static int dwc3_apple_core_init(",
                "static int dwc3_apple_init(", "static int dwc3_apple_exit(",
                "static int dwc3_usb_role_switch_set(",
                "static enum usb_role dwc3_usb_role_switch_get(",
                "static int dwc3_apple_setup_role_switch(", "static int dwc3_apple_probe(",
                "static void dwc3_apple_remove("))
            harness = tree / (label + ".c")
            harness.write_text(PRELUDE.replace("/* ACTUAL_APPLE_TYPES */", types) + actual + MAIN)
            cls.binaries[label] = tree / label
            result = subprocess.run([
                shutil.which("cc"), "-std=gnu11", "-O0", "-Wall", "-Wextra", "-Werror",
                "-Wno-missing-field-initializers",
                str(harness), "-o", str(cls.binaries[label]),
            ], capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise AssertionError("DWC3 harness compilation failed: " + result.stderr)

    def run_case(self, label, case):
        return subprocess.run([str(self.binaries[label]), case],
                              capture_output=True, text=True, timeout=5)

    def assert_case_passes(self, case):
        result = self.run_case("patched", case)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_host_attach_detach_duplicate_events_and_reattach(self):
        self.assert_case_passes("host-cycle")

    def test_fixed_host_rejects_device_before_teardown(self):
        old = self.run_case("original", "reject-device")
        self.assertEqual(old.returncode, 10, old.stdout + old.stderr)
        self.assertIn("tore down active host", old.stderr)
        self.assert_case_passes("reject-device")

    def test_otg_controller_still_accepts_device_role(self):
        self.assert_case_passes("otg-device")

    def test_core_host_and_reset_errors_propagate_and_unwind(self):
        for case in ("probe-init-error", "resume-init-error", "host-init-error",
                     "reset-deassert-error", "detach-reset-error"):
            with self.subTest(case=case):
                self.assert_case_passes(case)

    def test_wait_marker_suppresses_legacy_force_host_and_removes_pending_probe(self):
        old = self.run_case("original", "probe-wait")
        self.assertEqual(old.returncode, 50, old.stdout + old.stderr)
        self.assertIn("did not suppress", old.stderr)
        self.assert_case_passes("probe-wait")

    def test_pending_probe_publishes_drvdata_without_forced_init(self):
        old = self.run_case("original", "probe-pending-remove")
        self.assertEqual(old.returncode, 51, old.stdout + old.stderr)
        self.assertIn("no glue drvdata", old.stderr)
        self.assert_case_passes("probe-pending-remove")

    def test_legacy_force_host_behavior_and_glue_removal_calls_are_preserved(self):
        for label in ("original", "patched"):
            with self.subTest(label=label):
                result = self.run_case(label, "probe-legacy")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
