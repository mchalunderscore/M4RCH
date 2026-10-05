"""Execute the late driver loader against recorded fake kernel interfaces."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from sdboot.rootfs import configure_package
from sdboot.packages import render_boot_configuration


class PeripheralTests(unittest.TestCase):
    def trial(self, group, *, marker=None, options="", board="apple,j614s", fail=""):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "chosen").mkdir()
            (root / "compatible").write_bytes(board.encode() + b"\0apple,t6040\0")
            (root / "cmdline").write_text(options)
            if marker is not None:
                (root / "chosen/arch-m4,ans-handoff").write_bytes(marker.encode() + b"\0")
            binary = root / "bin"
            binary.mkdir()
            log = root / "calls"
            for name, code in {
                "id": "printf '0\\n'",
                "modprobe": 'printf "%s\\n" "$1" >> "$CALLS"\n[ "$1" != "$FAIL_MODULE" ]',
            }.items():
                path = binary / name
                path.write_text("#!/bin/sh\n" + code + "\n")
                path.chmod(0o755)
            source = (PROJECT / "templates/enable-peripherals.sh").read_text()
            source = source.replace("PATH=/usr/sbin:/usr/bin:/sbin:/bin", f"PATH={binary}:/usr/bin:/bin")
            source = source.replace("/sys/firmware/devicetree/base/compatible", str(root / "compatible"))
            source = source.replace("/sys/firmware/devicetree/base/chosen", str(root / "chosen"))
            source = source.replace("/proc/cmdline", str(root / "cmdline"))
            script = root / "loader"
            script.write_text(source)
            result = subprocess.run(["sh", str(script), group], text=True, capture_output=True,
                                    env=dict(os.environ, CALLS=str(log), FAIL_MODULE=fail))
            return result, log.read_text().splitlines() if log.exists() else []

    def test_old_or_unknown_handoff_never_probes_nvme(self):
        for marker in (None, "v1", "v2\n", ""):
            with self.subTest(marker=marker):
                result, calls = self.trial("nvme", marker=marker)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(calls, [])
                self.assertIn("skipped", result.stdout)

    def test_nvme_requires_both_board_and_current_handoff(self):
        result, calls = self.trial("nvme", marker="v2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["apple-sart", "nvme-apple"])
        result, calls = self.trial("nvme", marker="v2", board="apple,j314s")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_boot_recovery_switches_prevent_controller_access(self):
        for group in ("platform", "usb", "nvme"):
            for option in ("arch_m4.peripherals=off", "arch_m4." + group + "=off"):
                with self.subTest(group=group, option=option):
                    result, calls = self.trial(group, marker="v2", options="root=UUID=a " + option)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(calls, [])

    def test_usb_uses_root_hub_then_pd_sequence_and_stops_on_failure(self):
        result, calls = self.trial("usb")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["phy-apple-t6040-usb2", "dwc3-apple", "spmi-apple-controller", "tps6598x"])
        result, calls = self.trial("usb", fail="dwc3-apple")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, ["phy-apple-t6040-usb2", "dwc3-apple"])

    def test_platform_loads_pmu_before_rtc_and_poweroff(self):
        result, calls = self.trial("platform")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["spmi-apple-controller", "apple_nvmem_spmi", "rtc-macsmc", "macsmc-reboot"])

    def test_package_late_units_do_not_wait_for_probe_to_finish(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = json.loads((PROJECT / "sdboot/config.json").read_text())
            configure_package(PROJECT, root, config)
            render_boot_configuration(PROJECT, root, config, "7.1-test")
            for group in ("platform", "usb", "nvme"):
                name = "m4rch-" + group + ".service"
                unit = (root / "usr/lib/systemd/system" / name).read_text()
                self.assertIn("After=multi-user.target", unit)
                self.assertIn("Type=exec\n", unit)
                self.assertIn("ConditionKernelCommandLine=!arch_m4.peripherals=off", unit)
                self.assertTrue((root / "etc/systemd/system/graphical.target.wants" / name).is_symlink())
            menu = (root / "usr/share/m4rch/grub.cfg.in").read_text()
            self.assertEqual(menu.count("menuentry "), 2)
            self.assertEqual(menu.count("arch_m4.peripherals=off"), 1)


if __name__ == "__main__":
    unittest.main()
