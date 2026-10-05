"""Compile and exercise actual patched kernel power functions without hardware.

Requires the source caches populated by make bundle and a host C compiler.
This checks host sequencing, active-low conversion and failures, not the
physical SMC GPIO protocol or native trackpad behavior.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = "drivers/hid/apple-dockchannel-hid/apple_dockchannel_hid.c"


def function(source, name):
    start = source.index("static int " + name + "(")
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


class TrackpadPowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("cc", "git", "patch"):
            if not shutil.which(tool):
                raise unittest.SkipTest("trackpad C harness requires " + tool)
        lock = json.loads((ROOT / "sources.lock.json").read_text())
        caches = {name: ROOT / "cache/git" / (name + ".git")
                  for name in ("linux", "wallace")}
        if not all(path.is_dir() for path in caches.values()):
            raise unittest.SkipTest("trackpad C harness requires cached make bundle sources")
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        work = Path(temporary.name)

        def cached(name, path):
            return subprocess.run(
                ["git", "--git-dir=" + str(caches[name]), "show",
                 lock[name]["revision"] + ":" + path],
                capture_output=True, text=True, check=True, timeout=15).stdout

        driver = work / DRIVER
        driver.parent.mkdir(parents=True)
        driver.write_text(cached("linux", DRIVER))
        patches = [cached("wallace", "patches/" + name) for name in
                   ("t6040-dockchannel-trackpad-fw.patch",
                    "t6040-dockchannel-hid-reset-contract.patch")]
        local = (ROOT / lock["linux_trackpad"]["patch"]).read_bytes()
        if hashlib.sha256(local).hexdigest() != lock["linux_trackpad"]["patch_sha256"]:
            raise AssertionError("trackpad patch does not match sources.lock.json")
        overlay = (ROOT / lock["linux_trackpad"]["overlay"]).read_bytes()
        if hashlib.sha256(overlay).hexdigest() != lock["linux_trackpad"]["overlay_sha256"]:
            raise AssertionError("trackpad overlay does not match sources.lock.json")
        if not re.search(rb"reset-gpios\s*=\s*<&smc_gpio_low\s+0x1c\s+GPIO_ACTIVE_LOW>;", overlay):
            raise AssertionError("C harness requires the J614s active-low reset binding")
        patches.append(local.decode())
        for patch in patches:
            subprocess.run(["patch", "-f", "-p1"], input=patch, cwd=work,
                           capture_output=True, text=True, check=True, timeout=15)
        source = driver.read_text()
        definitions = re.findall(
            r"^#define (?:CMD_SET_POWER|PWR_\w+|J614S_AFE_RESET_DELAY_MS)\s+[^\n]+",
            source, re.MULTILINE)
        packet = re.search(r"struct dchid_power_req \{.*?\} __packed;", source, re.DOTALL)
        if not packet:
            raise AssertionError("power packet definition missing")
        (work / "driver-power.inc").write_text("\n".join([
            *definitions, packet.group(), function(source, "dchid_host_power"),
            function(source, "dchid_reset_interface"),
        ]) + "\n")
        cls.binary = work / "trackpad-power"
        subprocess.run([
            "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-I", str(work),
            str(ROOT / "tests/fixtures/trackpad-power.c"), "-o", str(cls.binary),
        ], capture_output=True, text=True, check=True, timeout=30)

    def run_case(self, case):
        result = subprocess.run([str(self.binary), case], capture_output=True,
                                text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_power_off_asserts_physical_low_before_has_changed(self):
        self.run_case("off")

    def test_power_on_releases_physical_high_before_has_changed(self):
        self.run_case("on")

    def test_firmware_power_cycle_preserves_both_handshakes(self):
        self.run_case("cycle")

    def test_gpio_error_does_not_acknowledge_success_or_fall_back(self):
        self.run_case("gpio-failure")

    def test_will_timeout_does_not_touch_gpio(self):
        self.run_case("will-timeout")

    def test_rejected_v2_retains_legacy_protocol_without_gpio_writes(self):
        self.run_case("legacy-fallback")

    def test_absent_gpio_preserves_notifications_only(self):
        self.run_case("no-gpio")

    def test_keyboard_never_touches_trackpad_reset(self):
        self.run_case("keyboard")

    def test_has_changed_error_is_returned_without_legacy_fallback(self):
        self.run_case("has-failure")

    def test_unknown_power_state_cannot_toggle_reset(self):
        self.run_case("unsupported-state")


if __name__ == "__main__":
    unittest.main()
