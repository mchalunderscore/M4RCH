import io
import os
from pathlib import Path
import signal
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from sdboot import cpu_benchmark as cpu


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(value))


class MemoryCapture:
    def __init__(self):
        self.data = {}

    def json(self, name, value):
        self.data[name] = value

    def open(self, name):
        return io.StringIO()


class FakeProcess:
    pid = 4242

    def __init__(self, code=0):
        self.code = code
        self.returncode = None
        self.waited = False

    def poll(self):
        self.returncode = self.code
        return self.code

    def wait(self, timeout=None):
        self.waited = True
        self.returncode = self.code
        return self.code


class CpuBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sysfs, self.procfs = self.root / "sys", self.root / "proc"
        self.procfs.mkdir()
        write(self.sysfs / "devices/system/cpu/online", "0-11")
        self.account = SimpleNamespace(pw_name="alice", pw_uid=501, pw_gid=20, pw_dir="/home/alice")
        for number in range(12):
            directory = self.sysfs / f"devices/system/cpu/cpu{number}"
            part = 0x054 if 1 <= number <= 4 else 0x055
            write(directory / "regs/identification/midr_el1", hex((0x61 << 24) | (part << 4)))
            write(directory / "cpu_capacity", 1024)
            write(directory / "topology/cluster_id", 1 if 1 <= number <= 4 else (0 if number < 8 else 2))
            (directory / "of_node").mkdir()
        self.policy_root = self.sysfs / "devices/system/cpu/cpufreq"
        for index, members, maximum in ((0, "0 5 6 7", 4512000), (1, "1 2 3 4", 2592000),
                                        (8, "8 9 10 11", 4512000)):
            directory = self.policy_root / f"policy{index}"
            for name, value in {"related_cpus": members, "scaling_governor": "schedutil",
                                "scaling_available_governors": "schedutil performance powersave",
                                "scaling_min_freq": 1020000, "scaling_max_freq": maximum,
                                "scaling_cur_freq": maximum, "cpuinfo_cur_freq": 3924000}.items():
                write(directory / name, value)
        self.topology = cpu.discover(self.sysfs, set(range(12)))

    def governor(self, name):
        return cpu.read(self.policy_root / name / "scaling_governor")

    def test_shuffled_native_numbering_and_policy_classes(self):
        self.assertEqual(cpu.select_cpus(self.topology, "performance"), {0, 5, 6, 7, 8, 9, 10, 11})
        self.assertEqual(cpu.select_cpus(self.topology, "efficiency"), {1, 2, 3, 4})
        self.assertEqual(cpu.select_cpus(self.topology, "p0"), {0, 5, 6, 7})
        self.assertEqual(cpu.select_cpus(self.topology, "p1"), {8, 9, 10, 11})
        self.assertEqual(cpu.select_cpus(self.topology, "0,5-11"), {0, 5, 6, 7, 8, 9, 10, 11})

    def test_allowed_mask_filters_classes_and_rejects_explicit_excluded_cpu(self):
        limited = cpu.discover(self.sysfs, {0, 1, 8, 9})
        self.assertEqual(cpu.select_cpus(limited, "all"), {0, 1, 8, 9})
        self.assertEqual(cpu.select_cpus(limited, "performance"), {0, 8, 9})
        self.assertEqual(cpu.select_cpus(limited, "p1"), {8, 9})
        with self.assertRaisesRegex(ValueError, "excluded"):
            cpu.select_cpus(limited, "0,5")

    def test_unknown_midr_fails_class_selection_instead_of_frequency_guess(self):
        write(self.sysfs / "devices/system/cpu/cpu0/regs/identification/midr_el1", "0x410fd0c0")
        topology = cpu.discover(self.sysfs, set(range(12)))
        self.assertEqual(cpu.select_cpus(topology, "all"), set(range(12)))
        for selection in ("performance", "efficiency", "p0", "p1"):
            with self.subTest(selection=selection), self.assertRaisesRegex(ValueError, "MIDR"):
                cpu.select_cpus(topology, selection)

    def test_capacity_reads_live_cpu_and_big_endian_dt_values_separately(self):
        directory = self.sysfs / "devices/system/cpu/cpu1"
        write(directory / "cpu_capacity", 600)
        (directory / "of_node/capacity-dmips-mhz").write_bytes(struct.pack(">I", 741))
        item = cpu.discover(self.sysfs, {1})["cpus"][1]
        self.assertEqual((item["capacity"], item["dt_capacity_dmips_mhz"]), (600, 741))
        self.assertIsNone(self.topology["cpus"][0]["dt_capacity_dmips_mhz"])

    def test_performance_changes_selected_policy_only_and_restores_bounds(self):
        selected = cpu.select_cpus(self.topology, "p0")
        policies = cpu.policies_for(self.topology, selected)
        self.assertEqual([item["name"] for item in policies], ["policy0"])
        with patch.object(cpu.os, "geteuid", return_value=0):
            transaction = cpu.Governors(policies, "performance")
            with transaction:
                self.assertEqual(self.governor("policy0"), "performance")
                self.assertEqual(self.governor("policy1"), "schedutil")
                self.assertEqual(self.governor("policy8"), "schedutil")
                self.assertEqual(cpu.integer(self.policy_root / "policy0/scaling_max_freq"), 4512000)
        self.assertEqual(self.governor("policy0"), "schedutil")
        self.assertEqual(transaction.restoration[0]["restored"], True)

    def test_validation_of_all_policies_precedes_first_write(self):
        write(self.policy_root / "policy8/scaling_available_governors", "powersave")
        with patch.object(cpu.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(ValueError, "policy8"):
                with cpu.Governors(self.topology["policies"], "performance"):
                    self.fail("Unexpected successful transaction")
        self.assertTrue(all(self.governor(item["name"]) == "schedutil" for item in self.topology["policies"]))

    def test_partial_write_failure_restores_failed_and_preceding_policy(self):
        original_write = Path.write_text

        def fail_after_write(path, text, *args, **kwargs):
            result = original_write(path, text, *args, **kwargs)
            if path == self.policy_root / "policy8/scaling_governor" and text.strip() == "performance":
                raise OSError("partial write")
            return result

        policies = cpu.policies_for(self.topology, cpu.select_cpus(self.topology, "performance"))
        transaction = cpu.Governors(policies, "performance")
        with patch.object(cpu.os, "geteuid", return_value=0), patch.object(Path, "write_text", fail_after_write):
            with self.assertRaisesRegex(OSError, "partial write"):
                with transaction:
                    self.fail("Unexpected successful transaction")
        self.assertEqual(self.governor("policy0"), "schedutil")
        self.assertEqual(self.governor("policy8"), "schedutil")
        self.assertEqual(len(transaction.restoration), 2)
        self.assertTrue(all(item["restored"] for item in transaction.restoration))

    def test_root_workload_guard_and_target_home(self):
        root = SimpleNamespace(pw_name="root", pw_uid=0, pw_gid=0, pw_dir="/root")
        with patch.object(cpu.os, "geteuid", return_value=0), patch.dict(cpu.os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "must not run as root"):
                cpu.workload_user()
            with patch.object(cpu.pwd, "getpwnam", return_value=root):
                with self.assertRaisesRegex(ValueError, "must not be root"):
                    cpu.workload_user("root")
            with patch.object(cpu.pwd, "getpwnam", return_value=self.account):
                self.assertEqual(cpu.workload_user("alice").pw_dir, "/home/alice")
        with patch.object(cpu.os, "geteuid", return_value=1000), patch.object(cpu.pwd, "getpwnam", return_value=self.account):
            with self.assertRaisesRegex(ValueError, "different"):
                cpu.workload_user("alice")

    def test_child_drops_groups_gid_uid_after_setting_inherited_affinity(self):
        calls = []
        with patch.object(cpu.os, "geteuid", side_effect=[0, 501]), \
                patch.object(cpu.os, "sched_setaffinity", create=True, side_effect=lambda *args: calls.append(("affinity", args))), \
                patch.object(cpu.os, "initgroups", side_effect=lambda *args: calls.append(("groups", args))), \
                patch.object(cpu.os, "setgid", side_effect=lambda *args: calls.append(("gid", args))), \
                patch.object(cpu.os, "setuid", side_effect=lambda *args: calls.append(("uid", args))):
            cpu.child_setup(self.account, {0, 5})
        self.assertEqual([name for name, args in calls], ["affinity", "groups", "gid", "uid"])
        self.assertEqual(calls[-1], ("uid", (501,)))

    def experiment(self, process=None, popen_error=None, sleep=None):
        capture = MemoryCapture()
        process = process or FakeProcess()
        with patch.object(cpu.os, "geteuid", return_value=0), \
                patch.object(cpu.os, "killpg") as kill, \
                patch.object(cpu.subprocess, "Popen", side_effect=popen_error, return_value=process) as popen, \
                patch.object(cpu.time, "sleep", side_effect=sleep):
            summary = cpu.run_experiment(["/tmp/geekbench7", "literal;argument"], self.topology, {0, 5, 6, 7},
                                         self.account, capture, "performance", sysfs=self.sysfs, procfs=self.procfs)
        return summary, capture, process, popen, kill

    def test_failed_command_is_non_root_argv_without_shell_and_restores(self):
        summary, capture, process, popen, kill = self.experiment(FakeProcess(7))
        self.assertEqual(summary["returncode"], 7)
        self.assertTrue(summary["governors_restored"])
        self.assertTrue(process.waited)
        self.assertEqual(self.governor("policy0"), "schedutil")
        args, kwargs = popen.call_args
        self.assertEqual(args[0][-1], "literal;argument")
        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs["env"]["HOME"], "/home/alice")
        self.assertTrue(kwargs["start_new_session"])
        self.assertTrue(callable(kwargs["preexec_fn"]))
        self.assertEqual(capture.data["metadata.json"]["selected_cpus"], [0, 5, 6, 7])

    def test_launch_failure_restores_governors(self):
        summary, capture, process, popen, kill = self.experiment(popen_error=FileNotFoundError("missing workload"))
        self.assertIn("missing workload", summary["error"])
        self.assertTrue(summary["governors_restored"])
        self.assertEqual(self.governor("policy0"), "schedutil")
        self.assertFalse(process.waited)

    def test_sigint_and_sigterm_stop_group_and_wait_before_governor_restore(self):
        for number in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signal=number):
                process = FakeProcess(None)
                previous = signal.getsignal(number)
                original_write = Path.write_text

                def interrupt(delay):
                    self.assertEqual(self.governor("policy0"), "performance")
                    signal.getsignal(number)(number, None)
                    process.code = -number

                def assert_wait_before_restore(path, text, *args, **kwargs):
                    if path.name == "scaling_governor" and text.strip() == "schedutil":
                        self.assertTrue(process.waited)
                    return original_write(path, text, *args, **kwargs)

                with patch.object(Path, "write_text", assert_wait_before_restore):
                    summary, capture, process, popen, kill = self.experiment(process, sleep=interrupt)
                self.assertEqual(summary["signal"], number)
                self.assertEqual(summary["returncode"], -number)
                self.assertTrue(summary["governors_restored"])
                self.assertEqual(self.governor("policy0"), "schedutil")
                self.assertEqual(signal.getsignal(number), previous)
                kill.assert_any_call(4242, number)

    def test_final_snapshot_failure_does_not_hide_restore_or_signal_handlers(self):
        original_snapshot = cpu.snapshot
        calls = []

        def flaky_snapshot(*args, **kwargs):
            calls.append(True)
            if len(calls) == 3:
                raise PermissionError("sensor disappeared")
            return original_snapshot(*args, **kwargs)

        previous = signal.getsignal(signal.SIGTERM)
        with patch.object(cpu, "snapshot", flaky_snapshot):
            summary, capture, process, popen, kill = self.experiment()
        self.assertEqual(summary["after_error"], "sensor disappeared")
        self.assertTrue(summary["governors_restored"])
        self.assertEqual(self.governor("policy0"), "schedutil")
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)
        self.assertIn("summary.json", capture.data)

    def test_ignored_signal_stops_sampling_and_escalates_without_busy_loop(self):
        class IgnoringProcess(FakeProcess):
            def __init__(self):
                super().__init__(None)
                self.polls = 0
                self.wait_timeouts = []

            def poll(self):
                self.polls += 1
                return None

            def wait(self, timeout=None):
                self.wait_timeouts.append(timeout)
                if timeout is not None:
                    raise cpu.subprocess.TimeoutExpired("workload", timeout)
                self.waited = True
                self.returncode = -signal.SIGKILL
                return self.returncode

        process = IgnoringProcess()

        def interrupt(delay):
            signal.getsignal(signal.SIGINT)(signal.SIGINT, None)

        summary, capture, process, popen, kill = self.experiment(process, sleep=interrupt)
        self.assertEqual(summary["samples"], 1)
        self.assertLess(process.polls, 10)
        self.assertEqual(process.wait_timeouts, [5, None])
        self.assertEqual(summary["returncode"], -signal.SIGKILL)
        self.assertTrue(summary["governors_restored"])
        self.assertEqual(self.governor("policy0"), "schedutil")
        kill.assert_any_call(4242, signal.SIGKILL)

    def test_original_governors_are_written_before_mutation(self):
        capture = MemoryCapture()
        original_json = capture.json

        def assert_metadata(name, value):
            if name == "metadata.json":
                self.assertEqual(self.governor("policy0"), "schedutil")
                self.assertEqual(list(value["original_governors"].values()), ["schedutil"])
            original_json(name, value)

        capture.json = assert_metadata
        with patch.object(cpu.os, "geteuid", return_value=0), patch.object(cpu.os, "killpg"), \
                patch.object(cpu.subprocess, "Popen", return_value=FakeProcess()):
            cpu.run_experiment(["workload"], self.topology, {0}, self.account, capture,
                               "performance", sysfs=self.sysfs, procfs=self.procfs)

    def test_restoration_failure_is_visible(self):
        original_write = Path.write_text

        def fail_restore(path, text, *args, **kwargs):
            if path.name == "scaling_governor" and text.strip() == "schedutil":
                raise OSError("policy went away")
            return original_write(path, text, *args, **kwargs)

        with patch.object(Path, "write_text", fail_restore):
            summary, capture, process, popen, kill = self.experiment()
        self.assertFalse(summary["governors_restored"])
        self.assertIn("policy went away", summary["governor_restoration"][0]["error"])

    def test_affinity_escape_is_counted_when_workload_broadens_its_mask(self):
        fields = ["0"] * 49
        fields[0], fields[2], fields[36] = "R", "4242", "5"
        text = "4242 (workload) " + " ".join(fields)
        write(self.procfs / "4242/stat", text)
        write(self.procfs / "4242/task/4242/stat", text)
        write(self.procfs / "4242/task/4242/status", "Cpus_allowed_list:\t0-11\n")
        summary, capture, process, popen, kill = self.experiment()
        self.assertEqual(summary["affinity_escape_samples"], 1)

    def test_programmatic_root_account_guard_precedes_governor_changes(self):
        root = SimpleNamespace(pw_name="root", pw_uid=0, pw_gid=0, pw_dir="/root")
        with self.assertRaisesRegex(ValueError, "must not be root"):
            cpu.run_experiment(["workload"], self.topology, {0}, root, MemoryCapture(),
                               "performance", sysfs=self.sysfs, procfs=self.procfs)
        self.assertEqual(self.governor("policy0"), "schedutil")

    def test_requested_and_hardware_clock_peaks_remain_distinct(self):
        sample = cpu.snapshot(self.topology, sysfs=self.sysfs, procfs=self.procfs)
        peaks = {}
        cpu.update_peaks(peaks, sample)
        self.assertEqual(peaks["policies"]["policy0"]["scaling_cur_freq_peak_khz"], 4512000)
        self.assertEqual(peaks["policies"]["policy0"]["cpuinfo_cur_freq_peak_khz"], 3924000)
        self.assertIsNone(sample["cpu_runtime"]["0"]["thermal_pressure"])

    def test_process_stat_names_with_parentheses_and_thread_affinity(self):
        fields = ["0"] * 49
        fields[0], fields[1], fields[2], fields[11], fields[12], fields[36] = "R", "1", "4242", "10", "3", "5"
        text = "4242 (benchmark (worker)) " + " ".join(fields)
        write(self.procfs / "4242/stat", text)
        write(self.procfs / "4242/task/4242/stat", text)
        write(self.procfs / "4242/task/4242/status", "Cpus_allowed_list:\t0,5-11\n")
        rows = cpu.placement(self.procfs, 4242)
        self.assertEqual(rows[0]["name"], "benchmark (worker)")
        self.assertEqual(rows[0]["cpu"], 5)
        self.assertEqual(rows[0]["allowed_cpus"], [0, 5, 6, 7, 8, 9, 10, 11])

    def test_cgroup_ancestor_quota_and_cpuset_are_recorded(self):
        write(self.procfs / "self/cgroup", "0::/user.slice/session.scope")
        write(self.sysfs / "fs/cgroup/cpu.max", "max 100000")
        write(self.sysfs / "fs/cgroup/user.slice/cpu.max", "200000 100000")
        write(self.sysfs / "fs/cgroup/user.slice/session.scope/cpuset.cpus.effective", "0-11")
        report = cpu.cgroup_report(self.sysfs, self.procfs)
        self.assertEqual(report["limits"][str(self.sysfs / "fs/cgroup/user.slice")]["cpu.max"], "200000 100000")
        self.assertEqual(len(report["limits"]), 3)

    def test_capture_is_fresh_rejects_existing_and_symlink_files(self):
        account = SimpleNamespace(pw_uid=os.geteuid(), pw_gid=os.getegid())
        output = self.root / "capture"
        capture = cpu.Capture(output, account)
        try:
            capture.json("metadata.json", {"test": True})
            with self.assertRaises(FileExistsError):
                capture.json("metadata.json", {})
            (output / "summary.json").symlink_to(self.root / "outside")
            with self.assertRaises(FileExistsError):
                capture.json("summary.json", {})
            with self.assertRaises(FileExistsError):
                cpu.Capture(output, account)
        finally:
            capture.close()
        self.assertFalse((self.root / "outside").exists())


if __name__ == "__main__":
    unittest.main()
