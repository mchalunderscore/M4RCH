"""Pinned J614s hardware driver inputs and validation.

The stable profile never calls this module. Enabling these nodes permits live
register access, including two USB DARTs whose driver must remain built in for
SD. The other new controller drivers are modules, with userspace autoload guards.
"""
from __future__ import annotations

from pathlib import Path
import struct

from common import run, sha256

WALLACE_REVISION = "55f116dd0e0f28d1412c6be728a101f7d861c473"
OVERLAY = "patches/experimental-hardware.dtsi"
OVERLAY_SHA256 = "a96790d1e9d91376ddc11917e3134ad68b116b96959a9e4ae11b148555f1e4d9"
PATCHES = {
    "t6040-dwc3-apple-force-host.patch":
        "84cef2d3be3969bef9b8e4d9aa3683c6774592621acfe3167fd42d0f8a8168cb",
    "0001-phy-apple-add-experimental-T6040-USB2-only-slice.patch":
        "b7f02c3cb06b0ed6e490d473a2efd99f61b8cd1ab089a0a09f72ecdec7b60a30",
    "0001-usb-typec-tps6598x-add-SPMI-transport-for-T6040-SN20.patch":
        "9dcb4606e6385815dafa29f2690cf5cc29021d07387da78b55a09d4385b28350",
}

# Local correction after Wallace factors I2C probe into a shared SPMI/I2C path.
# Keep its origin and complete resulting source in the hardware cache identity.
TIPD_CONNECTOR_FIX = {
    "path": "patches/experimental-tipd-connector-device.patch",
    "sha256": "916ff318241734a618390f3768ba0da6972c6adb608acffbc35e11b942e43568",
    "origin": "m4rch local bus-neutral connector lookup correction",
    "base_linux_revision": "e9d2237cd064e6d086d938cd9c85e0c963cf7291",
    "transport_url": "https://github.com/damsleth/wallace/blob/" + WALLACE_REVISION
        + "/patches/0001-usb-typec-tps6598x-add-SPMI-transport-for-T6040-SN20.patch",
    "transport_core_sha256": "190689aeaeadfbed4ad01a7d4fbb8f1290f161d585b52f6caedbd0f8785f9a2c",
    "result_core_sha256": "18b0b90863d998d9b55dd0c757c63ae546d18a71e6646b7a1d8718f10a299b65",
    "native_verified": False,
}

# Register-window and selector commands from the reviewed SN201202x v6 port.
# The current board still uses bounded polling instead of that port's IRQs.
TIPD_REGISTERS_FIX = {
    "path": "patches/experimental-tipd-spmi-registers.patch",
    "sha256": "59f759ff710dc84b56d99371631b6b890045c8f604340ab05c4845d07236f331",
    "upstream_url": "https://lists.openwall.net/linux-kernel/2026/08/26/982",
    "upstream_message_id": "20260826-tipd-ace3-v6-3-e919f39a93a2@chaosmail.tech",
    "transport_spmi_sha256": "391811404e9736e8fa30f71fa1e8c2465b4cdb1b3c6c5f84cd9ffd58af112cd3",
    "result_spmi_sha256": "d13ac2eb1cbf21db4a72df1beb802a7b0aaf203d5ad735a0cff264da1e1299c6",
    "native_verified": False,
}

# Keep descriptors initialized and retained PD identity outside a workqueue stack.
TIPD_PARTNER_FIX = {
    "path": "patches/experimental-tipd-partner-lifetime.patch",
    "sha256": "cc76c59cc2d08fe40f11ad21f7fc722b34814451ce7e3dcf1ca496a99d653772",
    "origin": "m4rch local Type-C partner descriptor and identity lifetime correction",
    "base_core_sha256": "18b0b90863d998d9b55dd0c757c63ae546d18a71e6646b7a1d8718f10a299b65",
    "result_core_sha256": "011ac70235155b3b610cd2faba67eb46f996243d3705a72d4371c523287b05a0",
    "native_verified": False,
}

