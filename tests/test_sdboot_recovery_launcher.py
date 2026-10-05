"""Launcher state-machine tests: temporary files only, never Apple tools."""
import copy
import json
from pathlib import Path
import plistlib
import stat
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sdboot import recovery_launcher as launcher


class LauncherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.system, self.out = self.base / "system", self.base / "out"
        self.system.mkdir()
        self.out.mkdir()
        self.identity = {"storage_mode": "internal-stub", **{
            key: f"00000000-0000-4000-8000-{i:012X}" for i, key in enumerate(
                ("vgid", "store_uuid", "platform_uuid", "source_macos_vgid", "source_macos_store_uuid"), 1)},
            "roles": {role: {"uuid": f"00000000-0000-4000-8000-{i:012X}"}
                      for i, role in enumerate(("System", "Data", "Preboot", "Recovery"), 10)}}
        self.write("version", plistlib.dumps({"ProductVersion": "27.0.1", "ProductBuildVersion": "26A434"}))
        self.write("disabled_installer", plistlib.dumps({"AppName": launcher.card.APP,
                    "ProductVersion": "26.5.2", "ProductBuildVersion": "25F84"}))
        self.write("app_info", b"old application metadata")
        self.write("app_launcher", b"#!/bin/sh\necho old\n", 0o755)
        (self.system / launcher.card.RESOURCES).mkdir(parents=True)
        self.initial = self.snapshot()

    def path(self, key):
        return self.system / launcher.PATHS[key]

    def write(self, key, data, mode=0o644):
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)

    def snapshot(self):
        return {key: ((self.path(key).read_bytes(), stat.S_IMODE(self.path(key).stat().st_mode))
                      if self.path(key).exists() else None) for key in launcher.PATHS}

    def prepare(self):
        planned = launcher.plan(self.system, self.out, self.identity)
        return launcher.ensure(self.system, self.out, self.identity, planned)

    def inspect(self):
        return launcher.inspect(self.system, self.out, self.identity)

    def select_startup(self, record, callback=None):
        return launcher.select_startup(self.system, self.out, self.identity, record, callback or Mock())

    def simulate_legacy_armed(self, record):
        """Construct the retired metadata layout directly, without firmware claims."""
        launcher.complete(self.system, self.out, self.identity, record)
        for key in ("version", "app_info", "app_launcher", "disabled_installer"):
            spec = launcher._managed_for(record, key)
            self.write(key, bytes.fromhex(spec["hex"]), spec["mode"])
        self.path("version").rename(self.path("hidden_version"))
        self.path("disabled_installer").rename(self.path("installer"))

    def test_read_only_plan_uses_actual_system_version_and_hashes(self):
        plan = launcher.plan(self.system, self.out, self.identity)
        self.assertEqual(self.initial, self.snapshot())
        self.assertFalse(list(self.out.iterdir()))
        self.assertFalse(list((self.system / launcher.card.RESOURCES).iterdir()))
        marker = plistlib.loads(bytes.fromhex(plan["managed"]["installer"]["hex"]))
        self.assertEqual(marker, {"AppName": launcher.card.APP,
            "ProductVersion": "27.0.1", "ProductBuildVersion": "26A434"})
        for binding, key in launcher.BINDINGS.items():
            self.assertEqual(plan[binding], plan["managed"][key]["sha256"])
        self.assertEqual(plan, json.loads(json.dumps(plan)))

    def test_ensure_preserves_originals_absences_and_is_idempotent(self):
        record = self.prepare()
        self.assertEqual(self.initial, self.snapshot())
        backup = self.system / launcher.card.RESOURCES / record["backup"]
        for key, original in self.initial.items():
            if original is None:
                self.assertFalse((backup / key).exists())
            else:
                self.assertEqual(original[0], (backup / key).read_bytes())
                self.assertEqual(original[1], stat.S_IMODE((backup / key).stat().st_mode))
        self.assertEqual(self.prepare(), record)
        self.assertEqual(len(list((self.system / launcher.card.RESOURCES).iterdir())), 1)

    def test_selection_sees_normal_metadata_and_rechecks_every_pending_retry(self):
        record = self.prepare()
        def select():
            self.assertTrue(self.path("version").is_file())
            self.assertFalse(self.path("hidden_version").exists())
            self.assertFalse(self.path("installer").exists())
            self.assertEqual(plistlib.loads(self.path("disabled_installer").read_bytes())["ProductBuildVersion"], "26A434")
        callback = Mock(side_effect=select)
        self.select_startup(record, callback)
        self.assertTrue(self.inspect()["ready"])
        self.assertEqual(self.inspect()["layout"], "normal")
        self.assertFalse(self.path("installer").exists())
        self.assertFalse(self.path("hidden_version").exists())
        self.select_startup(record, callback)
        self.assertEqual(callback.call_count, 2)

    def test_selection_failure_leaves_normal_metadata(self):
        record = self.prepare()
        with self.assertRaisesRegex(RuntimeError, "authentication"):
            self.select_startup(record, Mock(side_effect=RuntimeError("authentication failed")))
        self.assertEqual(self.inspect()["layout"], "normal")
        self.assertTrue(self.path("version").exists())
        self.assertFalse(self.path("installer").exists())
        self.select_startup(record)
        self.assertTrue(self.inspect()["ready"])
        # A failed retry must also normalize a legacy armed update.
        self.simulate_legacy_armed(record)
        with self.assertRaisesRegex(RuntimeError, "authentication"):
            self.select_startup(record, Mock(side_effect=RuntimeError("authentication failed")))
        self.assertEqual(self.inspect()["layout"], "normal")

    def test_selection_recovers_each_legacy_layout_without_rearming(self):
        record = self.prepare()
        saved_intent = (self.out / launcher.STATE).read_bytes()
        for completed in (None, "version", "marker"):
            with self.subTest(completed=completed):
                self.simulate_legacy_armed(record)
                if completed == "version":
                    self.path("hidden_version").rename(self.path("version"))
                elif completed == "marker":
                    self.path("installer").rename(self.path("disabled_installer"))
                callback = Mock(side_effect=lambda: self.assertEqual(self.inspect()["layout"], "normal"))
                self.select_startup(record, callback)
                callback.assert_called_once()
                self.assertTrue(self.inspect()["ready"])
                self.assertEqual(self.inspect()["layout"], "normal")
                self.assertEqual(saved_intent, (self.out / launcher.STATE).read_bytes())

    def test_interrupted_recovery_cleanup_in_either_order_completes_without_bless(self):
        record = self.prepare()
        for first in ("version", "marker"):
            with self.subTest(first=first):
                self.simulate_legacy_armed(record)
                if first == "version":
                    self.path("hidden_version").rename(self.path("version"))
                else:
                    self.path("installer").rename(self.path("disabled_installer"))
                self.assertEqual(self.inspect()["layout"], "intermediate")
                launcher.complete(self.system, self.out, self.identity, record)
                self.assertEqual(self.inspect()["layout"], "normal")
                launcher.complete(self.system, self.out, self.identity, record)
                self.assertEqual(self.inspect()["layout"], "normal")

    def test_finished_recovery_allows_next_update_with_same_rollback(self):
        record = self.prepare()
        self.select_startup(record)
        launcher.complete(self.system, self.out, self.identity, record)
        self.assertEqual(self.prepare(), record)
        callback = Mock()
        self.select_startup(record, callback)
        callback.assert_called_once()
        self.assertTrue(self.inspect()["ready"])

    def test_atomic_app_install_interruptions_resume(self):
        record = self.prepare()
        atomic = launcher._atomic
        for interruption in (1, 2, 3):
            with self.subTest(publish=interruption):
                launcher.complete(self.system, self.out, self.identity, record)
                for key in ("app_info", "app_launcher", "disabled_installer"):
                    self.write(key, *self.initial[key])
                count = 0
                def interrupted(path, data, mode=0o600):
                    nonlocal count
                    atomic(path, data, mode)
                    count += 1
                    if count == interruption:
                        raise OSError("interrupted file publish")
                callback = Mock()
                with patch.object(launcher, "_atomic", side_effect=interrupted), self.assertRaises(OSError):
                    self.select_startup(record, callback)
                callback.assert_not_called()
                self.select_startup(record, callback)
                self.assertTrue(self.inspect()["ready"])

    def test_completion_interruptions_after_either_rename_resume(self):
        record = self.prepare()
        original = launcher._rename
        for interruption in (1, 2):
            with self.subTest(rename=interruption):
                self.simulate_legacy_armed(record)
                calls = 0
                def interrupted(source, destination):
                    nonlocal calls
                    original(source, destination)
                    calls += 1
                    if calls == interruption:
                        raise OSError("simulated power loss")
                with patch.object(launcher, "_rename", side_effect=interrupted), self.assertRaises(OSError):
                    launcher.complete(self.system, self.out, self.identity, record)
                launcher.complete(self.system, self.out, self.identity, record)
                self.assertEqual(self.inspect()["layout"], "normal")

    def test_original_absent_launcher_files_are_recorded_then_created(self):
        for key in ("app_info", "app_launcher", "disabled_installer"):
            self.path(key).unlink()
        record = self.prepare()
        for key in ("app_info", "app_launcher", "disabled_installer"):
            self.assertIsNone(record["originals"][key])
        self.select_startup(record)
        self.assertTrue(self.inspect()["ready"])
        launcher.complete(self.system, self.out, self.identity, record)
        self.assertEqual(self.prepare(), record)

    def test_interrupted_backup_has_no_active_effect_and_can_retry(self):
        original = launcher._atomic
        def interrupted(path, data, mode=0o600):
            original(path, data, mode)
            raise OSError("backup interrupted")
        with patch.object(launcher, "_atomic", side_effect=interrupted), self.assertRaises(OSError):
            self.prepare()
        self.assertEqual(self.snapshot(), self.initial)
        self.assertFalse((self.out / launcher.STATE).exists())
        record = self.prepare()
        self.assertEqual(self.inspect()["record"], record)

    def test_backup_tampering_is_rejected_on_every_operation(self):
        record = self.prepare()
        backup = self.system / launcher.card.RESOURCES / record["backup"]
        (backup / "version").write_bytes(b"changed")
        for operation in (self.inspect, lambda: self.prepare(), lambda: self.select_startup(record),
                          lambda: launcher.complete(self.system, self.out, self.identity, record)):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, "rollback changed"):
                operation()

    def test_unknown_changes_and_missing_existing_apps_are_rejected(self):
        record = self.prepare()
        original = self.path("app_launcher").read_bytes()
        self.write("app_launcher", b"unknown", 0o755)
        with self.assertRaisesRegex(ValueError, "Unknown modification"):
            self.select_startup(record)
        self.write("app_launcher", original, 0o755)
        self.path("app_info").unlink()
        with self.assertRaisesRegex(ValueError, "Missing Recovery launcher"):
            self.inspect()

    def test_symlink_in_metadata_or_backup_is_rejected(self):
        record = self.prepare()
        original = self.path("app_info").read_bytes()
        self.path("app_info").unlink()
        self.path("app_info").symlink_to(self.path("version"))
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.inspect()
        self.path("app_info").unlink()
        self.write("app_info", original)
        backup = self.system / launcher.card.RESOURCES / record["backup"]
        (backup / "version").unlink()
        (backup / "version").symlink_to(self.path("version"))
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.inspect()

    def test_foreign_identity_changed_plan_and_duplicate_pairs_are_rejected(self):
        planned = launcher.plan(self.system, self.out, self.identity)
        altered = copy.deepcopy(planned)
        altered["app_info_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "plan changed"):
            launcher.ensure(self.system, self.out, self.identity, altered)
        record = self.prepare()
        foreign = copy.deepcopy(self.identity)
        foreign["platform_uuid"] = "FFFFFFFF-0000-4000-8000-000000000000"
        with self.assertRaisesRegex(ValueError, "foreign"):
            launcher.inspect(self.system, self.out, foreign)
        self.write("hidden_version", self.path("version").read_bytes())
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.select_startup(record)

    def test_callback_metadata_change_fails_final_verification(self):
        record = self.prepare()
        with self.assertRaisesRegex(ValueError, "Unknown modification"):
            self.select_startup(record, lambda: self.write("version", b"modified during password prompt"))
        self.assertFalse(self.path("installer").exists())


if __name__ == "__main__":
    unittest.main()
