"""Build and validate J614s hardware artifacts in the ARM64 Linux builder.

Nothing in this module invokes a macOS boot-policy tool or opens a block device.
Wallace's pinned build harness owns the hardware patch stack; we add the Arch
userspace configuration and independently check the resulting artifacts.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile

from common import manifest_files, run, sha256, verify_manifest, write_json
from kernel_profile import output, requirements


M1N1_LABEL = "m1n1-m4rch-1.6.0"
# The pinned fork descends from upstream v1.6.0, then adds the Wallace work.
M1N1_BASE = {"tag": "v1.6.0", "revision": "2e6ac0b0b227fa4f89b27ba40f66aad6dd3a43a7"}


# Required by the initramfs, the SD path, and systemd. All are built in: this
# image loads the matched firmware from the bundled initramfs.
REQUIRED = """
ARCH_APPLE SMP ARM64_16K_PAGES BLK_DEV_INITRD RD_GZIP RD_XZ
DEVTMPFS DEVTMPFS_MOUNT TMPFS TMPFS_POSIX_ACL TMPFS_XATTR PROC_FS SYSFS
BINFMT_ELF BINFMT_SCRIPT UNIX98_PTYS TTY VT VT_CONSOLE
DRM DRM_SIMPLEDRM DRM_FBDEV_EMULATION FB FRAMEBUFFER_CONSOLE
INPUT INPUT_EVDEV HID HID_GENERIC UHID HID_APPLE APPLE_DOCKCHANNEL APPLE_DOCKCHANNEL_HID
APPLE_DOCKCHANNEL_TTY APPLE_MAILBOX APPLE_RTKIT APPLE_DART
PCI PCI_MSI PCIE_APPLE PCI_HOST_COMMON PINCTRL_APPLE_GPIO MFD_MACSMC GPIO_MACSMC
MMC MMC_BLOCK MMC_SDHCI MMC_SDHCI_PCI EXFAT_FS FAT_FS VFAT_FS
NLS_CODEPAGE_437 NLS_ISO8859_1 NLS_UTF8 EFI_PARTITION MSDOS_PARTITION
BLOCK BLK_DEV_LOOP EXT4_FS EXT4_FS_POSIX_ACL EXT4_FS_SECURITY
NET UNIX INET PACKET NETLINK_DIAG
CGROUPS CGROUP_PIDS CGROUP_SCHED FAIR_GROUP_SCHED CFS_BANDWIDTH
MEMCG CGROUP_CPUACCT CGROUP_FREEZER CGROUP_DEVICE CGROUP_BPF
NAMESPACES UTS_NS IPC_NS USER_NS PID_NS NET_NS
SYSVIPC POSIX_TIMERS EPOLL SIGNALFD TIMERFD EVENTFD INOTIFY_USER FHANDLE
SECCOMP SECCOMP_FILTER BPF BPF_SYSCALL AUDIT SECURITY SECURITYFS SECURITY_LANDLOCK
WATCHDOG APPLE_WATCHDOG WATCHDOG_HANDLE_BOOT_ENABLED
POWER_RESET POWER_RESET_MACSMC
ARCH_VEXPRESS ARM_AMBA SERIAL_AMBA_PL011 SERIAL_AMBA_PL011_CONSOLE
VIRTIO_MENU VIRTIO VIRTIO_MMIO VIRTIO_PCI VIRTIO_BLK
ARM_GIC_V3 ARM_GIC_V3_ITS PCI_HOST_GENERIC ARM_PSCI_FW
WIRELESS WLAN WLAN_VENDOR_BROADCOM RFKILL CFG80211 MAC80211
BRCMUTIL BRCMFMAC BRCMFMAC_PCIE BRCMFMAC_PROTO_MSGBUF FW_LOADER
BT BT_BREDR BT_RFCOMM BT_LE BT_HIDP BT_HCIBCM4377 HID_MULTITOUCH HID_MAGICMOUSE
CPU_FREQ ARM_APPLE_SOC_CPUFREQ PM_OPP CPU_FREQ_GOV_PERFORMANCE
CPU_FREQ_GOV_POWERSAVE CPU_FREQ_GOV_SCHEDUTIL
HWMON POWER_SUPPLY MACSMC_POWER SENSORS_MACSMC_HWMON
PWM PWM_APPLE NEW_LEDS LEDS_CLASS LEDS_PWM
DEBUG_INFO_NONE
""".split()

DISABLED = """
ARM64_4K_PAGES ARM64_64K_PAGES ARM64_SME BLK_DEV_NVME NVME_CORE NVME_APPLE
SPMI_APPLE NVMEM_APPLE_SPMI RTC_DRV_MACSMC
WATCHDOG_NOWAYOUT MODULES
KVM VIRTUALIZATION
DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT DEBUG_INFO_DWARF4 DEBUG_INFO_DWARF5 DEBUG_INFO_BTF
""".split()


def _output(args, **kwargs):
    return run(args, stdout=subprocess.PIPE, text=True, **kwargs).stdout.strip()


def checkout(name, spec, directory):
    """Cache git objects on the host, but keep all working trees in Linux."""
    revision = spec["revision"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError(f"{name}: a complete pinned Git revision is required")
    if not spec["url"].startswith("https://"):
        raise ValueError(f"{name}: source URL must use HTTPS")
    if directory.exists():
        result = subprocess.run(["git", "-C", str(directory), "rev-parse", "--verify", "HEAD"],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if result.returncode:
            # A interrupted first checkout can leave an unborn repository.
            shutil.rmtree(directory)
        elif result.stdout.strip() != revision:
            raise ValueError(f"{name}: cached working tree has the wrong revision")
        else:
            return directory
    cache = Path("/cache/git") / (name + ".git")
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        run(["git", "init", "--bare", cache])
    available = subprocess.run(
        ["git", "-C", str(cache), "cat-file", "-e", revision + "^{commit}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0
    if not available:
        run(["git", "-C", cache, "fetch", "--depth=1", spec["url"], revision])
    # Fetching a SHA only sets FETCH_HEAD; an otherwise empty bare repository
    # cannot be cloned until it has a real reference to that object.
    run(["git", "-C", cache, "update-ref", "refs/heads/source", revision])
    run(["git", "-C", cache, "symbolic-ref", "HEAD", "refs/heads/source"])
    run(["git", "clone", "--shared", "--no-checkout", cache, directory])
    run(["git", "-C", directory, "checkout", "--detach", revision])
    if _output(["git", "-C", directory, "rev-parse", "HEAD"]) != revision:
        raise ValueError(f"{name}: source revision verification failed")
    return directory


def adapt_harness(text, source, stage):
    """Redirect the pinned harness's paths; retain its patch/config assertions."""
    start = text.index('echo "== deps =="')
    end = text.index('BUILD_DIR="', start)
    # The builder image supplies these packages once. Upstream's unconditional
    # apt-get would require root/network every time its config helper is run.
    text = text[:start] + text[end:]
    return text.replace("/src", str(source)).replace("/out", str(stage))