# Keep cable-triggered initialization, PHY replay and the paired T6040 reset
# separate from the enrolled baseline DT. Reset uses only existing bank 0.
USB_CABLE_FIXES = (
    {
        "path": "patches/experimental-dwc3-cable-lifecycle.patch",
        "sha256": "5b0fc59d5d9821805ca48d92922322dbab529f96974f863b373105d11b894c14",
        "source": "drivers/usb/dwc3/dwc3-apple.c",
        "base_source_sha256": "8c3fd8c5db79f867b7a2671c0af33cdfea7ee67e54637dfcde03fb582bd42095",
        "result_source_sha256": "f7df0c0c3e294656ee56f565585a6c723c7c96aac060d76a5d56a79f32eab52a",
        "origin": "m4rch local fixed-host cable lifecycle and diagnostics candidate",
        "native_verified": False,
    },
    {
        "path": "patches/experimental-usb2-phy-replay.patch",
        "sha256": "9efcf490be4f75821d60b463fe21bddae45f3e1df1d01109272c44599ba1f425",
        "source": "drivers/phy/apple/t6040-usb2.c",
        "base_source_sha256": "9f70fe7dd39c7d46c6deccae84b39627c3cfe7d7ab0eff6799a2577d9599b8c8",
        "result_source_sha256": "198a3d5d7435f438a26d454ed4b0cc52ad8c28034ed5980a85f20a4ac5b86d7f",
        "origin": "m4rch local balanced T6040 USB2 host sequence replay candidate",
        "native_verified": False,
    },
    {
        "path": "patches/experimental-tipd-cable-diagnostics.patch",
        "sha256": "d8643f6fd12157a00820df7f51ba28e4643d6d055d2cf0ffcfa57d14b332e433",
        "source": "drivers/usb/typec/tipd/core.c",
        "base_source_sha256": TIPD_PARTNER_FIX["result_core_sha256"],
        "result_source_sha256": "ffcff0dafca9589c46d2549228c9e8911ef5528f8e00930322511d9dfb9a8d88",
        "origin": "m4rch local Type-C cable status and role callback diagnostics",
        "native_verified": False,
    },
    {
        "path": "patches/experimental-usb2-phy-reset.patch",
        "sha256": "d733722a6bfa530e6b431eced3361990bd154f662b5131da8211f818323de185",
        "source": "drivers/phy/apple/t6040-usb2.c",
        "base_source_sha256": "198a3d5d7435f438a26d454ed4b0cc52ad8c28034ed5980a85f20a4ac5b86d7f",
        "result_source_sha256": "7bd4b229ee2d89a34a94dd0664c93945560fa59b1e40601b2ddf4f457aeecfe3",
        "origin": "m4rch T6040 reset/host restore before DWC3 soft reset and balanced PHY exit",
        "native_verified": False,
    },
    {
        "path": "patches/experimental-dwc3-probe-retry.patch",
        "sha256": "7b8aa8ca2f77159e19780904d4aa6942940166d3317ee282723f24eca985e5ff",
        "source": "drivers/usb/dwc3/dwc3-apple.c",
        "base_source_sha256": "f7df0c0c3e294656ee56f565585a6c723c7c96aac060d76a5d56a79f32eab52a",
        "result_source_sha256": "8714bbccc22861f21ab7a31cec4e9950611ab0bd443c281487bb4d246260da23",
        "origin": "m4rch scoped deferred DWC3 core-probe resources and fresh retry context",
        "native_verified": False,
    },
)

