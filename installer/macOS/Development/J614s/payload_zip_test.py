import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import payload_zip
import stage1_inspect
import stage1_test


def digest(data):
    return hashlib.sha256(data).hexdigest()


class DevelopmentZipTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.m4rch = self.root / "m4rch"
        self.m4rch.mkdir()
        self.payload = self.inputs / "source.zip"
        self.metadata = self.inputs / "metadata.json"
        self.stage1 = self.inputs / "stage1.bin"
        self.stage1_bytes = stage1_test.native_sample()
        self.stage1.write_bytes(self.stage1_bytes)
        self.items = {
            "boot.img": b"boot",
            "root.img": b"root",
            "esp/m1n1/boot.bin": b"common",
            "esp/m1n1/boot-j700.bin": b"j700",
            "esp/aurora/stage1.bin": b"upstream-stage1",
            "esp/EFI/BOOT/BOOTAA64.EFI": b"efi",
            "aurora-volume.icns": b"icon",
        }
        self.save_zip()
        self.data = {
            "os_list": [
                {
                    "omarchy_target": "apple-silicon-full-os",
                    "installation_profile": "arch-minimal",
                    "layout_kind": "alarm-btrfs-v1",
                    "next_object": "m1n1/boot.bin",
                    "package": "official.zip",
                    "aurora_stage1": {
                        "kind": "common-raw-v1",
                        "qualified_machines": {"j700ap": ["26.6.2"]},
                    },
                    "aurora_stage2": {
                        "kind": "board-file-v1",
                        "board_members": {"j700ap": "esp/m1n1/boot-j700.bin"},
                    },
                }
            ]
        }
        self.metadata.write_text(json.dumps(self.data))

    def save_zip(self, extra=None):
        with zipfile.ZipFile(self.payload, "w") as archive:
            for name, data in self.items.items():
                archive.writestr(name, data)
            if extra:
                archive.writestr(extra, b"unexpected")

    def prepare(self, output, *, payload_hash=None, stage1_hash=None):
        with patch.object(payload_zip, "make_candidate", return_value=b"j614s-stage2"):
            return payload_zip.prepare(
                self.payload,
                self.metadata,
                payload_hash or digest(self.payload.read_bytes()),
                digest(self.metadata.read_bytes()),
                self.m4rch,
                output,
                self.stage1,
                stage1_hash or digest(self.stage1_bytes),
            )

    def test_streamed_candidate_binds_both_stages_and_preserves_source(self):
        before = self.payload.read_bytes()
        output = self.root / "output"
        receipt = self.prepare(output)
        metadata = json.loads((output / "metadata.json").read_bytes())["os_list"][0]
        self.assertEqual(metadata["allowed_device_classes"], ["j614sap"])
        self.assertEqual(
            metadata["aurora_stage1"]["qualified_machines"], {"j614sap": ["26.6.2"]}
        )
        self.assertEqual(
            metadata["aurora_stage2"]["board_members"]["j614sap"],
            "esp/m1n1/boot-j614s.bin",
        )
        with zipfile.ZipFile(output / payload_zip.OUTPUT_PAYLOAD) as archive:
            self.assertEqual(archive.read("root.img"), b"root")
            self.assertEqual(archive.read("esp/m1n1/boot-j614s.bin"), b"j614s-stage2")
            stage1 = archive.read("esp/aurora/stage1.bin")
        stage1_report = stage1_inspect.inspect(stage1, digest(stage1))
        self.assertEqual(
            stage1_report["original_esp_uuid"], "00000000-0000-0000-0000-000000000000"
        )
        self.assertEqual(stage1_report["original_stage2_path"], "m1n1/boot.bin")
        self.assertNotIn(stage1_test.ESP, stage1)
        self.assertFalse(receipt["install_ready"])
        self.assertFalse(receipt["stage1_native_boot_verified"])
        self.assertEqual(self.payload.read_bytes(), before)
        self.assertEqual(json.loads(self.metadata.read_text()), self.data)

    def test_wrong_hash_leaves_no_output(self):
        output = self.root / "output"
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.prepare(output, payload_hash="0" * 64)
        self.assertFalse(output.exists())

    def test_traversal_and_symlink_members_are_rejected(self):
        for extra in ("../escape", "esp/m1n1/../../escape"):
            self.save_zip(extra)
            output = self.root / "output"
            with self.assertRaisesRegex(ValueError, "unsafe"):
                self.prepare(output)
            self.assertFalse(output.exists())
        info = zipfile.ZipInfo("esp/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.save_zip(info)
        with self.assertRaisesRegex(ValueError, "non-regular"):
            self.prepare(self.root / "output")

    def test_requires_matching_cfg01_stage1(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.prepare(self.root / "output", stage1_hash="0" * 64)
        self.stage1.write_bytes(b"not cfg01")
        with self.assertRaises(ValueError):
            self.prepare(self.root / "output", stage1_hash=digest(b"not cfg01"))
        self.assertFalse((self.root / "output").exists())


if __name__ == "__main__":
    unittest.main()
