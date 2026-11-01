import io
from pathlib import Path
import tarfile
import tempfile
import unittest

import prepare_rebuilt_package as candidate


class RebuiltPackageTests(unittest.TestCase):
    def test_required_kernel_config_rejects_missing_sequencer(self):
        config = "\n".join(
            [
                'CONFIG_LOCALVERSION="-m4rch-aurora1"',
                "CONFIG_RUST=y",
                "CONFIG_SND_SEQUENCER=m",
                "CONFIG_SND_SEQ_DEVICE=m",
                "CONFIG_BTRFS_FS=m",
                "CONFIG_NVME_APPLE=m",
                "CONFIG_DM_CRYPT=m",
                "CONFIG_DM_INTEGRITY=m",
                "CONFIG_CRYPTO_XTS=m",
            ]
        )
        candidate.validate_config(config)
        with self.assertRaises(ValueError):
            candidate.validate_config(
                config.replace(
                    "CONFIG_SND_SEQUENCER=m", "# CONFIG_SND_SEQUENCER is not set"
                )
            )

    def test_module_archive_rejects_a_mismatched_kernel_release(self):
        def create(path, vermagic):
            prefix = f"lib/modules/{candidate.RELEASE}/"
            with tarfile.open(path, "w:gz") as archive:
                items = {
                    prefix
                    + "modules.dep": "".join(
                        f"{name}:\n" for name in candidate.REQUIRED_MODULES
                    ).encode()
                }
                items.update(
                    {
                        prefix + name: b"vermagic=" + vermagic
                        for name in candidate.REQUIRED_MODULES
                    }
                )
                for name, data in items.items():
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "modules.tar.gz"
            create(path, candidate.RELEASE.encode())
            self.assertEqual(
                set(candidate.verify_modules(path)), set(candidate.REQUIRED_MODULES)
            )
            create(path, b"wrong-release")
            with self.assertRaises(ValueError):
                candidate.verify_modules(path)


if __name__ == "__main__":
    unittest.main()
