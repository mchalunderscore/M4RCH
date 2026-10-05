"""Internal loader staging with fake disk inventory and temporary files only."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sdboot import enrollment
import test_internal_boot as internal_fixture


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        # Reuse the existing comprehensive mock internal APFS inventory.
        self.fixture = internal_fixture.InternalBootTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        fixture = self.fixture
        fixture.write_state()
        self.project = fixture.project
        self.out = self.project / "out/sdboot"
        self.out.mkdir()
        (self.project / "sdboot").mkdir()
        (self.project / "sdboot/recovery-enroll.sh").write_bytes(
            (ROOT / "sdboot/recovery-enroll.sh").read_bytes())
        self.resources = fixture.resources
        (self.resources / "enroll.sh").write_text("#!/bin/sh\necho previous\n")
        (self.resources / "enrolled.txt").write_text(
            fixture.identity["vgid"] + "\n" + fixture.boot_info["sha256"] + "\n")
        self.write_loader(b"fixed m1n1 and U-Boot loader")
        self.start_state = (self.project / "out/internal-boot-state.json").read_bytes()
        self.start_metadata = (self.resources / "card.json").read_bytes()
        self.start_receipt = (self.resources / "enrolled.txt").read_bytes()
        self.confirm = fixture.stack.enter_context(patch.object(enrollment.card, "confirm"))
        fixture.stack.enter_context(patch.object(enrollment, "DiskUtil", return_value=fixture.dutil))
        self.mount = fixture.stack.enter_context(patch.object(enrollment.card, "mounted", return_value=fixture.system))
        self.writable = fixture.stack.enter_context(patch.object(enrollment.card, "mounted_writable", return_value=fixture.system))

    def write_loader(self, data):
        (self.out / "loader.bin").write_bytes(data)
        (self.out / "loader-manifest.json").write_text(json.dumps({
            "schema": 1, "kind": "j614s-sd-loader", "boot_protocol": "uefi-arm64", "files": {
                "loader.bin": {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}}}))

    def test_stages_only_loader_and_script_with_verified_rollback(self):
        record = enrollment.stage(self.project, self.out)
        self.assertEqual(record["phase"], "staged")
        self.assertEqual((self.resources / "boot.bin").read_bytes(), (self.out / "loader.bin").read_bytes())
        self.assertEqual((self.resources / "enrolled.txt").read_bytes(), self.start_receipt)
        self.assertEqual((self.resources / "card.json").read_bytes(), self.start_metadata)
        self.assertEqual((self.project / "out/internal-boot-state.json").read_bytes(), self.start_state)
        backup = self.resources / record["backup"]
        self.assertEqual((backup / "boot.bin").read_bytes(), self.fixture.boot)
        self.assertEqual((backup / "internal-boot-state.json").read_bytes(), self.start_state)
        self.assertEqual(enrollment._check_backups(self.resources, record), backup)
        self.fixture.dutil.run.assert_not_called()
        self.confirm.assert_called_once()
        self.assertEqual(self.confirm.call_args.args[0], "STAGE LOADER " + self.fixture.identity["vgid"])

    def test_nvme_variant_uses_same_enrollment_history_and_preserves_sd_loader(self):
        original = (self.out / "loader.bin").read_bytes()
        directory = self.out / "nvme-loader"
        directory.mkdir()
        data = b"explicit ANS-aware m1n1 and unchanged UEFI bridge"
        (directory / "loader.bin").write_bytes(data)
        manifest = {"schema": 1, "kind": "j614s-sd-loader", "boot_protocol": "uefi-arm64",
                    "inputs": {"nvme_handoff": {"marker": "v2"}}, "files": {
                        "loader.bin": {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}}}
        (directory / "loader-manifest.json").write_text(json.dumps(manifest))
        record = enrollment.stage(self.project, self.out, nvme=True)
        self.assertEqual((self.resources / "boot.bin").read_bytes(), data)
        self.assertEqual((self.out / "loader.bin").read_bytes(), original)
        self.assertEqual(json.loads((self.out / enrollment.STATE).read_text()), record)
        self.assertFalse((directory / enrollment.STATE).exists())
        self.assertEqual((self.resources / "enrolled.txt").read_bytes(), self.start_receipt)
        enrollment._check_backups(self.resources, record)
        # An alternative filename cannot accidentally bypass pending state.
        with self.assertRaisesRegex(ValueError, "pending loader"):
            enrollment.stage(self.project, self.out)

    def test_nvme_variant_requires_attested_handoff_before_disk_access(self):
        directory = self.out / "nvme-loader"
        directory.mkdir()
        for name in ("loader.bin", "loader-manifest.json"):
            (directory / name).write_bytes((self.out / name).read_bytes())
        with self.assertRaisesRegex(ValueError, "ANS-aware"):
            enrollment.stage(self.project, self.out, nvme=True)
        self.mount.assert_not_called()
        self.confirm.assert_not_called()

    def test_retired_fit_loader_is_rejected_before_mount_or_confirmation(self):
        path = self.out / "loader-manifest.json"
        manifest = json.loads(path.read_text())
        manifest.pop("boot_protocol")
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "make loader"):
            enrollment.stage(self.project, self.out)
        self.mount.assert_not_called()
        self.writable.assert_not_called()
        self.confirm.assert_not_called()

    def test_repeating_staged_or_enrolled_loader_is_idempotent(self):
        record = enrollment.stage(self.project, self.out)
        original_dirs = list(self.resources.glob("sd-loader-backup-*"))
        self.confirm.reset_mock()
        self.writable.reset_mock()
        enrollment.stage(self.project, self.out)
        self.assertEqual(enrollment.status(self.project, self.out)["phase"], "awaiting-recovery")
        (self.resources / "enrolled.txt").write_text(
            self.fixture.identity["vgid"] + "\n" + record["target"]["sha256"] + "\n")
        enrollment.stage(self.project, self.out)
        self.assertEqual(enrollment.status(self.project, self.out)["phase"], "enrolled")
        self.confirm.assert_not_called()
        self.writable.assert_not_called()
        self.assertEqual(list(self.resources.glob("sd-loader-backup-*")), original_dirs)

    def test_interrupted_replacement_resumes_only_known_generation(self):
        original = enrollment._atomic
        def interrupted(path, data, mode=0o600):
            if path == self.resources / "enroll.sh":
                raise OSError("interrupted after boot replacement")
            return original(path, data, mode)
        with patch.object(enrollment, "_atomic", side_effect=interrupted), self.assertRaises(OSError):
            enrollment.stage(self.project, self.out)
        record = json.loads((self.out / enrollment.STATE).read_text())
        self.assertEqual(record["phase"], "prepared")
        self.assertEqual((self.resources / "boot.bin").read_bytes(), (self.out / "loader.bin").read_bytes())
        resumed = enrollment.stage(self.project, self.out)
        self.assertEqual(resumed["backup"], record["backup"])
        self.assertEqual(resumed["phase"], "staged")

    def test_pending_loader_blocks_a_different_build(self):
        enrollment.stage(self.project, self.out)
        before = (self.resources / "boot.bin").read_bytes()
        self.write_loader(b"different unreviewed loader generation")
        with self.assertRaisesRegex(ValueError, "Finish enrolling"):
            enrollment.stage(self.project, self.out)
        self.assertEqual((self.resources / "boot.bin").read_bytes(), before)

    def test_next_enrolled_loader_gets_an_independent_rollback_set(self):
        first = enrollment.stage(self.project, self.out)
        (self.resources / "enrolled.txt").write_text(
            self.fixture.identity["vgid"] + "\n" + first["target"]["sha256"] + "\n")
        self.write_loader(b"second fixed loader")
        second = enrollment.stage(self.project, self.out)
        self.assertNotEqual(first["backup"], second["backup"])
        self.assertEqual(second["previous"], first["target"])
        self.assertTrue((self.resources / second["backup"] / "enrollment-state.json").is_file())
        enrollment._check_backups(self.resources, first)

    def test_repeated_overrides_preserve_original_receipt_and_rollback(self):
        first = enrollment.stage(self.project, self.out)
        # Exercise compatibility with a pending record from the old implementation.
        first.pop("previous_receipt_sha256")
        enrollment._save(self.out, first)
        prior = first
        baseline = self.fixture.boot_info["sha256"]
        for payload in (b"second pending loader", b"third pending loader"):
            self.write_loader(payload)
            current = enrollment.stage(self.project, self.out, replace_pending=True)
            self.assertEqual(current["previous"], prior["target"])
            self.assertEqual(current["previous_receipt_sha256"], baseline)
            self.assertEqual((self.resources / "enrolled.txt").read_bytes(), self.start_receipt)
            self.assertIn("PREVIOUS_BOOT_SHA256='" + baseline + "'",
                          (self.resources / "enroll.sh").read_text())
            backup = enrollment._check_backups(self.resources, current)
            self.assertEqual(json.loads((backup / "enrollment-state.json").read_text()), prior)
            self.assertEqual(enrollment.status(self.project, self.out)["phase"], "awaiting-recovery")
            self.assertEqual(self.confirm.call_args.args[0],
                             "REPLACE PENDING LOADER " + self.fixture.identity["vgid"])
            self.assertEqual(enrollment.stage(self.project, self.out), current)
            prior = current
        self.assertEqual((self.resources / first["backup"] / "boot.bin").read_bytes(), self.fixture.boot)
        # Once Recovery enrolls the latest generation, ordinary staging uses it as baseline.
        (self.resources / "enrolled.txt").write_text(
            self.fixture.identity["vgid"] + "\n" + prior["target"]["sha256"] + "\n")
        self.write_loader(b"next ordinary update")
        current = enrollment.stage(self.project, self.out)
        self.assertEqual(current["previous_receipt_sha256"], prior["target"]["sha256"])

    def test_interrupted_override_resumes_at_each_durable_boundary(self):
        first = enrollment.stage(self.project, self.out)
        original = enrollment._atomic
        for boundary in ("boot.bin", "enroll.sh", "final-state"):
            with self.subTest(boundary=boundary):
                self.write_loader(("replacement interrupted at " + boundary).encode())
                def interrupted(path, data, mode=0o600):
                    if (path == self.resources / boundary or
                            (boundary == "final-state" and path == self.out / enrollment.STATE
                             and json.loads(data)["phase"] == "staged")):
                        raise OSError("simulated power loss")
                    return original(path, data, mode)
                with patch.object(enrollment, "_atomic", side_effect=interrupted):
                    with self.assertRaisesRegex(OSError, "simulated power loss"):
                        enrollment.stage(self.project, self.out, replace_pending=True)
                self.assertEqual((self.resources / "enrolled.txt").read_bytes(), self.start_receipt)
                resumed = enrollment.stage(self.project, self.out)
                self.assertEqual(resumed["phase"], "staged")
                self.assertEqual(resumed["previous_receipt_sha256"], self.fixture.boot_info["sha256"])
                enrollment._check_backups(self.resources, resumed)
        enrollment._check_backups(self.resources, first)

    def test_override_can_replace_prepared_update_before_first_write(self):
        original = enrollment._atomic
        def interrupted(path, data, mode=0o600):
            if path == self.resources / "boot.bin":
                raise OSError("before first active write")
            return original(path, data, mode)
        with patch.object(enrollment, "_atomic", side_effect=interrupted), self.assertRaises(OSError):
            enrollment.stage(self.project, self.out)
        self.assertEqual((self.resources / "boot.bin").read_bytes(), self.fixture.boot)
        self.write_loader(b"replacement of prepared update")
        current = enrollment.stage(self.project, self.out, replace_pending=True)
        self.assertEqual(current["previous"], self.fixture.boot_info)
        self.assertEqual(current["previous_receipt_sha256"], self.fixture.boot_info["sha256"])
        self.assertEqual(enrollment.status(self.project, self.out)["phase"], "awaiting-recovery")

    def test_override_back_to_enrolled_loader_resumes_before_payload_write(self):
        enrollment.stage(self.project, self.out)
        self.write_loader(self.fixture.boot)
        original = enrollment._atomic
        def interrupted(path, data, mode=0o600):
            if path == self.resources / "boot.bin":
                raise OSError("before rollback payload write")
            return original(path, data, mode)
        with patch.object(enrollment, "_atomic", side_effect=interrupted), self.assertRaises(OSError):
            enrollment.stage(self.project, self.out, replace_pending=True)
        self.assertEqual(enrollment.status(self.project, self.out)["phase"], "prepared")
        enrollment.stage(self.project, self.out)
        self.assertEqual(enrollment.status(self.project, self.out)["phase"], "enrolled")

    def test_override_still_rejects_unknown_active_inputs(self):
        enrollment.stage(self.project, self.out)
        self.write_loader(b"replacement loader")
        for name, data in (("boot.bin", b"unknown loader"), ("enroll.sh", b"unknown script"),
                           ("enrolled.txt", (self.fixture.identity["vgid"] + "\n" + "a" * 64 + "\n").encode())):
            with self.subTest(name=name):
                path = self.resources / name
                original = path.read_bytes()
                path.write_bytes(data)
                self.confirm.reset_mock()
                self.writable.reset_mock()
                with self.assertRaisesRegex(ValueError, "recorded inputs"):
                    enrollment.stage(self.project, self.out, replace_pending=True)
                self.confirm.assert_not_called()
                self.writable.assert_not_called()
                path.write_bytes(original)

    def test_override_checks_original_enrolled_ancestor(self):
        first = enrollment.stage(self.project, self.out)
        self.write_loader(b"second pending loader")
        enrollment.stage(self.project, self.out, replace_pending=True)
        state = (self.out / enrollment.STATE).read_bytes()
        (self.resources / first["backup"] / "boot.bin").write_bytes(b"damaged original backup")
        self.write_loader(b"third pending loader")
        self.confirm.reset_mock()
        with self.assertRaisesRegex(ValueError, "rollback"):
            enrollment.stage(self.project, self.out, replace_pending=True)
        self.confirm.assert_not_called()
        self.assertEqual((self.out / enrollment.STATE).read_bytes(), state)

    def test_cancel_override_leaves_active_files_and_backups_untouched(self):
        enrollment.stage(self.project, self.out)
        self.write_loader(b"replacement loader")
        paths = [self.out / enrollment.STATE] + [self.resources / name for name in enrollment.OLD_FILES]
        snapshot = {path: path.read_bytes() for path in paths}
        backups = list(self.resources.glob("sd-loader-backup-*"))
        self.confirm.side_effect = ValueError("Cancelled")
        with self.assertRaisesRegex(ValueError, "Cancelled"):
            enrollment.stage(self.project, self.out, replace_pending=True)
        self.assertEqual(snapshot, {path: path.read_bytes() for path in snapshot})
        self.assertEqual(backups, list(self.resources.glob("sd-loader-backup-*")))

    def test_invalid_new_backup_chain_does_not_publish_intent(self):
        first = enrollment.stage(self.project, self.out)
        self.write_loader(b"replacement loader")
        paths = [self.out / enrollment.STATE] + [self.resources / name for name in enrollment.OLD_FILES]
        snapshot = {path: path.read_bytes() for path in paths}
        original = enrollment._check_backups
        def reject_new_chain(resources, record, _seen=None):
            if record["backup"] != first["backup"]:
                raise ValueError("Invalid loader rollback chain")
            return original(resources, record, _seen)
        with patch.object(enrollment, "_check_backups", side_effect=reject_new_chain):
            with self.assertRaisesRegex(ValueError, "rollback chain"):
                enrollment.stage(self.project, self.out, replace_pending=True)
        self.assertEqual(snapshot, {path: path.read_bytes() for path in snapshot})

    def test_host_state_change_during_confirmation_aborts_override(self):
        first = enrollment.stage(self.project, self.out)
        self.write_loader(b"replacement loader")
        active = (self.resources / "boot.bin").read_bytes()
        def change_state(*args):
            changed = {**first, "phase": "prepared"}
            enrollment._save(self.out, changed)
        self.confirm.side_effect = change_state
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            enrollment.stage(self.project, self.out, replace_pending=True)
        self.assertEqual((self.resources / "boot.bin").read_bytes(), active)

    def test_unknown_legacy_update_is_refused_before_confirmation(self):
        (self.resources / "boot.bin").write_bytes(b"unfinished legacy update")
        for replace in (False, True):
            with self.subTest(replace=replace), self.assertRaisesRegex(ValueError, "unfinished"):
                enrollment.stage(self.project, self.out, replace_pending=replace)
        self.confirm.assert_not_called()
        self.writable.assert_not_called()

    def test_tampered_rollback_refuses_resume(self):
        record = enrollment.stage(self.project, self.out)
        (self.resources / record["backup"] / "boot.bin").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "rollback"):
            enrollment.stage(self.project, self.out)

    def test_status_does_not_mount_unmounted_system_or_write_state(self):
        self.fixture.dutil.info.return_value = {}
        result = enrollment.status(self.project, self.out)
        self.assertFalse(result["mounted"])
        self.assertEqual(result["phase"], "not-staged")
        self.mount.assert_not_called()
        self.writable.assert_not_called()
        self.fixture.dutil.run.assert_not_called()
        self.assertFalse((self.out / enrollment.STATE).exists())

    def test_render_refuses_main_macos_and_has_no_card_binding(self):
        identity = copy.deepcopy(self.fixture.identity)
        text = enrollment.render(self.project, identity, self.out / "loader.bin")
        for token in ("ROOT_", "root_whole", "BOOT_STORAGE_MODE", "external-sd", "##", "exfat"):
            self.assertNotIn(token, text)
        for required in ("one true recoveryOS", "Paired", "Internal)", "configure-boot", "--entry-point 2048"):
            self.assertIn(required, text)
        checked = subprocess.run(["sh", "-n"], input=text, text=True, capture_output=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        identity["vgid"] = identity["source_macos_vgid"]
        with self.assertRaisesRegex(ValueError, "separate internal"):
            enrollment.render(self.project, identity, self.out / "loader.bin")



if __name__ == "__main__":
    unittest.main()
