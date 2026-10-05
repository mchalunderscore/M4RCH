"""Exercise public enrollment preparation on fake APFS volumes only."""
import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import plistlib
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sdboot import enrollment, recovery_launcher
import test_sdboot_enrollment as staging_fixture


class AutomaticPreparationTests(unittest.TestCase):
    def setUp(self):
        fixture = staging_fixture.EnrollmentTests(methodName="runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.project, self.out = fixture.project, fixture.out
        self.system, self.resources = fixture.fixture.system, fixture.resources
        self.identity = enrollment._identity(fixture.fixture.identity)
        self.core = self.system / "System/Library/CoreServices"
        (self.core / "SystemVersion.plist").write_bytes(plistlib.dumps({
            "ProductName": "macOS", "ProductVersion": "26.5.2", "ProductBuildVersion": "25F84"}))
        (self.system / ".IAPhysicalMedia").unlink()
        for relative, data in enrollment.card.launcher_files().items():
            path = self.system / relative
            if relative == Path(".IAPhysicalMedia"):
                path = self.system / "IAPhysicalMedia-disabled.plist"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o755 if path.suffix == ".sh" else 0o644)
        self.write_nvme(b"ANS-aware loader generation")
        self.run = fixture.fixture.stack.enter_context(patch.object(enrollment, "run"))
        self.bootable = fixture.fixture.stack.enter_context(patch.object(enrollment.card, "set_bootable"))
        self.answer = fixture.fixture.stack.enter_context(patch.object(enrollment, "_answer", side_effect=[True, False]))

    def write_nvme(self, data):
        directory = self.out / "nvme-loader"
        directory.mkdir(exist_ok=True)
        (directory / "loader.bin").write_bytes(data)
        (directory / "loader-manifest.json").write_text(json.dumps({
            "schema": 1, "kind": "j614s-sd-loader", "boot_protocol": "uefi-arm64",
            "inputs": {"nvme_handoff": {"marker": "v2"}}, "files": {
                "loader.bin": {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}}}))

    def prepare(self, **kwargs):
        return enrollment.prepare(self.project, self.out, **kwargs)

    def complete_recovery(self, record):
        (self.resources / "enrolled.txt").write_text(
            self.identity["vgid"] + "\n" + record["target"]["sha256"] + "\n")
        current = recovery_launcher.inspect(self.system, self.out, self.identity)
        recovery_launcher.complete(self.system, self.out, self.identity, current["record"])

    def simulate_legacy_armed(self):
        """Represent a previous run of the retired installer-marker workflow."""
        (self.core / "SystemVersion.plist").rename(self.core / "SystemVersion-disabled.plist")
        (self.system / "IAPhysicalMedia-disabled.plist").rename(self.system / ".IAPhysicalMedia")

    def test_default_flow_selects_target_leaves_normal_metadata_and_does_not_enroll_or_shutdown(self):
        def selected(args):
            self.assertEqual(args, ["/usr/sbin/bless", "--setBoot", "--mount", self.system])
            self.assertTrue((self.core / "SystemVersion.plist").is_file())
            self.assertFalse((self.system / ".IAPhysicalMedia").exists())
        self.run.side_effect = selected
        record = self.prepare()
        self.assertEqual((self.resources / "boot.bin").read_bytes(),
                         (self.out / "nvme-loader/loader.bin").read_bytes())
        self.assertEqual((self.resources / "enrolled.txt").read_bytes(), self.fixture.start_receipt)
        self.assertEqual(recovery_launcher.inspect(self.system, self.out, self.identity)["layout"], "normal")
        self.assertTrue((self.core / "SystemVersion.plist").is_file())
        self.assertFalse((self.core / "SystemVersion-disabled.plist").exists())
        self.assertFalse((self.system / ".IAPhysicalMedia").exists())
        self.assertIn("AUTO_LAUNCH='1'", (self.resources / "enroll.sh").read_text())
        enrollment._check_backups(self.resources, record)
        self.run.assert_called_once()
        self.bootable.assert_called_once_with(self.system)
        self.fixture.confirm.assert_not_called()
        self.assertEqual(self.answer.call_count, 2)

    def test_cancellation_precedes_loader_and_metadata_writes(self):
        paths = [self.resources / name for name in enrollment.OLD_FILES]
        snapshot = {path: path.read_bytes() for path in paths}
        self.answer.side_effect = [False]
        with self.assertRaisesRegex(ValueError, "Cancelled"):
            self.prepare()
        self.assertEqual(snapshot, {path: path.read_bytes() for path in snapshot})
        self.assertFalse((self.out / enrollment.STATE).exists())
        self.assertFalse(list(self.resources.glob("recovery-launcher-backup-*")))
        self.run.assert_not_called()
        self.bootable.assert_not_called()

    def test_instructions_use_options_and_explicit_recovery_terminal_command(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.prepare()
        text = output.getvalue()
        self.assertIn("Hold the power button continuously", text)
        self.assertIn("Choose Options, then Continue", text)
        self.assertIn("Open Utilities > Terminal", text)
        self.assertIn(f'sh "{self.resources / "enroll.sh"}" --update', text)
        self.assertNotIn("should open automatically", text)
        self.assertNotIn("Choose Arch M4 Boot", text)

    def test_pending_legacy_layouts_restore_normal_metadata_and_preserve_backups(self):
        record = self.prepare()
        saved_loader_state = (self.out / enrollment.STATE).read_bytes()
        saved_metadata_state = (self.out / recovery_launcher.STATE).read_bytes()
        backup_names = sorted(path.name for path in self.resources.glob("*backup-*"))
        for completed in (None, "version", "marker"):
            with self.subTest(completed=completed):
                self.simulate_legacy_armed()
                if completed == "version":
                    (self.core / "SystemVersion-disabled.plist").rename(self.core / "SystemVersion.plist")
                elif completed == "marker":
                    (self.system / ".IAPhysicalMedia").rename(self.system / "IAPhysicalMedia-disabled.plist")
                def selected(args):
                    self.assertEqual(recovery_launcher.inspect(self.system, self.out, self.identity)["layout"], "normal")
                self.run.reset_mock()
                self.run.side_effect = selected
                self.answer.side_effect = [True, False]
                self.assertEqual(self.prepare(), record)
                self.run.assert_called_once()
                self.assertEqual(recovery_launcher.inspect(self.system, self.out, self.identity)["layout"], "normal")
                self.assertEqual((self.out / enrollment.STATE).read_bytes(), saved_loader_state)
                self.assertEqual((self.out / recovery_launcher.STATE).read_bytes(), saved_metadata_state)
                self.assertEqual(sorted(path.name for path in self.resources.glob("*backup-*")), backup_names)
                self.assertEqual((self.resources / "enrolled.txt").read_bytes(), self.fixture.start_receipt)
                enrollment._check_backups(self.resources, record)

    def test_missing_nvme_artifact_fails_before_disk_resolution(self):
        (self.out / "nvme-loader/loader.bin").unlink()
        with patch.object(enrollment, "_resolve") as resolve, self.assertRaises(ValueError):
            self.prepare()
        resolve.assert_not_called()
        self.answer.assert_not_called()
        self.run.assert_not_called()

    def test_bless_failure_retains_normal_metadata_and_retryable_staged_loader(self):
        self.run.side_effect = subprocess.CalledProcessError(200, "bless")
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare()
        self.assertTrue((self.core / "SystemVersion.plist").is_file())
        self.assertFalse((self.system / ".IAPhysicalMedia").exists())
        self.assertEqual((self.resources / "enrolled.txt").read_bytes(), self.fixture.start_receipt)
        self.run.side_effect = None
        self.answer.side_effect = [True, False]
        record = self.prepare()
        self.assertEqual(recovery_launcher.inspect(self.system, self.out, self.identity)["layout"], "normal")
        enrollment._check_backups(self.resources, record)

    def test_enrolled_retry_does_not_rearm_change_startup_or_prompt(self):
        record = self.prepare()
        self.complete_recovery(record)
        self.run.reset_mock()
        self.bootable.reset_mock()
        self.answer.reset_mock(side_effect=True)
        self.answer.side_effect = AssertionError("already enrolled must not prompt")
        before = (self.out / enrollment.STATE).read_bytes()
        self.assertEqual(self.prepare(), record)
        self.assertEqual((self.out / enrollment.STATE).read_bytes(), before)
        self.assertEqual(recovery_launcher.inspect(self.system, self.out, self.identity)["layout"], "normal")
        self.run.assert_not_called()
        self.bootable.assert_not_called()

    def test_enrolled_manual_generation_needs_no_launcher_migration(self):
        record = enrollment.stage(self.project, self.out, nvme=True)
        (self.resources / "enrolled.txt").write_text(
            self.identity["vgid"] + "\n" + record["target"]["sha256"] + "\n")
        before = {path: path.read_bytes() for path in
                  (self.out / enrollment.STATE, self.resources / "enroll.sh")}
        directories = list(self.resources.glob("*backup-*"))
        self.answer.side_effect = AssertionError("enrolled manual loader must not prompt")
        self.assertEqual(self.prepare(), record)
        self.assertEqual(before, {path: path.read_bytes() for path in before})
        self.assertEqual(list(self.resources.glob("*backup-*")), directories)
        self.assertFalse((self.out / recovery_launcher.STATE).exists())
        self.run.assert_not_called()
        self.bootable.assert_not_called()

    def test_receipt_written_before_recovery_interruption_finishes_cleanup_without_bless(self):
        record = self.prepare()
        self.simulate_legacy_armed()
        (self.resources / "enrolled.txt").write_text(
            self.identity["vgid"] + "\n" + record["target"]["sha256"] + "\n")
        self.run.reset_mock()
        self.answer.side_effect = [True]
        self.prepare()
        self.run.assert_not_called()
        self.assertEqual(recovery_launcher.inspect(self.system, self.out, self.identity)["layout"], "normal")

    def test_shutdown_requires_separate_affirmative_answer(self):
        self.answer.side_effect = [True, True]
        self.prepare()
        self.assertEqual(self.run.call_args_list[-1].args[0], ["/sbin/shutdown", "-h", "now"])

    def test_loader_change_during_apple_prompt_fails_with_normal_metadata(self):
        def change_loader(args):
            (self.resources / "boot.bin").write_bytes(b"unexpected replacement during authentication")
        self.run.side_effect = change_loader
        with self.assertRaisesRegex(ValueError, "target changed"):
            self.prepare()
        self.assertTrue((self.core / "SystemVersion.plist").is_file())
        self.assertFalse((self.system / ".IAPhysicalMedia").exists())

    def test_status_distinguishes_enrollment_from_pending_metadata_cleanup(self):
        record = self.prepare()
        self.simulate_legacy_armed()
        (self.resources / "enrolled.txt").write_text(
            self.identity["vgid"] + "\n" + record["target"]["sha256"] + "\n")
        status = enrollment.status(self.project, self.out)
        self.assertEqual(status["phase"], "enrolled-cleanup-pending")
        self.assertEqual(status["recovery_launcher"], "armed")
        self.complete_recovery(record)
        self.assertEqual(enrollment.status(self.project, self.out)["phase"], "enrolled")

    def test_cleanup_rejects_mountpoint_changed_during_remount(self):
        record = self.prepare()
        self.simulate_legacy_armed()
        (self.resources / "enrolled.txt").write_text(
            self.identity["vgid"] + "\n" + record["target"]["sha256"] + "\n")
        self.fixture.writable.return_value = self.system.parent / "different-volume"
        self.answer.side_effect = [True]
        self.run.reset_mock()
        with self.assertRaisesRegex(ValueError, "identity changed"):
            self.prepare()
        self.assertEqual(recovery_launcher.inspect(self.system, self.out, self.identity)["layout"], "armed")
        self.run.assert_not_called()

    def test_pending_manual_script_migrates_without_losing_enrolled_ancestor(self):
        manual = enrollment.stage(self.project, self.out, nvme=True)
        current = self.prepare()
        self.assertNotEqual(current["backup"], manual["backup"])
        self.assertEqual(current["previous_receipt_sha256"], self.fixture.fixture.boot_info["sha256"])
        enrollment._check_backups(self.resources, current)
        self.assertEqual((self.resources / manual["backup"] / "boot.bin").read_bytes(), self.fixture.fixture.boot)

    def test_cancel_unpublished_pending_loader_with_explicit_safe_generation(self):
        original = enrollment._atomic
        def interrupted(path, data, mode=0o600):
            if path == self.resources / "boot.bin":
                raise OSError("power lost before publishing pending NVMe loader")
            return original(path, data, mode)
        with patch.object(enrollment, "_atomic", side_effect=interrupted), self.assertRaises(OSError):
            self.prepare()
        pending = json.loads((self.out / enrollment.STATE).read_text())
        self.fixture.write_loader(self.fixture.fixture.boot)
        self.answer.side_effect = [True]
        self.run.reset_mock()
        current = self.prepare(nvme=False, replace_pending=True)
        self.assertEqual(current["target"], self.fixture.fixture.boot_info)
        self.assertNotEqual(current["backup"], pending["backup"])
        self.assertEqual(json.loads((self.out / enrollment.STATE).read_text()), current)
        self.assertEqual((self.resources / "enrolled.txt").read_bytes(), self.fixture.start_receipt)
        enrollment._check_backups(self.resources, current)
        self.run.assert_not_called()
        self.assertFalse((self.out / recovery_launcher.STATE).exists())

    def test_safe_variant_is_explicit_and_keeps_same_enrollment_history(self):
        record = self.prepare(nvme=False)
        self.assertEqual((self.resources / "boot.bin").read_bytes(), (self.out / "loader.bin").read_bytes())
        self.assertEqual(record["identity"], self.identity)

    def test_pending_replacement_requires_override_and_keeps_original_backup(self):
        first = self.prepare()
        self.write_nvme(b"second ANS-aware loader")
        self.answer.reset_mock()
        with self.assertRaisesRegex(ValueError, "pending loader"):
            self.prepare()
        self.answer.assert_not_called()
        self.answer.side_effect = [True, False]
        second = self.prepare(replace_pending=True)
        self.assertNotEqual(first["backup"], second["backup"])
        enrollment._check_backups(self.resources, second)
        self.assertEqual((self.resources / first["backup"] / "boot.bin").read_bytes(), self.fixture.fixture.boot)


if __name__ == "__main__":
    unittest.main()
