import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from common import sha256, write_json
import stub_payload as stub


class StubPayloadTests(unittest.TestCase):
    def identity(self):
        return {"ApBoardID": "0x04", "ApChipID": "0x6040",
                "Info": {"DeviceClass": "j614sap", "RestoreBehavior": "Erase",
                         "Variant": "macOS Customer"},
                "Manifest": {name: {"Info": {"Path": path}} for name, path in {
                    "BaseSystem": "base.dmg.aea", "OS": "os.dmg.aea",
                    "Cryptex1,SystemOS": "cryptex.dmg.aea", "KernelCache": "kernelcache",
                    "Ap,SecurePageTableMonitor": "Firmware/sptm.im4p",
                    "iBootData": "Firmware/ibootdata.im4p"}.items()}}

    def test_exact_identity_required(self):
        manifest = {"ProductBuildVersion": "25F84", "BuildIdentities": [self.identity()]}
        self.assertEqual(stub.select_identity(manifest), self.identity())
        for changed in ("ApBoardID", "ApChipID"):
            wrong = copy.deepcopy(manifest)
            wrong["BuildIdentities"][0][changed] = "0x00"
            with self.assertRaisesRegex(ValueError, "exactly one"):
                stub.select_identity(wrong)
        manifest["BuildIdentities"].append(self.identity())
        with self.assertRaisesRegex(ValueError, "exactly one"):
            stub.select_identity(manifest)

    def test_m4_restore_members_keep_boot_firmware_but_exclude_system_images(self):
        self.assertEqual(stub.restore_members(self.identity()),
                         {"kernelcache", "Firmware/sptm.im4p", "Firmware/ibootdata.im4p"})

    def test_pinned_lock_covers_26_metadata_and_real_bootability(self):
        lock = stub.load_lock()
        self.assertEqual(lock["restore_bundle_path"], "restore")
        self.assertIn("usr/standalone/bootcaches.plist", lock["files"])
        self.assertIn("Firmware/sptm.t6041.release.im4p", lock["files"])
        self.assertIn("BootabilityBundle/Restore/Bootability/BootabilityBrain.framework/Versions/A/BootabilityBrain",
                      lock["files"])
        self.assertFalse(any(name.endswith(".dmg.aea") for name in lock["files"]))

    def test_archive_paths_and_links_cannot_escape(self):
        for name in ("", ".", "../outside", "/etc/passwd", "a/../../outside", "a/./b"):
            with self.assertRaises(ValueError):
                stub.relative_path(name)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for target in ("/etc/passwd", "../outside"):
                with self.assertRaises(ValueError):
                    stub.safe_link(root, root / "link", target)
            stub.safe_link(root, root / "link", "inside")
            self.assertEqual((root / "link").readlink(), Path("inside"))

    def test_cached_payload_rejects_tampering_and_extra_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "System").mkdir()
            item = root / "System/file"
            item.write_bytes(b"verified")
            files, links, directories = stub.inventory(root)
            manifest = {"schema": 1, "apple_build": "25F84", "model": "Mac16,8",
                        "device_class": "j614sap", "board_id": "0x04", "chip_id": "0x6040",
                        "restore_bundle_path": "restore", "input_lock_sha256": sha256(stub.LOCK_PATH),
                        "builder_sha256": sha256(stub.__file__), "files": files,
                        "symlinks": links, "directories": directories}
            write_json(root / "manifest.json", manifest)
            self.assertEqual(stub.verify(root), manifest)
            item.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "changed"):
                stub.verify(root)
            item.write_bytes(b"verified")
            item.chmod(0o700)
            with self.assertRaisesRegex(ValueError, "changed"):
                stub.verify(root)
            item.chmod(files["System/file"]["mode"])
            (root / "extra").write_text("unexpected")
            with self.assertRaisesRegex(ValueError, "changed"):
                stub.verify(root)


if __name__ == "__main__":
    unittest.main()
