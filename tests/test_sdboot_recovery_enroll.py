"""Execute the SD loader Recovery template using only temporary fake volumes.

Tests provide a synthetic diskutil/APFS identity inventory and render the
current sdboot script. All privileged commands resolve to mocks;
no host disks, boot policy, credentials, or reboot commands are touched.
"""
import hashlib
import json
import os
import plistlib
from pathlib import Path
import pty
import select
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sdboot import enrollment

NAMES = ("VGID", "SYSTEM_UUID", "DATA_UUID", "PREBOOT_UUID", "RECOVERY_UUID",
         "STORE_UUID", "PLATFORM_UUID")
IDS = {name: f"{index:08X}-1111-2222-3333-444444444444"
       for index, name in enumerate(NAMES, 1)}

BASE_MOCK = r'''import hashlib, json, os, pathlib, plistlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
data = json.loads(pathlib.Path(os.environ["ENROLL_FIXTURE"]).read_text())
if name == "PlistBuddy":
    try:
        value = plistlib.loads(pathlib.Path(args[2]).read_bytes())
        for key in args[1].removeprefix("Print :").split(":"):
            value = value[int(key)] if isinstance(value, list) else value[key]
        print(str(value).lower() if isinstance(value, bool) else value)
    except (KeyError, IndexError, ValueError):
        sys.exit(1)
    sys.exit(0)
with open(os.environ["ENROLL_LOG"], "a") as out:
    out.write(json.dumps([name, *args]) + "\n")
if name == "uname": print("Darwin" if args == ["-s"] else "arm64")
elif name == "sysctl": print("Mac16,8")
elif name == "id": print("0")
elif name == "ioreg": sys.stdout.buffer.write(plistlib.dumps([{"IOPlatformUUID": data["platform"]}]))
elif name == "diskutil":
    if args[:2] == ["info", "-plist"]:
        sys.stdout.buffer.write(plistlib.dumps(data["infos"][args[2]]))
    elif args[:2] == ["apfs", "list"]:
        sys.stdout.buffer.write(plistlib.dumps(data["apfs"]))
    elif args[:2] == ["list", "-plist"]:
        sys.stdout.buffer.write(plistlib.dumps(data["partitions"]))
    elif args[0] != "mount": sys.exit(88)
elif name == "bputil":
    if args[0] == "-d": print(data["policy"])
    else: sys.exit(data.get("policy_exit", 0))
elif name == "kmutil": sys.exit(data.get("kmutil_exit", 0))
elif name == "mount": pass
elif name == "sha256":
    if args[:1] != ["-q"] or len(args) != 2: sys.exit(89)
    if "hash_output" in data: print(data["hash_output"])
    else: print(hashlib.sha256(pathlib.Path(args[1]).read_bytes()).hexdigest())
    sys.exit(data.get("hash_exit", 0))
elif name == "plutil":
    try: plistlib.loads(pathlib.Path(args[-1]).read_bytes())
    except Exception: sys.exit(1)
else: sys.exit(89)
'''
PREVIOUS = "a" * 64

