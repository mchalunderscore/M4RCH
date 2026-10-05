"""Exercise the NVMe firmware fixes against the pinned kernel source.

The real patch test uses the already downloaded source cache; building hardware
also verifies the resulting complete source hashes. No controller is accessed.
"""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib"))
import hardware_profile as hardware


class NvmeFirmwareTests(unittest.TestCase):
    def test_patch_inputs_and_origins(self):
        self.assertEqual(len(hardware.NVME_PATCHES), 9)
        for name, revision, digest in hardware.NVME_PATCHES:
            with self.subTest(patch=name):
                data = (PROJECT / "patches" / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
                self.assertIn(revision.encode(), data)
                self.assertIn(revision, hardware.nvme_patch_url(name, revision))


    @unittest.skipUnless(all((PROJECT / ("cache/git/" + name + ".git")).is_dir() for name in ("linux", "wallace")), "requires downloaded pinned source")
    def test_real_patch_application_and_firmware_contract(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            files = ["drivers/nvme/host/apple.c", *hardware.NVME_CORE_RESULT_SHA256,
                     "Documentation/devicetree/bindings/nvme/apple,nvme-ans.yaml"]
            for file in files:
                path = root / file
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(subprocess.check_output(["git", "--git-dir=" + str(PROJECT / "cache/git/linux.git"),
                    "show", "e9d2237cd064e6d086d938cd9c85e0c963cf7291:" + file]))
            # The actual Wallace harness applies this failed historical reset
            # before our patchset. Reproduce that predecessor, then verify that
            # our first patch removes it and leaves the upstream reset logic.
            old = subprocess.check_output(["git", "--git-dir=" + str(PROJECT / "cache/git/wallace.git"),
                "show", hardware.WALLACE_REVISION + ":patches/t6040-nvme-apple-force-clean-ans-boot.patch"])
            self.assertEqual(hashlib.sha256(old).hexdigest(),
                "399578f56d4ec6ae1d865be68878b68dad6868d1a56015b085cd088592994904")
            subprocess.run(["git", "apply", "-"], input=old, cwd=root, check=True)
            for patch, _, _ in hardware.NVME_PATCHES:
                subprocess.run(["git", "apply", str(PROJECT / "patches" / patch)], cwd=root, check=True)
            expected = {"drivers/nvme/host/apple.c": hardware.NVME_RESULT_SHA256,
                        **hardware.NVME_CORE_RESULT_SHA256}
            for file, digest in expected.items():
                self.assertEqual(hashlib.sha256((root / file).read_bytes()).hexdigest(), digest)
            source = (root / "drivers/nvme/host/apple.c").read_text()
            self.assertNotIn("mmio_nvmmu", source)
            self.assertNotIn("APPLE_ANS_UNKNOWN_CTRL", source)
            self.assertIn("ret = nvme_set_queue_count(&anv->ctrl, &nr_io_queues);", source)
            self.assertIn("blk_mq_destroy_queue(anv->ctrl.admin_q);", source)
            self.assertIn("NVME_QUIRK_ADMIN_PAGE_ALIGN", source)
            # Run the actual v2 MMIO programming block using recording writes.
            begin = source.index("\tif (anv->hw->needs_ioq_register) {")
            end = source.index("\n\tapple_nvme_init_queue(&anv->ioq);", begin)
            code = source[begin:end]
            fixture = '''#include <assert.h>
#include <stdint.h>
#define APPLE_ANS_T8132_IOQ_CQES 0x1208
#define APPLE_ANS_T8132_IOQ_CMDS 0x1200
#define APPLE_ANS_T8132_IOQ_SIZE 0x1210
static uint64_t writes[3], addresses[3]; static int count;
static void record(uint64_t value, uint64_t address) { writes[count] = value; addresses[count++] = address; }
#define writeq record
#define writel record
struct hw { int needs_ioq_register, max_queue_depth; };
struct ctrl { struct hw *hw; struct { uint64_t cq_dma_addr, sq_dma_addr; } ioq; uint64_t mmio_nvme; };
static void configure(struct ctrl *anv) { ACTUAL_CODE }
int main(void) {
 struct hw hw = {1,64}; struct ctrl a = {&hw,{0x80004000,0x80008000},0x44dcc0000};
 configure(&a);
 assert(count == 3 && addresses[0] == 0x44dcc1208 && addresses[1] == 0x44dcc1200 && addresses[2] == 0x44dcc1210);
 assert(writes[0] == a.ioq.cq_dma_addr && writes[1] == a.ioq.sq_dma_addr);
 assert((writes[2] & 0xffff) + 1 == 64 && (writes[2] >> 16) + 1 == 64);
 count = 0; hw.needs_ioq_register = 0; configure(&a); assert(!count);
 return 0;
}
'''.replace("ACTUAL_CODE", code)
            cfile = root / "queue-regression.c"
            cfile.write_text(fixture)
            executable = root / "queue-regression"
            compiler = shutil.which("cc")
            self.assertIsNotNone(compiler)
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", str(cfile), "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    unittest.main()