def check_config(path, profile="stable"):
    values = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            values[key.removeprefix("CONFIG_")] = value
    builtin, modules, disabled = requirements(REQUIRED, DISABLED, profile)
    errors = [f"CONFIG_{key} must be y" for key in sorted(builtin) if values.get(key) != "y"]
    errors += [f"CONFIG_{key} must be m" for key in sorted(modules) if values.get(key) != "m"]
    errors += [f"CONFIG_{key} must be disabled" for key in sorted(disabled)
               if values.get(key) in ("y", "m")]
    if values.get("WATCHDOG_OPEN_TIMEOUT") != "0":
        errors.append("CONFIG_WATCHDOG_OPEN_TIMEOUT must be 0")
    if "landlock" not in values.get("LSM", "").strip('"').split(","):
        errors.append("CONFIG_LSM must enable landlock for pacman's download sandbox")
    if errors:
        raise ValueError("Kernel configuration rejected:\n" + "\n".join(errors))


def check_image(path):
    with Path(path).open("rb") as stream:
        header = stream.read(64)
    if len(header) != 64 or header[0x38:0x3c] != b"ARM\x64":
        raise ValueError("Kernel is not an ARM64 Image")
    image_size, flags = struct.unpack_from("<QQ", header, 0x10)
    if image_size < Path(path).stat().st_size or image_size == 0:
        raise ValueError("ARM64 Image has an invalid size header")
    if (flags >> 1) & 3 != 2:
        raise ValueError("Kernel must use 16 KiB pages")