# The PD transport selects registers with SPMI ZERO_WRITE and wakes the chip.
# Wallace's kernel only implements extended transfers. Carry the upstream
# command/FIFO fixes without importing the unrelated interrupt-controller
# machinery or changing this board's reviewed polling DT.
SPMI_PATCHES = (
    ("experimental-spmi-fifo-validation.patch",
     "342272e4e4d5104c5f4561239215d93ef830e682",
     "8fd487d1c5a1686b3b54bdcf9a8f7aa3f93ee5470365d58ba7e718648928127b"),
    ("experimental-spmi-transaction-status.patch",
     "443532c200aa0d6c2bbe13d0a152fccfb2268ab0",
     "e9208b92c36ed5b75d6335a2b3a3e5a4e8065434c298052a7bde655cb75eb51b"),
    ("experimental-spmi-commands.patch",
     "a82a7fec5d6eea7acc73eca3600da9081eaf18e5",
     "404fbe97f97204a49f5696c596878516645cb2860d371a74422a9736b375e52b"),
    ("experimental-spmi-fifo-locking.patch",
     "270ef6de927892264f144bf22e9e12b4f9612545",
     "745c51ca2ad31e1d5eff4239d5e3624fe026877f9f4efc03ddb223d0fcca46f1"),
)
SPMI_RESULT_SHA256 = "09321b711d7923d75b63778222b63f183a38e4320d7009da591d5a7f4ef73c50"

# Replace the July firmware workarounds with Sven Peter's reviewed firmware
# ABI fixes and Yureka's v2 ANS2 support. The v2 queue-size register is zero
# based: programming 64 for a 64-entry CQ made firmware use 65 entries.
# The v2 driver uses only the controller aperture for NVMe and NVMMU. The SD
# overlay supplies its full 0x60000 span; the enrolled baseline stays intact.
NVME_PATCHES = (
    ("nvme-remove-forced-cold-reset.patch", WALLACE_REVISION,
     "b511886baefd46e213baee3a82e5e2664eff5f569d2b7a722f31bb45f189e76b"),
    ("nvme-admin-queue-destroy.patch", "9c02d723ef803dd08423fda8f3b89296da051727",
     "d0e99e1eb428529f48dceabbf86b7a38322621bd5cce96c5472d5697000a82ac"),
    ("nvme-no-data-dma-direction.patch", "07133e8a2fb8e8c4caa0eef3b3c9bb6b9a395940",
     "27bac894578b1abf9afeab28ef752216ec62e3f224c5bbda0b26b72fe570f16f"),
    ("nvme-tcb-zero-opcode.patch", "835cbc4205acff2f6af7f1b63a69c2b19154aa61",
     "78ada7336be2c470f9e6ae517d7a10a55411ed88266e5c644d0e97617fbf2457"),
    ("nvme-admin-page-align-quirk.patch", "04fa7c4f1bfaefdf70779dfccb2d8359938b9543",
     "063ea425c6fca6b0e3a081895df95b79c0a09c0079c5c6ed9b348875692c2915"),
    ("nvme-apple-admin-page-align.patch", "c3d4bb4f1caba82170a36ec8a454b71915a8f5ee",
     "9cb8e2e842ae34cfdfb626952b12cf43038b13a42e31dcd42aa579d1dd4a15ca"),
    ("nvme-remove-prp-chicken-bit.patch", "a4f6716c6a69ce98b9850c9ce4ada5be975fe846",
     "1a6f0a996416564b4507498705fec42cfc7ac4db5a840efab445d4c8ec8f41d5"),
    ("nvme-t8132-binding.patch", "9dbada7ebff2bb68f4f1e44450c728b86805703b",
     "578870058ce4777659611acfcf0662c93664c6e02044fac0bcc0b73a8d0d46ce"),
    ("nvme-t8132-v2.patch", "42839287f85c8c36b63579371af533fcd1b8c970",
     "7ba12be7c79bec229a29098ad37d6b826b5d03a17650a05547e25c19acc85834"),
)
NVME_RESULT_SHA256 = "90417ee2b423e5f8c14cbb2d4ae2435c82278feb897d9ce33561ebde03c6f296"
NVME_CORE_RESULT_SHA256 = {
    "drivers/nvme/host/core.c": "87accb42c912f82c61bd8126058c6ef4a25c52ff6d17e2335946eeb540f89d97",
    "drivers/nvme/host/nvme.h": "517828fde1212f0dffd34bf51ae98e97973e7a362ae3d0e33878a3e0048596d0",
}


