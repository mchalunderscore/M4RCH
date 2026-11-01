import io
import gzip
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import preflight
import build_stage2


class PreflightTests(unittest.TestCase):
    def test_stage2_round_trip_and_rejects_wrong_tree(self):
        prefix = bytes(16384)
        dtb = struct.pack(">II", 0xD00DFEED, 40) + bytes(32)
        uboot = bytearray(80)
        struct.pack_into("<QQ", uboot, 8, 0, 80)
        uboot[56:60] = b"ARM\x64"
        result = build_stage2.assemble(prefix, dtb, bytes(uboot))
        self.assertEqual(result[: len(prefix) + len(dtb)], prefix + dtb)
        self.assertEqual(gzip.decompress(result[len(prefix) + len(dtb) :]), uboot)
        with self.assertRaises(ValueError):
            build_stage2.assemble(prefix, b"not a tree", bytes(uboot))

    def test_missing_and_modified_inputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(preflight.audit(root)["inputs_verified"])
            file = root / "input"
            file.write_bytes(b"changed")
            with patch.object(
                preflight,
                "INPUTS",
                {
                    "kernel": ("input", "0" * 64),
                    "config": ("absent", "0" * 64),
                    "modules": ("absent", "0" * 64),
                },
            ):
                self.assertEqual(
                    preflight.audit(root)["inputs"]["kernel"]["status"], "mismatch"
                )

    def test_module_must_be_unique_regular_file_in_matching_release(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "modules.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                item = tarfile.TarInfo(preflight.MODULE)
                item.size = 1
                output.addfile(item, io.BytesIO(b"x"))
            self.assertTrue(preflight.inspect_modules(archive))
            with tarfile.open(archive, "w:gz") as output:
                item = tarfile.TarInfo(preflight.MODULE)
                item.type = tarfile.SYMTYPE
                item.linkname = "elsewhere"
                output.addfile(item)
            self.assertFalse(preflight.inspect_modules(archive))


if __name__ == "__main__":
    unittest.main()
