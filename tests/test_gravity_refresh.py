import gzip
import importlib.util
from pathlib import Path
import struct
import unittest

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gravity_refresh_test', PROJECT / 'scripts/stage-gravity-refresh.py')
refresh = importlib.util.module_from_spec(spec); spec.loader.exec_module(refresh)


class InstalledBaselineTests(unittest.TestCase):
    def bundle(self):
        dtb = struct.pack('>II', 0xd00dfeed, 40) + bytes(32)
        image = bytearray(64)
        struct.pack_into('<QQ', image, 8, 0, 128)
        image[56:60] = b'ARM\x64'
        return bytes(16384) + dtb + gzip.compress(image, mtime=0), dtb

    def test_preserves_installed_baseline_bytes(self):
        bundle, dtb = self.bundle()
        self.assertEqual(refresh.installed_dtb(bundle), dtb)

    def test_refuses_truncated_or_unaligned_or_non_arm64_installed_bundle(self):
        bundle, _ = self.bundle()
        for bad in (bundle[:-6], bundle[1:], bytes(16384) + bundle[16384:16424] + gzip.compress(bytes(64))):
            with self.subTest(length=len(bad)):
                with self.assertRaises(ValueError):
                    refresh.installed_dtb(bad)
