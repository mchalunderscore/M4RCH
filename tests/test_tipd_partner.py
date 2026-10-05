"""Exercise actual TIPD partner construction against a retaining class consumer.

Requires the pinned source caches and a host C compiler. Pattern initialization
makes unspecified descriptor fields fail deterministically in the old source;
the identity checks verify lifetime and replacement order without hardware.
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

TIPD = "drivers/usb/typec/tipd/"
TRANSPORT = "0001-usb-typec-tps6598x-add-SPMI-transport-for-T6040-SN20.patch"


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
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
enum typec_accessory { TYPEC_ACCESSORY_NONE };
enum typec_pwr_opmode { TYPEC_PWR_MODE_USB, TYPEC_PWR_MODE_PD = 3 };
enum typec_orientation {
    TYPEC_ORIENTATION_NONE, TYPEC_ORIENTATION_NORMAL, TYPEC_ORIENTATION_REVERSE
};
enum usb_role { USB_ROLE_NONE, USB_ROLE_HOST, USB_ROLE_DEVICE };
struct typec_partner;
struct device;
/* ACTUAL_TYPEC_DESCRIPTORS */
struct typec_partner {
    struct usb_pd_identity *identity;
    u16 pd_revision;
    u8 usb_capability;
    void (*attach)(struct typec_partner *, struct device *);
    void (*deattach)(struct typec_partner *, struct device *);
};
struct work_struct { int unused; };
struct delayed_work { struct work_struct work; };
struct cd321x_status {
    u32 status, pwr_status, data_status, status_changed;
    struct usb_pd_identity partner_identity;
};
struct tps6598x {
    int lock, dev, psy;
    void *port, *role_sw;
    struct typec_partner *partner;
    struct usb_pd_identity partner_identity;
    u32 data_status, pwr_status;
};
struct cd321x {
    struct tps6598x tps;
    struct { void *alt; int mode; void *data; } state;
    struct cd321x_status update_status;
    struct delayed_work update_work;
    struct usb_pd_identity cur_partner_identity;
};
#define container_of(p,t,m) ((t *)((char *)(p) - offsetof(t,m)))
#define to_delayed_work(p) container_of(p, struct delayed_work, work)
#define guard(kind) ignore_lock
static void ignore_lock(void *lock) { (void)lock; }
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define dev_warn(...) ((void)0)
#define TPS_STATUS_PLUG_PRESENT 1U
#define TPS_DATA_STATUS_USB2_CONNECTION 1U
#define TPS_DATA_STATUS_USB3_CONNECTION 2U
#define TPS_DATA_STATUS_USB_DATA_ROLE 4U
#define TPS_POWER_STATUS_PWROPMODE(p) (p)
#define TPS_STATUS_TO_UPSIDE_DOWN(s) ((s) & 2U)
#define TPS_STATUS_TO_TYPEC_PORTROLE(s) ((s) & 4U)
#define TPS_STATUS_TO_TYPEC_VCONN(s) ((s) & 8U)
#define TPS_STATUS_TO_TYPEC_DATAROLE(s) ((s) & 16U)
#define TYPEC_STATE_SAFE 0
#define TYPEC_STATE_USB 1
#define ignore_two(a,b) ((void)(a), (void)(b))
#define typec_set_pwr_opmode ignore_two
#define typec_set_pwr_role ignore_two
#define typec_set_vconn_role ignore_two
#define typec_set_orientation ignore_two
#define typec_set_mode ignore_two
#define typec_set_data_role ignore_two
#define power_supply_changed(p) ((void)(p))
#define typec_partner_set_identity(p) ((void)(p))
static void tps6598x_set_data_role(struct tps6598x *tps, int role, bool connected) {
    (void)tps; (void)role; (void)connected;
}
static int tps6598x_read_partner_identity(struct tps6598x *tps) {
    (void)tps; return 0;
}
static enum usb_role usb_role_switch_get_role(void *role_sw) {
    (void)role_sw; return USB_ROLE_NONE;
}
static void usb_role_switch_set_role(void *role_sw, enum usb_role role) {
    (void)role_sw; (void)role;
}
static void cd321x_typec_update_mode(struct tps6598x *tps, struct cd321x_status *st) {
    (void)tps; (void)st;
}
static struct typec_partner created, previous;
static struct usb_pd_identity before, expected;
static struct usb_pd_identity *persistent;
static bool check_defaults, check_identity, check_preservation;
static unsigned registrations, unregistrations;
static void require(bool condition, int code, const char *message) {
    if (!condition) { fprintf(stderr, "%s\n", message); exit(code); }
}
static struct typec_partner *typec_register_partner(void *port,
                                                  struct typec_partner_desc *desc) {
    (void)port;
    ++registrations;
    if (check_defaults)
        require(!desc->pd_revision && !desc->usb_capability &&
                !desc->attach && !desc->deattach, 10,
                "unspecified partner fields are not zero");
    if (check_identity) {
        require(desc->identity == persistent, 20,
                "class retained identity is not controller-owned");
        require(!memcmp(desc->identity, &expected, sizeof(expected)), 21,
                "persistent identity was not copied before registration");
    }
    if (check_preservation)
        require(unregistrations == 1, 30,
                "old partner was not unregistered before replacement");
    /* Like the Type-C class, retain the identity address rather than copying it. */
    created.identity = desc->identity;
    created.pd_revision = desc->pd_revision;
    created.usb_capability = desc->usb_capability;
    created.attach = desc->attach;
    created.deattach = desc->deattach;
    return &created;
}
static void typec_unregister_partner(struct typec_partner *partner) {
    if (!partner) return;
    ++unregistrations;
    if (check_preservation) {
        require(partner == &previous, 31, "unexpected partner unregistered");
        require(!memcmp(partner->identity, &before, sizeof(before)), 32,
                "old partner identity changed before unregistration");
    }
}
"""

