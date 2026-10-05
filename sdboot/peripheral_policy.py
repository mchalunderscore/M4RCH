#!/usr/bin/env python3
"""Check the existing CPU/SMC support and report native readings without writes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import struct

REQUIRED_CONFIG = (
    "CPU_FREQ", "CPU_FREQ_STAT", "ARM_APPLE_SOC_CPUFREQ", "PM_OPP",
    "CPU_FREQ_DEFAULT_GOV_SCHEDUTIL", "CPU_FREQ_GOV_SCHEDUTIL",
    "CPU_FREQ_GOV_PERFORMANCE", "CPU_FREQ_GOV_POWERSAVE",
    "MFD_MACSMC", "MACSMC_POWER", "HWMON", "SENSORS_MACSMC_HWMON",
)
HWMON = "/soc/smc@50c600000/hwmon"
TEMPERATURE_KEYS = ("TH0x", "TB0T", "TCHP", "TW0P")
FAN_KEYS = ("F0Ac", "F1Ac")
USB_RIGHT = "/soc/usb@392280000"
USB_CONNECTOR = "/soc/spmi@509198000/usb-pd@c/connector"
SOC_TEMPERATURE_KEYS = ("Te05", "Te0S", "Tp01", "Tp05", "Tp09", "Tp0D", "Tp0Y",
                        "Tp0b", "Tp0e", "Tg1U", "Tg1k", "Tg0K", "Tg0L", "Tg0d",
                        "Tg0e", "Tg0j", "Tg0k")
E_MHZ = (1020, 1404, 1788, 2112, 2352, 2532, 2592)
P_MHZ = (1260, 1512, 1800, 2088, 2352, 2616, 2868, 3096, 3300,
         3468, 3624, 3756, 3852, 3924, 3996, 4044, 4104, 4416, 4512)


def _integer(raw, length=4):
    if len(raw) != length:
        raise ValueError("Malformed CPU/SMC device-tree integer")
    return int.from_bytes(raw, "big")


def check_nodes(nodes):
    """Check the baseline that the enrolled loader and SD kernel share.

    These checks verify descriptions, not that a driver probed on hardware.
    m1n1 removes fused-off CPUs from the live tree; the baseline lists the full
    supported topology, so do not require fourteen online CPUs at runtime.
    """
    def enabled(path):
        if path not in nodes:
            raise ValueError(f"CPU/SMC node missing: {path}")
        parent = path
        while parent:
            if nodes.get(parent, {}).get("status", b"okay\0") not in (b"okay\0", b"ok\0"):
                raise ValueError(f"CPU/SMC node disabled: {parent}")
            parent = parent.rsplit("/", 1)[0]
        return nodes[path]

    domains = []
    for index, address in enumerate((0x210e20000, 0x211e20000, 0x212e20000)):
        path = f"/soc/cpufreq@{address:x}"
        props = enabled(path)
        if (props.get("compatible") != b"apple,t8112-cluster-cpufreq\0" or
                props.get("reg") != struct.pack(">IIII", address >> 32, address & 0xffffffff, 0, 0x1000) or
                props.get("#performance-domain-cells") != b"\0\0\0\0"):
            raise ValueError(f"Unexpected T6040 cpufreq register layout: {path}")
        handle = _integer(props.get("phandle", b""))
        table = f"/opp-table-{index}"
        opp = enabled(table)
        if opp.get("compatible") != b"operating-points-v2\0" or "opp-shared" not in opp:
            raise ValueError(f"Missing shared operating-points table: {table}")
        table_handle = _integer(opp.get("phandle", b""))
        frequencies = []
        for name, entry in nodes.items():
            if name.rsplit("/", 1)[0] == table:
                enabled(name)
                frequencies.append((_integer(entry.get("opp-level", b"")),
                                    _integer(entry.get("opp-hz", b""), 8)))
        expected = [(level, mhz * 1000000) for level, mhz in enumerate(E_MHZ if index == 0 else P_MHZ, 1)]
        if sorted(frequencies) != expected:
            raise ValueError(f"T6040 operating points differ from Wallace's measured table: {table}")
        domains.append((handle, table_handle))
    if len({handle for handle, _ in domains}) != 3 or len({table for _, table in domains}) != 3:
        raise ValueError("T6040 CPU clusters must have separate performance and OPP domains")
    cpu_counts = [0, 0, 0]
    for name, props in nodes.items():
        if name.rsplit("/", 1)[0] != "/cpus" or props.get("device_type") != b"cpu\0":
            continue
        if props.get("status", b"okay\0") not in (b"okay\0", b"ok\0"):
            continue
        enabled(name)
        reg = _integer(props.get("reg", b""), 8)
        cluster = {0: 0, 0x101: 1, 0x102: 2}.get(reg >> 8)
        if cluster is None or (_integer(props.get("performance-domains", b"")),
                               _integer(props.get("operating-points-v2", b""))) != domains[cluster]:
            raise ValueError(f"CPU has incorrect T6040 cluster/OPP binding: {name}")
        cpu_counts[cluster] += 1
    if not all(cpu_counts):
        raise ValueError("Each T6040 cpufreq cluster needs an enabled CPU description")
    if enabled(HWMON).get("compatible") != b"apple,smc-hwmon\0":
        raise ValueError("SMC hardware-monitor driver binding is missing")
    for prefix, keys in (("temperature", TEMPERATURE_KEYS), ("fan", FAN_KEYS)):
        for key in keys:
            props = enabled(f"{HWMON}/{prefix}-{key}")
            if props.get("apple,key-id") != key.encode() + b"\0" or not props.get("label", b"").rstrip(b"\0"):
                raise ValueError(f"SMC {key} key or label is missing")
    return {"cpufreq_domains": 3, "baseline_cpus_per_domain": cpu_counts,
            "temperature_keys": list(TEMPERATURE_KEYS), "fan_rpm_keys": list(FAN_KEYS),
            "native_frequency_transitions_verified": False}


def check_build(config_path, dtb_path):
    from boot import read_fdt
    text = Path(config_path).read_text()
    missing = [name for name in REQUIRED_CONFIG
               if not re.search(r"^CONFIG_" + name + r"=y$", text, re.MULTILINE)]
    if missing:
        raise ValueError("CPU/SMC required built-in options missing: " + ", ".join(missing))
    return check_nodes(read_fdt(Path(dtb_path)))


def check_overlay_nodes(nodes):
    """Check the merged SD DT separately, preserving the enrolled baseline."""
    result = check_nodes(nodes)
    for key in SOC_TEMPERATURE_KEYS:
        props = nodes.get(f"{HWMON}/temperature-{key}", {})
        if (props.get("apple,key-id") != key.encode() + b"\0" or
                not props.get("label", b"").rstrip(b"\0") or
                props.get("status", b"okay\0") not in (b"okay\0", b"ok\0")):
            raise ValueError(f"Verified J614s temperature key missing from SD overlay: {key}")
    for index in (0, 1):
        props = nodes[f"{HWMON}/fan-F{index}Ac"]
        for prop, suffix in (("minimum", "Mn"), ("maximum", "Mx"), ("target", "Tg"), ("mode", "Md")):
            if props.get("apple,fan-" + prop) != f"F{index}{suffix}".encode() + b"\0":
                raise ValueError(f"Verified J614s fan {index} {prop} key missing from SD overlay")
    usb = check_usb_overlay(nodes)
    return dict(result, soc_temperature_keys=list(SOC_TEMPERATURE_KEYS), usb=usb)


def check_usb_overlay(nodes):
    """Verify role events can reach the right controller after SD overlay merge.

    The legacy force-host property stays in the enrolled baseline. Its SD-only
    override must accompany the graph; a graph alone would leave DWC3 already
    in HOST and bypass the first attachment's PHY initialization.
    """
    controller = nodes.get(USB_RIGHT, {})
    connector = nodes.get(USB_CONNECTOR, {})
    if (controller.get("arch-m4,usb-wait-for-cable") != b"" or
            controller.get("usb-role-switch") != b"" or
            controller.get("dr_mode") != b"host\0" or
            controller.get("maximum-speed") != b"high-speed\0" or
            "apple,force-device-mode" in controller):
        raise ValueError("SD USB overlay must wait for cable events in USB2 host mode")
    if connector.get("data-role") != b"host\0" or connector.get("power-role") != b"source\0":
        raise ValueError("SD USB overlay must retain the right host/source connector")
    for path in ("/soc/usb@382280000", "/soc/usb@38a280000"):
        if path in nodes and nodes[path].get("status") != b"disabled\0":
            raise ValueError("SD USB overlay unexpectedly enables an unreviewed left port")
    endpoints = (USB_RIGHT + "/port/endpoint", USB_CONNECTOR + "/port/endpoint")
    handles = []
    for path in endpoints:
        parent = path
        while parent:
            props = nodes.get(parent)
            if props is None or props.get("status", b"okay\0") not in (b"okay\0", b"ok\0"):
                raise ValueError("SD USB role graph has a missing or disabled endpoint ancestor")
            parent = parent.rsplit("/", 1)[0]
        handles.append(_integer(nodes[path].get("phandle", b"")))
    if len(set(handles)) != 2 or any(handle in (0, 0xffffffff) for handle in handles):
        raise ValueError("SD USB role graph must have distinct valid endpoint phandles")
    for path, remote in zip(endpoints, reversed(handles)):
        if _integer(nodes[path].get("remote-endpoint", b"")) != remote:
            raise ValueError("SD USB role graph must have reciprocal controller/connector endpoints")
    return {"port": "right", "maximum_speed": "high-speed", "wait_for_cable": True,
            "native_device_enumeration_verified": False}


def read_runtime(sysfs=Path("/sys"), procfs=None):
    """Return evidence, including absent files; never select a policy or fan mode."""
    sysfs = Path(sysfs)
    # An injected sysfs root must not mix a fixture's hardware with this host's
    # process state. Callers can supply a separate procfs fixture explicitly.
    procfs = Path(procfs) if procfs is not None else (Path("/proc") if sysfs == Path("/sys") else sysfs / "proc")

    def read(path):
        try:
            with path.open() as stream:
                return stream.read(16384).strip()
        except (OSError, UnicodeError):
            return None

    def read_cell(path):
        try:
            with path.open("rb") as stream:
                raw = stream.read(5)
        except OSError:
            return None
        return int.from_bytes(raw, "big") if len(raw) == 4 else None

    def cpu_ids(value):
        """Accept both Linux CPU lists and CPUFreq's space-separated lists."""
        result = set()
        if value is None:
            return result
        for item in re.split(r"[\s,]+", value):
            if not item:
                continue
            match = re.fullmatch(r"(\d+)(?:-(\d+))?", item)
            if not match:
                return set()
            first = int(match[1])
            last = int(match[2]) if match[2] is not None else first
            if first > last or last > 4095:
                return set()
            result.update(range(first, last + 1))
        return result

    policy_fields = ("affected_cpus", "related_cpus", "scaling_driver", "scaling_governor",
                     "scaling_available_governors", "scaling_available_frequencies",
                     "scaling_cur_freq", "cpuinfo_cur_freq", "cpuinfo_min_freq",
                     "cpuinfo_max_freq", "scaling_min_freq", "scaling_max_freq",
                     "stats/total_trans", "stats/time_in_state")
    policies = {}
    for directory in sorted((sysfs / "devices/system/cpu/cpufreq").glob("policy*"))[:64]:
        policies[directory.name] = {name: read(directory / name) for name in policy_fields}
    cpu_root = sysfs / "devices/system/cpu"
    cpus = {}
    topology_fields = ("cluster_id", "core_id", "physical_package_id", "cluster_cpus_list",
                       "core_cpus_list", "thread_siblings_list", "core_siblings_list")
    directories = [path for path in cpu_root.glob("cpu[0-9]*") if re.fullmatch(r"cpu\d+", path.name)]
    for directory in sorted(directories, key=lambda path: int(path.name[3:]))[:4096]:
        cpu = int(directory.name[3:])
        midr = read(directory / "regs/identification/midr_el1")
        implementer = part = None
        if midr is not None and re.fullmatch(r"0[xX][0-9a-fA-F]{1,16}", midr):
            value = int(midr, 16)
            implementer, part = (value >> 24) & 0xff, (value >> 4) & 0xfff
        core_class = {0x054: "efficiency", 0x055: "performance"}.get(part, "unknown") if implementer == 0x61 else "unknown"
        memberships = [name for name, fields in policies.items() if cpu in cpu_ids(fields["related_cpus"])]
        states = {}
        for state in sorted((directory / "cpuidle").glob("state[0-9]*"))[:64]:
            if re.fullmatch(r"state\d+", state.name):
                states[state.name] = {name: read(state / name) for name in ("name", "desc", "disable", "usage", "time")}
        cpus[directory.name] = {
            "midr": midr, "midr_implementer": implementer, "midr_part": part,
            "core_class": core_class, "online": read(directory / "online"),
            "cpu_capacity": read(directory / "cpu_capacity"),
            "thermal_pressure": read(directory / "thermal_pressure"),
            "capacity-dmips-mhz": read_cell(directory / "of_node/capacity-dmips-mhz"),
            "cpufreq_policy": memberships[0] if len(memberships) == 1 else None,
            "topology": {name: read(directory / "topology" / name) for name in topology_fields},
            "cpuidle_states": states,
        }
    cpu_state = {name: read(cpu_root / name) for name in ("online", "possible", "present")}
    cpu_state["cpus"] = cpus
    cpu_state["cpuidle"] = {name: read(cpu_root / "cpuidle" / name)
                             for name in ("current_driver", "current_governor", "current_governor_ro")}
    status = read(procfs / "self/status")
    process = {"scope": "collector process", "Cpus_allowed": None, "Cpus_allowed_list": None,
               "Mems_allowed_list": None, "cgroup": read(procfs / "self/cgroup"),
               "cgroup_v2_path": None, "cgroup_v2_limits": {}}
    if status is not None:
        for line in status.splitlines():
            name, separator, value = line.partition(":")
            if separator and name in ("Cpus_allowed", "Cpus_allowed_list", "Mems_allowed_list"):
                process[name] = value.strip()
    for line in (process["cgroup"] or "").splitlines():
        fields = line.split(":", 2)
        if len(fields) != 3 or fields[:2] != ["0", ""]:
            continue
        group = fields[2]
        if not group.startswith("/") or any(part in (".", "..") for part in group.split("/")) or "\0" in group:
            continue
        process["cgroup_v2_path"] = group
        # A parent can impose a quota even when the leaf says "max". Preserve
        # the hierarchy's raw limits rather than claiming the leaf is unlimited.
        parts = [part for part in group.split("/") if part]
        if len(parts) > 32:
            continue
        for count in range(len(parts), -1, -1):
            relative = "/".join(parts[:count])
            directory = sysfs / "fs/cgroup" / relative
            process["cgroup_v2_limits"]["/" + relative] = {
                name: read(directory / name) for name in ("cpuset.cpus.effective", "cpu.max", "cpu.stat")}
        break
    sensors = {}
    for directory in sorted((sysfs / "class/hwmon").glob("hwmon*"))[:128]:
        if read(directory / "name") != "macsmc_hwmon":
            continue
        fields = {}
        for path in sorted(directory.iterdir()):
            if re.fullmatch(r"(?:temp|fan|power|in|curr)\d+_(?:input|label|min|max|target)", path.name):
                fields[path.name] = read(path)
        sensors[directory.name] = fields
    return {"schema": 1, "cpufreq": policies, "macsmc_hwmon": sensors,
            "cpu": cpu_state, "cmdline": read(procfs / "cmdline"), "process": process,
            "fan_control_parameter": read(sysfs / "module/macsmc_hwmon/parameters/fan_control"),
            "frequency_units": "kHz", "temperature_units": "millidegrees Celsius",
            "fan_units": "RPM", "writes_performed": False,
            "note": "One snapshot does not verify frequency transitions or manual fan control."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", action="store_true", help="read Linux sysfs without writes")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--dtb", type=Path)
    args = parser.parse_args()
    if args.runtime and not (args.config or args.dtb):
        result = read_runtime()
    elif args.config and args.dtb and not args.runtime:
        result = check_build(args.config, args.dtb)
    else:
        parser.error("use --runtime or both --config and --dtb")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