# These commands act only on the fixture tree. Snapshot each boundary so a
# passing test establishes receipt durability *before* changing picker metadata.
EXTRA_MOCK = r'''
if name in ("mv", "sync", "reboot", "mount", "kmutil"):
    root = pathlib.Path(os.environ["ENROLL_FIXTURE"]).parent
    system = root / "Volumes/Arch Boot"
    resources = system / "Finish Installation.app/Contents/Resources"
    core = system / "System/Library/CoreServices"
    receipt = resources / "enrolled.txt"
    event = {"command": name, "args": args,
             "receipt": receipt.read_text() if receipt.is_file() else None,
             "version": (core / "SystemVersion.plist").exists(),
             "hidden_version": (core / "SystemVersion-disabled.plist").exists(),
             "marker": (system / ".IAPhysicalMedia").exists(),
             "disabled_marker": (system / "IAPhysicalMedia-disabled.plist").exists()}
    event_path = root / "events.jsonl"
    with event_path.open("a") as out:
        out.write(json.dumps(event) + "\n")
    if name == "mv":
        source, dest = (pathlib.Path(arg) for arg in args)
        assert root in source.parents and root in dest.parents
        if data.get("fail_move") == dest.name: sys.exit(73)
        source.replace(dest)
        if data.get("fail_after_move") == dest.name: sys.exit(74)
        sys.exit(0)
    if name == "sync":
        number = sum(json.loads(line)["command"] == "sync"
                     for line in event_path.read_text().splitlines())
        sys.exit(75 if data.get("fail_sync_number") == number else 0)
    if name == "reboot": sys.exit(0)
    if name == "mount": sys.exit(data.get("mount_exit", 0))
'''
MOCK = BASE_MOCK.replace('if name == "uname":', EXTRA_MOCK + '\nif name == "uname":')


class SdbootRecoveryEnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="arch-m4-sd-enrollment-test-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.system = self.path / "Volumes/Arch Boot"
        self.resources = self.system / "Finish Installation.app/Contents/Resources"
        self.resources.mkdir(parents=True)
        self.core = self.system / "System/Library/CoreServices"
        self.core.mkdir(parents=True)
        (self.core / "SystemVersion-disabled.plist").write_text("prepared")
        (self.system / ".IAPhysicalMedia").write_text("installer")
        self.payload = b"fixed m1n1 and U-Boot loader\0" * 400
        self.bundle = self.resources / "boot.bin"
        self.bundle.write_bytes(self.payload)
        self.preboot = self.path / "Volumes/Preboot"
        owner = self.preboot / IDS["VGID"] / "var/db/AdminUserRecoveryInfo.plist"
        owner.parent.mkdir(parents=True)
        owner.write_bytes(plistlib.dumps({"owner": {"GeneratedUID": IDS["PLATFORM_UUID"]}}))
        self.owner = owner
        self.bin = self.path / "bin"
        self.bin.mkdir()
        self.fixture_path = self.path / "fixture.json"
        self.log = self.path / "calls.jsonl"
        self.script = self.resources / "enroll.sh"
        self.identity = {"vgid": IDS["VGID"], "store_uuid": IDS["STORE_UUID"],
                         "platform_uuid": IDS["PLATFORM_UUID"], "storage_mode": "internal-stub",
                         "source_macos_vgid": "11111111-1111-2222-3333-444444444444",
                         "source_macos_store_uuid": "22222222-1111-2222-3333-444444444444",
                         "roles": {role: {"uuid": IDS[role.upper() + "_UUID"]}
                                   for role in ("System", "Data", "Preboot", "Recovery")}}
        infos = {}
        volumes = []
        for role in ("System", "Data", "Preboot", "Recovery"):
            volume_uuid = IDS[role.upper() + "_UUID"]
            info = {"VolumeUUID": volume_uuid, "APFSContainerReference": "disk8",
                    "APFSVolumeGroupID": IDS["VGID"]}
            if role == "System": info["MountPoint"] = str(self.system)
            if role == "Preboot": info["MountPoint"] = str(self.preboot)
            infos[volume_uuid] = info
            volumes.append({"APFSVolumeUUID": volume_uuid, "Roles": [role]})
        infos["disk0s4"] = {"DiskUUID": IDS["STORE_UUID"], "ParentWholeDisk": "disk0"}
        infos["disk0"] = {
            "WholeDisk": True, "VirtualOrPhysical": "Unknown", "Internal": True,
            "RemovableMediaOrExternalDevice": False, "Ejectable": False,
            "BusProtocol": "Apple Fabric",
            "DeviceTreePath": "IODeviceTree:/arm-io@10F00000/ans@9600000/iop-ans-nub/AppleANS3CGv2Controller",
        }
        self.data = {"platform": IDS["PLATFORM_UUID"], "infos": infos,
                     "policy": "Recovery OS status: Paired\nCurrent OS environment: one true recoveryOS\n",
                     "apfs": {"Containers": [{"ContainerReference": "disk8",
                         "PhysicalStores": [{"DeviceIdentifier": "disk0s4", "DiskUUID": IDS["STORE_UUID"]}],
                         "Volumes": volumes}]}}
        self.identity["previous_boot_sha256"] = PREVIOUS
        self.target = hashlib.sha256(self.payload).hexdigest()
        self.receipt = self.resources / "enrolled.txt"
        self.receipt.write_text(self.receipt_text(PREVIOUS))
        self.version = self.core / "SystemVersion.plist"
        self.hidden_version = self.core / "SystemVersion-disabled.plist"
        self.marker = self.system / ".IAPhysicalMedia"
        self.disabled_marker = self.system / "IAPhysicalMedia-disabled.plist"
        contents = self.resources.parent
        self.info = contents / "Info.plist"
        self.launcher = contents / "MacOS/launch.sh"
        self.launcher.parent.mkdir()
        self.info.write_text("hash-bound app metadata\n")
        self.launcher.write_text('#!/bin/sh\nexec sh "../Resources/enroll.sh" --update\n')
        self.launcher.chmod(0o755)
        self.plan = {key + "_sha256": hashlib.sha256(path.read_bytes()).hexdigest()
                     for key, path in (("system_version", self.hidden_version),
                                       ("installer", self.marker),
                                       ("app_info", self.info), ("app_launcher", self.launcher))}
        for command in ("PlistBuddy", "uname", "sysctl", "id", "ioreg", "diskutil", "bputil",
                        "kmutil", "mount", "plutil", "sha256", "mv", "sync", "reboot"):
            path = self.bin / command
            path.write_text(f"#!{sys.executable}\n" + MOCK)
            path.chmod(0o755)
        self.events_path = self.path / "events.jsonl"
        self.render()

    def receipt_text(self, digest):
        return IDS["VGID"] + "\n" + digest + "\n"

    def render(self, auto=True):
        text = enrollment.render(ROOT, self.identity, self.bundle,
                                 launcher=self.plan if auto else None, initial=getattr(self, "initial", False),
                                 owner_sha256=hashlib.sha256(self.owner.read_bytes()).hexdigest()
                                 if getattr(self, "initial", False) else None)
        self.assertNotIn("##", text)
        text = text.replace("PATH=/usr/bin:/bin:/usr/sbin:/sbin",
                            f"PATH='{self.bin}':/usr/bin:/bin:/usr/sbin:/sbin")
        text = text.replace("/usr/libexec/PlistBuddy", str(self.bin / "PlistBuddy"))
        text = text.replace("in /Volumes/*)", f"in '{self.path}/Volumes/'*)")
        self.script.write_text(text)

    def prepare_run(self):
        self.fixture_path.write_text(json.dumps(self.data))
        self.log.unlink(missing_ok=True)
        self.events_path.unlink(missing_ok=True)
        return {**os.environ, "ENROLL_FIXTURE": str(self.fixture_path), "ENROLL_LOG": str(self.log)}

    def read_calls(self):
        self.calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        self.events = [json.loads(line) for line in self.events_path.read_text().splitlines()] if self.events_path.exists() else []

    def run_script(self, *args, answer="y\n"):
        result = subprocess.run(["/bin/sh", str(self.script), *args], env=self.prepare_run(),
                                input=answer, text=True, capture_output=True, timeout=30)
        self.read_calls()
        return result

    def snapshot(self):
        result = {}
        for root in (self.system, self.preboot):
            for path in sorted(root.rglob("*")):
                if path.is_symlink(): result[str(path)] = ("link", os.readlink(path))
                elif path.is_file(): result[str(path)] = ("file", path.read_bytes())
                else: result[str(path)] = ("directory",)
        return result

    def completed(self):
        if self.hidden_version.exists(): self.hidden_version.replace(self.version)
        if self.marker.exists(): self.marker.replace(self.disabled_marker)

    def assert_rejected(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(any(call[0] in ("kmutil", "mount", "mv", "sync", "reboot") for call in self.calls), self.calls)

    def assert_complete(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.receipt.read_text(), self.receipt_text(self.target))
        self.assertTrue(self.version.is_file())
        self.assertTrue(self.disabled_marker.is_file())
        self.assertFalse(self.hidden_version.exists())
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.bundle.read_bytes(), self.payload)

    def initial_setup(self):
        self.initial = True
        self.receipt.unlink()
        self.completed()
        self.render()

    def test_initial_enrollment_authorizes_policy_then_creates_first_receipt(self):
        self.initial_setup()
        self.assert_complete(self.run_script("--enroll"))
        policy = [c for c in self.calls if c[0] == "bputil" and c[1] != "-d"]
        self.assertEqual(policy, [["bputil", "-nc", "-v", IDS["VGID"]]])
        self.assertLess(self.calls.index(policy[0]), next(i for i, c in enumerate(self.calls) if c[0] == "kmutil"))
        self.assertIsNone(next(e["receipt"] for e in self.events if e["command"] == "kmutil"))
        self.assert_complete(self.run_script("--enroll", answer=""))
        self.assertFalse(any(c[0] == "kmutil" or (c[0] == "bputil" and c[1] != "-d") for c in self.calls))

    def test_initial_update_mode_cannot_skip_initial_policy_authorization(self):
        self.initial_setup()
        self.assert_rejected(self.run_script("--update"))
        self.assertFalse(self.receipt.exists())

    def test_initial_policy_failure_does_not_configure_boot_or_create_receipt(self):
        self.initial_setup()
        self.data["policy_exit"] = 91
        result = self.run_script("--enroll")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] in ("kmutil", "mount", "mv", "sync") for c in self.calls))
        self.assertFalse(self.receipt.exists())

    def test_initial_kmutil_failure_can_retry_without_false_receipt(self):
        self.initial_setup()
        self.data["kmutil_exit"] = 92
        result = self.run_script("--enroll")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.receipt.exists())
        self.data.pop("kmutil_exit")
        self.assert_complete(self.run_script("--enroll"))

    def test_initial_changed_valid_owner_is_rejected_before_policy_or_boot_enrollment(self):
        self.initial_setup()
        self.owner.write_bytes(plistlib.dumps({"other-owner": {"GeneratedUID": IDS["VGID"]}}))
        self.assert_rejected(self.run_script("--enroll"))
        self.assertFalse(any(c[0] == "bputil" and c[1] != "-d" for c in self.calls))
        self.assertFalse(self.receipt.exists())

    def test_initial_check_is_read_only_with_no_receipt(self):
        self.initial_setup()
        before = self.snapshot()
        self.assertEqual(self.run_script("--check", answer="").returncode, 0)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any(c[0] in ("mount", "kmutil", "mv", "sync", "reboot") or
                             (c[0] == "bputil" and c[1] != "-d") for c in self.calls))

    def test_armed_check_is_read_only_without_prompt_or_mount(self):
        before = self.snapshot()
        result = self.run_script("--check", answer="")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertNotIn("Continue?", result.stdout)
        self.assertFalse(any(c[0] in ("mount", "mv", "kmutil", "sync", "reboot") or
                             c[:2] == ["diskutil", "mount"] for c in self.calls))

    def test_default_update_records_receipt_durably_before_restoring_metadata(self):
        result = self.run_script()
        self.assert_complete(result)
        self.assertIn("Continue? [y/N]", result.stdout)
        self.assertEqual([c for c in self.calls if c[0] == "kmutil"], [[
            "kmutil", "configure-boot", "-c", str(self.bundle), "--raw", "--entry-point", "2048",
            "--lowest-virtual-address", "0", "-v", str(self.system)]])
        self.assertEqual([e["command"] for e in self.events],
                         ["kmutil", "mount", "mv", "sync", "sync", "mount", "mv", "mv", "sync"])
        self.assertEqual(self.events[2]["args"][1], str(self.receipt))
        self.assertEqual(self.events[2]["receipt"], self.receipt_text(PREVIOUS))
        for event in self.events[3:]:
            self.assertEqual(event["receipt"], self.receipt_text(self.target))
        self.assertTrue(self.events[3]["hidden_version"])
        self.assertTrue(self.events[3]["marker"])
        self.assertEqual([Path(e["args"][-1]).name for e in self.events if e["command"] == "mv"],
                         ["enrolled.txt", "SystemVersion.plist", "IAPhysicalMedia-disabled.plist"])
        self.assertFalse(any(c[0] == "reboot" or (c[0] == "bputil" and c[1] != "-d") for c in self.calls))
        self.assertFalse(list(self.resources.glob(".enrolled.*")))

    def test_explicit_yes_and_no_password_arguments(self):
        result = self.run_script("--update", answer="yes\n")
        self.assert_complete(result)
        self.assertFalse(any("password" in part.lower() for c in self.calls for part in c))

    def test_confirmation_defaults_to_cancel(self):
        before = self.snapshot()
        for answer in ("", "\n", "n\n", "yes please\n", "ENROLL " + IDS["VGID"] + "\n"):
            with self.subTest(answer=answer):
                self.assert_rejected(self.run_script(answer=answer))
                self.assertEqual(before, self.snapshot())

    def test_manual_mode_keeps_completed_metadata_and_no_reboot(self):
        self.completed()
        self.render(auto=False)
        before = {p: p.read_bytes() for p in (self.version, self.disabled_marker, self.info, self.launcher)}
        result = self.run_script("--update", answer="y\ny\n")
        self.assert_complete(result)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertEqual([Path(e["args"][-1]).name for e in self.events if e["command"] == "mv"], ["enrolled.txt"])
        self.assertFalse(any(c[0] == "reboot" for c in self.calls))
        self.assertNotIn("Reboot now?", result.stdout)

    def test_manual_mode_rejects_armed_metadata(self):
        self.render(auto=False)
        self.assert_rejected(self.run_script())

    def test_matching_receipt_resumes_all_valid_metadata_states_without_kmutil(self):
        self.receipt.write_text(self.receipt_text(self.target))
        for version_normal, marker_disabled in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(version_normal=version_normal, marker_disabled=marker_disabled):
                version_source = self.version if self.version.exists() else self.hidden_version
                version_dest = self.version if version_normal else self.hidden_version
                if version_source != version_dest: version_source.replace(version_dest)
                marker_source = self.marker if self.marker.exists() else self.disabled_marker
                marker_dest = self.disabled_marker if marker_disabled else self.marker
                if marker_source != marker_dest: marker_source.replace(marker_dest)
                before = self.snapshot()
                check = self.run_script("--check", answer="")
                self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
                self.assertEqual(before, self.snapshot())
                result = self.run_script(answer="")
                self.assert_complete(result)
                self.assertNotIn("Continue?", result.stdout)
                self.assertFalse(any(c[0] == "kmutil" for c in self.calls))
                if version_normal and marker_disabled:
                    self.assertFalse(self.events)

    def test_failed_kmutil_leaves_receipt_and_armed_metadata_unchanged(self):
        self.data["kmutil_exit"] = 1
        before = self.snapshot()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, self.snapshot())
        self.assertEqual([e["command"] for e in self.events], ["kmutil"])

    def test_failed_receipt_mount_or_move_never_restores_picker_metadata(self):
        for fault in ("mount", "receipt"):
            with self.subTest(fault=fault):
                self.data.pop("mount_exit", None)
                self.data.pop("fail_move", None)
                self.data["mount_exit" if fault == "mount" else "fail_move"] = 1 if fault == "mount" else "enrolled.txt"
                before = self.snapshot()
                result = self.run_script()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(before, self.snapshot())
                self.assertFalse(list(self.resources.glob(".enrolled.*")))
                self.assertFalse(self.version.exists())
                self.assertTrue(self.marker.exists())

    def test_receipt_sync_failure_is_resumable_without_enrolling_again(self):
        self.data["fail_sync_number"] = 1
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.receipt.read_text(), self.receipt_text(self.target))
        self.assertTrue(self.hidden_version.exists())
        self.assertTrue(self.marker.exists())
        del self.data["fail_sync_number"]
        self.assert_complete(self.run_script(answer=""))
        self.assertFalse(any(c[0] == "kmutil" for c in self.calls))
        self.assertEqual(self.events[0]["command"], "sync")
        self.assertEqual(self.events[0]["receipt"], self.receipt_text(self.target))
        self.assertTrue(self.events[0]["hidden_version"])

    def test_failed_resume_sync_preserves_armed_metadata(self):
        self.receipt.write_text(self.receipt_text(self.target))
        self.data["fail_sync_number"] = 1
        before = self.snapshot()
        result = self.run_script(answer="")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, self.snapshot())
        self.assertEqual([e["command"] for e in self.events], ["sync"])

    def test_interruptions_at_every_atomic_move_resume_without_reenrollment(self):
        for destination in ("enrolled.txt", "SystemVersion.plist", "IAPhysicalMedia-disabled.plist"):
            with self.subTest(destination=destination):
                self.receipt.write_text(self.receipt_text(PREVIOUS))
                if self.version.exists(): self.version.replace(self.hidden_version)
                if self.disabled_marker.exists(): self.disabled_marker.replace(self.marker)
                self.data["fail_after_move"] = destination
                result = self.run_script()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.receipt.read_text(), self.receipt_text(self.target))
                del self.data["fail_after_move"]
                self.assert_complete(self.run_script(answer=""))
                self.assertFalse(any(c[0] == "kmutil" for c in self.calls))

    def test_rejects_missing_duplicate_tampered_and_symlinked_metadata(self):
        for target, duplicate in ((self.hidden_version, self.version), (self.marker, self.disabled_marker),
                                  (self.info, None), (self.launcher, None)):
            original = target.read_bytes()
            for fault in ("missing", "tampered", "symlink", "dangling", "duplicate"):
                if fault == "duplicate" and duplicate is None: continue
                with self.subTest(target=target.name, fault=fault):
                    target.unlink()
                    other = self.path / "other"
                    if fault == "tampered": target.write_bytes(original + b"tampered")
                    if fault == "symlink":
                        other.write_bytes(original)
                        target.symlink_to(other)
                    if fault == "dangling": target.symlink_to(self.path / "absent")
                    if fault == "duplicate":
                        target.write_bytes(original)
                        duplicate.write_bytes(original)
                    before = self.snapshot()
                    self.assert_rejected(self.run_script("--check", answer=""))
                    self.assertEqual(before, self.snapshot())
                    target.unlink(missing_ok=True)
                    if duplicate: duplicate.unlink(missing_ok=True)
                    other.unlink(missing_ok=True)
                    target.write_bytes(original)

    def test_rejects_symlinked_metadata_directory(self):
        macos = self.launcher.parent
        saved = self.path / "saved-MacOS"
        macos.replace(saved)
        macos.symlink_to(saved, target_is_directory=True)
        self.assert_rejected(self.run_script("--check"))

    def test_rejects_invalid_receipt_and_modified_boot_payload(self):
        previous = self.receipt.read_text()
        for text in (self.receipt_text("b" * 64), self.receipt_text(PREVIOUS) + "extra\n",
                     self.receipt_text(PREVIOUS).rstrip("\n"), IDS["SYSTEM_UUID"] + "\n" + PREVIOUS + "\n"):
            with self.subTest(receipt=text):
                self.receipt.write_text(text)
                self.assert_rejected(self.run_script())
        self.receipt.write_text(previous)
        self.bundle.write_bytes(self.payload[:-1] + b"!")
        self.assert_rejected(self.run_script())

    def test_wrong_recovery_mac_and_internal_disk_fail_before_enrollment(self):
        baseline = json.loads(json.dumps(self.data))
        for fault in ("macos", "unpaired", "not-1tr", "wrong-mac", "external", "removable",
                      "usb", "wrong-controller", "wrong-store", "wrong-vgid", "extra-volume"):
            with self.subTest(fault=fault):
                self.data = json.loads(json.dumps(baseline))
                if fault == "macos": self.data["policy"] = "OS Type: macOS\nOS Pairing Status: Paired\none true recoveryOS\n"
                if fault == "unpaired": self.data["policy"] = "OS Type: one true recoveryOS\nOS Pairing Status: Not Paired\n"
                if fault == "not-1tr": self.data["policy"] = "OS Type: recoveryOS\nOS Pairing Status: Paired\n"
                if fault == "wrong-mac": self.data["platform"] = IDS["SYSTEM_UUID"]
                disk = self.data["infos"]["disk0"]
                if fault == "external": disk["Internal"] = False
                if fault == "removable": disk["RemovableMediaOrExternalDevice"] = True
                if fault == "usb": disk["BusProtocol"] = "USB"
                if fault == "wrong-controller": disk["DeviceTreePath"] = "IODeviceTree:/usb-controller"
                if fault == "wrong-store": self.data["infos"]["disk0s4"]["DiskUUID"] = IDS["SYSTEM_UUID"]
                if fault == "wrong-vgid": self.data["infos"][IDS["SYSTEM_UUID"]]["APFSVolumeGroupID"] = IDS["DATA_UUID"]
                if fault == "extra-volume": self.data["apfs"]["Containers"][0]["Volumes"].append({"Roles": []})
                self.assert_rejected(self.run_script())

    def test_noninteractive_confirmation_does_not_accept_a_second_line_as_reboot(self):
        result = self.run_script(answer="yes\nyes\n")
        self.assert_complete(result)
        self.assertNotIn("Reboot now?", result.stdout)
        self.assertFalse(any(c[0] == "reboot" for c in self.calls))

    def run_terminal(self, reboot_answer):
        master, slave = pty.openpty()
        env = self.prepare_run()
        process = subprocess.Popen(["/bin/sh", str(self.script)], stdin=slave, stdout=slave,
                                   stderr=slave, env=env)
        os.close(slave)
        output = b""
        replied = False
        deadline = time.monotonic() + 30
        try:
            while process.poll() is None:
                if time.monotonic() > deadline: self.fail("Recovery fixture hung: " + output.decode(errors="replace"))
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready:
                    try: chunk = os.read(master, 65536)
                    except OSError: break
                    if not chunk: break
                    output += chunk
                    if not replied and b"Reboot now? [y/N] " in output:
                        os.write(master, reboot_answer)
                        replied = True
            process.wait(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
        self.read_calls()
        self.assertTrue(replied, output.decode(errors="replace"))
        return process.returncode, output.decode(errors="replace")

    def test_interactive_reboot_requires_explicit_yes_and_eof_defaults_no(self):
        self.receipt.write_text(self.receipt_text(self.target))
        self.completed()
        for answer, expected in ((b"\n", False), (b"n\n", False), (b"\x04", False), (b"yes\n", True)):
            with self.subTest(answer=answer):
                code, output = self.run_terminal(answer)
                self.assertEqual(code, 0, output)
                self.assertEqual(any(c[0] == "reboot" for c in self.calls), expected)
                self.assertFalse(any(c[0] == "kmutil" for c in self.calls))


if __name__ == "__main__":
    unittest.main()
