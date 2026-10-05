#!/usr/bin/env python3
"""Run a CPU experiment without changing boot files, frequency limits or fans.

Only an explicitly selected performance governor is temporary. The workload
runs as a non-root account, with inherited CPU affinity and its own process
group. Captures distinguish requested clocks from hardware clock readings.
"""
from __future__ import annotations

import argparse
from contextlib import AbstractContextManager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import pwd
import re
import signal
import stat
import subprocess
import sys
import time


def read(path, limit=1048576):
    try:
        with Path(path).open() as stream:
            return stream.read(limit).strip()
    except (OSError, UnicodeError):
        return None


def integer(path):
    value = read(path)
    try:
        return int(value, 0) if value is not None else None
    except ValueError:
        return None


def cpu_list(value):
    """Parse the kernel's comma/range syntax, or space-separated policy CPUs."""
    result = set()
    for field in re.split(r"[\s,]+", value.strip()):
        if not field:
            continue
        match = re.fullmatch(r"([0-9]+)(?:-([0-9]+))?", field)
        if not match:
            raise ValueError(f"Invalid CPU list: {value!r}")
        first, last = int(match[1]), int(match[2] or match[1])
        if first > last or last > 65535:
            raise ValueError(f"Invalid CPU range: {field}")
        result.update(range(first, last + 1))
    return result


def discover(sysfs=Path("/sys"), allowed=None):
    cpu_root = Path(sysfs) / "devices/system/cpu"
    online = cpu_list(read(cpu_root / "online") or "")
    allowed = set(os.sched_getaffinity(0) if allowed is None else allowed)
    if not online or not (online & allowed):
        raise ValueError("No online CPUs are available to this process")
    cpus = []
    for number in sorted(online):
        directory = cpu_root / f"cpu{number}"
        midr = integer(directory / "regs/identification/midr_el1")
        implementer = (midr >> 24) & 255 if midr is not None else None
        part = (midr >> 4) & 4095 if midr is not None else None
        kind = {0x055: "performance", 0x054: "efficiency"}.get(part) if implementer == 0x61 else None
        try:
            capacity_raw = (directory / "of_node/capacity-dmips-mhz").read_bytes()
            dt_capacity = int.from_bytes(capacity_raw, "big") if len(capacity_raw) == 4 else None
        except OSError:
            dt_capacity = None
        cpus.append({"cpu": number, "allowed": number in allowed,
                     "midr": f"0x{midr:08x}" if midr is not None else None,
                     "implementer": implementer, "part": part, "class": kind,
                     "capacity": integer(directory / "cpu_capacity"),
                     "dt_capacity_dmips_mhz": dt_capacity,
                     "thermal_pressure": integer(directory / "thermal_pressure"),
                     "topology": {name: read(directory / "topology" / name) for name in
                                  ("physical_package_id", "cluster_id", "core_id",
                                   "core_cpus_list", "cluster_cpus_list")}})
    policies = []
    for directory in sorted((cpu_root / "cpufreq").glob("policy*"),
                            key=lambda path: int(path.name[6:]) if path.name[6:].isdigit() else -1):
        if not re.fullmatch(r"policy[0-9]+", directory.name):
            continue
        related = cpu_list(read(directory / "related_cpus") or read(directory / "affected_cpus") or "")
        policies.append({"name": directory.name, "cpus": sorted(related), "path": str(directory)})
    return {"online": sorted(online), "allowed": sorted(allowed), "cpus": cpus, "policies": policies}


def select_cpus(topology, selection):
    eligible = set(topology["online"]) & set(topology["allowed"])
    classes = {item["cpu"]: item["class"] for item in topology["cpus"]}
    if selection == "all":
        return eligible
    if selection in ("performance", "efficiency", "p0", "p1"):
        if any(classes.get(cpu) is None for cpu in eligible):
            raise ValueError("CPU class selection requires known Apple T6040 MIDRs on every allowed CPU")
        kind = "performance" if selection in ("p0", "p1") else selection
        selected = {cpu for cpu in eligible if classes[cpu] == kind}
        if selection in ("p0", "p1"):
            clusters = []
            for policy in topology["policies"]:
                members = set(policy["cpus"]) & set(topology["online"])
                if members and all(classes.get(cpu) == "performance" for cpu in members):
                    clusters.append(members)
            if len(clusters) != 2 or clusters[0] & clusters[1]:
                raise ValueError("P0/P1 selection requires two distinct, identifiable performance policies")
            selected = eligible & clusters[int(selection[1])]
    else:
        selected = cpu_list(selection)
        if not selected <= eligible:
            raise ValueError("Requested CPUs are offline or excluded by this process's affinity/cpuset")
    if not selected:
        raise ValueError("The selected CPU class has no allowed online CPUs")
    return selected


