from pathlib import Path
import struct
import copy
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib"))
sys.path.insert(0, str(PROJECT))
from sdboot import peripheral_policy as policy


def cell(value):
    return struct.pack(">I", value)


def baseline():
    nodes = {"/": {}, "/soc": {}, "/cpus": {},
             "/soc/smc@50c600000": {}, policy.HWMON: {"compatible": b"apple,smc-hwmon\0"}}
    for index, address in enumerate((0x210e20000, 0x211e20000, 0x212e20000)):
        nodes[f"/soc/cpufreq@{address:x}"] = {
            "compatible": b"apple,t8112-cluster-cpufreq\0",
            "reg": struct.pack(">IIII", address >> 32, address & 0xffffffff, 0, 4096),
            "phandle": cell(10 + index), "#performance-domain-cells": cell(0)}
        table = f"/opp-table-{index}"
        nodes[table] = {"compatible": b"operating-points-v2\0", "opp-shared": b"", "phandle": cell(20 + index)}
        for level, mhz in enumerate(policy.E_MHZ if index == 0 else policy.P_MHZ, 1):
            nodes[f"{table}/opp{level}"] = {"opp-level": cell(level), "opp-hz": struct.pack(">Q", mhz * 1000000)}
        mpidr = (0, 0x10100, 0x10200)[index]
        nodes[f"/cpus/cpu@{mpidr:x}"] = {
            "device_type": b"cpu\0", "reg": struct.pack(">Q", mpidr),
            "performance-domains": cell(10 + index), "operating-points-v2": cell(20 + index)}
    for prefix, keys in (("temperature", policy.TEMPERATURE_KEYS), ("fan", policy.FAN_KEYS)):
        for key in keys:
            nodes[f"{policy.HWMON}/{prefix}-{key}"] = {"apple,key-id": key.encode() + b"\0", "label": b"sensor\0"}
    return nodes


def usb_graph():
    controller, connector = policy.USB_RIGHT, policy.USB_CONNECTOR
    return {
        "/": {}, "/soc": {}, "/soc/spmi@509198000": {},
        "/soc/spmi@509198000/usb-pd@c": {},
        controller: {"arch-m4,usb-wait-for-cable": b"", "usb-role-switch": b"",
                     "apple,force-host-mode": b"", "dr_mode": b"host\0",
                     "maximum-speed": b"high-speed\0"},
        connector: {"data-role": b"host\0", "power-role": b"source\0"},
        controller + "/port": {}, connector + "/port": {},
        controller + "/port/endpoint": {"phandle": cell(30), "remote-endpoint": cell(31)},
        connector + "/port/endpoint": {"phandle": cell(31), "remote-endpoint": cell(30)},
    }