def nvme_patch_url(name, revision):
    if name == "nvme-remove-forced-cold-reset.patch":
        return "https://github.com/damsleth/wallace/blob/" + revision + "/patches/t6040-nvme-apple-force-clean-ans-boot.patch"
    host = ("https://cyberchaos.dev/yuka/linux/-/commit/" if name.startswith("nvme-t8132-")
            else "https://github.com/AsahiLinux/linux/commit/")
    return host + revision + ".patch"


MODULE_COMPATIBLES = {
    "nvme_apple": "apple,t8132-nvme-ans2",
    "apple_sart": "apple,t6000-sart",
    "spmi_apple_controller": "apple,spmi",
    "apple_nvmem_spmi": "apple,spmi-nvmem",
    "rtc_macsmc": "apple,smc-rtc",
    "macsmc_reboot": "apple,smc-reboot",
    "phy_apple_t6040_usb2": "apple,t6040-atcphy",
    "dwc3_apple": "apple,t8103-dwc3",
    "tps6598x": "usbc,sn201202x,spmi",
}

# These supplement the normal userspace/driver profile in boot.py. Keep modules
# as modules: compiling them in defeats the ability to initiate a trial from a
# running desktop after recording the baseline and synchronizing SD storage.
BUILTIN = """
SPMI NVMEM RTC_CLASS I2C
TYPEC_TPS6598X_SPMI USB_SUPPORT USB USB_XHCI_HCD USB_XHCI_PLATFORM
GENERIC_PHY USB_ROLE_SWITCH
""".split()
MODULES = """
NVME_CORE BLK_DEV_NVME NVME_APPLE APPLE_SART
SPMI_APPLE NVMEM_APPLE_SPMI RTC_DRV_MACSMC POWER_RESET_MACSMC
USB_DWC3 USB_DWC3_APPLE PHY_APPLE_T6040_USB2 TYPEC TYPEC_TPS6598X
""".split()
BLOCKED_MODULES = (
    "nvme-apple", "apple-sart", "spmi-apple-controller", "apple_nvmem_spmi",
    "rtc-macsmc", "macsmc-reboot", "phy-apple-t6040-usb2", "dwc3-apple",
    "tps6598x",
)


def inputs(project, lock):
    """Include authenticated board and patch identities in the build cache key."""
    if lock["wallace"]["revision"] != WALLACE_REVISION:
        raise ValueError("Experimental hardware must be reviewed against the pinned Wallace revision")
    path = Path(project) / OVERLAY
    if sha256(path) != OVERLAY_SHA256:
        raise ValueError("Experimental hardware overlay failed SHA-256 verification")
    for name, _, digest in NVME_PATCHES:
        if sha256(Path(project) / "patches" / name) != digest:
            raise ValueError(f"Experimental NVMe patch failed SHA-256 verification: {name}")
    for name, _, digest in SPMI_PATCHES:
        if sha256(Path(project) / "patches" / name) != digest:
            raise ValueError(f"Experimental SPMI patch failed SHA-256 verification: {name}")
    if sha256(Path(project) / TIPD_CONNECTOR_FIX["path"]) != TIPD_CONNECTOR_FIX["sha256"]:
        raise ValueError("Experimental Type-C connector patch failed SHA-256 verification")
    if sha256(Path(project) / TIPD_REGISTERS_FIX["path"]) != TIPD_REGISTERS_FIX["sha256"]:
        raise ValueError("Experimental Type-C register patch failed SHA-256 verification")
    if sha256(Path(project) / TIPD_PARTNER_FIX["path"]) != TIPD_PARTNER_FIX["sha256"]:
        raise ValueError("Experimental Type-C partner patch failed SHA-256 verification")
    for fix in USB_CABLE_FIXES:
        if sha256(Path(project) / fix["path"]) != fix["sha256"]:
            raise ValueError(f"Experimental USB cable patch failed SHA-256 verification: {fix['path']}")
    return {
        "wallace_revision": WALLACE_REVISION,
        "overlay": OVERLAY,
        "overlay_sha256": OVERLAY_SHA256,
        "patches": dict(PATCHES),
        "spmi_patches": [dict(path="patches/" + name, revision=revision, sha256=digest,
                              url="https://cyberchaos.dev/yuka/linux/-/commit/" + revision + ".patch")
                         for name, revision, digest in SPMI_PATCHES],
        "spmi_result_sha256": SPMI_RESULT_SHA256,
        "tipd_connector_fix": dict(TIPD_CONNECTOR_FIX),
        "tipd_registers_fix": dict(TIPD_REGISTERS_FIX),
        "tipd_partner_fix": dict(TIPD_PARTNER_FIX),
        "usb_cable_fixes": [dict(fix) for fix in USB_CABLE_FIXES],
        "nvme_patches": [dict(path="patches/" + name, revision=revision, sha256=digest,
                              url=nvme_patch_url(name, revision))
                         for name, revision, digest in NVME_PATCHES],
        "nvme_result_sha256": NVME_RESULT_SHA256,
        "nvme_core_result_sha256": dict(NVME_CORE_RESULT_SHA256),
        "module_compatibles": dict(MODULE_COMPATIBLES),
        "builtin": list(BUILTIN),
        "modules": list(MODULES),
        "blocked_modules": list(BLOCKED_MODULES),
    }