MAIN = r"""
int main(int argc, char **argv) {
    require(argc == 2, 1, "missing test case");
    struct cd321x cd = {0};
    before.id_header = 0x11223344;
    expected.id_header = 0x55667788;
    expected.vdo[2] = 0xaabbccdd;
    cd.update_status.status = TPS_STATUS_PLUG_PRESENT;
    cd.update_status.pwr_status = TYPEC_PWR_MODE_PD;
    cd.update_status.partner_identity = expected;
    persistent = &cd.cur_partner_identity;
    if (!strcmp(argv[1], "generic-defaults")) {
        check_defaults = check_identity = true;
        cd.tps.partner_identity = expected;
        cd.tps.pwr_status = TYPEC_PWR_MODE_PD;
        persistent = &cd.tps.partner_identity;
        require(!tps6598x_connect(&cd.tps, TPS_STATUS_PLUG_PRESENT), 2,
                "generic registration failed");
    } else {
        if (!strcmp(argv[1], "cd-defaults")) {
            check_defaults = true;
            cd.update_status.pwr_status = TYPEC_PWR_MODE_USB;
        } else if (!strcmp(argv[1], "cd-identity")) {
            check_identity = true;
        } else {
            cd.cur_partner_identity = before;
            previous.identity = persistent;
            cd.tps.partner = &previous;
            check_preservation = true;
            if (!strcmp(argv[1], "cd-replace")) {
                check_identity = true;
            } else if (!strcmp(argv[1], "cd-unchanged")) {
                cd.update_status.partner_identity = before;
            } else if (!strcmp(argv[1], "cd-disconnect")) {
                cd.update_status.status = 0;
            } else {
                require(false, 1, "unknown test case");
            }
        }
        cd321x_update_work(&cd.update_work.work);
    }
    if (!strcmp(argv[1], "cd-unchanged")) {
        require(!registrations && !unregistrations && cd.tps.partner == &previous,
                40, "unchanged partner was replaced");
        require(!memcmp(persistent, &before, sizeof(before)), 41,
                "unchanged partner identity was modified");
    } else if (!strcmp(argv[1], "cd-disconnect")) {
        require(!registrations && unregistrations == 1 && !cd.tps.partner,
                42, "disconnection did not remove only the old partner");
        require(!memcmp(persistent, &before, sizeof(before)), 43,
                "disconnection changed the old identity");
    } else {
        require(registrations == 1 && cd.tps.partner == &created, 44,
                "partner was not registered exactly once");
        if (check_identity) {
            require(created.identity == persistent, 45,
                    "retained identity address did not survive worker return");
            require(!memcmp(created.identity, &expected, sizeof(expected)), 46,
                    "retained identity content changed after worker return");
        }
    }
    puts("partner descriptor and identity lifetime checks passed");
    return 0;
}
"""


class TipdPartnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("cc", "git"):
            if not shutil.which(tool):
                raise unittest.SkipTest("TIPD C harness requires " + tool)
        lock = json.loads((PROJECT / "sources.lock.json").read_text())
        caches = {name: PROJECT / "cache/git" / (name + ".git")
                  for name in ("linux", "wallace")}
        if not all(path.is_dir() for path in caches.values()):
            raise unittest.SkipTest("TIPD C harness requires pinned cached sources")
        temporary = tempfile.TemporaryDirectory(prefix="arch-m4-tipd-partner-test-")
        cls.addClassCleanup(temporary.cleanup)
        tree = Path(temporary.name)

        def cached(name, path):
            return subprocess.check_output([
                "git", "--git-dir=" + str(caches[name]), "show",
                lock[name]["revision"] + ":" + path], timeout=15)

        for name in ("Kconfig", "Makefile", "core.c", "tps6598x.h"):
            path = tree / TIPD / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(cached("linux", TIPD + name))
        transport = cached("wallace", "patches/" + TRANSPORT)
        if hashlib.sha256(transport).hexdigest() != hardware.PATCHES[TRANSPORT]:
            raise AssertionError("cached Wallace transport does not match pinned digest")
        subprocess.run(["git", "apply", "-"], input=transport,
                       cwd=tree, check=True, timeout=15)
        source = tree / TIPD / "core.c"
        if hashlib.sha256(source.read_bytes()).hexdigest() != hardware.TIPD_CONNECTOR_FIX["transport_core_sha256"]:
            raise AssertionError("Wallace TIPD core does not match pinned digest")
        for metadata in (hardware.TIPD_CONNECTOR_FIX, hardware.TIPD_PARTNER_FIX):
            patch = PROJECT / metadata["path"]
            if hashlib.sha256(patch.read_bytes()).hexdigest() != metadata["sha256"]:
                raise AssertionError("local TIPD patch does not match pinned digest: " + str(patch))
            if metadata is hardware.TIPD_PARTNER_FIX:
                cls.original = source.read_text()
                if hashlib.sha256(source.read_bytes()).hexdigest() != metadata["base_core_sha256"]:
                    raise AssertionError("partner patch base does not match pinned digest")
            subprocess.run(["git", "apply", "--check", str(patch)],
                           cwd=tree, check=True, timeout=15)
            subprocess.run(["git", "apply", str(patch)],
                           cwd=tree, check=True, timeout=15)
        if hashlib.sha256(source.read_bytes()).hexdigest() != hardware.TIPD_PARTNER_FIX["result_core_sha256"]:
            raise AssertionError("patched TIPD core does not match pinned digest")
        header = cached("linux", "include/linux/usb/typec.h").decode()
        descriptors = "\n".join(re.search(
            r"struct " + name + r" \{.*?\n\};", header, re.S).group()
            for name in ("usb_pd_identity", "typec_partner_desc"))
        consumer = cached("linux", "drivers/usb/typec/class.c").decode()
        for field in ("identity", "pd_revision", "usb_capability", "attach", "deattach"):
            if "partner->" + field + " = desc->" + field + ";" not in consumer:
                raise AssertionError("fake consumer no longer matches pinned Type-C class")
        cls.binaries = {}
        for label, body in (("original", cls.original), ("patched", source.read_text())):
            actual = "\n".join(function(body, declaration) for declaration in (
                "static int tps6598x_connect(", "static void cd321x_update_work("))
            harness = tree / (label + ".c")
            harness.write_text(PRELUDE.replace("/* ACTUAL_TYPEC_DESCRIPTORS */", descriptors)
                               + actual + MAIN)
            cls.binaries[label] = tree / label
            result = subprocess.run([
                shutil.which("cc"), "-std=gnu11", "-O0", "-Wall", "-Wextra", "-Werror",
                "-ftrivial-auto-var-init=pattern", str(harness), "-o", str(cls.binaries[label]),
            ], capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise AssertionError("TIPD harness compilation failed: " + result.stderr)

    def run_case(self, label, case):
        return subprocess.run([str(self.binaries[label]), case],
                              capture_output=True, text=True, timeout=5)

    def test_descriptors_initialize_every_class_consumed_field(self):
        for case in ("generic-defaults", "cd-defaults"):
            with self.subTest(case=case):
                old = self.run_case("original", case)
                self.assertEqual(old.returncode, 10, old.stdout + old.stderr)
                self.assertIn("not zero", old.stderr)
                fixed = self.run_case("patched", case)
                self.assertEqual(fixed.returncode, 0, fixed.stdout + fixed.stderr)

    def test_pd_identity_is_persistent_before_and_after_registration(self):
        old = self.run_case("original", "cd-identity")
        self.assertEqual(old.returncode, 20, old.stdout + old.stderr)
        self.assertIn("not controller-owned", old.stderr)
        fixed = self.run_case("patched", "cd-identity")
        self.assertEqual(fixed.returncode, 0, fixed.stdout + fixed.stderr)

    def test_replacement_unregisters_old_identity_before_overwriting_it(self):
        old = self.run_case("original", "cd-replace")
        self.assertEqual(old.returncode, 20, old.stdout + old.stderr)
        fixed = self.run_case("patched", "cd-replace")
        self.assertEqual(fixed.returncode, 0, fixed.stdout + fixed.stderr)

    def test_unchanged_partner_and_disconnection_preserve_identity(self):
        for case in ("cd-unchanged", "cd-disconnect"):
            with self.subTest(case=case):
                fixed = self.run_case("patched", case)
                self.assertEqual(fixed.returncode, 0, fixed.stdout + fixed.stderr)


if __name__ == "__main__":
    unittest.main()
