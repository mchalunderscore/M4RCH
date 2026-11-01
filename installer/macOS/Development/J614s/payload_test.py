import gzip
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import payload_stage2
import preflight


def digest(value):
    return hashlib.sha256(value).hexdigest()


class Stage2OverlayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bundle = self.root / "bundle"
        self.m4rch = self.root / "m4rch"
        (self.bundle / "esp/m1n1").mkdir(parents=True)
        self.m4rch.mkdir()
        common = b"common"
        board = b"j700"
        (self.bundle / "esp/m1n1/boot.bin").write_bytes(common)
        (self.bundle / "esp/m1n1/boot-j700.bin").write_bytes(board)
        self.manifest = {
            "schema": 1,
            "sourceSha256": digest(common),
            "boards": {
                "j700ap": {
                    "member": "esp/m1n1/boot-j700.bin",
                    "bytes": len(board),
                    "sha256": digest(board),
                }
            },
        }
        (self.bundle / "stage2.json").write_text(json.dumps(self.manifest))
        prefix = b"x" * 16384
        dtb = struct.pack(">II", 0xD00DFEED, 40) + bytes(32)
        uboot = bytearray(64)
        struct.pack_into("<QQ", uboot, 8, 0, 64)
        uboot[56:60] = b"ARM\x64"
        self.files = {"m1n1_stage2": prefix, "dtb": dtb, "uboot": bytes(uboot)}
        self.inputs = {}
        for name, data in self.files.items():
            (self.m4rch / name).write_bytes(data)
            self.inputs[name] = (name, digest(data))

    def generate(self, output):
        with patch.object(preflight, "INPUTS", self.inputs), patch.object(
            preflight, "audit", return_value={"inputs_verified": True}
        ):
            return payload_stage2.generate(self.bundle, self.m4rch, output)

    def test_overlay_preserves_existing_board_and_binds_candidate(self):
        output = self.root / "overlay"
        receipt = self.generate(output)
        manifest = json.loads((output / "stage2.json").read_text())
        self.assertEqual(
            manifest["boards"]["j700ap"], self.manifest["boards"]["j700ap"]
        )
        candidate = (output / payload_stage2.MEMBER).read_bytes()
        self.assertEqual(manifest["boards"]["j614sap"]["sha256"], digest(candidate))
        self.assertEqual(receipt["sha256"], digest(candidate))
        self.assertFalse(receipt["install_ready"])
        offset = len(self.files["m1n1_stage2"]) + len(self.files["dtb"])
        self.assertEqual(gzip.decompress(candidate[offset:]), self.files["uboot"])
        self.assertEqual(
            json.loads((self.bundle / "stage2.json").read_text()), self.manifest
        )

    def test_rejects_corrupted_upstream_member_before_creating_output(self):
        (self.bundle / "esp/m1n1/boot-j700.bin").write_bytes(b"tampered")
        output = self.root / "overlay"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            self.generate(output)
        self.assertFalse(output.exists())

    def test_rejects_changed_candidate_input(self):
        (self.m4rch / "dtb").write_bytes(b"changed")
        output = self.root / "overlay"
        with self.assertRaisesRegex(ValueError, "changed during build"):
            self.generate(output)
        self.assertFalse(output.exists())

    def test_rejects_output_inside_input_tree(self):
        with self.assertRaisesRegex(ValueError, "outside both input trees"):
            self.generate(self.bundle / "overlay")
        self.assertFalse((self.bundle / "overlay").exists())


if __name__ == "__main__":
    unittest.main()
