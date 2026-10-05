"""Exercise private evidence collection and non-overwriting return archives."""
import gzip
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from sdboot.native_lab import bundle, device_tree, snapshot
from sdboot.macos_port_map import select


class NativeLabTests(unittest.TestCase):
    def test_mac_map_handles_plist_root_and_filters_owner_firmware_and_tunables(self):
        root = {"IORegistryEntryName": "Root", "IOConsoleUsers": "private",
                "IORegistryEntryChildren": [{"IORegistryEntryName": "atc-phy0",
                    "AAPL,phandle": b"\x01\0\0\0", "reg": b"\x02\0\0\0",
                    "tunable-host": b"omit", "firmware": b"omit", "serial-number": "omit"}]}
        result = select(root)
        self.assertEqual(set(result), {"/Root/atc-phy0"})
        self.assertEqual(set(result["/Root/atc-phy0"]), {"AAPL,phandle", "reg"})
        self.assertEqual(result["/Root/atc-phy0"]["reg"]["little_endian_u32"], [2])

    def test_snapshot_retains_command_failure_and_records_live_port_graph(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            proc, sysfs = root / "proc", root / "sys"
            proc.mkdir()
            (proc / "cmdline").write_text("idle=nop arm64.nowfxt")
            with gzip.open(proc / "config.gz", "wb") as target:
                target.write(b"CONFIG_ARM_APPLE_CPUIDLE=y\nCONFIG_CPU_IDLE=y\nCONFIG_OTHER=y\n")
            node = sysfs / "firmware/devicetree/base/soc/usb@392280000"
            node.mkdir(parents=True)
            (node / "compatible").write_bytes(b"apple,t8103-dwc3\0")
            (node / "status").write_bytes(b"okay\0")
            (node / "reg").write_bytes(bytes.fromhex("0000000392280000"))
            calls = []
            def unavailable(argv):
                calls.append(argv)
                return {"argv": argv, "error": "fixture missing optional command"}
            output = snapshot(root / "capture", "right-key", sysfs=sysfs, proc=proc,
                              boot=root / "boot", runner=unavailable)
            hardware = json.loads((output / "hardware.json").read_text())
            self.assertEqual(hardware["cmdline"], "idle=nop arm64.nowfxt")
            self.assertEqual(hardware["device_tree"]["/soc/usb@392280000"]["status"], ["okay"])
            self.assertEqual(hardware["device_tree"]["/soc/usb@392280000"]["reg"]["cells"], [3, 0x92280000])
            self.assertNotIn("CONFIG_OTHER=y", hardware["kernel_config"]["settings"])
            self.assertFalse(hardware["efi"]["present"])
            self.assertTrue((output / "COMPLETE").is_file())
            self.assertFalse((output / "INCOMPLETE").exists())
            self.assertIn("error", json.loads((output / "usb.json").read_text()))
            self.assertIn(["lsusb", "-t"], calls)

    def test_snapshot_refuses_existing_output_and_symlink_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            prior = root / "prior"
            prior.mkdir()
            (prior / "keep").write_text("untouched")
            with self.assertRaises(FileExistsError):
                snapshot(prior, "baseline")
            self.assertEqual((prior / "keep").read_text(), "untouched")
            (root / "link").symlink_to(prior, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                snapshot(root / "link/new", "baseline")
            self.assertFalse((prior / "new").exists())

    def test_device_tree_omits_unselected_data_and_does_not_follow_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            node = root / "chosen"
            node.mkdir()
            (node / "serial-number").write_bytes(b"not needed")
            (node / "compatible").symlink_to(node / "serial-number")
            elsewhere = root / "outside"
            elsewhere.mkdir()
            (elsewhere / "status").write_bytes(b"secret")
            (root / "usb-linked").symlink_to(elsewhere, target_is_directory=True)
            result = device_tree(root)
            self.assertEqual(result["/chosen"], {})
            self.assertNotIn("/usb-linked", result)

    def test_bundle_requires_report_and_exports_exact_regular_file_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            capture = root / "capture"
            capture.mkdir()
            archive = root / "return.tar.gz"
            with self.assertRaisesRegex(ValueError, "HANDOVER"):
                bundle(capture, archive)
            (capture / "HANDOVER.md").write_text("Observed facts and next steps.\n")
            (capture / "usb").mkdir()
            (capture / "usb/evidence.json").write_text('{"speed": "12"}\n')
            self.assertEqual(bundle(capture, archive), archive)
            with tarfile.open(archive) as package:
                self.assertEqual(package.extractfile("HANDOVER.md").read(), (capture / "HANDOVER.md").read_bytes())
                self.assertEqual(package.extractfile("usb/evidence.json").read(), (capture / "usb/evidence.json").read_bytes())
                self.assertTrue(all(not m.issym() and not m.islnk() for m in package.getmembers()))
            previous = archive.read_bytes()
            with self.assertRaisesRegex(ValueError, "new archive"):
                bundle(capture, archive)
            self.assertEqual(archive.read_bytes(), previous)

    def test_bundle_rejects_symlinks_and_archive_inside_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            capture = root / "capture"
            capture.mkdir()
            (capture / "HANDOVER.md").write_text("report")
            secret = root / "private"
            secret.write_text("must not archive")
            (capture / "linked").symlink_to(secret)
            with self.assertRaisesRegex(ValueError, "regular"):
                bundle(capture, root / "return.tar.gz")
            self.assertFalse((root / "return.tar.gz").exists())
            (capture / "linked").unlink()
            with self.assertRaisesRegex(ValueError, "outside"):
                bundle(capture, capture / "return.tar.gz")


if __name__ == "__main__":
    unittest.main()
