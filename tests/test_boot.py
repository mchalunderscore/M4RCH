"""Artifact preflight tests; these exercise failure modes without hardware."""
import importlib.util
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import boot


def device_tree(nvme_status=b"disabled\0", sd_status=b"okay\0", model=b"apple,j614s\0apple,t6040\0"):
    names = ["compatible", "status", "mmc0", "wifi0", "bluetooth0"]
    strings, offsets = b"", {}
    for name in names:
        offsets[name] = len(strings)
        strings += name.encode() + b"\0"
    tree = bytearray()

    def start(name):
        tree.extend(struct.pack(">I", 1) + name.encode() + b"\0")
        tree.extend(b"\0" * (-len(tree) % 4))

    def end():
        tree.extend(struct.pack(">I", 2))

    def prop(name, value):
        tree.extend(struct.pack(">III", 3, len(value), offsets[name]) + value)
        tree.extend(b"\0" * (-len(tree) % 4))

    start("")
    prop("compatible", model)
    start("aliases")
    for name, path in (("mmc0", "sd"), ("wifi0", "wifi"), ("bluetooth0", "bt")):
        prop(name, ("/soc/" + path).encode() + b"\0")
    end()
    start("soc")
    for name in ("sd", "wifi", "bt", "nvme"):
        start(name)
        if name == "sd":
            prop("status", sd_status)
        if name == "nvme":
            prop("compatible", b"apple,t6040-nvme\0")
            prop("status", nvme_status)
        end()
    end()
    end()
    tree.extend(struct.pack(">I", 9))
    structure_start = 56  # header plus empty reservation map
    string_start = structure_start + len(tree)
    header = struct.pack(">10I", 0xd00dfeed, string_start + len(strings),
                         structure_start, string_start, 40, 17, 16, 0,
                         len(strings), len(tree))
    return header + bytes(16) + tree + strings


class BootPreflightTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_release_is_numeric_and_independent_of_git_or_dirty_tags(self):
        makefile = self.root / "Makefile"
        makefile.write_text("VERSION = 7\nPATCHLEVEL = 1\nSUBLEVEL = 3\nEXTRAVERSION = -dirty\n")
        self.assertEqual(boot.kernel_release(makefile), "7.1.3-m4rch")
        for content in ("VERSION=7\nPATCHLEVEL=1\n", "VERSION=7\nPATCHLEVEL=1\nSUBLEVEL=bad\n",
                        "VERSION=7\nVERSION=8\nPATCHLEVEL=1\nSUBLEVEL=3\n"):
            makefile.write_text(content)
            with self.assertRaisesRegex(ValueError, "unambiguous"):
                boot.kernel_release(makefile)

    def test_rejects_the_old_pcie_diagnostic_binary(self):
        path = self.root / "m1n1.bin"
        valid = (b"Initializing t6040 PCIe controller\0"
                 b"FDT: couldn't add reservation for M4+ SMP-RO CTRR area\0")
        path.write_bytes(valid)
        boot.check_m1n1(path)
        for marker in (b"op-115 read-only diagnostic", b"stopping before ports",
                       b"clock-tunable diagnostic complete"):
            path.write_bytes(valid + marker)
            with self.assertRaisesRegex(ValueError, "obsolete T6040 PCIe diagnostic"):
                boot.check_m1n1(path)
        path.write_bytes(b"unrelated m1n1 build")
        with self.assertRaisesRegex(ValueError, "no T6040 PCIe"):
            boot.check_m1n1(path)
        path.write_bytes(valid + b"Waiting for proxy connection")
        with self.assertRaisesRegex(ValueError, "early proxy"):
            boot.check_m1n1(path)
        path.write_bytes(b"Initializing t6040 PCIe controller\0")
        with self.assertRaisesRegex(ValueError, "no M4 SMP CTRR"):
            boot.check_m1n1(path)

    def test_trackpad_gpio_rejects_wrong_provider_pin_and_polarity(self):
        provider = "/soc/smc@50c600000/gpio@67700000"
        touch = "/soc/hid@514600000/multi-touch"
        nodes = {
            provider: {"compatible": b"apple,smc-low-gpio\0", "gpio-controller": b"",
                       "#gpio-cells": struct.pack(">I", 2), "phandle": struct.pack(">I", 123)},
            touch: {"reset-gpios": struct.pack(">III", 123, 0x1c, 1)},
        }
        boot.check_trackpad_nodes(nodes)
        for values in ((123, 0x19, 1), (123, 0x1c, 0), (456, 0x1c, 1)):
            wrong = copy.deepcopy(nodes)
            wrong[touch]["reset-gpios"] = struct.pack(">III", *values)
            with self.assertRaisesRegex(ValueError, "gp1c"):
                boot.check_trackpad_nodes(wrong)
        wrong = copy.deepcopy(nodes)
        wrong[provider]["compatible"] = b"apple,smc-gpio\0"
        with self.assertRaisesRegex(ValueError, "lowercase-gp"):
            boot.check_trackpad_nodes(wrong)
        nodes["/soc/smc@50c600000"] = {"status": b"disabled\0"}
        with self.assertRaisesRegex(ValueError, "disabled"):
            boot.check_trackpad_nodes(nodes)

    def test_trackpad_inputs_reject_modified_patch_or_wiring(self):
        project = Path(boot.__file__).resolve().parents[1]
        lock = json.loads((project / "sources.lock.json").read_text())
        self.assertEqual(set(boot.trackpad_inputs(lock)), {"patch", "overlay"})
        for key in ("patch", "overlay"):
            wrong = copy.deepcopy(lock)
            wrong["linux_trackpad"][key + "_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                boot.trackpad_inputs(wrong)
            wrong = copy.deepcopy(lock)
            wrong["linux_trackpad"][key] = "../unexpected"
            with self.assertRaisesRegex(ValueError, "path"):
                boot.trackpad_inputs(wrong)

    def test_trackpad_image_requires_host_power_sequence(self):
        path = self.root / "Image"
        path.write_bytes(b"unmodified kernel")
        with self.assertRaisesRegex(ValueError, "host power sequence"):
            boot.check_trackpad_image(path)
        path.write_bytes(b"kernel\0J614s trackpad host power sequence\0")
        with self.assertRaisesRegex(ValueError, "active-low"):
            boot.check_trackpad_image(path)
        path.write_bytes(b"kernel\0J614s trackpad active-low host power sequence\0")
        boot.check_trackpad_image(path)

    def test_smp_backports_reject_changed_inputs(self):
        project = Path(boot.__file__).resolve().parents[1]
        for name in ("m1n1_smp", "linux_smp"):
            lock = json.loads((project / "sources.lock.json").read_text())
            self.assertTrue(boot.smp_patch(lock, name).is_file())
            lock[name]["patch_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                boot.smp_patch(lock, name)
            lock[name]["files"]["../unexpected.c"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "backport paths"):
                boot.smp_patch(lock, name)

    def test_pcie_patch_must_match_locked_digest_and_path(self):
        project = Path(boot.__file__).resolve().parents[1]
        lock = json.loads((project / "sources.lock.json").read_text())
        self.assertTrue(boot.pcie_patch(lock).is_file())
        lock["m1n1_pcie"]["patch_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            boot.pcie_patch(lock)
        lock["m1n1_pcie"]["patch"] = "../different.patch"
        with self.assertRaisesRegex(ValueError, "backport path"):
            boot.pcie_patch(lock)

    def test_rejects_wrong_kernel_page_size(self):
        image = bytearray(64)
        image[0x38:0x3c] = b"ARM\x64"
        struct.pack_into("<QQ", image, 0x10, 64, 2 << 1)
        path = self.root / "Image"
        path.write_bytes(image)
        boot.check_image(path)
        struct.pack_into("<Q", image, 0x18, 1 << 1)
        path.write_bytes(image)
        with self.assertRaisesRegex(ValueError, "16 KiB"):
            boot.check_image(path)

    def test_requires_sd_and_disables_nvme(self):
        path = self.root / "apple.dtb"
        path.write_bytes(device_tree())
        boot.check_dtb(path)
        path.write_bytes(device_tree(nvme_status=b"okay\0"))
        with self.assertRaisesRegex(ValueError, "NVMe"):
            boot.check_dtb(path)
        path.write_bytes(device_tree(sd_status=b"disabled\0"))
        with self.assertRaisesRegex(ValueError, "SD reader"):
            boot.check_dtb(path)

    def test_rejects_wrong_machine_dtb(self):
        path = self.root / "apple.dtb"
        path.write_bytes(device_tree(model=b"apple,j614c\0apple,t6041\0"))
        with self.assertRaisesRegex(ValueError, "Mac16,8"):
            boot.check_dtb(path)

    def test_rejects_incomplete_or_modular_kernel(self):
        path = self.root / "config"
        text = "".join(f"CONFIG_{symbol}=y\n" for symbol in boot.REQUIRED)
        text += "CONFIG_WATCHDOG_OPEN_TIMEOUT=0\n"
        text += 'CONFIG_LSM="landlock,lockdown,yama,loadpin,safesetid,ipe,bpf"\n'
        path.write_text(text)
        boot.check_config(path)
        path.write_text(text.replace("CONFIG_SMP=y", "# CONFIG_SMP is not set"))
        with self.assertRaisesRegex(ValueError, "CONFIG_SMP must be y"):
            boot.check_config(path)
        for symbol in ("UHID", "BT_HIDP", "BT_RFCOMM", "HID_GENERIC"):
            path.write_text(text.replace(f"CONFIG_{symbol}=y", f"# CONFIG_{symbol} is not set"))
            with self.assertRaisesRegex(ValueError, f"CONFIG_{symbol} must be y"):
                boot.check_config(path)
        path.write_text(text.replace("CONFIG_MMC_SDHCI_PCI=y", "CONFIG_MMC_SDHCI_PCI=m"))
        with self.assertRaisesRegex(ValueError, "MMC_SDHCI_PCI"):
            boot.check_config(path)
        path.write_text(text + "CONFIG_NVME_APPLE=y\n")
        with self.assertRaisesRegex(ValueError, "NVME_APPLE"):
            boot.check_config(path)
        path.write_text(text.replace("CONFIG_SECURITY_LANDLOCK=y", "# CONFIG_SECURITY_LANDLOCK is not set"))
        with self.assertRaisesRegex(ValueError, "SECURITY_LANDLOCK"):
            boot.check_config(path)
        path.write_text(text.replace('CONFIG_LSM="landlock,', 'CONFIG_LSM="'))
        with self.assertRaisesRegex(ValueError, "CONFIG_LSM must enable landlock"):
            boot.check_config(path)
        for state in ("y", "m"):
            path.write_text(text + "CONFIG_KVM=" + state + "\n")
            with self.assertRaisesRegex(ValueError, "CONFIG_KVM must be disabled"):
                boot.check_config(path)


if __name__ == "__main__":
    unittest.main()
