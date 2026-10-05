import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib"))
from driver_tools import FILES, stage

spec = importlib.util.spec_from_file_location("module_installer", PROJECT / "templates/install-driver-modules.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

RELEASE = "7.1.3-m4rch"
PREFIX = f"usr/lib/modules/{RELEASE}"
BLOCKED = ["nvme-apple", "macsmc-reboot"]


class DriverToolsTests(unittest.TestCase):
    def archive(self, root, extra=()):
        path = root / "source.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            member = tarfile.TarInfo(PREFIX + "/kernel/drivers/test.ko")
            content = b"fixture module contents"
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
            for member, content in extra:
                archive.addfile(member, io.BytesIO(content) if content else None)
        return path

    def stage(self, root, extra=()):
        return stage(PROJECT, root / "tools", modules_archive=self.archive(root, extra),
                     kernel_release=RELEASE, kernel_sha256="a" * 64, blocked_modules=BLOCKED)

    def depmod(self, root, fail=False):
        command = root / "depmod"
        command.write_text('#!/bin/sh\n'
                           'test "$1" = -b || exit 80\n'
                           'test -f "$2/lib/modules/$3/kernel/drivers/test.ko" || exit 81\n'
                           + ('exit 7\n' if fail else
                              'printf "kernel/drivers/test.ko:\\n" > "$2/lib/modules/$3/modules.dep"\n'))
        command.chmod(0o755)
        return str(command)

    def test_staging_hashes_files_and_rejects_symlink_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = self.stage(root)
            manifest = installer.metadata(output)
            self.assertEqual(manifest["kernel_release"], RELEASE)
            self.assertEqual(manifest["blocked_modules"], BLOCKED)
            for name, source in FILES.items():
                self.assertEqual((output / name).read_bytes(), (PROJECT / "templates" / source).read_bytes())
                if name not in ("install-driver-modules.py", "README.txt"):
                    subprocess.run(["sh", "-n", str(output / name)], check=True)
            outside = root / "preserved"
            outside.write_text("original")
            (output / "modules.tar.gz").unlink()
            (output / "modules.tar.gz").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "regular file"):
                self.stage(root)
            self.assertEqual(outside.read_text(), "original")

    def test_side_by_side_install_builds_dependencies_and_blocks_autoload(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(installer.os, "sync", create=True):
            root = Path(tmp)
            output = self.stage(root)
            system = root / "system"
            old = system / "usr/lib/modules/old/kernel/working.ko"
            old.parent.mkdir(parents=True)
            old.write_text("preserve the running kernel")
            original_depmod = self.depmod(root)
            result = installer.install(output, root=system, depmod=original_depmod)
            self.assertEqual(result["kernel_release"], RELEASE)
            self.assertEqual(old.read_text(), "preserve the running kernel")
            self.assertEqual((system / PREFIX / "kernel/drivers/test.ko").read_bytes(), b"fixture module contents")
            self.assertEqual((system / PREFIX / "modules.dep").read_text(), "kernel/drivers/test.ko:\n")
            self.assertEqual((system / "etc/modprobe.d/m4rch-drivers.conf").read_bytes(),
                             (output / "autoload-blocklist.conf").read_bytes())
            self.assertEqual((system / "usr/local/bin/m4rch-driver-diagnostics").stat().st_mode & 0o777, 0o755)
            self.assertFalse(list((system / "usr/lib/modules").glob(".arch-m4-modules-*")))
            with self.assertRaisesRegex(ValueError, "already exists"):
                installer.install(output, root=system, depmod=original_depmod)
            self.assertEqual(old.read_text(), "preserve the running kernel")

    def test_depmod_failure_never_publishes_partial_modules_or_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = self.stage(root)
            system = root / "system"
            with self.assertRaises(subprocess.CalledProcessError):
                installer.install(output, root=system, depmod=self.depmod(root, fail=True))
            self.assertFalse((system / PREFIX).exists())
            self.assertFalse((system / "etc/modprobe.d/m4rch-drivers.conf").exists())
            self.assertFalse(list((system / "usr/lib/modules").iterdir()))

    def test_existing_custom_blocklist_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = self.stage(root)
            system = root / "system"
            blocklist = system / "etc/modprobe.d/m4rch-drivers.conf"
            blocklist.parent.mkdir(parents=True)
            blocklist.write_text("# my local edits\nblacklist custom_driver\n")
            with self.assertRaisesRegex(ValueError, "configuration was preserved"):
                installer.install(output, root=system, depmod=self.depmod(root))
            self.assertEqual(blocklist.read_text(), "# my local edits\nblacklist custom_driver\n")
            self.assertFalse((system / PREFIX).exists())

    def test_archive_rejects_traversal_other_releases_duplicates_links_and_devices(self):
        cases = [
            (PREFIX + "/../../../../etc/passwd", tarfile.REGTYPE, b"bad"),
            ("/etc/passwd", tarfile.REGTYPE, b"bad"),
            ("usr/lib/modules/another/kernel/bad.ko", tarfile.REGTYPE, b"bad"),
            (PREFIX + "/kernel/drivers/test.ko", tarfile.REGTYPE, b"duplicate"),
            (PREFIX + "/build", tarfile.SYMTYPE, b""),
            (PREFIX + "/hardlink", tarfile.LNKTYPE, b""),
            (PREFIX + "/device", tarfile.CHRTYPE, b""),
            (PREFIX + "/fifo", tarfile.FIFOTYPE, b""),
        ]
        for name, kind, payload in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                member = tarfile.TarInfo(name)
                member.type = kind
                member.size = len(payload)
                if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                    member.linkname = "/etc/passwd"
                output = self.stage(root, [(member, payload)])
                system = root / "system"
                with self.assertRaises(ValueError):
                    installer.install(output, root=system, depmod=self.depmod(root))
                self.assertFalse(system.exists())

    def test_modified_archive_and_manifest_release_are_rejected_before_writes(self):
        for change in ("archive", "release"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                output = self.stage(root)
                if change == "archive":
                    with (output / "modules.tar.gz").open("ab") as stream:
                        stream.write(b"modified")
                else:
                    path = output / "driver-tools-manifest.json"
                    manifest = json.loads(path.read_text())
                    manifest["kernel_release"] = "../escape"
                    path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    installer.install(output, root=root / "system", depmod=self.depmod(root))
                self.assertFalse((root / "system").exists())


class DriverDiagnosticsTests(unittest.TestCase):
    def fixture(self, root, body, user_id="0"):
        fakebin = root / "bin"
        fakebin.mkdir()
        (fakebin / "id").write_text(f"#!/bin/sh\nprintf '%s\\n' '{user_id}'\n")
        (fakebin / "sync").write_text('#!/bin/sh\ntest -s "$TEST_OUTPUT"\n')
        for command in fakebin.iterdir():
            command.chmod(0o755)
        source = (PROJECT / "templates/collect-driver-diagnostics.sh").read_text()
        source = source.split("section 'Kernel, boot and module identity'", 1)[0] + body
        source = source.replace("PATH=/usr/sbin:/usr/bin:/sbin:/bin",
                                f"PATH='{fakebin}':/usr/sbin:/usr/bin:/sbin:/bin")
        script = root / "collector.sh"
        script.write_text(source)
        output = root / "report with spaces.txt"
        environment = dict(os.environ, TEST_OUTPUT=str(output))
        return script, output, environment

    def test_usb_connection_state_reads_roles_and_attachment_without_changing_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sysfs = root / "sys"
            values = {
                "class/typec/port0/data_role": "[host] device\n",
                "class/typec/port0/power_role": "[source] sink\n",
                "class/typec/port0/orientation": "reverse\n",
                "class/typec/port0/power_operation_mode": "default\n",
                "class/typec/port0-partner/supports_usb_power_delivery": "no\n",
                "class/usb_role/usb2/role": "host\n",
                "bus/usb/devices/usb1/product": "xHCI Host Controller\n",
                "bus/usb/devices/usb1/devpath": "0\n",
                "bus/usb/devices/1-1/idVendor": "1050\n",
                "bus/usb/devices/1-1/idProduct": "0407\n",
                "bus/usb/devices/1-1/speed": "12\n",
                "bus/usb/devices/1-1/authorized": "1\n",
            }
            for name, value in values.items():
                path = sysfs / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value)
            # A report should neither invoke power negotiation nor inspect
            # unrelated driver controls when walking these writable classes.
            reset = sysfs / "class/typec/port0/reset"
            reset.write_text("DO-NOT-READ-OR-WRITE\n")
            script, output, environment = self.fixture(
                root, 'usb_connection_state "$TEST_SYSFS"\n'
                'usb_connection_state "$TEST_SYSFS/absent"\n'
                'printf "End of driver diagnostics.\\n"\n')
            environment["TEST_SYSFS"] = str(sysfs)
            result = subprocess.run(["sh", str(script), "--output", str(output)],
                                    env=environment, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = output.read_text()
            for name, value in values.items():
                self.assertIn(str(sysfs / name), report)
                self.assertIn(value, report)
                self.assertEqual((sysfs / name).read_text(), value)
            self.assertIn("No registered devices in this class.", report)
            self.assertNotIn("DO-NOT-READ-OR-WRITE", report)
            self.assertEqual(reset.read_text(), "DO-NOT-READ-OR-WRITE\n")

    def test_usb_host_port_state_reads_only_portsc_without_touching_debugfs_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            debugfs = root / "debug"
            values = {
                "usb/xhci/392280000.usb/ports/port01/portsc": "Port Status 0x000002a0\n",
                "usb/xhci/392280000.usb/ports/port02/portsc": "Port Status 0x00001203\n",
                "usb/xhci/another-host/ports/port01/portsc": "Port Status 0x00000200\n",
            }
            blocked = {
                "usb/xhci/392280000.usb/ports/port01/reset": "DO-NOT-RESET\n",
                "usb/xhci/392280000.usb/ports/port01/compliance": "DO-NOT-CHANGE-COMPLIANCE\n",
                "usb/xhci/392280000.usb/ports/port01/link_state": "DO-NOT-CHANGE-LINK\n",
                "usb/xhci/392280000.usb/ports/port01/nested/portsc": "DO-NOT-RECURSE\n",
                "usb/xhci/392280000.usb/ports/port01/bandwidth": "DO-NOT-READ-PORT-BANDWIDTH\n",
                "usb/xhci/392280000.usb/bandwidth": "DO-NOT-READ-HOST-BANDWIDTH\n",
                "usb/xhci/392280000.usb/command-ring": "DO-NOT-READ-RING\n",
                "usb/other-controller/ports/port01/portsc": "DO-NOT-READ-OTHER-CONTROLLER\n",
            }
            for name, value in (values | blocked).items():
                path = debugfs / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value)
            script, output, environment = self.fixture(
                root, 'usb_host_port_state "$TEST_DEBUGFS"\n'
                'usb_host_port_state "$TEST_DEBUGFS/absent"\n'
                'printf "End of driver diagnostics.\\n"\n')
            reads = root / "file-reads.txt"
            # Record the actual file arguments, rather than merely checking
            # that unrelated files did not appear in the output.
            cat = root / "bin/cat"
            cat.write_text('#!/bin/sh\n'
                           'printf "%s\\n" "$@" >> "$TEST_FILE_READS"\n'
                           'exec /bin/cat "$@"\n')
            cat.chmod(0o755)
            environment.update(TEST_DEBUGFS=str(debugfs), TEST_FILE_READS=str(reads))
            result = subprocess.run(["sh", str(script), "--output", str(output)],
                                    env=environment, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = output.read_text()
            self.assertCountEqual(reads.read_text().splitlines(),
                                  [str(debugfs / name) for name in values])
            for name, value in values.items():
                self.assertIn(str(debugfs / name), report)
                self.assertIn(value, report)
                self.assertEqual((debugfs / name).read_text(), value)
            for name, value in blocked.items():
                self.assertNotIn(str(debugfs / name), report)
                self.assertNotIn(value, report)
                self.assertEqual((debugfs / name).read_text(), value)
            self.assertIn("No readable xHCI port status files", report)

    def test_ext4_errors_and_mount_namespace_are_collected_without_writing_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc, sysfs = root / "proc", root / "ext4"
            (proc / "self").mkdir(parents=True)
            mountinfo = "42 1 179:2 / / rw,noatime - ext4 /dev/mmcblk0p2 rw,emergency_ro\n"
            (proc / "self/mountinfo").write_text(mountinfo + "x" * 1048576 + "MOUNT-TAIL")
            filesystem = sysfs / "mmcblk0p2"
            filesystem.mkdir(parents=True)
            attributes = {
                "errors_count": "3\n", "first_error_func": "ext4_journal_check_start\n",
                "first_error_time": "1791130800\n", "first_error_line": "84\n",
                "first_error_errcode": "5\n", "first_error_ino": "99\n", "first_error_block": "100\n",
                "last_error_func": "ext4_handle_error\n", "last_error_time": "1791130801\n",
                "last_error_line": "749\n", "last_error_errcode": "30\n",
                "last_error_ino": "101\n", "last_error_block": "102\n",
            }
            for name, value in attributes.items():
                (filesystem / name).write_text(value)
            # A writable fault-injection attribute must never be inspected.
            trigger = filesystem / "trigger_fs_error"
            trigger.write_text("DO-NOT-READ-OR-WRITE\n")
            script, output, environment = self.fixture(
                root, 'filesystem_state "$TEST_PROC" "$TEST_EXT4"\n'
                'printf "End of driver diagnostics.\\n"\n')
            environment.update(TEST_PROC=str(proc), TEST_EXT4=str(sysfs))
            result = subprocess.run(["sh", str(script), "--output", str(output)],
                                    env=environment, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = output.read_text()
            self.assertIn(mountinfo, report)
            self.assertNotIn("MOUNT-TAIL", report)
            self.assertNotIn("DO-NOT-READ-OR-WRITE", report)
            self.assertEqual(trigger.read_text(), "DO-NOT-READ-OR-WRITE\n")
            for name, value in attributes.items():
                self.assertIn(str(filesystem / name), report)
                self.assertIn(value, report)
                self.assertEqual((filesystem / name).read_text(), value)

    def test_usb_graph_preserves_boolean_presence_and_big_endian_links_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dt = root / "devicetree"
            values = {
                "soc/usb@392280000/arch-m4,usb-wait-for-cable": b"",
                "soc/usb@392280000/usb-role-switch": b"",
                "soc/usb@392280000/port/endpoint/phandle": bytes.fromhex("00000030"),
                "soc/usb@392280000/port/endpoint/remote-endpoint": bytes.fromhex("00000031"),
                "soc/spmi@509198000/usb-pd@c/connector/data-role": b"host\0",
                "soc/spmi@509198000/usb-pd@c/connector/port/endpoint/phandle": bytes.fromhex("00000031"),
                "soc/spmi@509198000/usb-pd@c/connector/port/endpoint/remote-endpoint": bytes.fromhex("00000030"),
            }
            for name, value in values.items():
                path = dt / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(value)
            excluded = dt / "soc/usb@392280000/unrelated-property"
            excluded.write_text("DO-NOT-READ\n")
            script, output, environment = self.fixture(
                root, 'usb_role_graph "$TEST_DT"\n'
                'usb_role_graph "$TEST_DT/absent"\n'
                'printf "End of driver diagnostics.\\n"\n')
            environment["TEST_DT"] = str(dt)
            result = subprocess.run(["sh", str(script), "--output", str(output)],
                                    env=environment, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = output.read_text()
            self.assertIn("arch-m4,usb-wait-for-cable: present", report)
            self.assertIn("usb-role-switch: present", report)
            self.assertRegex(report, r"00\s+00\s+00\s+30")
            self.assertRegex(report, r"00\s+00\s+00\s+31")
            self.assertIn("Node absent.", report)
            self.assertNotIn("DO-NOT-READ", report)
            self.assertNotIn(str(excluded), report)
            for name, value in values.items():
                self.assertEqual((dt / name).read_bytes(), value)
            self.assertEqual(excluded.read_text(), "DO-NOT-READ\n")

    def test_atomic_collection_captures_errors_and_preserves_previous_report_on_failure(self):
        bodies = [
            ('printf "driver report\\n"; printf "warning\\n" >&2\n'
             'printf "End of driver diagnostics.\\n"\n', True),
            ('printf "partial report\\n"\n', False),
            ('printf "End of driver diagnostics.\\n"\nexit 7\n', False),
        ]
        for body, success in bodies:
            with self.subTest(success=success), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                script, output, environment = self.fixture(root, body)
                output.write_text("previous report\n")
                result = subprocess.run(["sh", str(script), "--output", str(output)], env=environment,
                                        text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode == 0, success, result.stderr)
                self.assertEqual(output.read_text(), "driver report\nwarning\nEnd of driver diagnostics.\n"
                                 if success else "previous report\n")
                self.assertFalse(list(root.glob(".m4rch-driver-diagnostics.*")))

    def test_nonroot_collection_does_not_replace_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            script, output, environment = self.fixture(Path(tmp), "exit 99\n", user_id="1000")
            output.write_text("previous report\n")
            result = subprocess.run(["sh", str(script), "--output", str(output)], env=environment,
                                    text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(output.read_text(), "previous report\n")


if __name__ == "__main__":
    unittest.main()
