import hashlib
import binascii
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import stage1_inspect as stage1

ESP = b"5fdb35c6-3a66-416d-8358-6555fd99fcc5"


def sample(base):
    trailer = b"chainload=" + ESP + b";boot.bin\n"
    trailer += b"chosen.asahi,efi-system-partition=" + ESP + b"\n" + bytes(4)
    data = base + trailer
    return data + bytes(-len(data) % stage1.ALIGNMENT)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def native_sample():
    body = struct.pack("<II", 1, 0) + ESP + bytes(4)
    path = b";boot.bin"
    body += path + bytes(192 - len(path))
    body += struct.pack("<I", binascii.crc32(body))
    return b"prefix" + stage1.MARKER + body + b"STACKBOT"


class Stage1Tests(unittest.TestCase):
    def test_native_config_crc_and_fields(self):
        data = native_sample()
        result = stage1.inspect(data, digest(data))
        self.assertEqual(result["format"], "aurora-cfg01-v1")
        self.assertTrue(result["aurora_native_config_compatible"])
        self.assertEqual(result["original_esp_uuid"], ESP.decode())
        self.assertEqual(result["original_stage2_path"], "boot.bin")
        self.assertFalse(result["install_ready"])

    def test_native_rejects_bad_crc_unsafe_path_and_duplicate_marker(self):
        data = native_sample()
        offset = data.index(stage1.MARKER) + len(stage1.MARKER)
        bad_crc = bytearray(data)
        bad_crc[offset + 48 + 1] = ord("x")
        with self.assertRaisesRegex(ValueError, "CRC"):
            stage1.inspect(bad_crc, digest(bad_crc))
        bad_path = bytearray(data)
        bad_path[offset + 48 : offset + 53] = b";../x"
        body = bad_path[offset : offset + 240]
        bad_path[offset + 240 : offset + 244] = struct.pack("<I", binascii.crc32(body))
        with self.assertRaisesRegex(ValueError, "relative path"):
            stage1.inspect(bad_path, digest(bad_path))
        duplicate = data[:-8] + stage1.MARKER + data[-8:]
        with self.assertRaisesRegex(ValueError, "one CFG01 marker"):
            stage1.inspect(duplicate, digest(duplicate))

    def test_native_export_preserves_image_and_never_overwrites(self):
        data = native_sample()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "configured.bin"
            target = Path(directory) / "native.bin"
            source.write_bytes(data)
            args = [
                "stage1_inspect.py",
                str(source),
                "--sha256",
                digest(data),
                "--native-stage1-output",
                str(target),
            ]
            with patch("sys.argv", args):
                self.assertEqual(stage1.main(), 0)
                self.assertEqual(target.read_bytes(), data)
                self.assertEqual(stage1.main(), 1)
            self.assertEqual(target.read_bytes(), data)

    def test_bound_aligned_legacy_payload(self):
        base = b"x" * (stage1.ALIGNMENT - 8) + b"STACKBOT"
        data = sample(base)
        result = stage1.inspect(data, digest(data))
        self.assertTrue(result["aurora_legacy_base_compatible"])
        self.assertEqual(result["base_sha256"], digest(base))
        self.assertFalse(result["install_ready"])

    def test_mismatched_digest_and_nonzero_padding_rejected(self):
        data = sample(b"x" * (stage1.ALIGNMENT - 8) + b"STACKBOT")
        with self.assertRaises(ValueError):
            stage1.inspect(data, "0" * 64)
        altered = data[:-1] + b"x"
        with self.assertRaises(ValueError):
            stage1.inspect(altered, digest(altered))

    def test_oversized_legacy_base_rejected_by_aurora_contract(self):
        base = b"x" * ((4 << 20) - 8) + b"STACKBOT"
        data = sample(base)
        result = stage1.inspect(data, digest(data))
        self.assertFalse(result["aurora_legacy_base_compatible"])
        self.assertFalse(
            result["aurora_legacy_base_checks"]["base_at_most_aurora_limit"]
        )

    def test_candidate_base_is_exclusive_and_matches_identified_input(self):
        base = b"x" * (stage1.ALIGNMENT - 8) + b"STACKBOT"
        data = sample(base)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "configured.bin"
            target = Path(directory) / "legacy-base.bin"
            source.write_bytes(data)
            args = [
                "stage1_inspect.py",
                str(source),
                "--sha256",
                digest(data),
                "--legacy-base-output",
                str(target),
            ]
            with patch("sys.argv", args):
                self.assertEqual(stage1.main(), 0)
                self.assertEqual(target.read_bytes(), base)
                self.assertEqual(stage1.main(), 1)
            self.assertEqual(target.read_bytes(), base)


if __name__ == "__main__":
    unittest.main()
