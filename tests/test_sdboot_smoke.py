import ast
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from sdboot.smoke_native import PROBE, check_log, extract_partition, qemu_boot


class NativeSmokeTests(unittest.TestCase):
    def log(self, attempt):
        markers = ("GROWTH_PASS", "IDENTITY_PASS", "MODULES_PASS", "PACMAN_PASS", "PACMAN_SYNC_PASS", "PASS")
        result = "\n".join(f"ARCHM4_NATIVE_{marker}:nonce:{attempt}" for marker in markers)
        if attempt == 1:
            result += "\nARCHM4: expanding native SD root to available card capacity"
        else:
            result += "\nARCHM4_NATIVE_CUSTOM_PACKAGE_UPDATE_PASS:nonce:2"
        return result + "\nARCHM4_GRUB_UEFI_BOOT\nreboot: Power down\n"

    def test_requires_all_evidence_and_idempotent_growth(self):
        check_log(self.log(1), "nonce", 1)
        check_log(self.log(2), "nonce", 2)
        for text, attempt in ((self.log(1).replace("PACMAN_PASS", "PACMAN_SKIP"), 1),
                              (self.log(1).replace("PACMAN_SYNC_PASS", "PACMAN_SYNC_SKIP"), 1),
                              (self.log(1) + "ARCHM4_NATIVE_FAIL:error", 1),
                              (self.log(2) + "ARCHM4 STOP:error", 2),
                              (self.log(2).replace("reboot: Power down", ""), 2),
                              (self.log(2) + "ARCHM4: expanding native SD root", 2),
                              (self.log(2) + "resize2fs 1.47.2", 2),
                              (self.log(2).replace("CUSTOM_PACKAGE_UPDATE_PASS", "SKIPPED"), 2),
                              ("error: module not found\n" + self.log(1), 1),
                              (self.log(1).replace("ARCHM4: expanding native SD root", ""), 1)):
            with self.subTest(text=text, attempt=attempt), self.assertRaises(ValueError):
                check_log(text, "nonce", attempt)

    def test_partition_extraction_is_bounded_and_preserves_zeros(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            image, output = directory / "image", directory / "partition"
            image.write_bytes(b"a" * 512 + bytes(512) + b"c" * 512 + b"d" * 512)
            extract_partition(image, {"first_lba": 1, "last_lba": 2}, output)
            self.assertEqual(output.read_bytes(), bytes(512) + b"c" * 512)
            with self.assertRaisesRegex(ValueError, "Truncated"):
                extract_partition(image, {"first_lba": 1, "last_lba": 4}, output)

    def test_probe_compiles_and_contains_binary_signatures(self):
        tree = ast.parse(PROBE)
        compile(tree, "<native-probe>", "exec")
        values = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)]
        self.assertIn(b"\x53\xef", values)
        self.assertIn(b"\x89PNG\r\n\x1a\n", values)

    def test_initramfs_stop_terminates_only_the_spawned_vm(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            process = Mock()
            process.poll.return_value = None

            def start(command, stdout, stderr):
                self.assertIn("-bios", command)
                self.assertNotIn("-kernel", command)
                self.assertNotIn("-initrd", command)
                stdout.write(b"ARCHM4 STOP: failed explicit initramfs check\n")
                stdout.flush()
                return process

            with patch("sdboot.smoke_native.subprocess.Popen", side_effect=start), \
                    patch("sdboot.smoke_native.Path.is_file", return_value=True):
                with self.assertRaisesRegex(ValueError, "initramfs stopped"):
                    qemu_boot(work / "image", work / "boot.log")
            process.terminate.assert_called_once_with()
            process.wait.assert_called_once_with(timeout=5)
            process.kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