class PeripheralPolicyTests(unittest.TestCase):
    def test_three_clusters_and_temperatures_are_not_native_success_claim(self):
        result = policy.check_nodes(baseline())
        self.assertEqual(result["cpufreq_domains"], 3)
        self.assertFalse(result["native_frequency_transitions_verified"])
        self.assertEqual(result["temperature_keys"], ["TH0x", "TB0T", "TCHP", "TW0P"])

    def test_wrong_cpu_domain_or_shared_p_cluster_table_fails(self):
        for prop, value in (("performance-domains", 11), ("operating-points-v2", 21)):
            with self.subTest(prop=prop):
                nodes = baseline()
                nodes["/cpus/cpu@10200"][prop] = cell(value)
                with self.assertRaisesRegex(ValueError, "cluster/OPP"):
                    policy.check_nodes(nodes)

    def test_overflowed_p_cluster_frequency_is_rejected(self):
        nodes = baseline()
        nodes["/opp-table-1/opp19"]["opp-hz"] = struct.pack(">Q", 4512000000 & 0xffffffff)
        with self.assertRaisesRegex(ValueError, "operating points"):
            policy.check_nodes(nodes)

    def test_disabled_parent_and_missing_fan_cannot_pass(self):
        nodes = baseline()
        nodes["/soc/smc@50c600000"]["status"] = b"disabled\0"
        with self.assertRaisesRegex(ValueError, "disabled"):
            policy.check_nodes(nodes)
        nodes = baseline()
        del nodes[policy.HWMON + "/fan-F1Ac"]
        with self.assertRaisesRegex(ValueError, "missing"):
            policy.check_nodes(nodes)

    def test_missing_config_stops_before_dtb_parse(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config"
            config.write_text("\n".join("CONFIG_" + name + "=y" for name in policy.REQUIRED_CONFIG if name != "ARM_APPLE_SOC_CPUFREQ"))
            with self.assertRaisesRegex(ValueError, "ARM_APPLE_SOC_CPUFREQ"):
                policy.check_build(config, Path(temporary) / "missing.dtb")

    def test_sd_overlay_requires_verified_sensor_and_fan_keys(self):
        nodes = baseline()
        nodes.update({path: props for path, props in usb_graph().items() if path not in nodes})
        for key in policy.SOC_TEMPERATURE_KEYS:
            nodes[f"{policy.HWMON}/temperature-{key}"] = {"apple,key-id": key.encode() + b"\0", "label": b"sensor\0"}
        for index in (0, 1):
            props = nodes[f"{policy.HWMON}/fan-F{index}Ac"]
            for name, suffix in (("minimum", "Mn"), ("maximum", "Mx"), ("target", "Tg"), ("mode", "Md")):
                props["apple,fan-" + name] = f"F{index}{suffix}".encode() + b"\0"
        self.assertEqual(len(policy.check_overlay_nodes(nodes)["soc_temperature_keys"]), 17)
        nodes[f"{policy.HWMON}/fan-F1Ac"]["apple,fan-target"] = b"F0Tg\0"
        with self.assertRaisesRegex(ValueError, "fan 1 target"):
            policy.check_overlay_nodes(nodes)

    def test_usb_graph_overrides_legacy_force_host_without_changing_baseline(self):
        result = policy.check_usb_overlay(usb_graph())
        self.assertTrue(result["wait_for_cable"])
        self.assertFalse(result["native_device_enumeration_verified"])

    def test_usb_graph_rejects_missing_switch_or_cable_override(self):
        for prop in ("usb-role-switch", "arch-m4,usb-wait-for-cable"):
            with self.subTest(prop=prop):
                nodes = usb_graph()
                del nodes[policy.USB_RIGHT][prop]
                with self.assertRaisesRegex(ValueError, "wait for cable"):
                    policy.check_usb_overlay(nodes)

    def test_usb_graph_rejects_one_way_links_aliases_and_disabled_pd(self):
        base = usb_graph()
        changes = (
            (policy.USB_RIGHT + "/port/endpoint", "remote-endpoint", cell(99)),
            (policy.USB_CONNECTOR + "/port/endpoint", "remote-endpoint", cell(31)),
            (policy.USB_CONNECTOR + "/port/endpoint", "phandle", cell(30)),
            ("/soc/spmi@509198000", "status", b"disabled\0"),
            (policy.USB_RIGHT, "dr_mode", b"otg\0"),
        )
        for path, prop, value in changes:
            with self.subTest(path=path, prop=prop):
                nodes = copy.deepcopy(base)
                nodes[path][prop] = value
                with self.assertRaises(ValueError):
                    policy.check_usb_overlay(nodes)

    def test_usb_graph_cannot_enable_an_unreviewed_left_port(self):
        nodes = usb_graph()
        nodes["/soc/usb@382280000"] = {"status": b"okay\0"}
        with self.assertRaisesRegex(ValueError, "unreviewed left port"):
            policy.check_usb_overlay(nodes)

    def test_runtime_reads_actual_policies_and_only_smc_without_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                "devices/system/cpu/cpufreq/policy4/scaling_driver": "apple-soc\n",
                "devices/system/cpu/cpufreq/policy4/scaling_cur_freq": "4512000\n",
                "class/hwmon/hwmon2/name": "macsmc_hwmon\n",
                "class/hwmon/hwmon2/fan1_input": "0\n",
                "class/hwmon/hwmon2/fan1_target": "0\n",
                "class/hwmon/hwmon2/fan1_max": "7826\n",
                "class/hwmon/hwmon2/temp1_label": "Battery Hotspot\n",
                "class/hwmon/hwmon2/temp1_input": "26000\n",
                "class/hwmon/hwmon9/name": "unrelated\n",
                "class/hwmon/hwmon9/temp1_input": "99999\n",
                "module/macsmc_hwmon/parameters/fan_control": "N\n"}
            for name, value in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value)
                path.chmod(0o444)
            report = policy.read_runtime(root)
            self.assertEqual(report["cpufreq"]["policy4"]["scaling_cur_freq"], "4512000")
            self.assertIsNone(report["cpufreq"]["policy4"]["cpuinfo_cur_freq"])
            self.assertEqual(report["macsmc_hwmon"]["hwmon2"]["fan1_input"], "0")
            self.assertNotIn("hwmon9", report["macsmc_hwmon"])
            self.assertFalse(report["writes_performed"])
            self.assertEqual(report["fan_control_parameter"], "N")
            for name, value in files.items():
                self.assertEqual((root / name).read_text(), value)

    def test_absent_hardware_is_reported_as_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = policy.read_runtime(Path(temporary))
            self.assertEqual(result["cpufreq"], {})
            self.assertEqual(result["macsmc_hwmon"], {})
            self.assertIsNone(result["fan_control_parameter"])
            self.assertIsNone(result["cpu"]["online"])
            self.assertIsNone(result["cpu"]["possible"])
            self.assertIsNone(result["cpu"]["present"])
            self.assertEqual(result["cpu"]["cpus"], {})
            self.assertIsNone(result["cpu"]["cpuidle"]["current_driver"])
            self.assertIsNone(result["cmdline"])
            self.assertIsNone(result["process"]["Cpus_allowed_list"])


class RuntimeSchedulingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sysfs, self.procfs = self.root / "sys", self.root / "proc"
        self.sysfs.mkdir()
        self.procfs.mkdir()

    def fixture(self, name, value, root=None):
        path = (self.sysfs if root is None else root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else value.encode())
        path.chmod(0o444)
        return path

    def report(self):
        return policy.read_runtime(self.sysfs, self.procfs)

    def test_apple_core_classification_uses_midr_and_shared_policy_membership(self):
        self.fixture("devices/system/cpu/online", "0-2,5,8-11\n")
        self.fixture("devices/system/cpu/possible", "0-11\n")
        self.fixture("devices/system/cpu/present", "0-11\n")
        self.fixture("devices/system/cpu/cpufreq/policy0/related_cpus", "0 5 6 7\n")
        self.fixture("devices/system/cpu/cpufreq/policy1/related_cpus", "1 2 3 4\n")
        self.fixture("devices/system/cpu/cpufreq/policy8/related_cpus", "8-11\n")
        # CPU0 boots on a P core; core type cannot be inferred from its number
        # or from the cpufreq policy's number.
        for cpu, midr, capacity in ((8, "0x00000000611f0551", "1024"),
                                    (1, "0x611f0541", "470"),
                                    (0, "0x611f0551", "1024"),
                                    (5, "0x611f0551", "1024")):
            self.fixture(f"devices/system/cpu/cpu{cpu}/regs/identification/midr_el1", midr)
            self.fixture(f"devices/system/cpu/cpu{cpu}/cpu_capacity", capacity)
        report = self.report()
        cpus = report["cpu"]["cpus"]
        self.assertEqual(list(cpus), ["cpu0", "cpu1", "cpu5", "cpu8"])
        self.assertEqual(cpus["cpu0"]["core_class"], "performance")
        self.assertEqual(cpus["cpu1"]["core_class"], "efficiency")
        self.assertEqual(cpus["cpu1"]["midr_implementer"], 0x61)
        self.assertEqual(cpus["cpu1"]["midr_part"], 0x054)
        self.assertEqual(cpus["cpu0"]["cpufreq_policy"], "policy0")
        self.assertEqual(cpus["cpu5"]["cpufreq_policy"], "policy0")
        self.assertEqual(cpus["cpu1"]["cpufreq_policy"], "policy1")
        self.assertEqual(cpus["cpu8"]["cpufreq_policy"], "policy8")
        self.assertEqual(cpus["cpu1"]["cpu_capacity"], "470")
        self.assertEqual(report["cpu"]["online"], "0-2,5,8-11")
        self.assertIsNone(cpus["cpu0"]["online"])
        self.assertIsNone(cpus["cpu0"]["thermal_pressure"])

    def test_unknown_midr_never_guesses_core_type_from_cpu_number(self):
        for cpu, value in ((0, "0x411f0541"), (1, "0x611f9991"), (5, "malformed")):
            self.fixture(f"devices/system/cpu/cpu{cpu}/regs/identification/midr_el1", value)
        self.fixture("devices/system/cpu/cpu8/topology/cluster_id", "2")
        cpus = self.report()["cpu"]["cpus"]
        for cpu in cpus.values():
            self.assertEqual(cpu["core_class"], "unknown")
            self.assertIsNone(cpu["cpu_capacity"])
            self.assertIsNone(cpu["cpufreq_policy"])
        self.assertIsNone(cpus["cpu5"]["midr_implementer"])
        self.assertIsNone(cpus["cpu5"]["midr_part"])
        self.assertIsNone(cpus["cpu8"]["midr"])

    def test_live_of_node_capacity_cells_topology_and_idle_states_are_read_only(self):
        files = {
            "devices/system/cpu/cpu0/of_node/capacity-dmips-mhz": cell(1024),
            "devices/system/cpu/cpu0/topology/cluster_id": "1\n",
            "devices/system/cpu/cpu0/topology/cluster_cpus_list": "0,5-7\n",
            "devices/system/cpu/cpu0/topology/thread_siblings_list": "0\n",
            "devices/system/cpu/cpu0/thermal_pressure": "0\n",
            "devices/system/cpu/cpu0/cpuidle/state0/name": "WFI\n",
            "devices/system/cpu/cpu0/cpuidle/state0/disable": "1\n",
            "devices/system/cpu/cpuidle/current_driver": "apple_idle\n",
            "devices/system/cpu/cpuidle/current_governor_ro": "menu\n",
        }
        for name, value in files.items():
            self.fixture(name, value)
        before = {name: (self.sysfs / name).read_bytes() for name in files}
        report = self.report()
        cpu = report["cpu"]["cpus"]["cpu0"]
        self.assertEqual(cpu["capacity-dmips-mhz"], 1024)
        self.assertEqual(cpu["thermal_pressure"], "0")
        self.assertEqual(cpu["topology"]["cluster_cpus_list"], "0,5-7")
        self.assertEqual(cpu["cpuidle_states"]["state0"]["name"], "WFI")
        self.assertEqual(cpu["cpuidle_states"]["state0"]["disable"], "1")
        self.assertIsNone(cpu["cpuidle_states"]["state0"]["usage"])
        self.assertEqual(report["cpu"]["cpuidle"]["current_driver"], "apple_idle")
        self.assertEqual(report["cpu"]["cpuidle"]["current_governor_ro"], "menu")
        self.assertEqual(before, {name: (self.sysfs / name).read_bytes() for name in files})

    def test_missing_and_malformed_device_tree_capacity_are_not_zero(self):
        for cpu, value in ((0, b""), (1, b"\0\0"), (2, cell(700) + b"\0")):
            self.fixture(f"devices/system/cpu/cpu{cpu}/of_node/capacity-dmips-mhz", value)
        self.fixture("devices/system/cpu/cpu3/of_node/capacity-dmips-mhz", cell(0))
        self.fixture("devices/system/cpu/cpu4/cpu_capacity", "1024")
        cpus = self.report()["cpu"]["cpus"]
        for cpu in (0, 1, 2, 4):
            self.assertIsNone(cpus[f"cpu{cpu}"]["capacity-dmips-mhz"])
        self.assertEqual(cpus["cpu3"]["capacity-dmips-mhz"], 0)

    def test_process_limits_include_parent_quotas_and_effective_cpuset(self):
        self.fixture("cmdline", "root=UUID=test idle=nop arm64.nowfxt\n", self.procfs)
        self.fixture("self/status", "Name:\tpower-report\nCpus_allowed:\t00000fe1\nCpus_allowed_list:\t0,5-11\nMems_allowed_list:\t0\n", self.procfs)
        self.fixture("self/cgroup", "0::/user.slice/session.scope\n", self.procfs)
        self.fixture("fs/cgroup/user.slice/session.scope/cpu.max", "max 100000\n")
        self.fixture("fs/cgroup/user.slice/session.scope/cpuset.cpus.effective", "0,5-11\n")
        self.fixture("fs/cgroup/user.slice/cpu.max", "100000 100000\n")
        self.fixture("fs/cgroup/user.slice/cpu.stat", "nr_throttled 19\nthrottled_usec 9000\n")
        report = self.report()
        self.assertIn("idle=nop", report["cmdline"])
        process = report["process"]
        self.assertEqual(process["scope"], "collector process")
        self.assertEqual(process["Cpus_allowed_list"], "0,5-11")
        self.assertEqual(process["cgroup_v2_path"], "/user.slice/session.scope")
        groups = process["cgroup_v2_limits"]
        self.assertEqual(groups["/user.slice/session.scope"]["cpu.max"], "max 100000")
        self.assertEqual(groups["/user.slice/session.scope"]["cpuset.cpus.effective"], "0,5-11")
        self.assertEqual(groups["/user.slice"]["cpu.max"], "100000 100000")
        self.assertIn("nr_throttled 19", groups["/user.slice"]["cpu.stat"])
        self.assertIsNone(groups["/"]["cpu.max"])

    def test_cgroup_path_cannot_escape_the_injected_sysfs(self):
        self.fixture("self/cgroup", "0::/../../outside\n", self.procfs)
        self.fixture("cpu.max", "1 100000", self.root / "outside")
        process = self.report()["process"]
        self.assertIsNone(process["cgroup_v2_path"])
        self.assertEqual(process["cgroup_v2_limits"], {})

    def test_injected_sysfs_without_procfs_does_not_read_host_process_state(self):
        self.fixture("proc/cmdline", "fixture-only idle=nop\n")
        result = policy.read_runtime(self.sysfs)
        self.assertEqual(result["cmdline"], "fixture-only idle=nop")
        self.assertIsNone(result["process"]["Cpus_allowed_list"])


if __name__ == "__main__":
    unittest.main()