def prepare(builddir, stage):
    """Apply USB and missing M4 NVMe patches after Wallace's base harness.

    Do not use USB_HOST=1: Wallace forbids that switch with its trackpad-upload
    experiment. Here the working tp2 input stack remains intact and the USB
    drivers wait for an explicit module-load trial, rather than early probing.
    """
    overlay = Path(__file__).resolve().parents[1] / OVERLAY
    if sha256(overlay) != OVERLAY_SHA256:
        raise ValueError("Experimental hardware overlay failed SHA-256 verification")
    # Validate all sources before applying any of them.
    paths = [Path(stage) / name for name in PATCHES]
    for path in paths:
        if sha256(path) != PATCHES[path.name]:
            raise ValueError(f"Experimental hardware patch failed SHA-256 verification: {path.name}")
    for name, _, digest in NVME_PATCHES:
        path = overlay.parent / name
        if sha256(path) != digest:
            raise ValueError(f"Experimental NVMe patch failed SHA-256 verification: {name}")
        paths.append(path)
    for name, _, digest in SPMI_PATCHES:
        path = overlay.parent / name
        if sha256(path) != digest:
            raise ValueError(f"Experimental SPMI patch failed SHA-256 verification: {name}")
        paths.append(path)
    connector_patch = overlay.parent.parent / TIPD_CONNECTOR_FIX["path"]
    if sha256(connector_patch) != TIPD_CONNECTOR_FIX["sha256"]:
        raise ValueError("Experimental Type-C connector patch failed SHA-256 verification")
    paths.append(connector_patch)
    registers_patch = overlay.parent.parent / TIPD_REGISTERS_FIX["path"]
    if sha256(registers_patch) != TIPD_REGISTERS_FIX["sha256"]:
        raise ValueError("Experimental Type-C register patch failed SHA-256 verification")
    paths.append(registers_patch)
    partner_patch = overlay.parent.parent / TIPD_PARTNER_FIX["path"]
    if sha256(partner_patch) != TIPD_PARTNER_FIX["sha256"]:
        raise ValueError("Experimental Type-C partner patch failed SHA-256 verification")
    paths.append(partner_patch)
    usb_cable_patches = {}
    for fix in USB_CABLE_FIXES:
        path = overlay.parent.parent / fix["path"]
        if sha256(path) != fix["sha256"]:
            raise ValueError(f"Experimental USB cable patch failed SHA-256 verification: {fix['path']}")
        paths.append(path)
        usb_cable_patches[path] = fix
    for path in paths:
        if path == partner_patch and sha256(Path(builddir) / "drivers/usb/typec/tipd/core.c") != TIPD_PARTNER_FIX["base_core_sha256"]:
            raise ValueError("Experimental Type-C connector source differs from the reviewed correction")
        if path in usb_cable_patches:
            fix = usb_cable_patches[path]
            if sha256(Path(builddir) / fix["source"]) != fix["base_source_sha256"]:
                raise ValueError(f"Experimental USB cable prerequisite differs: {fix['source']}")
        run(["git", "apply", "--check", path], cwd=builddir)
        run(["git", "apply", path], cwd=builddir)
        if path in usb_cable_patches:
            fix = usb_cable_patches[path]
            if sha256(Path(builddir) / fix["source"]) != fix["result_source_sha256"]:
                raise ValueError(f"Experimental USB cable source differs from the reviewed candidate: {fix['source']}")
    # A later reviewed patch may extend the same source. Check every transition
    # above and retain the last resulting hash for the final source audit.
    final_sources = {fix["source"]: fix["result_source_sha256"] for fix in USB_CABLE_FIXES}
    for source, digest in final_sources.items():
        if sha256(Path(builddir) / source) != digest:
            raise ValueError(f"Experimental USB cable final source differs: {source}")
    if sha256(Path(builddir) / "drivers/nvme/host/apple.c") != NVME_RESULT_SHA256:
        raise ValueError("Experimental M4 NVMe source differs from the reviewed port")
    if sha256(Path(builddir) / "drivers/spmi/spmi-apple-controller.c") != SPMI_RESULT_SHA256:
        raise ValueError("Experimental Apple SPMI source differs from the reviewed port")
    if sha256(Path(builddir) / "drivers/usb/typec/tipd/spmi.c") != TIPD_REGISTERS_FIX["result_spmi_sha256"]:
        raise ValueError("Experimental Type-C SPMI source differs from the reviewed correction")
    for name, digest in NVME_CORE_RESULT_SHA256.items():
        if sha256(Path(builddir) / name) != digest:
            raise ValueError(f"NVMe admin alignment prerequisite differs: {name}")
    return overlay.read_text()


