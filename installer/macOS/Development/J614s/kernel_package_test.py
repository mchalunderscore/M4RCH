import unittest

import kernel_package_audit


class KernelPackageTests(unittest.TestCase):
    def test_configuration_requires_each_crypto_and_storage_setting(self):
        config = "\n".join(
            f"{key}={value}"
            for key, value in kernel_package_audit.REQUIRED_CONFIG.items()
        )
        self.assertEqual(
            kernel_package_audit.checked_config(config),
            kernel_package_audit.REQUIRED_CONFIG,
        )
        with self.assertRaises(ValueError):
            kernel_package_audit.checked_config(
                config.replace("CONFIG_DM_CRYPT=m", "CONFIG_DM_CRYPT=n")
            )
        with self.assertRaises(ValueError):
            kernel_package_audit.checked_config(config + "\nCONFIG_DM_CRYPT=m")


if __name__ == "__main__":
    unittest.main()
