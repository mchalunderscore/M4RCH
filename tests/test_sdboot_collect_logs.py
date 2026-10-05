import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import uuid

SOURCE = Path(__file__).resolve().parents[1] / "sdboot/collect_sd_logs.py"
SPEC = importlib.util.spec_from_file_location("collect_sd_logs", SOURCE)
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class CollectorTests(unittest.TestCase):
    def fixture(self):
        whole = {"DeviceIdentifier": "disk7", "DeviceNode": "/dev/disk7",
                 "WholeDisk": True, "Internal": True, "Removable": True,
                 "VirtualOrPhysical": "Physical", "BusProtocol": "Secure Digital"}
        part = {"DeviceIdentifier": "disk7s2", "DeviceNode": "/dev/disk7s2",
                "ParentWholeDisk": "disk7", "WholeDisk": False,
                "Content": "Linux Filesystem", "DiskUUID": collector.ROOT_PARTITION_UUID,
                "MountPoint": ""}
        return whole, part

    def test_builtin_sd_internal_true_is_allowed(self):
        whole, part = self.fixture()
        result = collector.validate_disk("/dev/disk7", lambda n: whole if n == "disk7" else part)
        self.assertEqual(result[0], "/dev/disk7s2")

    def test_wrong_device_identity_and_mounted_root_are_rejected(self):
        changes = ((0, "BusProtocol", "PCI-Express"), (0, "Removable", False),
                   (0, "VirtualOrPhysical", "Virtual"), (0, "DeviceIdentifier", "disk0"),
                   (1, "ParentWholeDisk", "disk0"), (1, "DiskUUID", str(uuid.uuid4())),
                   (1, "Mounted", True), (1, "MountPoint", "/Volumes/root"))
        for index, key, value in changes:
            with self.subTest(key=key):
                info = self.fixture()
                info[index][key] = value
                with self.assertRaises(ValueError):
                    collector.validate_disk("/dev/disk7", lambda n: info[0 if n == "disk7" else 1])

    def test_slice_raw_and_shell_inputs_are_rejected_before_inspection(self):
        for value in ("/dev/rdisk7", "/dev/disk7s2", "disk7", "/dev/disk7;id"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                collector.validate_disk(value, lambda n: self.fail("inspected invalid disk"))

    def test_superblock_requires_magic_uuid_label_and_size(self):
        raw = bytearray(4096)
        raw[1080:1082] = b"\x53\xef"
        raw[1128:1144] = uuid.UUID(collector.ROOT_UUID).bytes
        raw[1144:1152] = b"ARCHROOT"
        collector.validate_superblock(raw)
        for offset in (1080, 1128, 1144):
            changed = raw[:]
            changed[offset] ^= 1
            with self.assertRaises(ValueError):
                collector.validate_superblock(changed)
        with self.assertRaises(ValueError):
            collector.validate_superblock(raw[:2048])

    def test_directory_parser_never_accepts_malformed_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            capture = collector.Capture("image", Path(temporary))
            with patch.object(capture, "command", return_value="/1/100600/0/0/../../etc/passwd/123/\n"):
                with self.assertRaises(ValueError):
                    capture.listing("/var/log/journal")
        self.assertFalse(collector.JOURNAL.fullmatch("../../danger.journal"))
        self.assertFalse(collector.JOURNAL.fullmatch('system".journal'))
        self.assertTrue(collector.JOURNAL.fullmatch("system@abc-123.journal~"))

    def test_only_fixed_readonly_debugfs_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            capture = collector.Capture("image", Path(temporary))
            with patch.object(collector.subprocess, "run") as run:
                run.return_value.returncode = 0
                capture.command("stats")
            self.assertEqual(run.call_args.args[0], [str(collector.DEBUGFS), "-c", "-R", "stats", "image"])
            self.assertNotIn("shell", run.call_args.kwargs)

    def test_zero_exit_does_not_hide_filesystem_open_or_checksum_failures(self):
        messages = [
            "/dev/disk7s2: Block bitmap checksum does not match bitmap while reading allocation bitmaps\nls: Filesystem not open\n",
            "Checksum errors in superblock! Retrying...\n",
            "stat: Inode checksum does not match inode while reading inode\n",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            capture = collector.Capture("image", Path(temporary))
            for message in messages:
                def failed(command, **kwargs):
                    kwargs["stderr"].write(("debugfs 1.47.4 (6-Mar-2025)\n" + message).encode())
                    return collector.subprocess.CompletedProcess(command, 0)
                with self.subTest(message=message), \
                        patch.object(collector.subprocess, "run", side_effect=failed):
                    with self.assertRaisesRegex(ValueError, "Read-only debugfs failed"):
                        capture.listing("/var/log/journal")

    def test_only_missing_optional_files_are_tolerated(self):
        def missing(command, **kwargs):
            kwargs["stderr"].write(b"debugfs 1.47.4 (6-Mar-2025)\n/var/log/journal: File not found by ext2_lookup\n")
            return collector.subprocess.CompletedProcess(command, 0)
        with tempfile.TemporaryDirectory() as temporary:
            capture = collector.Capture("image", Path(temporary))
            with patch.object(collector.subprocess, "run", side_effect=missing):
                self.assertEqual(capture.listing("/var/log/journal"), [])
                with self.assertRaisesRegex(ValueError, "Read-only debugfs failed"):
                    capture.command("stats")

    def test_superblock_checksum_fallback_on_stdout_is_rejected(self):
        def fallback(command, **kwargs):
            kwargs["stdout"].write(b"Checksum errors in superblock! Retrying...\nFilesystem volume name: ARCHROOT\n")
            kwargs["stderr"].write(b"debugfs 1.47.4 (6-Mar-2025)\n")
            return collector.subprocess.CompletedProcess(command, 0)
        with tempfile.TemporaryDirectory() as temporary:
            capture = collector.Capture("image", Path(temporary))
            with patch.object(collector.subprocess, "run", side_effect=fallback):
                with self.assertRaisesRegex(ValueError, "disable checks"):
                    capture.command("stats")

    def test_symlinks_and_oversize_files_are_not_dumped(self):
        with tempfile.TemporaryDirectory() as temporary:
            capture = collector.Capture("image", Path(temporary))
            for details in ("Type: symlink Size: 1", f"Type: regular Size: {collector.MAX_FILE + 1}"):
                with patch.object(capture, "command", return_value=details) as command:
                    capture.dump("/var/log/pacman.log", Path(temporary) / "pacman.log")
                self.assertEqual(command.call_count, 1)

    def test_exhausted_capture_budget_does_not_spawn_another_process(self):
        for exhausted in ("commands", "deadline"):
            with self.subTest(exhausted=exhausted), tempfile.TemporaryDirectory() as temporary:
                capture = collector.Capture("image", Path(temporary))
                if exhausted == "commands":
                    capture.commands = collector.MAX_COMMANDS
                else:
                    capture.deadline = 0
                with patch.object(collector.subprocess, "run") as run:
                    with self.assertRaisesRegex(ValueError, "limit reached"):
                        capture.command("stats")
                run.assert_not_called()

    def test_skipped_journals_still_count_towards_traversal_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            capture = collector.Capture("image", Path(temporary))
            machine = "a" * 32
            listings = [[(machine, stat.S_IFDIR)],
                        [(f"system@{number}.journal", stat.S_IFREG)
                         for number in range(collector.MAX_FILES + 10)]]
            with patch.object(capture, "command", return_value=""), \
                    patch.object(capture, "listing", side_effect=listings), \
                    patch.object(capture, "dump") as dump:
                capture.collect()
            journal_attempts = [call for call in dump.call_args_list
                                if call.args[0].startswith("/var/log/journal/")]
            self.assertEqual(len(journal_attempts), collector.MAX_FILES)
            self.assertIn("journal candidate limit", (Path(temporary) / "debugfs.txt").read_text())

    def test_capture_path_cannot_escape_debugfs_argument_quoting(self):
        for character in ('"', "\\", "\n", "\r"):
            with self.subTest(character=character), self.assertRaisesRegex(ValueError, "quoting"):
                collector.Capture("image", Path("/tmp/capture" + character + "suffix"))

    def test_safe_directory_rejects_symlink_component(self):
        with tempfile.TemporaryDirectory() as temporary:
            real = Path(temporary) / "real"
            real.mkdir()
            link = Path(temporary) / "link"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(ValueError):
                collector.safe_directory(link)


if __name__ == "__main__":
    unittest.main()
