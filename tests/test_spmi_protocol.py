"""Exercise the actual patched Apple SPMI protocol against a mock FIFO.

This checks command framing and failure cleanup, not real bus operation.
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


PRELUDE = r"""
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define __iomem
#define BIT(n) (1U << (n))
#define GENMASK(h,l) ((~0U >> (31-(h))) & (~0U << (l)))
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
struct mutex { int held; };
static int fail_lock;
static int mutex_lock_interruptible(struct mutex *m) {
    if (fail_lock) return -EINTR;
    assert(!m->held); m->held = 1; return 0;
}
static void mutex_unlock(struct mutex *m) { assert(m->held); m->held = 0; }
struct spmi_controller { void *data; int dev; };
#define spmi_controller_get_drvdata(c) ((c)->data)
static unsigned char mmio[16];
static u32 writes[16], replies[16];
static unsigned nw, nr, pos;
static void writel(u32 v, void *p) {
    assert(p == mmio + 4); assert(nw < 16); writes[nw++] = v;
}
static u32 readl(void *p) {
    if (p == mmio) return pos == nr ? BIT(24) : 0;
    assert(p == mmio + 8); assert(pos < nr); return replies[pos++];
}
#define readl_poll_timeout(addr,val,cond,interval,timeout) \
    ({ (val) = readl(addr); (cond) ? 0 : -ETIMEDOUT; })
static void reset_fifo(void) {
    memset(writes, 0, sizeof(writes));
    memset(replies, 0, sizeof(replies));
    nw = pos = fail_lock = 0; nr = 1; replies[0] = BIT(15);
}
"""

MAIN = r"""
int main(void) {
    struct apple_spmi bus = { .regs = mmio };
    struct spmi_controller c = { .data = &bus };
    u8 selector = 0x20, data[16] = {1,2,3,4,5,6}, result[16];

    /* SN201202x select: selector belongs in command, not a payload word. */
    reset_fifo();
    assert(!spmi_write_cmd(&c, SPMI_CMD_ZERO_WRITE, 0xc, 0, &selector, 1));
    assert(nw == 1 && writes[0] == 0x20008ca0);
    assert(!bus.fifo_lock.held);

    reset_fifo();
    assert(!spmi_cmd(&c, SPMI_CMD_WAKEUP, 0xc));
    assert(nw == 1 && writes[0] == 0x00008c13);

    /* SN201202x selector status uses standard READ, not EXT_READ. */
    reset_fifo(); nr = 2; replies[0] = 0x00010000; replies[1] = 0x1a;
    assert(!spmi_read_cmd(&c, SPMI_CMD_READ, 0xc, 0, result, 1));
    assert(nw == 1 && writes[0] == 0x00008c60 && result[0] == 0x1a);

    /* SN201202x writes use its separate 0xa0 payload aperture. */
    reset_fifo();
    assert(!spmi_write_cmd(&c, SPMI_CMD_EXT_WRITE, 0xc, 0xa0, data, 4));
    assert(nw == 2 && writes[0] == 0x00a08c03 && writes[1] == 0x04030201);

    /* Existing PMU extended writes must retain their framing and payload. */
    reset_fifo();
    assert(!spmi_write_cmd(&c, SPMI_CMD_EXT_WRITEL, 0xe, 0x2100, data, 6));
    assert(nw == 3 && writes[0] == 0x21008e35);
    assert(writes[1] == 0x04030201 && writes[2] == 0x00000605);

    reset_fifo();
    replies[0] = 0xffff0000; nr = 5;
    replies[1] = 0x04030201; replies[2] = 0x08070605;
    replies[3] = 0x0c0b0a09; replies[4] = 0x100f0e0d;
    assert(!spmi_read_cmd(&c, SPMI_CMD_EXT_READ, 0xc, 0x20, result, 16));
    assert(nw == 1 && writes[0] == 0x00208c2f);
    for (unsigned i = 0; i < 16; i++) assert(result[i] == i + 1);

    reset_fifo(); replies[0] = 0;
    assert(spmi_cmd(&c, SPMI_CMD_WAKEUP, 0xc) == -EIO); /* no ACK */
    assert(!bus.fifo_lock.held);
    reset_fifo(); nr = 2; replies[0] = 0;
    assert(spmi_read_cmd(&c, SPMI_CMD_EXT_READ, 0xc, 0, result, 1) == -EIO);
    assert(!bus.fifo_lock.held); /* parity failure */
    reset_fifo(); replies[0] = 0x00010000;
    assert(spmi_read_cmd(&c, SPMI_CMD_EXT_READ, 0xc, 0, result, 1) == -EIO);
    assert(!bus.fifo_lock.held); /* missing response body */
    reset_fifo(); nr = 0;
    assert(spmi_cmd(&c, SPMI_CMD_WAKEUP, 0xc) == -ETIMEDOUT);
    assert(!bus.fifo_lock.held);
    reset_fifo(); fail_lock = 1;
    assert(spmi_cmd(&c, SPMI_CMD_WAKEUP, 0xc) == -EINTR);
    assert(!nw && !bus.fifo_lock.held);
    reset_fifo();
    assert(spmi_cmd(&c, 0xff, 0xc) == -EINVAL);
    assert(!nw && !bus.fifo_lock.held);
    puts("SPMI framing, PMU compatibility, FIFO errors and lock cleanup passed");
    return 0;
}
"""


@unittest.skipUnless(shutil.which("cc") and (PROJECT / "cache/git/linux.git").is_dir(),
                     "requires host C compiler and pinned Linux source cache")
class SpmiProtocolTests(unittest.TestCase):
    def test_pinned_patch_series_and_live_driver_functions(self):
        lock = json.loads((PROJECT / "sources.lock.json").read_text())
        ref = lock["linux"]["revision"]
        repo = "--git-dir=" + str(PROJECT / "cache/git/linux.git")
        with tempfile.TemporaryDirectory() as name:
            tree = Path(name)
            source = tree / "drivers/spmi/spmi-apple-controller.c"
            source.parent.mkdir(parents=True)
            source.write_bytes(subprocess.check_output([
                "git", repo, "show", ref + ":drivers/spmi/spmi-apple-controller.c"]))
            for filename, _, digest in hardware.SPMI_PATCHES:
                patch = PROJECT / "patches" / filename
                self.assertEqual(hashlib.sha256(patch.read_bytes()).hexdigest(), digest)
                subprocess.run(["git", "apply", "--check", str(patch)], cwd=tree, check=True)
                subprocess.run(["git", "apply", str(patch)], cwd=tree, check=True)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                             hardware.SPMI_RESULT_SHA256)
            body = source.read_text().split("static int apple_spmi_probe(")[0]
            body = re.sub(r"^#include .*\n", "", body, flags=re.M)
            header = subprocess.check_output([
                "git", repo, "show", ref + ":include/linux/spmi.h"], text=True)
            defines = "\n".join(line for line in header.splitlines()
                                if line.startswith("#define SPMI_CMD_"))
            harness = tree / "test.c"
            harness.write_text(PRELUDE + defines + "\n" + body + MAIN)
            subprocess.run([shutil.which("cc"), "-std=gnu11", "-Wall", "-Wextra",
                            "-Werror", str(harness), "-o", str(tree / "test")], check=True)
            result = subprocess.run([str(tree / "test")], check=True,
                                    text=True, capture_output=True)
            self.assertIn("passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