def policies_for(topology, selected):
    return [item for item in topology["policies"] if set(item["cpus"]) & selected]


class Governors(AbstractContextManager):
    """Validate every policy before changing one; restore even a partial write."""
    def __init__(self, policies, governor=None):
        self.policies, self.governor = policies, governor
        self.originals, self.changed, self.restoration = {}, [], []

    def validate(self):
        if self.governor is None:
            return
        if not self.policies:
            raise ValueError("Selected CPUs have no cpufreq policies")
        if os.geteuid() != 0:
            raise ValueError("Temporary governor changes require sudo")
        for item in self.policies:
            path = Path(item["path"]) / "scaling_governor"
            original = read(path)
            available = (read(path.with_name("scaling_available_governors")) or "").split()
            if not original or not re.fullmatch(r"[a-zA-Z0-9_-]+", original) or self.governor not in available:
                raise ValueError(f"Cannot safely select {self.governor} on {item['name']}")
            if not os.access(path, os.W_OK):
                raise ValueError(f"Governor is not writable: {path}")
            self.originals[str(path)] = original

    def restore(self):
        for path in reversed(self.changed):
            try:
                Path(path).write_text(self.originals[path] + "\n")
                if read(path) != self.originals[path]:
                    raise OSError("governor readback differs from original")
                self.restoration.append({"path": path, "restored": True})
            except OSError as error:
                self.restoration.append({"path": path, "restored": False, "error": str(error)})
        self.changed.clear()

    def __enter__(self):
        if self.originals:
            for path, original in self.originals.items():
                if read(path) != original:
                    raise OSError(f"Governor changed during preparation; retry the experiment: {path}")
        else:
            self.validate()
        try:
            for path, original in self.originals.items():
                if original != self.governor:
                    self.changed.append(path)
                    Path(path).write_text(self.governor + "\n")
                    if read(path) != self.governor:
                        raise OSError(f"Governor selection did not stick: {path}")
        except BaseException:
            self.restore()
            raise
        return self

    def __exit__(self, *exception):
        self.restore()
        return False


def workload_user(name=None):
    """Reject a root workload before any governor or capture writes."""
    euid = os.geteuid()
    if euid == 0:
        name = name or os.environ.get("SUDO_USER")
        if not name:
            raise ValueError("Use sudo from your account, or specify --user alice; workloads must not run as root")
        account = pwd.getpwnam(name)
    else:
        account = pwd.getpwnam(name) if name else pwd.getpwuid(euid)
        if account.pw_uid != euid:
            raise ValueError("Only root may select a different --user")
    if account.pw_uid == 0:
        raise ValueError("The workload account must not be root")
    return account


def child_setup(account, cpus):
    os.sched_setaffinity(0, cpus)
    if os.geteuid() == 0:
        os.initgroups(account.pw_name, account.pw_gid)
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    if os.geteuid() == 0:
        raise PermissionError("Refusing to execute a root workload")


class Capture:
    """Pin a fresh directory by descriptor; do not follow output-file symlinks."""
    def __init__(self, path, account):
        path = Path(path).absolute()
        self.path, self.account = path, account
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        self.directory = None
        self.files = []
        try:
            os.mkdir(path.name, 0o700, dir_fd=parent)
            self.directory = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            info = os.fstat(self.directory)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise PermissionError("Capture directory ownership or permissions changed unexpectedly")
        except BaseException:
            if self.directory is not None:
                os.close(self.directory)
                self.directory = None
            raise
        finally:
            os.close(parent)

    def open(self, name):
        if not re.fullmatch(r"[a-z]+\.(?:json|jsonl)", name):
            raise ValueError("Invalid capture filename")
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=self.directory)
        self.files.append(descriptor)
        return os.fdopen(descriptor, "w", closefd=False)

    def json(self, name, value):
        with self.open(name) as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")

    def close(self):
        try:
            for descriptor in self.files:
                try:
                    if os.geteuid() == 0:
                        os.fchown(descriptor, self.account.pw_uid, self.account.pw_gid)
                finally:
                    os.close(descriptor)
            if os.geteuid() == 0 and self.directory is not None:
                os.fchown(self.directory, self.account.pw_uid, self.account.pw_gid)
        finally:
            if self.directory is not None:
                os.close(self.directory)
                self.directory = None


