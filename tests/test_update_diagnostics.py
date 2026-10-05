"""Exercise native capture orchestration without querying the host's hardware."""

import hashlib
import json
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class UpdateDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        # A short temporary path also fits macOS's AF_UNIX socket path limit.
        temporary = tempfile.TemporaryDirectory(prefix="update-diag-", dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.kit = self.root / "update kit"
        self.kit.mkdir()
        self.fakebin = self.root / "bin"
        self.fakebin.mkdir()
        self.home = self.root / "alice home"
        self.home.mkdir()
        self.cwd = self.root / "root working directory"
        self.cwd.mkdir()
        self.calls = self.root / "calls.jsonl"
        self.config = self.root / "commands.json"
        self.config.write_text("{}")
        self.runtime = self.root / "run-user"
        self.bus = self.runtime / "1000/bus"
        self.bus.parent.mkdir(parents=True)
        self.script = self.kit / "diagnose.sh"
        self.collector = self.kit / "m4rch-driver-diagnostics"
        self.output = self.root / "new report"

        # Only ordinary file operations use host tools, and their operands are
        # temporary fixture paths. Linux, root, package and hardware tools are
        # all fakes; there is no fallback PATH that could find a live tool.
        for name in ("sh", "env", "dirname", "cut", "mkdir", "mktemp", "rm", "tar", "mv", "awk", "gzip"):
            executable = "/bin/sh" if name == "sh" else shutil.which(name)
            self.assertIsNotNone(executable, name)
            (self.fakebin / name).symlink_to(executable)
        dispatcher = self.fakebin / "fake-command"
        dispatcher.write_text(self.command_source())
        dispatcher.chmod(0o755)
        for name in ("uname", "id", "getent", "sha256sum", "date", "cat", "timeout", "runuser",
                     "pacman", "findmnt", "lspci", "ls", "udevadm", "getfacl", "rfkill",
                     "systemctl", "journalctl", "bluetoothctl", "wpctl", "pw-dump", "pactl", "sync"):
            (self.fakebin / name).symlink_to(dispatcher)

        source = (PROJECT / "templates/update-diagnostics.sh").read_text()
        self.assertIn("PATH=/usr/bin:/bin:/usr/sbin:/sbin", source)
        self.assertIn("/run/user/", source)
        source = source.replace("PATH=/usr/bin:/bin:/usr/sbin:/sbin",
                                "PATH=" + shlex.quote(str(self.fakebin)))
        source = source.replace("/run/user/", str(self.runtime) + "/")
        self.script.write_text(source)
        self.set_collector_status(0)
        (self.kit / "SHA256SUMS").write_text("fixture package checksum metadata\n")
        self.write_checksums()
        self.environment = {
            "PATH": str(self.fakebin), "LC_ALL": "C", "SUDO_USER": "alice",
            "HOME": str(self.root / "root home"), "USER": "root", "LOGNAME": "root",
            "XDG_RUNTIME_DIR": "/poison/runtime", "DBUS_SESSION_BUS_ADDRESS": "poison:bus",
            "PULSE_SERVER": "poison:pulse", "PIPEWIRE_REMOTE": "poison:pipewire",
            "ROOT_ONLY_SETTING": "must not reach desktop commands",
        }

    def command_source(self):
        # Embed fixture locations because env -i must remove test/root variables
        # too. The fake runuser really executes env -i, without changing users.
        return f"""#!{sys.executable}
import hashlib
import json
import os
from pathlib import Path
import sys

root = Path({str(self.root)!r})
fakebin = Path({str(self.fakebin)!r})
name = Path(sys.argv[0]).name
args = sys.argv[1:]
keys = ('PATH', 'LC_ALL', 'HOME', 'USER', 'LOGNAME', 'XDG_RUNTIME_DIR',
        'DBUS_SESSION_BUS_ADDRESS', 'PULSE_SERVER', 'PIPEWIRE_REMOTE',
        'ROOT_ONLY_SETTING', 'SUDO_USER')
with open({str(self.calls)!r}, 'a') as log:
    log.write(json.dumps({{'command': name, 'args': args, 'cwd': os.getcwd(),
                          'environment': {{key: os.environ.get(key) for key in keys}}}}) + '\\n')
failure = json.loads(Path({str(self.config)!r}).read_text()).get(name)
if failure:
    print('fixture optional command failed', file=sys.stderr)
    sys.exit(failure)
if name == 'uname':
    print('Linux' if args == ['-s'] else 'Linux fixture 6.19.0-t6040 aarch64')
elif name == 'id':
    print('1000' if args == ['-u', 'alice'] else '0')
elif name == 'getent':
    print('alice:x:1000:1000:Alice:' + {str(self.home)!r} + ':/bin/sh')
elif name == 'sha256sum':
    failed = False
    for line in Path(args[1]).read_text().splitlines():
        digest, filename = line.split('  ', 1)
        valid = hashlib.sha256(Path(filename).read_bytes()).hexdigest() == digest
        print(filename + (': OK' if valid else ': FAILED'))
        failed = failed or not valid
    sys.exit(1 if failed else 0)
elif name == 'date':
    print('20261005T123456Z' if args[-1] == '+%Y%m%dT%H%M%SZ' else '2026-10-05T12:34:56Z')
elif name == 'cat':
    for filename in args:
        path = Path(filename)
        if filename.startswith('/proc/'):
            print('fixture Linux virtual file: ' + filename)
        elif path.is_relative_to(root):
            sys.stdout.write(path.read_text())
        else:
            print('host file query suppressed by fixture: ' + filename)
elif name == 'timeout':
    # The capture is synchronous and small; preserve child exit status.
    command = args[3:]
    os.execv(str(fakebin / command[0]), command)
elif name == 'runuser':
    assert args[:3] == ['-u', 'alice', '--'], args
    command = args[3:]
    assert command[:2] == ['env', '-i'], command
    os.execv(str(fakebin / command[0]), command)
elif name == 'bluetoothctl' and args[:1] == ['devices']:
    print('Device 00:11:22:33:44:55 Fixture headset')
else:
    print('fixture ' + name + ' ' + ' '.join(args))
"""

    def set_collector_status(self, status):
        self.collector.write_text(
            '#!/bin/sh\n[ "$1" = --output ] || exit 2\n'
            'printf "Core driver evidence\\n" > "$2"\n'
            f"exit {status}\n")

    def write_checksums(self):
        files = (self.script, self.collector)
        (self.kit / "DIAGNOSTICS-SHA256SUMS").write_text("".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in files))

    def session_bus(self):
        bus = socket.socket(socket.AF_UNIX)
        self.addCleanup(bus.close)
        try:
            bus.bind(str(self.bus))
        except PermissionError:
            self.skipTest("Sandbox does not permit binding the temporary AF_UNIX session socket")

    def capture(self, *arguments):
        return subprocess.run(["/bin/sh", str(self.script), *map(str, arguments)],
                              cwd=self.cwd, env=self.environment, text=True,
                              capture_output=True, timeout=15, stdin=subprocess.DEVNULL)

    def logged(self, command=None):
        entries = [json.loads(line) for line in self.calls.read_text().splitlines()]
        return [entry for entry in entries if command is None or entry["command"] == command]

    def assert_complete(self, report):
        self.assertTrue((report / "COMPLETE.txt").is_file())
        self.assertFalse((report / "INCOMPLETE.txt").exists())
        archive = Path(str(report) + ".tar.gz")
        self.assertTrue(archive.is_file())
        self.assertEqual(list(report.parent.glob(report.name + ".tar.gz.partial.*")), [])
        expected = {
            "capture-info.txt", "01-current-state-time.txt", "01-current-state-drivers.txt",
            "01-current-state-access.txt", "bluetooth-system.txt", "bluetooth-audio.txt",
            "input-display-audio.txt", "COMPLETE.txt",
        }
        self.assertEqual({path.name for path in report.iterdir()}, expected)
        with tarfile.open(archive, "r:gz") as saved:
            self.assertEqual({item.name for item in saved.getmembers() if item.isfile()},
                             {f"{report.name}/{name}" for name in expected})
            for name in expected:
                self.assertEqual(saved.extractfile(f"{report.name}/{name}").read(),
                                 (report / name).read_bytes())

    def test_capture_archives_core_audio_and_metadata_with_isolated_desktop_environment(self):
        self.session_bus()
        xorg = self.home / ".local/share/xorg/Xorg.0.log"
        xorg.parent.mkdir(parents=True)
        xorg.write_text("selected user's Xorg evidence\n")
        result = self.capture("--non-interactive", "--output", self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_complete(self.output)
        info = (self.output / "capture-info.txt").read_text()
        for value in (f"Update directory: {self.kit}", f"Report directory: {self.output}",
                      "Desktop user: alice", "UID: 1000", f"HOME: {self.home}",
                      "Interactive USB phases: 0", "UTC: 20261005T123456Z",
                      "fixture package checksum metadata", "Diagnostic helper checksums:",
                      (self.kit / "DIAGNOSTICS-SHA256SUMS").read_text()):
            self.assertIn(value, info)
        self.assertEqual((self.output / "01-current-state-drivers.txt").read_text(),
                         "Core driver evidence\n")
        self.assertIn(xorg.read_text(), (self.output / "input-display-audio.txt").read_text())
        self.assertIn("Saved diagnostics:", result.stdout)
        self.assertEqual(len(self.logged("sync")), 1)
        self.assertEqual(self.logged("pacman")[0]["args"][:2], ["-Q", "linux-m4rch"])
        audio_commands = self.logged("wpctl") + self.logged("pw-dump") + self.logged("pactl")
        audio_commands += [entry for entry in self.logged()
                           if entry["command"] in ("systemctl", "journalctl")
                           and entry["args"][:1] == ["--user"]]
        self.assertEqual(len(audio_commands), 7)
        for entry in audio_commands:
            self.assertEqual(entry["cwd"], "/")
            self.assertEqual(entry["environment"], {
                "PATH": str(self.fakebin), "LC_ALL": "C", "HOME": str(self.home),
                "USER": "alice", "LOGNAME": "alice", "XDG_RUNTIME_DIR": str(self.bus.parent),
                "DBUS_SESSION_BUS_ADDRESS": f"unix:path={self.bus}", "PULSE_SERVER": None,
                "PIPEWIRE_REMOTE": None, "ROOT_ONLY_SETTING": None, "SUDO_USER": None,
            })
        for entry in self.logged("runuser"):
            self.assertEqual(entry["cwd"], "/")
            self.assertEqual(entry["args"][:5], ["-u", "alice", "--", "env", "-i"])
        self.assertIn(["info", "00:11:22:33:44:55"],
                      [entry["args"] for entry in self.logged("bluetoothctl")])

    def test_absent_session_bus_is_reported_and_capture_completes(self):
        result = self.capture("--non-interactive", "--output", self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_complete(self.output)
        self.assertIn("No desktop session bus for the selected user.",
                      (self.output / "bluetooth-audio.txt").read_text())
        self.assertEqual(self.logged("wpctl") + self.logged("pw-dump") + self.logged("pactl"), [])

    def test_optional_missing_and_failed_commands_are_recorded_without_aborting(self):
        self.session_bus()
        (self.fakebin / "rfkill").unlink()
        self.config.write_text(json.dumps({"bluetoothctl": 17, "wpctl": 9, "pacman": 23}))
        result = self.capture("--non-interactive", "--output", self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_complete(self.output)
        system = (self.output / "bluetooth-system.txt").read_text()
        self.assertIn("Command unavailable.", system)
        self.assertIn("Command exit status: 17", system)
        self.assertIn("Command exit status: 9", (self.output / "bluetooth-audio.txt").read_text())
        self.assertIn("Command exit status: 23", (self.output / "capture-info.txt").read_text())

    def test_tampered_helper_stops_before_creating_output(self):
        self.collector.write_text(self.collector.read_text() + "# changed after checksumming\n")
        result = self.capture("--non-interactive", "--output", self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("m4rch-driver-diagnostics: FAILED", result.stdout)
        self.assertFalse(self.output.exists())
        self.assertFalse(Path(str(self.output) + ".tar.gz").exists())
        self.assertEqual(self.logged("timeout") + self.logged("sync"), [])

    def test_core_collector_failure_retains_incomplete_evidence_without_archive(self):
        self.set_collector_status(7)
        self.write_checksums()
        result = self.capture("--non-interactive", "--output", self.output)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn("Capture incomplete; existing evidence is in", result.stderr)
        self.assertTrue((self.output / "INCOMPLETE.txt").is_file())
        self.assertTrue((self.output / "capture-info.txt").is_file())
        self.assertEqual((self.output / "01-current-state-drivers.txt").read_text(),
                         "Core driver evidence\n")
        self.assertFalse((self.output / "COMPLETE.txt").exists())
        self.assertFalse(Path(str(self.output) + ".tar.gz").exists())
        self.assertEqual(self.logged("sync"), [])
        self.assertNotIn("Saved diagnostics:", result.stdout)

    def test_existing_and_symlink_output_preserve_previous_evidence(self):
        target = self.root / "previous evidence"
        target.mkdir()
        preserved = target / "preserve.txt"
        preserved.write_text("previous report\n")
        symlink = self.root / "report symlink"
        symlink.symlink_to(target, target_is_directory=True)
        dangling = self.root / "dangling report"
        dangling.symlink_to(self.root / "missing target")
        for output in (target, symlink, dangling):
            with self.subTest(output=output.name):
                result = self.capture("--non-interactive", "--output", output)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Output already exists", result.stderr)
                self.assertFalse(Path(str(output) + ".tar.gz").exists())
                self.assertEqual(preserved.read_text(), "previous report\n")
        self.assertTrue(symlink.is_symlink())
        self.assertTrue(dangling.is_symlink())
        self.assertEqual(list(target.iterdir()), [preserved])
        self.assertEqual(self.logged("timeout") + self.logged("sync"), [])

    def test_existing_archive_is_preserved_before_output_creation(self):
        archive = Path(str(self.output) + ".tar.gz")
        archive.write_bytes(b"previous archive")
        result = self.capture("--non-interactive", "--output", self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(archive.read_bytes(), b"previous archive")
        self.assertFalse(self.output.exists())
        self.assertEqual(self.logged("timeout") + self.logged("sync"), [])

    def test_nonterminal_interactive_capture_stops_before_output_or_collector(self):
        result = self.capture("--output", self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Interactive capture needs a terminal", result.stderr)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.logged("sha256sum") + self.logged("timeout"), [])

    def test_default_reports_and_archives_are_unique_even_in_the_same_second(self):
        for _ in range(2):
            result = self.capture("--non-interactive")
            self.assertEqual(result.returncode, 0, result.stderr)
        reports = sorted(path for path in self.root.glob("diagnostics-20261005T123456Z-*")
                         if path.is_dir())
        self.assertEqual(len(reports), 2)
        self.assertNotEqual(reports[0], reports[1])
        for report in reports:
            self.assert_complete(report)
        self.assertEqual(len(list(self.root.glob("diagnostics-*.tar.gz"))), 2)


if __name__ == "__main__":
    unittest.main()