def read_fdt(path):
    """Read the small subset of flattened device trees needed for preflight."""
    blob = Path(path).read_bytes()
    if len(blob) < 40:
        raise ValueError("Truncated DTB")
    magic, size, structure, strings = struct.unpack_from(">4I", blob)
    if magic != 0xd00dfeed or size != len(blob):
        raise ValueError("Invalid DTB header")
    nodes, stack = {}, []
    cursor = structure
    while cursor + 4 <= size:
        token = struct.unpack_from(">I", blob, cursor)[0]
        cursor += 4
        if token == 1:  # FDT_BEGIN_NODE
            end = blob.index(b"\0", cursor)
            stack.append(blob[cursor:end].decode("ascii"))
            nodes["/" + "/".join(stack[1:])] = {}
            cursor = (end + 4) & ~3
        elif token == 2:  # FDT_END_NODE
            stack.pop()
        elif token == 3:  # FDT_PROP
            length, name_offset = struct.unpack_from(">II", blob, cursor)
            cursor += 8
            start = strings + name_offset
            end = blob.index(b"\0", start)
            name = blob[start:end].decode("ascii")
            if cursor + length > size:
                raise ValueError("Truncated DTB property")
            nodes["/" + "/".join(stack[1:])][name] = blob[cursor:cursor + length]
            cursor = (cursor + length + 3) & ~3
        elif token == 4:  # FDT_NOP
            continue
        elif token == 9:  # FDT_END
            return nodes
        else:
            raise ValueError(f"Unexpected DTB token {token}")
    raise ValueError("DTB has no end token")


def check_dtb(path, profile="stable"):
    output("/out", profile)
    nodes = read_fdt(path)
    compatible = nodes["/"].get("compatible", b"").split(b"\0")
    if b"apple,j614s" not in compatible or b"apple,t6040" not in compatible:
        raise ValueError("DTB is not for the Mac16,8 / J614s / T6040")

    def enabled(path):
        while path:
            if nodes[path].get("status", b"okay\0") not in (b"okay\0", b"ok\0"):
                return False
            path = path.rsplit("/", 1)[0]
        return True

    sd = nodes.get("/aliases", {}).get("mmc0", b"").rstrip(b"\0").decode("ascii")
    if sd not in nodes or not enabled(sd):
        raise ValueError("DTB has no enabled built-in SD reader")
    for alias in ("wifi0", "bluetooth0"):
        node = nodes.get("/aliases", {}).get(alias, b"").rstrip(b"\0").decode("ascii")
        if node not in nodes or not enabled(node):
            raise ValueError(f"DTB has no enabled {alias} endpoint")
    if profile != "stable":
        from hardware_profile import check_nodes
        check_nodes(nodes)
    else:
        for name, props in nodes.items():
            if b"nvme" in props.get("compatible", b"").lower() and enabled(name):
                raise ValueError(f"Internal NVMe must stay disabled: {name}")