POLICY_FIELDS = ("affected_cpus", "related_cpus", "scaling_driver", "scaling_governor",
                 "scaling_available_governors", "scaling_min_freq", "scaling_max_freq",
                 "cpuinfo_min_freq", "cpuinfo_max_freq", "scaling_cur_freq", "cpuinfo_cur_freq",
                 "scaling_available_frequencies", "schedutil/rate_limit_us")


def sensors(sysfs):
    result = {"power": {}, "hwmon": {}}
    for directory in sorted((Path(sysfs) / "class/power_supply").glob("*")):
        result["power"][directory.name] = {name: read(directory / name) for name in
                                            ("type", "online", "status", "capacity", "voltage_now",
                                             "current_now", "power_now", "temp", "energy_now", "energy_full")}
    for directory in sorted((Path(sysfs) / "class/hwmon").glob("hwmon*")):
        if "smc" not in (read(directory / "name") or "").lower():
            continue
        values = {"name": read(directory / "name")}
        try:
            paths = sorted(directory.iterdir())
        except OSError:
            paths = []
        for path in paths:
            if re.fullmatch(r"(?:temp|fan)[0-9]+_(?:input|label|min|max|target|fault)", path.name):
                values[path.name] = read(path)
        result["hwmon"][directory.name] = values
    return result


def cgroup_report(sysfs, procfs):
    raw = read(Path(procfs) / "self/cgroup")
    result = {"membership": raw, "limits": {}}
    for line in (raw or "").splitlines():
        fields = line.split(":", 2)
        if len(fields) != 3 or fields[0:2] != ["0", ""]:
            continue
        relative = Path(fields[2].lstrip("/"))
        if ".." in relative.parts:
            continue
        root = Path(sysfs) / "fs/cgroup"
        directory = root / relative
        while directory == root or root in directory.parents:
            result["limits"][str(directory)] = {name: read(directory / name) for name in
                                                ("cpu.max", "cpu.max.burst", "cpu.stat",
                                                 "cpuset.cpus.effective")}
            if directory == root:
                break
            directory = directory.parent
    return result


def process_stat(text):
    if not text:
        return None
    try:
        prefix, tail = text.rsplit(")", 1)
        fields = tail.split()
        return {"pid": int(prefix.split(" ", 1)[0]), "name": prefix.split("(", 1)[1],
                "state": fields[0], "ppid": int(fields[1]), "group": int(fields[2]),
                "utime_ticks": int(fields[11]), "stime_ticks": int(fields[12]), "cpu": int(fields[36])}
    except (IndexError, ValueError):
        return None


def placement(procfs, group):
    threads = []
    if group is None:
        return threads
    try:
        directories = list(Path(procfs).iterdir())
    except OSError:
        return threads
    for directory in directories:
        if not directory.name.isdigit():
            continue
        leader = process_stat(read(directory / "stat"))
        if leader is None or leader["group"] != group:
            continue
        for path in sorted((directory / "task").glob("*/stat")):
            info = process_stat(read(path))
            if info is not None:
                info["process_pid"] = leader["pid"]
                status = read(path.with_name("status")) or ""
                masks = [line.split(":", 1)[1].strip() for line in status.splitlines()
                         if line.startswith("Cpus_allowed_list:")]
                info["allowed_cpus"] = sorted(cpu_list(masks[0])) if masks else None
                threads.append(info)
    return threads


