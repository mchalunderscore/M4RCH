"""Reject hardware-description regressions before a native driver trial.

The fixture is a reduced dtc output from the pinned Wallace board plus the tp2
and experimental overlays, compiled on 2026-10-04. Register values independently
match the retained Apple 25F84 J614s ADT; it is not evidence of working drivers.
"""
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import hardware_profile as hardware

PROJECT = Path(__file__).resolve().parents[1]


class ExperimentalHardwareTests(unittest.TestCase):
    def setUp(self):
        data = json.loads((PROJECT / "tests/fixtures/experimental-dt-nodes.json").read_text())
        self.nodes = {name: {key: bytes.fromhex(value) for key, value in props.items()}
                      for name, props in data.items()}

    def test_compiled_board_is_accepted(self):
        hardware.check_nodes(self.nodes)

    def test_rejects_old_untranslated_pd_address(self):
        self.nodes["/soc/spmi@509198000"]["reg"] = struct.pack(">IIII", 3, 0x09198000, 0, 0x4000)
        with self.assertRaisesRegex(ValueError, "unexpected reg"):
            hardware.check_nodes(self.nodes)

    def test_rejects_missing_cold_boot_power_dependency(self):
        del self.nodes["/soc/spmi@509014000"]["power-domains"]
        with self.assertRaisesRegex(ValueError, "incorrect power domains"):
            hardware.check_nodes(self.nodes)

    def test_rejects_old_pmu_scratchpad_address(self):
        path = "/soc/spmi@509014000/pmic@e/nvmem-layout/rtc-offset@2100"
        self.nodes[path]["reg"] = struct.pack(">II", 0xf900, 6)
        with self.assertRaisesRegex(ValueError, "unexpected reg"):
            hardware.check_nodes(self.nodes)

    def test_rejects_wrong_usb_irq_and_iommu_order(self):
        path = "/soc/usb@392280000"
        for key, value in (("interrupts", struct.pack(">III", 0, 1619, 4)),
                           ("iommus", self.nodes[path]["iommus"][8:] + self.nodes[path]["iommus"][:8])):
            with self.subTest(key=key):
                nodes = copy.deepcopy(self.nodes)
                nodes[path][key] = value
                with self.assertRaisesRegex(ValueError, "unexpected " + key):
                    hardware.check_nodes(nodes)

    def test_rejects_alias_that_could_bypass_module_guard(self):
        self.nodes["/soc/usb@392280000"]["compatible"] += b"snps,dwc3\0"
        with self.assertRaisesRegex(ValueError, "unexpected compatible"):
            hardware.check_nodes(self.nodes)

    def test_rejects_accidental_left_port_and_fan_controls(self):
        left = copy.deepcopy(self.nodes)
        left["/soc/usb@382280000"]["status"] = b"okay\0"
        with self.assertRaisesRegex(ValueError, "unreviewed left port"):
            hardware.check_nodes(left)
        self.nodes["/soc/smc@50c600000/hwmon/fan-F0Ac"]["apple,fan-mode"] = b"F0Md\0"
        with self.assertRaisesRegex(ValueError, "automatic SMC fan control"):
            hardware.check_nodes(self.nodes)

    def test_rejects_inactive_pmu_and_widened_nvme_mapping(self):
        for path, key, value in (
            ("/soc/spmi@509014000", "status", b"disabled\0"),
            ("/soc/nvme@44dcc0000", "reg", struct.pack(">IIII", 4, 0x4dcc0000, 0, 0x60000)),
        ):
            with self.subTest(path=path):
                nodes = copy.deepcopy(self.nodes)
                nodes[path][key] = value
                with self.assertRaises(ValueError):
                    hardware.check_nodes(nodes)

    def test_local_overlay_and_source_revision_authenticated(self):
        lock = json.loads((PROJECT / "sources.lock.json").read_text())
        self.assertEqual(hardware.inputs(PROJECT, lock)["blocked_modules"],
                         list(hardware.BLOCKED_MODULES))
        lock["wallace"]["revision"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "pinned Wallace"):
            hardware.inputs(PROJECT, lock)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "patches").mkdir()
            (root / hardware.OVERLAY).write_text("unreviewed wiring")
            lock["wallace"]["revision"] = hardware.WALLACE_REVISION
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                hardware.inputs(root, lock)

    def test_patch_tamper_rejected_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for file in hardware.PATCHES:
                (root / file).write_text("tampered")
            with patch.object(hardware, "run") as run:
                with self.assertRaisesRegex(ValueError, "patch failed SHA-256"):
                    hardware.prepare(root, root)
                run.assert_not_called()


class ExperimentalModuleBindingTests(unittest.TestCase):
    def setUp(self):
        self.release = "7.1.3-m4rch"
        self.infos = {
            name: {"vermagic": [self.release + " SMP mod_unload aarch64"],
                   "alias": ["of:N*T*C" + compatible], "depends": [""]}
            for name, compatible in hardware.MODULE_COMPATIBLES.items()
        }
        self.infos["nvme_apple"]["depends"] = ["nvme-core,apple-sart"]

    def test_reviewed_bindings_and_guarded_dependencies_pass(self):
        report = hardware._check_module_bindings(self.infos, self.release)
        self.assertEqual(report["modules"], len(hardware.BLOCKED_MODULES))

    def test_old_successfully_compiled_but_inert_nvme_driver_is_rejected(self):
        self.infos["nvme_apple"]["alias"] = ["of:N*T*Capple,t8103-nvme-ans2",
                                               "of:N*T*Capple,nvme-ans2"]
        with self.assertRaisesRegex(ValueError, "does not bind apple,t8132-nvme-ans2"):
            hardware._check_module_bindings(self.infos, self.release)

    def test_missing_module_or_wrong_release_rejected(self):
        wrong = copy.deepcopy(self.infos)
        del wrong["tps6598x"]
        with self.assertRaisesRegex(ValueError, "module missing"):
            hardware._check_module_bindings(wrong, self.release)
        wrong = copy.deepcopy(self.infos)
        wrong["tps6598x"]["vermagic"] = ["7.1.3-other-build SMP aarch64"]
        with self.assertRaisesRegex(ValueError, "wrong kernel release"):
            hardware._check_module_bindings(wrong, self.release)

    def test_unguarded_dependency_cannot_bypass_autoload_policy(self):
        self.infos["innocent_auto_loaded_driver"] = {
            "vermagic": [self.release + " SMP mod_unload aarch64"],
            "depends": ["spmi-apple-controller"],
        }
        with self.assertRaisesRegex(ValueError, "Unguarded module"):
            hardware._check_module_bindings(self.infos, self.release)

    def test_bad_elf_and_empty_tree_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "bad.ko"
            file.write_bytes(b"not an ELF module")
            with self.assertRaisesRegex(ValueError, "not AArch64 ELF64"):
                hardware._module_info(file)
            with self.assertRaisesRegex(ValueError, "module missing"):
                hardware.check_modules(root)


if __name__ == "__main__":
    unittest.main()