def pcie_patch(lock):
    """Pin both the backport and its exact upstream result before cache reuse."""
    spec = lock["m1n1_pcie"]
    if (spec["patch"] != "patches/m1n1-t6040-pcie-upstream.patch" or
            spec["path"] != "src/pcie.c"):
        raise ValueError("Unexpected m1n1 PCIe backport path")
    patch = Path(__file__).resolve().parents[1] / spec["patch"]
    if sha256(patch) != spec["patch_sha256"]:
        raise ValueError("m1n1 PCIe patch failed SHA-256 verification")
    return patch


def trackpad_inputs(lock):
    """Authenticate the board-specific host power sequence and GPIO wiring."""
    spec = lock["linux_trackpad"]
    expected = {
        "patch": "patches/linux-j614s-trackpad-power.patch",
        "overlay": "patches/t6040-j614s-trackpad-power.dtsi",
    }
    paths = {}
    for key, name in expected.items():
        if spec[key] != name:
            raise ValueError(f"Unexpected trackpad {key} path")
        paths[key] = Path(__file__).resolve().parents[1] / name
        if sha256(paths[key]) != spec[key + "_sha256"]:
            raise ValueError(f"Trackpad {key} failed SHA-256 verification")
    return paths


def check_trackpad_nodes(nodes):
    """Reject a miswired reset pin before producing an enrollable bundle."""
    provider = "/soc/smc@50c600000/gpio@67700000"
    touch = "/soc/hid@514600000/multi-touch"
    gpio = nodes.get(provider, {})
    reset = nodes.get(touch, {}).get("reset-gpios", b"")
    if (gpio.get("compatible") != b"apple,smc-low-gpio\0" or
            gpio.get("#gpio-cells") != struct.pack(">I", 2) or
            "gpio-controller" not in gpio or len(gpio.get("phandle", b"")) != 4):
        raise ValueError("Trackpad requires the SMC lowercase-gp GPIO provider")
    expected = gpio["phandle"] + struct.pack(">II", 0x1c, 1)
    if reset != expected:
        raise ValueError("Trackpad reset must use gp1c with active-low polarity")
    for path in (provider, touch):
        while path:
            if nodes.get(path, {}).get("status", b"okay\0") not in (b"okay\0", b"ok\0"):
                raise ValueError(f"Trackpad power path is disabled: {path}")
            path = path.rsplit("/", 1)[0]


def check_trackpad_image(path):
    if b"J614s trackpad active-low host power sequence" not in Path(path).read_bytes():
        raise ValueError("Kernel has no J614s trackpad active-low host power sequence")


def smp_patch(lock, name):
    """Authenticate the narrow upstream SMP backports before cache reuse."""
    expected = {
        "m1n1_smp": ("patches/m1n1-t6040-smp-ctrr.patch", {
            "src/cpu_regs.h", "src/kboot.c"}),
        "linux_smp": ("patches/linux-arm64-wfxt-override.patch", {
            "arch/arm64/kernel/pi/idreg-override.c",
            "Documentation/admin-guide/kernel-parameters.txt"}),
    }
    patch_name, paths = expected[name]
    spec = lock[name]
    if spec["patch"] != patch_name or set(spec["files"]) != paths:
        raise ValueError(f"Unexpected {name} backport paths")
    patch = Path(__file__).resolve().parents[1] / patch_name
    if sha256(patch) != spec["patch_sha256"]:
        raise ValueError(f"{name} patch failed SHA-256 verification")
    return patch


def apply_smp_patch(directory, spec, patch):
    run(["git", "-C", directory, "apply", "--check", patch])
    run(["git", "-C", directory, "apply", patch])
    for name, digest in spec["files"].items():
        if sha256(directory / name) != digest:
            raise ValueError(f"SMP backport source differs from the pinned result: {name}")