def snapshot(topology, group=None, sysfs=Path("/sys"), procfs=Path("/proc")):
    result = {"timestamp": datetime.now(timezone.utc).isoformat(),
              "policies": {item["name"]: {name: read(Path(item["path"]) / name)
                                          for name in POLICY_FIELDS} for item in topology["policies"]},
              "cpu_runtime": {}, "proc_stat": read(Path(procfs) / "stat"),
              "loadavg": read(Path(procfs) / "loadavg"),
              "pressure_cpu": read(Path(procfs) / "pressure/cpu"),
              "workload_threads": placement(procfs, group)}
    for item in topology["cpus"]:
        directory = Path(sysfs) / f"devices/system/cpu/cpu{item['cpu']}"
        result["cpu_runtime"][str(item["cpu"])] = {name: integer(directory / name) for name in
                                                   ("cpu_capacity", "thermal_pressure")}
    result.update(sensors(sysfs))
    return result


def update_peaks(peaks, sample):
    for name, values in sample["policies"].items():
        policy = peaks.setdefault("policies", {}).setdefault(name, {})
        for field in ("scaling_cur_freq", "cpuinfo_cur_freq"):
            try:
                value = int(values[field])
            except (TypeError, ValueError):
                continue
            policy[field + "_peak_khz"] = max(policy.get(field + "_peak_khz", 0), value)
    for name, values in sample["hwmon"].items():
        monitor = peaks.setdefault("hwmon", {}).setdefault(name, {})
        for field, raw in values.items():
            if not re.fullmatch(r"(?:temp|fan)[0-9]+_input", field):
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                continue
            monitor[field + "_peak"] = max(monitor.get(field + "_peak", value), value)


