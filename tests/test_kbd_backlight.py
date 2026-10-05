from pathlib import Path
import subprocess
import tempfile
import unittest


TEMPLATE = Path(__file__).resolve().parents[1] / "templates/kbd-backlight.sh"


class KeyboardBacklightTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        root = Path(self.workspace.name)
        self.led = root / "led"
        self.led.mkdir()
        self.maximum = self.led / "max_brightness"
        self.brightness = self.led / "brightness"
        self.maximum.write_text("255\n")
        self.brightness.write_text("0\n")
        self.script = root / "backlight.sh"
        source = TEMPLATE.read_text()
        # Alter only this test copy: the installed privileged helper has no
        # environment variable or argument that can redirect its sysfs writes.
        self.assertEqual(source.count("led=/sys/class/leds/kbd_backlight"), 1)
        self.script.write_text(source.replace(
            "led=/sys/class/leds/kbd_backlight", f"led='{self.led}'"))

    def run_helper(self, *arguments):
        return subprocess.run(["sh", str(self.script), *arguments],
                              text=True, capture_output=True)

    def test_steps_and_clamping(self):
        for current, action, expected in ((0, "up", 26), (250, "up", 255),
                                           (255, "up", 255), (128, "down", 102),
                                           (5, "down", 0), (0, "down", 0),
                                           (255, "off", 0)):
            with self.subTest(current=current, action=action):
                self.brightness.write_text(f"{current}\n")
                result = self.run_helper(action)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.brightness.read_text(), f"{expected}\n")
        self.maximum.write_text("1\n")
        result = self.run_helper("up")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.brightness.read_text(), "1\n")

    def test_percent_and_read_only_status(self):
        for percent, expected in (("0", 0), ("50", 128), ("100", 255)):
            result = self.run_helper(percent)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.brightness.read_text(), f"{expected}\n")
        result = self.run_helper("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "255/255 (100%)\n")
        self.assertEqual(self.brightness.read_text(), "255\n")

    def test_bad_arguments_do_not_write(self):
        for arguments in ((), ("up", "extra"), ("-1",), ("101",),
                          ("50%",), ("010",), ("/tmp/brightness",)):
            with self.subTest(arguments=arguments):
                result = self.run_helper(*arguments)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(self.brightness.read_text(), "0\n")

    def test_missing_or_malformed_device_fails(self):
        for maximum, current in (("0", "0"), ("bad", "0"), ("255", "256"),
                                 ("255", "bad"), ("255", "08"),
                                 ("99999999999999999999", "0")):
            with self.subTest(maximum=maximum, current=current):
                self.maximum.write_text(maximum + "\n")
                self.brightness.write_text(current + "\n")
                result = self.run_helper("up")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(self.brightness.read_text(), current + "\n")
        self.maximum.unlink()
        self.assertEqual(self.run_helper("up").returncode, 1)
        self.brightness.unlink()
        self.led.rmdir()
        result = self.run_helper("up")
        self.assertEqual(result.returncode, 1)
        self.assertIn("device is missing", result.stderr)


if __name__ == "__main__":
    unittest.main()