def check_m1n1(path, *, ctrr_error=b"FDT: couldn't add reservation for M4+ SMP-RO CTRR area"):
    binary = Path(path).read_bytes()
    if b"Waiting for proxy connection" in binary:
        raise ValueError("m1n1 includes an early proxy window")
    if any(marker in binary for marker in (
            b"op-115 read-only diagnostic", b"stopping before ports",
            b"clock-tunable diagnostic complete")):
        raise ValueError("m1n1 includes the obsolete T6040 PCIe diagnostic")
    if b"Initializing t6040 PCIe controller" not in binary:
        raise ValueError("m1n1 has no T6040 PCIe controller support")
    if ctrr_error not in binary:
        raise ValueError("m1n1 has no M4 SMP CTRR memory reservation")


def kernel_release(makefile):
    """Name the local build using the pinned source's normal Linux version."""
    text = Path(makefile).read_text()
    fields = []
    for name in ("VERSION", "PATCHLEVEL", "SUBLEVEL"):
        values = re.findall(r"^" + name + r"\s*=\s*([0-9]+)\s*$", text, re.MULTILINE)
        if len(values) != 1:
            raise ValueError(f"Pinned Linux Makefile has no unambiguous {name}")
        fields.append(values[0])
    # mkinitcpio and other Linux tools require a numeric kernel ABI prefix.
    return ".".join(fields) + "-m4rch"