def stop_workload(process):
    """Signal the complete inherited process group, then reap the leader."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    # A launcher can exit before its workers. Do not leave those workers using
    # the experiment's selected governor after restoring it.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_experiment(command, topology, selected, account, capture, governor=None, interval=2.0,
                   sysfs=Path("/sys"), procfs=Path("/proc")):
    if account.pw_uid == 0:
        raise ValueError("The workload account must not be root")
    transaction = Governors(policies_for(topology, selected), governor)
    process = None
    interrupted = {"signal": None}
    previous = {}
    started = time.monotonic()
    summary = {"selected_cpus": sorted(selected), "samples": 0, "peaks": {},
               "affinity_escape_samples": 0, "returncode": None, "error": None}

    def on_signal(number, frame):
        interrupted["signal"] = number
        if process is not None:
            try:
                os.killpg(process.pid, number)
            except ProcessLookupError:
                pass

    try:
        for number in (signal.SIGINT, signal.SIGTERM):
            previous[number] = signal.signal(number, on_signal)
        transaction.validate()
        capture.json("metadata.json", {"command": command, "cwd": os.getcwd(),
                                      "account": {"name": account.pw_name, "uid": account.pw_uid,
                                                  "gid": account.pw_gid, "home": account.pw_dir},
                                      "requested_governor": governor,
                                      "original_governors": dict(transaction.originals), "topology": topology,
                                      "selected_cpus": sorted(selected), "interval_seconds": interval,
                                      "kernel_command_line": read(Path(procfs) / "cmdline"),
                                      "kernel_release": read(Path(procfs) / "sys/kernel/osrelease"),
                                      "process_status": read(Path(procfs) / "self/status"),
                                      "cgroups": cgroup_report(sysfs, procfs),
                                      "before": snapshot(topology, sysfs=sysfs, procfs=procfs)})
        with transaction, capture.open("samples.jsonl") as samples:
            if interrupted["signal"] is not None:
                raise InterruptedError("Interrupted before starting the workload")
            environment = os.environ.copy()
            environment.update(HOME=account.pw_dir, USER=account.pw_name, LOGNAME=account.pw_name)
            process = subprocess.Popen(command, env=environment, cwd=os.getcwd(), start_new_session=True,
                                       preexec_fn=lambda: child_setup(account, selected))
            try:
                while True:
                    if interrupted["signal"] is not None:
                        break
                    sample = snapshot(topology, process.pid, sysfs, procfs)
                    sample["elapsed_seconds"] = round(time.monotonic() - started, 3)
                    escaped = [item["pid"] for item in sample["workload_threads"]
                               if item["cpu"] not in selected or
                               (item["allowed_cpus"] is not None and not set(item["allowed_cpus"]) <= selected)]
                    sample["affinity_escape_threads"] = escaped
                    summary["affinity_escape_samples"] += bool(escaped)
                    samples.write(json.dumps(sample, sort_keys=True) + "\n")
                    samples.flush()
                    update_peaks(summary["peaks"], sample)
                    summary["samples"] += 1
                    result = process.poll()
                    if result is not None:
                        summary["returncode"] = result
                        break
                    if interrupted["signal"] is not None:
                        break
                    # Python resumes sleep after a handled signal. Keep waits
                    # short even when the requested sample interval is long.
                    wake = time.monotonic() + interval
                    while process.poll() is None and time.monotonic() < wake:
                        if interrupted["signal"] is not None:
                            break
                        time.sleep(min(0.2, max(0.0, wake - time.monotonic())))
            finally:
                stop_workload(process)
                summary["returncode"] = process.returncode
    except BaseException as error:
        summary["error"] = str(error) or type(error).__name__
    finally:
        # __enter__ restores a failed partial change. __exit__ restores all
        # normal and interrupted workload paths after the child is stopped.
        transaction.restore()
        summary.update(duration_seconds=round(time.monotonic() - started, 3),
                       signal=interrupted["signal"], original_governors=transaction.originals,
                       governor_restoration=transaction.restoration)
        summary["governors_restored"] = all(item["restored"] for item in transaction.restoration)
        try:
            try:
                summary["after"] = snapshot(topology, sysfs=sysfs, procfs=procfs)
            except (OSError, ValueError) as error:
                summary["after_error"] = str(error)
            capture.json("summary.json", summary)
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", help="print a read-only topology and power report")
    parser.add_argument("--cpus", default="all", help="all, performance, efficiency, p0, p1, or e.g. 0,5-11; class selection reduces the multicore count")
    parser.add_argument("--governor", choices=("performance",), help="temporarily select performance on chosen policies")
    parser.add_argument("--user", help="non-root workload account; sudo uses SUDO_USER by default")
    parser.add_argument("--output", type=Path, help="fresh capture directory; its parent must already exist")
    parser.add_argument("--interval", type=float, default=2.0, help="sample interval in seconds (default: 2)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- COMMAND ARGUMENTS (no shell evaluation)")
    args = parser.parse_args(argv)
    try:
        if sys.platform != "linux" or not hasattr(os, "sched_getaffinity"):
            raise ValueError("CPU experiments require Linux; --help is available on any host")
        if not math.isfinite(args.interval) or args.interval < 0.1:
            raise ValueError("--interval must be finite and at least 0.1 seconds")
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        topology = discover()
        selected = select_cpus(topology, args.cpus)
        if args.inspect:
            if command or args.governor or args.output:
                raise ValueError("--inspect does not accept a command, governor change or output directory")
            print(json.dumps({"topology": topology, "selected_cpus": sorted(selected),
                              "cgroups": cgroup_report(Path("/sys"), Path("/proc")),
                              "kernel_command_line": read("/proc/cmdline"),
                              "runtime": snapshot(topology)}, indent=2, sort_keys=True))
            return 0
        if not command:
            raise ValueError("Provide a workload after --, or use --inspect")
        account = workload_user(args.user)
        Governors(policies_for(topology, selected), args.governor).validate()
        output = args.output or Path.cwd() / ("cpu-benchmark-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
        capture = Capture(output, account)
        try:
            summary = run_experiment(command, topology, selected, account, capture,
                                     args.governor, args.interval)
        finally:
            capture.close()
        print(f"Capture: {output.absolute()}")
        if summary["affinity_escape_samples"]:
            print("The workload changed its CPU affinity; placement escaped the selected mask (see summary.json)", file=sys.stderr)
        if not summary["governors_restored"]:
            print("Governor restoration failed; see summary.json and restore original_governors manually", file=sys.stderr)
            return 1
        if summary["error"]:
            print("m4rch: " + summary["error"], file=sys.stderr)
            return 1
        if summary["signal"] is not None:
            return 128 + summary["signal"]
        return max(0, summary["returncode"] or 0) if (summary["returncode"] or 0) >= 0 else 128 - summary["returncode"]
    except (OSError, KeyError, ValueError) as error:
        print("m4rch: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
