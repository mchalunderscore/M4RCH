"""Run the patched SN201202x transport and shared bus lookup against fake buses.

The harness compiles actual source functions, with an independent model of the
device's distinct read/write windows. It cannot verify native power or USB I/O.
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
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


TRANSPORT_PRELUDE = r"""
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
#define BIT(n) (1U << (n))
#define min_t(t,a,b) ((t)(a) < (t)(b) ? (t)(a) : (t)(b))
#define EPROBE_DEFER 517
struct device { void *of_node; };
struct spmi_device { struct device dev; };
struct tipd_data { int unused; };
struct regmap { int unused; };
static struct tipd_data match;
static struct regmap map;
static int tps6598x_spmi_regmap_bus, tps6598x_regmap_config;
static u8 selected, payload[64];
static int select_error, read_error, window_read_error, write_error, wake_error, common_error;
static int map_error, irq_result, busy_reads, mismatch, standard_reads;
static int selects, reads, writes, sleeps, common_calls, wake_calls;
static int last_common_irq;
static struct device *last_common_dev;
static const struct tipd_data *device_get_match_data(struct device *dev) {
    (void)dev; return &match;
}
static int spmi_register_zero_write(struct spmi_device *sdev, u8 reg) {
    (void)sdev; selects++; selected = reg; return select_error;
}
static int __attribute__((unused)) spmi_register_read(struct spmi_device *sdev, u8 addr, u8 *val) {
    (void)sdev; assert(addr == 0); standard_reads++;
    if (read_error) return read_error;
    *val = mismatch ? selected ^ 1 : selected | (busy_reads-- > 0 ? 128 : 0);
    return 0;
}
static int spmi_ext_register_read(struct spmi_device *sdev, u8 addr,
                                  u8 *val, size_t len) {
    (void)sdev;
    /* Selector register requires READ, not EXT_READ. */
    if (addr < 0x20 || addr + len > 0x60 || !len || len > 16) return -EIO;
    reads++; if (window_read_error && reads == 2) return window_read_error;
    memcpy(val, payload + addr - 0x20, len); return 0;
}
static int spmi_ext_register_write(struct spmi_device *sdev, u8 addr,
                                   const u8 *val, size_t len) {
    (void)sdev;
    if (addr < 0xa0 || addr + len > 0xe0 || !len || len > 16) return -EIO;
    writes++; if (write_error) return write_error;
    memcpy(payload + addr - 0xa0, val, len); return 0;
}
static void usleep_range(int low, int high) {
    assert(low == 1000 && high == 2000); sleeps++;
}
static int spmi_command_wakeup(struct spmi_device *sdev) {
    (void)sdev; wake_calls++; return wake_error;
}
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
static struct regmap *devm_regmap_init(struct device *dev, void *bus,
                                      void *context, void *config) {
    assert(dev == &((struct spmi_device *)context)->dev);
    assert(bus == &tps6598x_spmi_regmap_bus && config == &tps6598x_regmap_config);
    return map_error ? (void *)(intptr_t)map_error : &map;
}
static int of_irq_get(void *node, int index) {
    (void)node; assert(!index); return irq_result;
}
static int __attribute__((unused)) dev_err_probe(struct device *dev, int error, const char *stage) {
    (void)dev; assert(strstr(stage, "failed")); return error;
}
static int tps6598x_probe_common(struct device *dev, struct regmap *regmap,
                                int irq, const struct tipd_data *data) {
    assert(regmap == &map && data == &match);
    common_calls++; last_common_dev = dev; last_common_irq = irq;
    return common_error;
}
static void reset(void) {
    select_error = read_error = window_read_error = write_error = wake_error = common_error = 0;
    map_error = busy_reads = mismatch = standard_reads = 0;
    selects = reads = writes = sleeps = common_calls = wake_calls = 0;
    irq_result = -ENXIO; memset(payload, 0, sizeof(payload));
}
"""

TRANSPORT_MAIN = r"""
int main(int argc, char **argv) {
    struct spmi_device sdev = {0};
    u8 reg = 0x1a, output[65], input[65], packed[65];
    assert(argc == 2); reset();
    for (unsigned i = 0; i < 64; i++) input[i] = payload[i] = i + 1;
    if (!strcmp(argv[1], "selector")) {
        busy_reads = 2;
        if (tps6598x_spmi_read(&sdev, &reg, 1, output, 64)) return 10;
        assert(standard_reads == 3 && sleeps == 2 && reads == 4 && selects == 1);
        assert(!memcmp(input, output, 64));
    } else if (!strcmp(argv[1], "write")) {
        /* Isolate WRITE-window behavior from the known old selector defect. */
        memset(payload, 0, sizeof(payload));
        if (tps6598x_spmi_window_write(&sdev, input, 64)) return 20;
        assert(writes == 4 && !memcmp(input, payload, 64));
        reset(); memcpy(packed + 1, input, 64); packed[0] = reg;
        assert(!tps6598x_spmi_write(&sdev, packed, 65));
        assert(selects == 1 && writes == 4 && !memcmp(input, payload, 64));
    } else if (!strcmp(argv[1], "bounds")) {
        assert(tps6598x_spmi_read(&sdev, &reg, 1, output, 65) == -EINVAL);
        assert(tps6598x_spmi_gather_write(&sdev, &reg, 1, input, 65) == -EINVAL);
        assert(tps6598x_spmi_read(&sdev, &reg, 2, output, 1) == -EINVAL);
        assert(tps6598x_spmi_write(&sdev, input, 0) == -EINVAL);
        reg = 0x80;
        assert(tps6598x_spmi_read(&sdev, &reg, 1, output, 1) == -EINVAL);
        assert(!selects && !reads && !writes && !standard_reads);
    } else if (!strcmp(argv[1], "errors")) {
        select_error = -EIO;
        assert(tps6598x_spmi_read(&sdev, &reg, 1, output, 1) == -EIO);
        assert(!standard_reads && !reads);
        reset(); read_error = -EINTR;
        assert(tps6598x_spmi_read(&sdev, &reg, 1, output, 1) == -EINTR);
        reset(); window_read_error = -EIO;
        assert(tps6598x_spmi_read(&sdev, &reg, 1, output, 64) == -EIO);
        assert(reads == 2 && standard_reads == 1); /* abort at the second chunk */
        reset(); write_error = -EIO;
        assert(tps6598x_spmi_gather_write(&sdev, &reg, 1, input, 1) == -EIO);
        reset(); mismatch = 1;
        assert(tps6598x_spmi_read(&sdev, &reg, 1, output, 1) == -EIO);
        assert(standard_reads == 1 && !reads && !sleeps);
        reset(); busy_reads = 101;
        assert(tps6598x_spmi_read(&sdev, &reg, 1, output, 1) == -ETIMEDOUT);
        assert(standard_reads == 100 && sleeps == 100 && !reads);
    } else if (!strcmp(argv[1], "probe")) {
        wake_error = -EIO;
        if (tps6598x_spmi_probe(&sdev) != -EIO || common_calls) return 30;
        reset(); assert(!tps6598x_spmi_probe(&sdev));
        assert(wake_calls == 1 && common_calls == 1 && last_common_irq == 0);
        assert(last_common_dev == &sdev.dev);
        reset(); irq_result = -EPROBE_DEFER;
        assert(tps6598x_spmi_probe(&sdev) == -EPROBE_DEFER && !common_calls);
        reset(); irq_result = 12; common_error = -ENODEV;
        assert(tps6598x_spmi_probe(&sdev) == -ENODEV && last_common_irq == 12);
        reset(); map_error = -ENOMEM;
        assert(tps6598x_spmi_probe(&sdev) == -ENOMEM && !common_calls);
    } else return 99;
    puts("SPMI transport checks passed"); return 0;
}
"""

CONNECTOR_PRELUDE = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
struct device { int unused; };
struct i2c_client { void *adapter; struct device dev; };
struct fwnode_handle { int unused; };
struct tps6598x { bool i2c_protocol; };
static struct i2c_client bus;
static struct fwnode_handle connector;
static bool is_i2c, supports_i2c, invalid_lookup;
static struct device *expected;
#define I2C_FUNC_I2C 1
static struct i2c_client *i2c_verify_client(struct device *dev) {
    assert(dev == expected); return is_i2c ? &bus : NULL;
}
static int i2c_check_functionality(void *adapter, int capability) {
    assert(adapter == &bus && capability == I2C_FUNC_I2C); return supports_i2c;
}
static struct fwnode_handle *device_get_named_child_node(struct device *dev,
                                                        const char *name) {
    assert(!strcmp(name, "connector"));
    if (dev != expected) { invalid_lookup = true; return NULL; }
    return &connector;
}
"""


class TipdSpmiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("cc") or not shutil.which("git"):
            raise unittest.SkipTest("TIPD harness requires cc and git")
        lock = json.loads((PROJECT / "sources.lock.json").read_text())
        caches = {name: PROJECT / "cache/git" / (name + ".git") for name in ("linux", "wallace")}
        if not all(path.is_dir() for path in caches.values()):
            raise unittest.SkipTest("TIPD harness requires pinned cached sources")
        temporary = tempfile.TemporaryDirectory(prefix="arch-m4-tipd-spmi-test-")
        cls.addClassCleanup(temporary.cleanup)
        tree = Path(temporary.name)

        def cached(name, path):
            return subprocess.check_output(["git", "--git-dir=" + str(caches[name]),
                                           "show", lock[name]["revision"] + ":" + path], timeout=15)

        for name in ("Kconfig", "Makefile", "core.c", "tps6598x.h"):
            path = tree / TIPD / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(cached("linux", TIPD + name))
        transport = cached("wallace", "patches/" + TRANSPORT)
        if hashlib.sha256(transport).hexdigest() != hardware.PATCHES[TRANSPORT]:
            raise AssertionError("Wallace transport digest mismatch")
        subprocess.run(["git", "apply", "-"], input=transport, cwd=tree, check=True, timeout=15)
        original_spmi = (tree / TIPD / "spmi.c").read_text()
        original_core = (tree / TIPD / "core.c").read_text()
        for metadata, file, before_key, after_key in (
            (hardware.TIPD_CONNECTOR_FIX, "core.c", "transport_core_sha256", "result_core_sha256"),
            (hardware.TIPD_REGISTERS_FIX, "spmi.c", "transport_spmi_sha256", "result_spmi_sha256"),
        ):
            source = tree / TIPD / file
            patch = PROJECT / metadata["path"]
            if (hashlib.sha256(patch.read_bytes()).hexdigest() != metadata["sha256"]
                    or hashlib.sha256(source.read_bytes()).hexdigest() != metadata[before_key]):
                raise AssertionError("TIPD patch/base digest mismatch")
            subprocess.run(["git", "apply", "--check", str(patch)], cwd=tree, check=True, timeout=15)
            subprocess.run(["git", "apply", str(patch)], cwd=tree, check=True, timeout=15)
            if hashlib.sha256(source.read_bytes()).hexdigest() != metadata[after_key]:
                raise AssertionError("patched TIPD source digest mismatch")
        cls.binaries = {}
        for label, spmi, core in (("old", original_spmi, original_core),
                                  ("fixed", (tree / TIPD / "spmi.c").read_text(),
                                   (tree / TIPD / "core.c").read_text())):
            body = re.sub(r"^#include .*\n", "", spmi.split("static const struct regmap_bus")[0], flags=re.M)
            body += "\n" + function(spmi, "static int tps6598x_spmi_probe(")
            cls.compile(tree, label + "-transport", TRANSPORT_PRELUDE + body + TRANSPORT_MAIN)
            # Compile the actual two bus-sensitive blocks from common probe.
            probe = function(core, "int tps6598x_probe_common(")
            adapter = probe[probe.index("\tclient = i2c_verify_client(dev);"):probe.index("\n\tif (tps->data->switch_power_state)")]
            lookup = next(line for line in probe.splitlines() if "fwnode = device_get_named_child_node(" in line)
            code = "\nstatic int lookup(struct device *dev, struct tps6598x *tps) {\nstruct i2c_client *client; struct fwnode_handle *fwnode;\n" + adapter + "\n" + lookup + "\nreturn fwnode == &connector && !invalid_lookup ? 0 : 31;\n}\n"
            code += r'''
int main(int argc, char **argv) {
    struct device spmi; struct tps6598x tps = {0}; assert(argc == 2);
    is_i2c = strcmp(argv[1], "spmi") != 0;
    supports_i2c = strcmp(argv[1], "smbus") != 0;
    expected = is_i2c ? &bus.dev : &spmi; bus.adapter = &bus;
    int ret = lookup(expected, &tps);
    assert(tps.i2c_protocol == (is_i2c && supports_i2c));
    return ret;
}
'''
            cls.compile(tree, label + "-connector", CONNECTOR_PRELUDE + code)

    @classmethod
    def compile(cls, tree, name, code):
        source = tree / (name + ".c")
        source.write_text(code)
        binary = tree / name
        result = subprocess.run([shutil.which("cc"), "-std=gnu11", "-O0", "-Wall", "-Wextra",
                                 "-Werror", str(source), "-o", str(binary)],
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError("TIPD harness compilation failed: " + result.stderr)
        cls.binaries[name] = binary

    def run_case(self, name, case, expected=0):
        result = subprocess.run([str(self.binaries[name]), case], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)

    def test_standard_selector_and_separate_chunked_write_window(self):
        for case, error in (("selector", 10), ("write", 20)):
            with self.subTest(case=case):
                self.run_case("old-transport", case, error)
                self.run_case("fixed-transport", case)

    def test_bounds_bus_errors_mismatch_and_bounded_timeout(self):
        for case in ("bounds", "errors"):
            with self.subTest(case=case):
                self.run_case("fixed-transport", case)

    def test_probe_stops_on_wakeup_failure_and_propagates_deferred_irq(self):
        self.run_case("old-transport", "probe", 30)
        self.run_case("fixed-transport", "probe")

    def test_shared_connector_lookup_accepts_spmi_and_preserves_i2c(self):
        self.run_case("old-connector", "spmi", 31)
        for case in ("spmi", "i2c", "smbus"):
            with self.subTest(case=case):
                self.run_case("fixed-connector", case)
        self.run_case("old-connector", "i2c")


if __name__ == "__main__":
    unittest.main()