def build_hardware(config, lock, profile="stable"):
    if config.get("model") != "Mac16,8" or config.get("board") != "j614s":
        raise ValueError("Only Mac16,8 / j614s is supported by this profile")
    if os.uname().sysname != "Linux" or os.uname().machine != "aarch64":
        raise ValueError("Run the boot builder through its ARM64 Linux container")
    jobs = int(config.get("jobs", 8))
    if jobs < 1 or jobs > 256:
        raise ValueError("jobs must be between 1 and 256")
    out = output("/out", profile)
    out.mkdir(parents=True, exist_ok=True)
    upstream_pcie_patch = pcie_patch(lock)
    trackpad = trackpad_inputs(lock)
    upstream_smp_patches = {name: smp_patch(lock, name)
                            for name in ("m1n1_smp", "linux_smp")}
    inputs = {name: lock[name] for name in
              ("wallace", "linux", "m1n1", "m1n1_pcie", "m1n1_smp", "linux_smp",
               "linux_trackpad", "source_date_epoch")}
    inputs.update(model=config["model"], board=config["board"], recipe=sha256(__file__))
    inputs.update(profile=profile, kernel_profile=sha256(Path(__file__).with_name("kernel_profile.py")))
    if profile != "stable":
        import hardware_profile
        inputs["experimental"] = hardware_profile.inputs(Path(__file__).resolve().parents[1], lock)
    if profile == "experimental-nvme":
        import nvme_handoff
        inputs["nvme_handoff"] = nvme_handoff.inputs(Path(__file__).resolve().parents[1], lock)
    identity = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    hardware_manifest = out / "boot/hardware-manifest.json"
    if hardware_manifest.is_file():
        cached = json.loads(hardware_manifest.read_text())
        if cached.get("identity") == identity:
            verify_manifest(hardware_manifest)
            check_m1n1(out / "boot/m1n1.bin")
            check_config(out / "boot/kernel.config", profile)
            check_dtb(out / "boot/t6040-j614s.dtb", profile)
            if profile != "stable" and sha256(out / "modules.tar.gz") != cached["modules_sha256"]:
                raise ValueError("Cached modules archive differs from the kernel build")
            check_trackpad_nodes(read_fdt(out / "boot/t6040-j614s.dtb"))
            if b"J614s trackpad active-low host power sequence" not in gzip.decompress(
                    (out / "boot/Image.gz").read_bytes()):
                raise ValueError("Cached kernel has no J614s trackpad active-low host power sequence")
            print("Reusing verified kernel, DTB and m1n1 artifacts.", flush=True)
            return cached
    # Keep the source and object tree for retries. Different pinned source sets
    # get different directories; code-only fixes can reuse the compiler cache.
    source_key = hashlib.sha256(json.dumps(
        {name: lock[name] for name in ("wallace", "linux", "m1n1")},
        sort_keys=True).encode()).hexdigest()[:16]
    work = Path("/work") / ("boot-" + source_key + ("-" + profile if profile != "stable" else ""))
    work.mkdir(exist_ok=True)
    stage = work / "stage"
    stage.mkdir(exist_ok=True)
    artifacts = out / "boot"
    artifacts.mkdir(exist_ok=True)
    sources = {name: checkout(name, lock[name], work / name)
               for name in ("wallace", "linux", "m1n1")}
    wallace, linux, m1n1 = (sources[name] for name in ("wallace", "linux", "m1n1"))
    release = kernel_release(linux / "Makefile")
    for directory, suffix in (("patches", "*.patch"), ("dts", "*.dts"), ("dts", "*.dtsi")):
        for path in (wallace / directory).glob(suffix):
            shutil.copy2(path, stage / path.name)
    # Wallace keeps some board files outside its Linux Git branch. Its original
    # harness expects these as uncommitted files in /src; supply the exact
    # version-controlled Wallace corpus instead of depending on its author's Mac.
    for path in (wallace / "dts").glob("*.dts*"):
        shutil.copy2(path, linux / "arch/arm64/boot/dts/apple" / path.name)
    harness = stage / "kbuild.sh"
    harness.write_text(adapt_harness(
        (wallace / "scripts/t6040-kbuild.sh").read_text(), linux, stage))
    builddir = work / "linux-build"
    env = dict(os.environ, BUILD_DIR=str(builddir), BUILD_WORKTREE="1",
               DOCKCHANNEL="1", DOCKCHANNEL_NBCON="1", MACSMC="1",
               HID_TYPE_FIX="1", TRACKPAD_FW="1", TRACKPAD_RESET_CONTRACT="1",
               WIFI="1", PCIE="1", CPUFREQ="1", NPROC=str(jobs), KBUILD_OVERWRITE="1",
               KBUILD_BUILD_TIMESTAMP="@" + str(lock["source_date_epoch"]),
               KBUILD_BUILD_USER="m4rch", KBUILD_BUILD_HOST="builder",
               KBUILD_BUILD_VERSION="1", SOURCE_DATE_EPOCH=str(lock["source_date_epoch"]))
    if builddir.exists():
        run(["git", "-C", builddir, "reset", "--hard", lock["linux"]["revision"]])
    run(["bash", harness], env=env)
    apply_smp_patch(builddir, lock["linux_smp"], upstream_smp_patches["linux_smp"])
    run(["git", "-C", builddir, "apply", "--check", trackpad["patch"]])
    run(["git", "-C", builddir, "apply", trackpad["patch"]])
    # The SD-root overlay is an ordinary DTS in Wallace, not a named harness
    # profile. It explicitly disables ANS/NVMe and the unproven PMU/RTC path.
    final_dts = "t6040-j614s-dcuart-wifi-cpufreq-sdroot"
    shutil.copy2(stage / (final_dts + ".dts"),
                 builddir / "arch/arm64/boot/dts/apple" / (final_dts + ".dts"))
    with (builddir / "arch/arm64/boot/dts/apple" / (final_dts + ".dts")).open("a") as stream:
        stream.write("\n" + trackpad["overlay"].read_text())
        if profile != "stable":
            stream.write("\n" + hardware_profile.prepare(builddir, stage))
    # Reset inherited optional modules before configuring either profile. In
    # stable, turning MODULES off otherwise promotes =m choices to =y; in the
    # experimental build, this makes the explicit additions auditable.
    config_path = builddir / ".config"
    config_path.write_text(re.sub(r"^CONFIG_(\w+)=m$", r"# CONFIG_\1 is not set",
                                  config_path.read_text(), flags=re.MULTILINE))
    options = []
    platforms = re.findall(r"^config (ARCH_\w+)$",
                           (builddir / "arch/arm64/Kconfig.platforms").read_text(),
                           re.MULTILINE)
    for name in platforms:
        if name not in ("ARCH_APPLE", "ARCH_VEXPRESS"):
            options += ["-d", name]
    builtin, modules, disabled = requirements(REQUIRED, DISABLED, profile)
    for name in sorted(builtin):
        options += ["-e", name]
    for name in sorted(modules):
        options += ["-m", name]
    for name in sorted(disabled):
        options += ["-d", name]
    options += ["--set-val", "WATCHDOG_OPEN_TIMEOUT", "0"]
    # Recipe hashes belong in provenance; release strings stay readable.
    options += ["--set-str", "LOCALVERSION", "", "-d", "LOCALVERSION_AUTO"]
    # Landlock must be both compiled and enabled in the boot-time LSM list.
    options += ["--set-str", "LSM", "landlock,lockdown,yama,loadpin,safesetid,ipe,bpf"]
    run(["./scripts/config", "--file", ".config", *options], cwd=builddir)
    make = ["make", "ARCH=arm64", "KERNELRELEASE=" + release, "LOCALVERSION="]
    run([*make, "olddefconfig"], cwd=builddir, env=env)
    check_config(builddir / ".config", profile)
    run([*make, "-j" + str(jobs), "Image",
         "apple/" + final_dts + ".dtb", *(["modules"] if profile != "stable" else [])], cwd=builddir, env=env)
    kernel = builddir / "arch/arm64/boot/Image"
    dtb = builddir / "arch/arm64/boot/dts/apple" / (final_dts + ".dtb")
    check_image(kernel)
    check_dtb(dtb, profile)
    check_trackpad_image(kernel)
    check_trackpad_nodes(read_fdt(dtb))
    observed_release = _output([*make, "-s", "kernelrelease"], cwd=builddir, env=env)
    if observed_release != release:
        raise ValueError("Compiled kernel release differs from the pinned m4rch version")
    if profile != "stable":
        package_modules(builddir, out / "modules.tar.gz", release, env)

    run(["git", "-C", m1n1, "submodule", "update", "--init", "--depth=1"])
    framebuffer_patch = wallace / "patches/m1n1-fb-console-always.patch"
    run(["git", "-C", m1n1, "reset", "--hard", lock["m1n1"]["revision"]])
    run(["git", "-C", m1n1, "apply", "--check", framebuffer_patch])
    run(["git", "-C", m1n1, "apply", framebuffer_patch])
    run(["git", "-C", m1n1, "apply", "--check", upstream_pcie_patch])
    run(["git", "-C", m1n1, "apply", upstream_pcie_patch])
    if sha256(m1n1 / "src/pcie.c") != lock["m1n1_pcie"]["sha256"]:
        raise ValueError("m1n1 PCIe source differs from the pinned upstream implementation")
    apply_smp_patch(m1n1, lock["m1n1_smp"], upstream_smp_patches["m1n1_smp"])
    if profile == "experimental-nvme":
        nvme_handoff.prepare(m1n1, stage)
    # Debian releases with ImageMagick 6 call this command `convert`.
    if not shutil.which("magick"):
        if not shutil.which("convert"):
            raise ValueError("m1n1 requires ImageMagick (magick or convert)")
        bindir = work / "bin"
        bindir.mkdir(exist_ok=True)
        wrapper = bindir / "magick"
        wrapper.write_text('#!/bin/sh\nexec convert "$@"\n')
        wrapper.chmod(0o755)
        env["PATH"] = str(bindir) + os.pathsep + env["PATH"]
    env["CARGO_HOME"] = "/cache/cargo"
    env["M1N1_VERSION_TAG"] = M1N1_LABEL
    run(["make", "-j" + str(jobs), "BUILDSTD=1", "RELEASE=1",
         "EXTRA_CFLAGS=-DFB_CONSOLE_ALWAYS", "CARGO_FLAGS=-Z build-std=alloc,core --locked"],
        cwd=m1n1, env=env)
    prefix = m1n1 / "build/m1n1.bin"
    check_m1n1(prefix)
    for src, name in ((prefix, "m1n1.bin"), (dtb, "t6040-j614s.dtb"),
                      (builddir / ".config", "kernel.config"),
                      (builddir / "System.map", "System.map")):
        shutil.copy2(src, artifacts / name)
    (artifacts / "Image.gz").write_bytes(gzip.compress(kernel.read_bytes(), compresslevel=9, mtime=0))
    names = ["m1n1.bin", "Image.gz", "t6040-j614s.dtb", "kernel.config", "System.map"]
    manifest = {
        "identity": identity, "inputs": inputs,
        "kernel_release": release,
        "build_labels": {"linux": "linux-m4rch-" + release.removesuffix("-m4rch"), "m1n1": M1N1_LABEL},
        "m1n1_upstream_base": M1N1_BASE,
        "harness_sha256": sha256(harness), "m1n1_patch_sha256": sha256(framebuffer_patch),
        "m1n1_pcie": lock["m1n1_pcie"],
        "m1n1_smp": lock["m1n1_smp"], "linux_smp": lock["linux_smp"],
        "linux_trackpad": lock["linux_trackpad"],
        "toolchain": {tool: _output([tool, "--version"]).splitlines()[0]
                      for tool in ("gcc", "rustc", "cargo", "dtc")},
        "files": manifest_files(artifacts, names),
    }
    if profile != "stable":
        manifest["modules_sha256"] = sha256(out / "modules.tar.gz")
    write_json(hardware_manifest, manifest)
    return manifest