def _cells(value):
    if len(value) % 4:
        raise ValueError("Malformed experimental hardware device-tree cell array")
    return struct.unpack(">" + "I" * (len(value) // 4), value)


def check_nodes(nodes):
    """Reject dangerous address, dependency or unintended-port drift in the DTB."""
    def enabled(path):
        if path not in nodes:
            raise ValueError(f"Experimental hardware node missing: {path}")
        name = path
        while name:
            if nodes.get(name, {}).get("status", b"okay\0") not in (b"okay\0", b"ok\0"):
                raise ValueError(f"Experimental hardware path disabled: {name}")
            name = name.rsplit("/", 1)[0]
        return nodes[path]

    def exact(path, key, expected):
        props = enabled(path)
        actual = props.get(key, b"")
        if isinstance(expected, tuple):
            actual = _cells(actual)
        if actual != expected:
            raise ValueError(f"Experimental hardware {path} has unexpected {key}")

    phandles = { _cells(p["phandle"])[0]: (n, p) for n, p in nodes.items()
                 if "phandle" in p }

    def power(path, labels):
        handles = _cells(enabled(path).get("power-domains", b""))
        actual = []
        for handle in handles:
            if handle not in phandles:
                raise ValueError(f"Experimental hardware {path} has unknown power domain")
            name, props = phandles[handle]
            enabled(name)
            if _cells(props.get("#power-domain-cells", b"")) != (0,):
                raise ValueError(f"Experimental hardware {path} has nonzero power domain cells")
            actual.append(props.get("label", b"").rstrip(b"\0").decode("ascii"))
        if actual != list(labels):
            raise ValueError(f"Experimental hardware {path} has incorrect power domains: {actual}")

    exact("/soc/mailbox@409608000", "reg", (4, 0x09608000, 0, 0x4000))
    exact("/soc/iommu@40dc50000", "reg", (4, 0x0dc50000, 0, 0xc000))
    exact("/soc/nvme@44dcc0000", "reg", (
        4, 0x4dcc0000, 0, 0x10000, 4, 0x09600000, 0, 0x4000,
        4, 0x0dcc0000, 0, 0x60000))
    power("/soc/mailbox@409608000", ("ans",))
    power("/soc/iommu@40dc50000", ("ans",))
    power("/soc/nvme@44dcc0000", ("ans", "apcie_sys_st0", "apcie_sys_st1"))

    # PMU base, SID, and exact measured scratchpad cells. Driver binding writes
    # boot-state data through macsmc-reboot; these are not passive DT nodes.
    pmu = "/soc/spmi@509014000"
    exact(pmu, "reg", (5, 0x09014000, 0, 0x100))
    power(pmu, ("nub_spmi0",))
    exact(pmu + "/pmic@e", "reg", (14, 0))
    for name, cells in {
        "rtc-offset@2100": (0x2100, 6), "boot-stage@f801": (0xf801, 1),
        "boot-error-count@f802,0": (0xf802, 1),
        "panic-count@f802,4": (0xf802, 1), "shutdown-flag@f80f,3": (0xf80f, 1),
    }.items():
        exact(pmu + "/pmic@e/nvmem-layout/" + name, "reg", cells)
    for name in ("rtc", "reboot", "hwmon"):
        enabled("/soc/smc@50c600000/" + name)
    # Fan control is intentionally excluded; this is a stability test profile,
    # and read-only RPM reporting needs neither target nor manual-mode keys.
    for name, props in nodes.items():
        if name.startswith("/soc/smc@50c600000/hwmon/"):
            if "apple,fan-target" in props or "apple,fan-mode" in props:
                raise ValueError("Experimental hardware must keep automatic SMC fan control")

    phy = "/soc/phy@392a90000"
    exact(phy, "reg", (3, 0x92a90000, 0, 0x4000, 3, 0x92800000, 0, 0x4000))
    power(phy, ("atc2_usb",))
    exact(phy, "#phy-cells", (1,))
    for path, address in (("/soc/iommu@392f00000", 0x92f00000),
                          ("/soc/iommu@392f80000", 0x92f80000)):
        exact(path, "reg", (3, address, 0, 0xc000))
        power(path, ("atc2_usb",))
        exact(path, "interrupts", (0, 1687, 4))
    usb = "/soc/usb@392280000"
    exact(usb, "reg", (3, 0x92280000, 0, 0xcd00, 3, 0x9228cd00, 0, 0x3200))
    power(usb, ("atc2_usb",))
    exact(usb, "interrupts", (0, 1683, 4))
    exact(usb, "compatible", b"apple,t8103-dwc3\0")
    exact(usb, "dr_mode", b"host\0")
    exact(usb, "maximum-speed", b"high-speed\0")
    if "apple,force-host-mode" not in nodes[usb] or "apple,force-device-mode" in nodes[usb]:
        raise ValueError("Experimental right USB port must use the reviewed host-only path")
    phy_handle = _cells(nodes[phy]["phandle"])[0]
    exact(usb, "phys", (phy_handle, 3))  # PHY_TYPE_USB2
    dart_handles = [_cells(nodes[p]["phandle"])[0] for p in (
        "/soc/iommu@392f00000", "/soc/iommu@392f80000")]
    exact(usb, "iommus", (dart_handles[0], 0, dart_handles[1], 1))

    pd = "/soc/spmi@509198000"
    exact(pd, "reg", (5, 0x09198000, 0, 0x4000))
    power(pd, ("nub_spmi_a1",))
    exact(pd + "/usb-pd@c", "reg", (12, 0))
    exact(pd + "/usb-pd@c", "compatible", b"usbc,sn201202x,spmi\0")
    exact(pd + "/usb-pd@c/connector", "power-role", b"source\0")
    exact(pd + "/usb-pd@c/connector", "data-role", b"host\0")
    for path, props in nodes.items():
        if b"usbc,sn201202x,spmi" in props.get("compatible", b"").split(b"\0"):
            if path != pd + "/usb-pd@c":
                raise ValueError("Experimental hardware unexpectedly enables another PD controller")
    for path in ("/soc/usb@382280000", "/soc/usb@38a280000",
                 "/soc/iommu@382f00000", "/soc/iommu@382f80000",
                 "/soc/iommu@38af00000", "/soc/iommu@38af80000"):
        if nodes.get(path, {}).get("status") != b"disabled\0":
            raise ValueError(f"Experimental hardware unexpectedly enables unreviewed left port: {path}")


def _module_info(path):
    """Read an uncompressed AArch64 .ko's modinfo without host ELF tools."""
    data = Path(path).read_bytes()
    if (len(data) < 64 or data[:7] != b"\x7fELF\x02\x01\x01" or
            struct.unpack_from("<H", data, 18)[0] != 183):
        raise ValueError(f"Experimental module is not AArch64 ELF64: {path}")
    offset = struct.unpack_from("<Q", data, 40)[0]
    size, count, strings = struct.unpack_from("<HHH", data, 58)
    if size != 64 or not count or strings >= count or offset + size * count > len(data):
        raise ValueError(f"Invalid experimental module section table: {path}")
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, offset + i * size)
                for i in range(count)]
    string_section = sections[strings]
    start, length = string_section[4:6]
    if start + length > len(data):
        raise ValueError(f"Invalid experimental module section strings: {path}")
    names = data[start:start + length]
    result = {}
    for section in sections:
        name_offset = section[0]
        if name_offset >= len(names):
            raise ValueError(f"Invalid experimental module section name: {path}")
        if names[name_offset:].split(b"\0", 1)[0] != b".modinfo":
            continue
        start, length = section[4:6]
        if start + length > len(data):
            raise ValueError(f"Invalid experimental module modinfo: {path}")
        for item in data[start:start + length].split(b"\0"):
            if b"=" in item:
                key, value = item.decode("utf-8").split("=", 1)
                result.setdefault(key, []).append(value)
    if not result:
        raise ValueError(f"Experimental module has no modinfo: {path}")
    return result


