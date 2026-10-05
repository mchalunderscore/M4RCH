"""First-time boot provisioning on fake APFS inventories; no real disk writes."""
import copy
import hashlib
import json
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import card
import internal_boot as boot
import internal_disk as disk
import stub_payload
from common import sha256
from test_internal_disk import FakeDiskUtil, uid


class BootstrapDisk(FakeDiskUtil):
    def __init__(self):
        super().__init__()
        self.failure = None

    def get(self, *args):
        if args[:2] != ("apfs", "listVolumeGroups"):
            return super().get(*args)
        container = next(c for c in self.containers if c["ContainerReference"] == args[2])
        return {"Containers": [{"VolumeGroups": [{"APFSVolumeGroupUUID": uid(30).upper(),
            "Volumes": [{"Role": role, "DeviceIdentifier": next(v["DeviceIdentifier"] for v in container["Volumes"] if v["Roles"] == [role])}
                        for role in ("System", "Data")]}]}]}

    def run(self, *args):
        if args[:2] == ("apfs", "resizeContainer"):
            super().run(*args)
        elif args[0] == "enableOwnership":
            self.commands.append(args)
            return
        else:
            container = self.containers[-1]
            if args[:2] == ("apfs", "changeVolumeRole"):
                volume = next(v for v in container["Volumes"] if v["DeviceIdentifier"] == args[2])
                volume["Roles"] = ["Data"]
            elif args[0] == "rename":
                volume = next(v for v in container["Volumes"] if v["DeviceIdentifier"] == args[1])
                volume["Name"] = args[2]
            elif args[:2] == ("apfs", "addVolume"):
                role = {"S": "System", "B": "Preboot", "R": "Recovery"}[args[args.index("-role") + 1]]
                n = len(container["Volumes"]) + 1
                container["Volumes"].append(self.volume(f"disk4s{n}", 104+n, args[4], [role]))
            else:
                raise AssertionError(args)
            self.commands.append(args)
        if self.failure is not None and self.failure(args):
            self.failure = None
            raise RuntimeError("Interrupted after successful fake diskutil command")


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="m4rch-bootstrap-test-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.project = self.path / "project"
        self.payload = self.project / "out/stub"
        self.payload.mkdir(parents=True)
        for role in ("System", "Data", "Preboot", "Recovery"):
            (self.payload / role).mkdir()
        version = self.payload / "System/System/Library/CoreServices/SystemVersion.plist"
        version.parent.mkdir(parents=True)
        version.write_bytes(plistlib.dumps({"ProductVersion": "26.5.2", "ProductBuildVersion": "25F84"}))
        contents = self.payload / "System/Finish Installation.app/Contents"
        contents.mkdir(parents=True)
        (contents / "Info.plist").write_bytes(plistlib.dumps({"original": "Asahi"}))
        (self.payload / "System/.IAPhysicalMedia").write_bytes(plistlib.dumps({"AppName": card.APP, "ProductBuildVersion": "00A191", "ProductVersion": "12.1"}))
        for role in ("Data", "Preboot", "Recovery"):
            (self.payload / role / "pinned-file").write_text(role)
        (self.payload / "manifest.json").write_text('{"apple_build": "25F84"}')
        license_path = self.project / "third_party/ASAHI-LICENSE"
        license_path.parent.mkdir()
        license_path.write_text("fixture MIT license")
        self.source = self.project / "out/loader.bin"
        self.source.write_bytes(b"fixed loader without Linux kernel")
        self.expected = {"sha256": sha256(self.source), "bytes": self.source.stat().st_size}
        self.dutil = BootstrapDisk()
        self.mounts = {}
        self.blank = self.path / "blank"
        self.blank.mkdir()
        self.owner = plistlib.dumps({"owner": {"GeneratedUID": uid(500)}})
        patches = [patch.object(card, "require_macos"), patch.object(card, "platform_uuid", return_value=uid(501).upper()),
                   patch.object(card.os, "geteuid", return_value=0), patch.object(card, "confirm"),
                   patch.object(card, "source_owner_metadata", return_value=self.owner),
                   patch.object(card, "mounted_writable", side_effect=self.mount),
                   patch.object(stub_payload, "prepare"), patch.object(stub_payload, "verify", return_value={"apple_build": "25F84"}),
                   patch("common.run"), patch.object(disk, "Path", return_value=self.blank)]
        self.mocks = [p.start() for p in patches]
        for p in reversed(patches): self.addCleanup(p.stop)
        self.confirm = self.mocks[3]

    def mount(self, dutil, device, volume_uuid):
        path = self.path / "mounts" / volume_uuid
        path.mkdir(parents=True, exist_ok=True)
        self.mounts[volume_uuid] = path
        return path

    def install(self):
        return boot.ensure(self.project, self.source, self.expected, dutil=self.dutil)

    def test_fresh_setup_has_one_resize_four_roles_and_no_fake_receipt(self):
        state = self.install()
        self.assertEqual(state["phase"], "ready")
        self.assertTrue(state["initial_enrollment"])
        self.assertEqual([c for c in self.dutil.commands if c[:2] == ("apfs", "resizeContainer")],
                         [tuple(state["partition"]["plan"]["resize_argv"])])
        self.assertEqual(set(state["identity"]["roles"]), {"System", "Data", "Preboot", "Recovery"})
        self.confirm.assert_called_once()
        self.assertEqual(self.confirm.call_args.args[0], "CREATE INTERNAL " + uid(2).upper())
        resources = self.mounts[state["identity"]["roles"]["System"]["uuid"]] / card.RESOURCES
        self.assertEqual((resources / "boot.bin").read_bytes(), self.source.read_bytes())
        self.assertFalse((resources / "enrolled.txt").exists())
        self.assertFalse(any("disk7" in str(command) for command in self.dutil.commands))
        commands = list(self.dutil.commands)
        self.assertEqual(self.install(), state)
        self.assertEqual(self.dutil.commands, commands)
        self.mocks[6].assert_called_once()  # Current ready path never fetches again.

    def test_successful_resize_interruption_is_adopted_without_second_resize(self):
        self.dutil.failure = lambda args: args[:2] == ("apfs", "resizeContainer")
        with self.assertRaises(RuntimeError): self.install()
        self.assertEqual(boot.read_state(self.project)["phase"], "partition-started")
        self.assertEqual(self.install()["phase"], "ready")
        self.assertEqual(len([c for c in self.dutil.commands if c[:2] == ("apfs", "resizeContainer")]), 1)
        self.confirm.assert_called_once()

    def test_every_role_operation_resumes_without_repeating_write(self):
        for n in range(5):
            with self.subTest(operation=n):
                self.setUp()
                count = 0
                def fail(args):
                    nonlocal count
                    if args[:2] == ("apfs", "resizeContainer"): return False
                    count += 1
                    return count == n + 1
                self.dutil.failure = fail
                with self.assertRaises(RuntimeError): self.install()
                saved = boot.read_state(self.project)
                self.assertEqual(saved["phase"], "roles")
                self.assertIn("pending", saved)
                state = self.install()
                self.assertEqual(state["phase"], "ready")
                role_commands = [c for c in self.dutil.commands if c[0] != "enableOwnership" and c[:2] != ("apfs", "resizeContainer")]
                self.assertEqual(len(role_commands), 5)

    def test_interrupted_payload_copy_resumes_verified_files(self):
        original = boot._copy_payload
        count = 0
        def fail(source, destination):
            nonlocal count
            original(source, destination)
            count += 1
            if count == 2: raise RuntimeError("payload interruption")
        with patch.object(boot, "_copy_payload", side_effect=fail), self.assertRaises(RuntimeError): self.install()
        self.assertEqual(boot.read_state(self.project)["phase"], "payload")
        self.assertEqual(self.install()["phase"], "ready")
        self.assertEqual(len([c for c in self.dutil.commands if c[:2] == ("apfs", "resizeContainer")]), 1)

    def test_mismatched_role_after_interruption_is_not_adopted(self):
        self.dutil.failure = lambda args: args[:2] == ("apfs", "addVolume")
        with self.assertRaises(RuntimeError): self.install()
        self.dutil.containers[-1]["Volumes"][-1]["Name"] = "unrelated volume"
        commands = list(self.dutil.commands)
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(self.dutil.commands, commands)

    def test_existing_named_stub_without_local_state_prevents_second_allocation(self):
        self.dutil.containers[-1]["Volumes"][0]["Name"] = "Arch M4 Boot"
        with self.assertRaisesRegex(ValueError, "already exists"): self.install()
        self.assertEqual(self.dutil.commands, [])
        self.confirm.assert_not_called()

    def test_input_change_on_resume_blocks_every_disk_write(self):
        self.dutil.failure = lambda args: args[:2] == ("apfs", "resizeContainer")
        with self.assertRaises(RuntimeError): self.install()
        self.source.write_bytes(b"different fixed loader")
        self.expected = {"sha256": sha256(self.source), "bytes": self.source.stat().st_size}
        commands = list(self.dutil.commands)
        with self.assertRaisesRegex(ValueError, "inputs changed"): self.install()
        self.assertEqual(self.dutil.commands, commands)

    def enrollment_fixture(self):
        from sdboot import enrollment
        state = self.install()
        out = self.project / "out"
        (out / "loader-manifest.json").write_text(json.dumps({"schema": 1, "kind": "j614s-sd-loader",
            "boot_protocol": "uefi-arm64", "files": {"loader.bin": self.expected}}))
        (self.project / "sdboot").mkdir()
        (self.project / "sdboot/recovery-enroll.sh").write_bytes((ROOT / "sdboot/recovery-enroll.sh").read_bytes())
        def mounted(dutil, device, **kwargs):
            volume = next(v for c in dutil.containers for v in c["Volumes"] if v["DeviceIdentifier"] == device)
            return self.mounts[card.canonical_uuid(volume["APFSVolumeUUID"])]
        patches = [patch.object(enrollment, "DiskUtil", return_value=self.dutil),
                   patch.object(card, "mounted", side_effect=mounted),
                   patch.object(card, "set_bootable"), patch.object(enrollment, "run")]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return enrollment, state, out

    def test_initial_prepare_selects_apple_stub_without_fabricating_receipt(self):
        enrollment, state, out = self.enrollment_fixture()
        with patch.object(enrollment, "_answer", side_effect=[True, False]):
            record = enrollment.prepare(self.project, out, nvme=False)
        self.assertEqual(record["phase"], "ready")
        system = self.mounts[state["identity"]["roles"]["System"]["uuid"]]
        resources = system / card.RESOURCES
        self.assertFalse((resources / "enrolled.txt").exists())
        self.assertIn("INITIAL_ENROLLMENT='1'", (resources / "enroll.sh").read_text())
        self.assertTrue((system / "IAPhysicalMedia-disabled.plist").exists())
        self.assertFalse((system / ".IAPhysicalMedia").exists())
        self.assertFalse((out / enrollment.STATE).exists())
        enrollment.run.assert_called_once_with(["/usr/sbin/bless", "--setBoot", "--mount", system])
        with patch.object(enrollment, "_answer", return_value=False):
            enrollment.prepare(self.project, out, nvme=False)
        enrollment.run.assert_called_once()  # No second personalization after successful selection.
        self.assertFalse((resources / "enrolled.txt").exists())

    def test_initial_prepare_cancel_preserves_created_stub_and_all_metadata(self):
        enrollment, state, out = self.enrollment_fixture()
        system = self.mounts[state["identity"]["roles"]["System"]["uuid"]]
        before = {p.relative_to(system): p.read_bytes() for p in system.rglob("*") if p.is_file()}
        with patch.object(enrollment, "_answer", return_value=False), self.assertRaisesRegex(ValueError, "Cancelled"):
            enrollment.prepare(self.project, out, nvme=False)
        after = {p.relative_to(system): p.read_bytes() for p in system.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((out / "initial-enrollment-state.json").exists())
        enrollment.run.assert_not_called()

    def test_initial_prepare_bless_failure_retries_without_recreating_partition(self):
        enrollment, state, out = self.enrollment_fixture()
        commands = list(self.dutil.commands)
        enrollment.run.side_effect = RuntimeError("owner authorization failed")
        with patch.object(enrollment, "_answer", return_value=True), self.assertRaises(RuntimeError):
            enrollment.prepare(self.project, out, nvme=False)
        self.assertEqual(json.loads((out / "initial-enrollment-state.json").read_text())["phase"], "prepared")
        enrollment.run.side_effect = None
        with patch.object(enrollment, "_answer", return_value=False):
            self.assertEqual(enrollment.prepare(self.project, out, nvme=False)["phase"], "ready")
        self.assertEqual(self.dutil.commands, commands)

    def test_unrelated_file_during_payload_resume_is_preserved_and_rejected(self):
        original = boot._copy_payload
        def stop(source, destination):
            original(source, destination)
            raise RuntimeError("after first payload copy")
        with patch.object(boot, "_copy_payload", side_effect=stop), self.assertRaises(RuntimeError): self.install()
        state = boot.read_state(self.project)
        container = self.dutil.containers[-1]
        uuid = card.canonical_uuid(next(v for v in container["Volumes"] if v["Roles"] == ["System"])["APFSVolumeUUID"])
        unrelated = self.mounts[uuid] / "user-data.txt"
        unrelated.write_text("preserve")
        commands = list(self.dutil.commands)
        with self.assertRaisesRegex(ValueError, "Unrelated file"): self.install()
        self.assertEqual(unrelated.read_text(), "preserve")
        self.assertEqual(self.dutil.commands, commands)

    def test_unselected_initial_status_is_not_reported_as_enrolled(self):
        enrollment, state, out = self.enrollment_fixture()
        report = enrollment.status(self.project, out, emit=False)
        self.assertEqual(report["phase"], "awaiting-first-enrollment")
        self.assertIsNone(report["receipt_sha256"])
        system = self.mounts[state["identity"]["roles"]["System"]["uuid"]]
        (system / card.RESOURCES / "enrolled.txt").write_text(state["identity"]["vgid"] + "\n" + self.expected["sha256"] + "\n")
        self.assertEqual(enrollment.status(self.project, out, emit=False)["phase"], "enrolled")

    def test_payload_resume_rejects_changed_encryption_or_migration_before_writes(self):
        original = boot._copy_payload
        def stop(source, destination):
            original(source, destination)
            raise RuntimeError("after first payload copy")
        with patch.object(boot, "_copy_payload", side_effect=stop), self.assertRaises(RuntimeError): self.install()
        recovery = next(v for v in self.dutil.containers[-1]["Volumes"] if v["Roles"] == ["Recovery"])
        commands = list(self.dutil.commands)
        for field, invalid in (("FileVault", True), ("CryptoMigrationOn", True), ("Encryption", None), ("Locked", True)):
            old = recovery[field]
            recovery[field] = invalid
            with self.subTest(field=field), self.assertRaises(ValueError): self.install()
            self.assertEqual(self.dutil.commands, commands)
            recovery[field] = old

    def test_identical_immutable_owner_never_attempts_chmod(self):
        owner = self.path / "owner.plist"
        owner.write_bytes(self.owner)
        owner.chmod(0o600)
        with patch.object(Path, "chmod", side_effect=PermissionError("simulated schg")) as chmod:
            boot._write_once(owner, self.owner, 0o600)
        chmod.assert_not_called()
        self.assertEqual(owner.read_bytes(), self.owner)

    def test_unrecorded_copy_temp_named_file_is_never_deleted(self):
        source = self.path / "copy-source"
        destination = self.path / "copy-destination"
        source.mkdir()
        destination.mkdir()
        unrelated = destination / ".stub-copy-keep-this.txt"
        unrelated.write_text("unrelated user text")
        with self.assertRaisesRegex(ValueError, "Unrelated file"):
            boot._check_payload_destination(source, destination)
        self.assertEqual(unrelated.read_text(), "unrelated user text")

    def test_partial_data_only_stub_blocks_fresh_clone_second_allocation(self):
        self.dutil.failure = lambda args: args[0] == "rename"
        with self.assertRaises(RuntimeError): self.install()
        boot.state_path(self.project).unlink()
        self.dutil.limits.update(CurrentSize=self.dutil.parts[1]["Size"],
                                 ContainerCurrentSize=self.dutil.parts[1]["Size"])
        commands = list(self.dutil.commands)
        with self.assertRaisesRegex(ValueError, "already exists"): self.install()
        self.assertEqual(self.dutil.commands, commands)


if __name__ == "__main__": unittest.main()
