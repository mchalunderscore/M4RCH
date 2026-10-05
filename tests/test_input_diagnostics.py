import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class InputDiagnosticsTests(unittest.TestCase):
    def fixture(self, root, body, user_id="0"):
        fakebin = root / "bin"
        fakebin.mkdir()
        (fakebin / "id").write_text(f"#!/bin/sh\nprintf '%s\\n' '{user_id}'\n")
        (fakebin / "sync").write_text(
            '#!/bin/sh\nprintf "sync\\n" >> "$TEST_CALLS"\n'
            'test -s "$TEST_OUTPUT"\n')
        for command in fakebin.iterdir():
            command.chmod(0o755)
        source = (PROJECT / "templates/collect-input-diagnostics.sh").read_text()
        # Exercise the actual argument handling/capture/publish code. Only the
        # report body is replaced, so these tests never inspect host input/logs.
        source = source.split("section 'Kernel and boot arguments'", 1)[0] + body
        source = source.replace("PATH=/usr/sbin:/usr/bin:/sbin:/bin",
                                f"PATH='{fakebin}':/usr/sbin:/usr/bin:/sbin:/bin")
        script = root / "collector.sh"
        script.write_text(source)
        output = root / "report with spaces.txt"
        calls = root / "calls"
        environment = dict(os.environ, TEST_CALLS=str(calls), TEST_OUTPUT=str(output))
        return script, output, calls, environment

    def run_collector(self, script, environment, *arguments):
        return subprocess.run(["sh", str(script), *map(str, arguments)],
                              env=environment, text=True, capture_output=True, timeout=10)

    def test_output_captures_both_streams_and_syncs_before_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = ('printf "kernel log\\n"\nprintf "diagnostic warning\\n" >&2\n'
                    'printf "End of input diagnostics.\\n"\n')
            script, output, calls, environment = self.fixture(root, body)
            output.write_text("previous report\n")
            result = self.run_collector(script, environment, "--output", output)
            expected = "kernel log\ndiagnostic warning\nEnd of input diagnostics.\n"
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text(), expected)
            self.assertEqual(result.stdout, f"Saved {len(expected.encode())} bytes to {output}\n")
            self.assertEqual(calls.read_text(), "sync\n")
            self.assertEqual(list(root.glob(".m4rch-input-diagnostics.*")), [])

    def test_failed_empty_or_incomplete_collection_preserves_previous_report(self):
        for body in ('printf "End of input diagnostics.\\n"\nexit 7\n',
                     'exit 0\n', 'printf "partial report\\n"\n'):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                script, output, calls, environment = self.fixture(root, body)
                output.write_text("previous report\n")
                result = self.run_collector(script, environment, "--output", output)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("previous report was preserved", result.stderr)
                self.assertEqual(output.read_text(), "previous report\n")
                self.assertFalse(calls.exists())
                self.assertEqual(list(root.glob(".m4rch-input-diagnostics.*")), [])

    def test_argument_and_root_checks_do_not_touch_output(self):
        for user_id, extra in (("1000", ()), ("0", ("extra",))):
            with self.subTest(user_id=user_id), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                script, output, calls, environment = self.fixture(root, "exit 99\n", user_id)
                output.write_text("previous report\n")
                result = self.run_collector(script, environment, "--output", output, *extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output.read_text(), "previous report\n")
                self.assertFalse(calls.exists())
                self.assertEqual(list(root.glob(".m4rch-input-diagnostics.*")), [])

    def test_default_mode_still_writes_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            script, output, calls, environment = self.fixture(Path(tmp), 'printf "report\\n"\n')
            result = self.run_collector(script, environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "report\n")
            self.assertFalse(output.exists())
            self.assertFalse(calls.exists())


if __name__ == "__main__":
    unittest.main()