def _check_module_bindings(infos, release):
    """Ensure the guarded modules really implement their advertised devices."""
    for name, compatible in MODULE_COMPATIBLES.items():
        if name not in infos:
            raise ValueError(f"Experimental hardware module missing: {name}")
        aliases = infos[name].get("alias", [])
        if "of:N*T*C" + compatible not in aliases:
            raise ValueError(f"Experimental {name} module does not bind {compatible}")
    blocked = {name.replace("-", "_") for name in BLOCKED_MODULES}
    for name, info in infos.items():
        magic = info.get("vermagic", [])
        if len(magic) != 1 or not magic[0].startswith(release + " "):
            raise ValueError(f"Experimental module has the wrong kernel release: {name}")
        deps = {dep.replace("-", "_") for group in info.get("depends", [])
                for dep in group.split(",") if dep}
        if name not in blocked and deps & blocked:
            raise ValueError(f"Unguarded module {name} can load a guarded hardware dependency")
    return {"modules": len(infos), "kernel_release": release,
            "guarded_bindings": dict(MODULE_COMPATIBLES)}


def check_modules(tree):
    """Inspect installed modules before packaging; fail if a driver is inert.

    In particular, the original pinned Linux nvme-apple module compiled fine but
    lacked the T8132 alias and two-base support mentioned by Wallace's harness.
    Checking the actual .ko prevents silently shipping that unbound driver.
    """
    tree = Path(tree)
    infos = {}
    for path in sorted((tree / "kernel").rglob("*.ko")):
        info = _module_info(path)
        expected = path.stem.replace("-", "_")
        if info.get("name") != [expected] or expected in infos:
            raise ValueError(f"Experimental module filename/name mismatch: {path}")
        infos[expected] = info
    return _check_module_bindings(infos, tree.name)
