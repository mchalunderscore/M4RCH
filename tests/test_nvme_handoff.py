import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib"))
import nvme_handoff


def function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    offset = opening + 1
    while depth:
        depth += (source[offset] == "{") - (source[offset] == "}")
        offset += 1
    return source[start:offset]


class NvmeHandoffTests(unittest.TestCase):
    def patched(self, root):
        # Exact MIT-licensed upstream src/nvme.c from M1N1_REVISION, checked in
        # so make check works before downloading sources or building a kernel.
        source = (PROJECT / "tests/fixtures/m1n1-nvme-base.c").read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), nvme_handoff.BASE_SHA256)
        (root / "src").mkdir()
        (root / "src/nvme.c").write_bytes(source)
        shutil.copyfile(PROJECT / "tests/fixtures/m1n1-nvme-base.h", root / "src/nvme.h")
        for name in ("rtkit.c", "rtkit.h"):
            shutil.copyfile(PROJECT / "tests/fixtures" / ("m1n1-" + name.replace(".", "-base.")), root / "src" / name)
        nvme_handoff.prepare(root, root)
        return (root / "src/nvme.c").read_text()

    def test_pinned_sources_apply_and_metadata_detects_drift(self):
        lock = json.loads((PROJECT / "sources.lock.json").read_text())
        metadata = nvme_handoff.inputs(PROJECT, lock)
        self.assertFalse(metadata["native_verified"])
        self.assertEqual(len(metadata["upstream_commits"]), 5)
        with tempfile.TemporaryDirectory() as tmp:
            source = self.patched(Path(tmp))
            self.assertEqual(hashlib.sha256(source.encode()).hexdigest(), nvme_handoff.RESULT_SHA256)
            with self.assertRaisesRegex(ValueError, "base source differs"):
                nvme_handoff.prepare(tmp, tmp)
        lock["m1n1"]["revision"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "pinned"):
            nvme_handoff.inputs(PROJECT, lock)

    def test_actual_c_guards_and_handoff_order(self):
        compiler = shutil.which("cc")
        self.assertIsNotNone(compiler, "A host C compiler is required for the handoff control-flow test")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.patched(root)
            # Compile the actual early target/address guards and handoff body,
            # replacing only hardware access functions with recording stubs.
            guard = function(source, "bool nvme_init(void)")
            guard = guard[:guard.index("    u32 cg;")] + "    return true;\n}\n"
            guard = guard.replace("bool nvme_init(void)", "bool validate_target(void)")
            shutdown = function(source, "void nvme_shutdown(void)")
            checked = function(source, "static bool nvme_shutdown_checked(void)")
            prepare = function(source, "bool nvme_prepare_handoff(void)")
            (root / "src/kboot.c").write_text('int kboot_boot(void *kernel)\n{\n    printf("Setting SMP mode to WFE...\\n");\n}\n')
            nvme_handoff.prepare_uefi(root)
            kboot = (root / "src/kboot.c").read_text()
            hook = kboot[kboot.index("    /* This hook"):kboot.index('    printf("Setting SMP')]
            fixture = (PROJECT / "tests/fixtures/nvme-handoff.c").read_text()
            fixture = fixture.replace("/* ACTUAL_TARGET_GUARDS */", guard)
            fixture = fixture.replace("/* ACTUAL_SHUTDOWN_CHECKED */", checked)
            fixture = fixture.replace("/* ACTUAL_PREPARE_HANDOFF */", prepare)
            fixture = fixture.replace("/* ACTUAL_SHUTDOWN */", shutdown)
            fixture = fixture.replace("/* ACTUAL_UEFI_HOOK */", hook)
            path = root / "fixture.c"
            path.write_text(fixture)
            executable = root / "fixture"
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-Wno-unused-parameter", str(path), "-o", str(executable)], check=True)
            result = subprocess.run([str(executable)], check=True, text=True, capture_output=True)
            self.assertIn("NVMe handoff control-flow checks passed", result.stdout)

    def compile_fixture(self, root, fixture_name, replacements):
        fixture = (PROJECT / "tests/fixtures" / fixture_name).read_text()
        for marker, code in replacements.items():
            fixture = fixture.replace("/* " + marker + " */", code)
        path = root / fixture_name
        path.write_text(fixture)
        executable = root / (fixture_name + ".test")
        subprocess.run([shutil.which("cc"), "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-parameter", str(path), "-o", str(executable)], check=True)
        return subprocess.run([str(executable)], check=True, text=True, capture_output=True).stdout

    def test_actual_rtkit_handshake_failures_are_not_hidden(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            self.patched(root)
            rtkit = (root / "src/rtkit.c").read_text()
            result = self.compile_fixture(root, "rtkit-sleep-checked.c", {
                "ACTUAL_SWITCH_POWER_STATE": function(rtkit, "static bool rtkit_switch_power_state("),
                "ACTUAL_CHECKED_SLEEP": function(rtkit, "bool rtkit_sleep_checked("),
            })
            self.assertIn("Checked RTKit sleep preserves failures", result)
            # Existing clients keep exactly their previous API implementation.
            base = (PROJECT / "tests/fixtures/m1n1-rtkit-base.c").read_text()
            self.assertEqual(function(rtkit, "bool rtkit_sleep("), function(base, "bool rtkit_sleep("))

    def test_actual_initialization_latches_failed_dma_ownership(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = self.patched(root)
            result = self.compile_fixture(root, "nvme-init-lifetime.c", {
                "ACTUAL_INIT": function(source, "bool nvme_init(void)"),
                "ACTUAL_FLUSH": function(source, "bool nvme_flush("),
                "ACTUAL_READ": function(source, "bool nvme_read("),
            })
            self.assertIn("retains DMA buffers after failed adoption", result)

    def test_binary_guard_requires_handoff_and_target_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m1n1.bin"
            path.write_bytes(nvme_handoff.MARKER)
            with self.assertRaises(ValueError):
                nvme_handoff.check_binary(path)
            path.write_bytes(nvme_handoff.MARKER + b"unexpected J614s ANS address translation")
            nvme_handoff.check_binary(path)
            with self.assertRaisesRegex(ValueError, "live handoff marker"):
                nvme_handoff.check_binary(path, uefi=True)
            path.write_bytes(path.read_bytes() + nvme_handoff.DT_MARKER.encode())
            nvme_handoff.check_binary(path, uefi=True)


if __name__ == "__main__":
    unittest.main()
