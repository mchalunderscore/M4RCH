import gzip
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

PROJECT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT / "sdboot"), str(PROJECT / "lib")]
import split_loader
import enrollment
from common import manifest_files, write_json
spec = importlib.util.spec_from_file_location("setup_split", PROJECT / "scripts/setup-split-boot.py")
setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)


class SplitLoaderTests(unittest.TestCase):
    def test_stage1_binds_exact_partition_and_root_filename(self):
        prefix = bytes(16384)
        image = split_loader.stage1_payload(prefix)
        self.assertEqual(image[:16384], prefix)
        self.assertEqual(len(image) % 16384, 0)
        self.assertIn(("chainload=" + split_loader.ESP_UUID + ";boot.bin\n").encode(), image)
        self.assertIn(("chosen.asahi,efi-system-partition=" + split_loader.ESP_UUID + "\n").encode(), image)
        with self.assertRaises(ValueError): split_loader.stage1_payload(b"unaligned")

    def test_stage2_compression_leaves_appended_variables_parseable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prefix = bytes(16384)
            dtb = struct.pack(">II", 0xd00dfeed, 40) + bytes(32)
            image = bytearray(64)
            struct.pack_into("<QQ", image, 8, 0, 128)
            image[56:60] = b"ARM\x64"
            for name, data in (("m1n1.bin", prefix), ("baseline.dtb", dtb), ("u-boot-nodtb.bin", image)):
                (root / name).write_bytes(data)
            stage2 = split_loader.stage2_payload(root)
            variables = b"chosen.asahi,m1n1-stage1-version=test\n\0\0\0\0"
            inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
            self.assertEqual(inflater.decompress(stage2[16424:] + variables), image)
            self.assertTrue(inflater.eof)
            self.assertEqual(inflater.unused_data, variables)
            self.assertEqual(stage2, split_loader.stage2_payload(root))

    def test_enrollment_selects_stage1_not_stage2(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); artifacts = root / "split-loader"; artifacts.mkdir()
            (artifacts / "loader.bin").write_bytes(b"stage1")
            (artifacts / "boot.bin").write_bytes(b"stage2")
            write_json(artifacts / "loader-manifest.json", {
                "schema": 1, "kind": "j614s-stage1-loader", "boot_protocol": "m1n1-chainload",
                "inputs": {"nvme_handoff": {"verified": True}},
                "files": manifest_files(artifacts, ["loader.bin", "boot.bin"])})
            source, info = enrollment._source(root, "stage1")
            self.assertEqual(source.name, "loader.bin")
            self.assertEqual(info["bytes"], 6)
            (artifacts / "boot.bin").write_bytes(b"tampered")
            with self.assertRaises(ValueError): enrollment._source(root, "stage1")

    def test_stage2_replacement_preserves_verified_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); esp = root / "esp"; esp.mkdir()
            source = root / "source"; source.write_bytes(b"new stage2")
            (esp / "boot.bin").write_bytes(b"previous stage2")
            with patch.object(setup, "run"):
                result = setup.install_stage2(source, esp, root / "backup")
            self.assertEqual((esp / "boot.bin").read_bytes(), b"new stage2")
            self.assertEqual((root / "backup/boot.bin").read_bytes(), b"previous stage2")
            self.assertNotEqual(result["previous_sha256"], result["stage2_sha256"])
            self.assertEqual(sorted(path.name for path in esp.iterdir()), ["boot.bin"])

    def test_corrupt_stage2_copy_never_replaces_working_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); esp = root / "esp"; esp.mkdir()
            source = root / "source"; source.write_bytes(b"new")
            (esp / "boot.bin").write_bytes(b"working")
            with patch.object(setup.shutil, "copyfileobj", side_effect=lambda incoming, output: output.write(b"bad")):
                with self.assertRaisesRegex(ValueError, "verification"):
                    setup.install_stage2(source, esp, root / "backup")
            self.assertEqual((esp / "boot.bin").read_bytes(), b"working")
            self.assertEqual(sorted(path.name for path in esp.iterdir()), ["boot.bin"])
