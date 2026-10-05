"""Exercise the actual macOS debugfs against a disposable corrupt ext4 image."""
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
TOOLS = PROJECT / "out/native-ext4-tools/e2fsprogs-1.47.4"
DEBUGFS = TOOLS / "debugfs/debugfs"
MKE2FS = TOOLS / "misc/mke2fs"


@unittest.skipUnless(DEBUGFS.is_file() and MKE2FS.is_file(),
                     "project-local native e2fsprogs fixture tools are not built")
class RealCorruptBitmapTests(unittest.TestCase):
    def test_catastrophic_readonly_extracts_logs_without_changing_corrupt_image(self):
        with tempfile.TemporaryDirectory(dir=PROJECT / "out/native-ext4-tools") as temporary:
            work = Path(temporary)
            image = work / "root.ext4"
            stage = work / "tree"
            relative = "var/log/journal/0123456789abcdef0123456789abcdef"
            (stage / relative).mkdir(parents=True)
            pacman = b"[2026-10-05] read-only capture fixture\n"
            journal = b"journal-extraction-fixture\0" * 4096
            (stage / "var/log/pacman.log").write_bytes(pacman)
            (stage / relative / "system.journal").write_bytes(journal)
            with image.open("wb") as stream:
                stream.truncate(64 * 1024**2)
            subprocess.run([str(MKE2FS), "-q", "-F", "-t", "ext4", "-b", "4096",
                            "-I", "256", "-O", "extents,64bit,metadata_csum",
                            "-d", str(stage), str(image)], check=True, capture_output=True)

            def run(*args):
                result = subprocess.run([str(DEBUGFS), *args, str(image)],
                                        capture_output=True, text=True, check=True)
                return result.stdout + result.stderr

            self.assertIn("Filesystem UUID:", run("-R", "stats"))
            # Corrupt one allocation bit, leaving the descriptor's stored
            # bitmap checksum intact. No real block device is opened here.
            with image.open("r+b") as stream:
                stream.seek(4096)
                descriptor = stream.read(64)
                bitmap = (struct.unpack_from("<I", descriptor, 0)[0]
                          | struct.unpack_from("<I", descriptor, 32)[0] << 32)
                stream.seek(bitmap * 4096)
                byte = stream.read(1)
                stream.seek(bitmap * 4096)
                stream.write(bytes([byte[0] ^ 1]))
            before = hashlib.sha256(image.read_bytes()).digest()
            failed = run("-R", "stats")
            self.assertIn("Block bitmap checksum does not match bitmap", failed)
            self.assertIn("Filesystem not open", failed)
            for command in ("stats", "stat <8>", "logdump -S",
                            "ls -p /var/log/journal", "ls -p /" + relative,
                            "stat /var/log/pacman.log"):
                self.assertNotIn("Filesystem not open", run("-c", "-R", command))
            run("-c", "-R", f"dump /var/log/pacman.log {work}/pacman.log")
            run("-c", "-R", f"dump /{relative}/system.journal {work}/system.journal")
            self.assertEqual((work / "pacman.log").read_bytes(), pacman)
            self.assertEqual((work / "system.journal").read_bytes(), journal)
            self.assertEqual(hashlib.sha256(image.read_bytes()).digest(), before)


if __name__ == "__main__":
    unittest.main()