def package_modules(builddir, destination, release, env):
    """Publish stripped modules and dependency indexes with no host symlinks."""
    if not re.fullmatch(r"[A-Za-z0-9_.+-]+", release):
        raise ValueError("Invalid kernel release")
    with tempfile.TemporaryDirectory(prefix="module-install-", dir="/work") as temporary:
        root = Path(temporary)
        run(["make", "ARCH=arm64", "KERNELRELEASE=" + release, "LOCALVERSION=", "modules_install", "INSTALL_MOD_STRIP=1",
             "INSTALL_MOD_PATH=" + temporary, "DEPMOD=true"], cwd=builddir, env=env)
        tree = root / "lib/modules" / release
        for name in ("build", "source"):
            path = tree / name
            if path.is_symlink():
                path.unlink()
        from hardware_profile import check_modules
        check_modules(tree)
        # Fail missing module dependencies before shipping the archive.
        result = run(["depmod", "-b", root, "-e", "-F", builddir / "System.map", release],
                     capture_output=True, text=True)
        if "needs unknown symbol" in result.stderr:
            raise ValueError("Module dependency validation failed: " + result.stderr)
        (root / "usr").mkdir()
        (root / "lib").rename(root / "usr/lib")
        if not list((root / "usr/lib/modules" / release).rglob("*.ko*")):
            raise ValueError("Experimental kernel produced no modules")
        temp = destination.with_suffix(".tar.gz.tmp")
        with temp.open("wb") as stream, gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w|") as archive:
                for path in sorted((root / "usr").rglob("*")):
                    if path.is_symlink() or not (path.is_file() or path.is_dir()):
                        raise ValueError(f"Unexpected module archive member: {path}")
                    info = archive.gettarinfo(str(path), str(path.relative_to(root)))
                    info.uid = info.gid = 0
                    info.uname = info.gname = "root"
                    info.mtime = int(env["SOURCE_DATE_EPOCH"])
                    if path.is_file():
                        with path.open("rb") as data:
                            archive.addfile(info, data)
                    else:
                        archive.addfile(info)
        temp.replace(destination)
