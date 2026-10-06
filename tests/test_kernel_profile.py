"""Check the shared kernel profile requirements used by the native SD build."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import boot
import kernel_profile


class KernelProfileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_profile_paths_and_stable_requirements_are_unchanged(self):
        self.assertEqual(kernel_profile.output(self.root, "stable"), self.root)
        self.assertEqual(kernel_profile.output(self.root, "experimental"), self.root / "experimental")
        self.assertEqual(kernel_profile.output(self.root, "experimental-nvme"), self.root / "experimental-nvme")
        with self.assertRaisesRegex(ValueError, "Unknown kernel profile"):
            kernel_profile.output(self.root, "../stable")
        builtins, modules, disabled = kernel_profile.requirements(boot.REQUIRED, boot.DISABLED, "stable")
        self.assertEqual(builtins, set(boot.REQUIRED))
        self.assertEqual(modules, set())
        self.assertEqual(disabled, set(boot.DISABLED))

    def test_experimental_retains_boot_drivers_and_known_failure_exclusions(self):
        builtins, modules, disabled = kernel_profile.requirements(boot.REQUIRED, boot.DISABLED, "experimental")
        self.assertTrue({"MODULES", "EXT4_FS", "EXFAT_FS", "MMC_SDHCI_PCI", "APPLE_DART",
                         "PCIE_APPLE", "HID_APPLE", "SECURITY_LANDLOCK", "VIRTIO_BLK"} <= builtins)
        self.assertTrue({"FUSE_FS", "OVERLAY_FS", "NVME_APPLE", "RTC_DRV_MACSMC",
                         "POWER_RESET_MACSMC", "USB_DWC3_APPLE"} <= modules)
        self.assertTrue({"KVM", "VIRTUALIZATION", "USB4_DEBUGFS_WRITE"} <= disabled)
        self.assertTrue({"ARM64_SVE", "ARM64_SME"} <= builtins)
        self.assertIn("ARM64_SME", boot.DISABLED)
        self.assertFalse(builtins & modules or builtins & disabled or modules & disabled)
        self.assertEqual(kernel_profile.requirements(boot.REQUIRED, boot.DISABLED, "experimental-nvme"),
                         (builtins, modules, disabled))


if __name__ == "__main__":
    unittest.main()
