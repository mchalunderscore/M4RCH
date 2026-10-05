"""Fresh native ext4 Arch root and an SD-aware early userspace.

Runs inside the Linux builder; only ordinary files under /out are published.
The image helpers supply filesystem and signed-package primitives.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import uuid

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib"))
import image as primitives
from common import download, manifest_files, run, sha256, write_json
from image import link, root_workspace, write


def module_installer(project):
    spec = importlib.util.spec_from_file_location("sdboot_module_installer", project / "templates/install-driver-modules.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure_accounts(root, config):
    """Rename the pristine ALARM user without assigning builder-host ownership."""
    username = config["username"]
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,30}", username):
        raise ValueError("Invalid login name")
    if any(character in config["full_name"] for character in ":\n\r"):
        raise ValueError("Invalid full name")
    rows = [row.split(":") for row in (root / "etc/passwd").read_text().splitlines()]
    matches = [row for row in rows if row[0] == "alarm"]
    if len(matches) != 1 or matches[0][2:4] != ["1000", "1000"]:
        raise ValueError("Expected pristine ALARM account with UID/GID 1000")
    if username != "alarm" and any(row[0] == username for row in rows):
        raise ValueError("Requested login already exists")
    account = matches[0]
    account[0], account[4], account[5], account[6] = username, config["full_name"], f"/home/{username}", "/bin/bash"
    write(root, "etc/passwd", "\n".join(":".join(row) for row in rows) + "\n")
    for filename in ("group", "gshadow"):
        path = root / "etc" / filename
        if not path.is_file():
            continue
        rows = [row.split(":") for row in path.read_text().splitlines()]
        for row in rows:
            if row[0] == "alarm":
                row[0] = username
            for index in ([3] if filename == "group" else [2, 3]):
                row[index] = ",".join(username if member == "alarm" else member for member in row[index].split(","))
            if row[0] == "wheel" and username not in row[3].split(","):
                row[3] = ",".join(filter(None, [row[3], username]))
        write(root, "etc/" + filename, "\n".join(":".join(row) for row in rows) + "\n", 0o600 if filename == "gshadow" else 0o644)
    rows = [row.split(":") for row in (root / "etc/shadow").read_text().splitlines()]
    if sum(row[0] == "alarm" for row in rows) != 1:
        raise ValueError("Missing ALARM shadow entry")
    for row in rows:
        if row[0] == "alarm":
            row[0], row[1] = username, ""
            # No forced password change or expiry on the local autologin user.
            row[2:] = ["", "", "", "", "", "", ""]
        elif row[0] == "root" or row[1] not in ("*", "!"):
            row[1] = "!"
    write(root, "etc/shadow", "\n".join(":".join(row) for row in rows) + "\n", 0o600)
    for filename in ("subuid", "subgid"):
        path = root / "etc" / filename
        if path.exists():
            write(root, "etc/" + filename, re.sub(r"(?m)^alarm:", username + ":", path.read_text()))
    old_home, home = root / "home/alarm", root / "home" / username
    if old_home != home:
        old_home.rename(home)


def configure_pacman(root):
    # Never ship the builder's GnuPG private key. Populate a new machine-local
    # pacman keyring before completing the first ordinary boot instead.
    write(root, "etc/systemd/system/m4rch-pacman-init.service", """[Unit]
Description=Initialize the Arch Linux ARM package signing keyring
ConditionPathExists=!/etc/pacman.d/gnupg/.arch-m4-ready
Before=multi-user.target
[Service]
Type=oneshot
ExecStart=/usr/bin/pacman-key --init
ExecStart=/usr/bin/pacman-key --populate archlinuxarm
ExecStart=/usr/bin/touch /etc/pacman.d/gnupg/.arch-m4-ready
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
""")
    link(root, "etc/systemd/system/multi-user.target.wants/m4rch-pacman-init.service", "/etc/systemd/system/m4rch-pacman-init.service")


def configure_root(project, root, config):
    """Create per-installation identity; packaged policy is staged separately."""
    configure_accounts(root, config)
    username, hostname = config["username"], config["hostname"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", hostname):
        raise ValueError("Invalid hostname")
    write(root, "etc/hostname", hostname + "\n")
    write(root, "etc/hosts", f"127.0.0.1 localhost\n::1 localhost\n127.0.1.1 {hostname}.localdomain {hostname}\n")
    boot_partuuid = uuid.uuid5(uuid.UUID(config["root_uuid"]), "arch-m4-uefi-v2:boot")
    # FAT has no stored Unix ownership or permissions. Mount masks make the
    # boot files readable to ordinary users while reserving writes for root.
    write(root, "etc/fstab", f"UUID={config['root_uuid']} / ext4 defaults,noatime 0 1\nPARTUUID={boot_partuuid} /boot vfat defaults,uid=0,gid=0,fmask=0133,dmask=0022 0 2\n")
    write(root, "etc/vconsole.conf", "KEYMAP=us\n")
    write(root, "etc/locale.conf", "LANG=C.UTF-8\n")
    zone = root / "usr/share/zoneinfo" / config["timezone"]
    if not zone.is_file():
        raise ValueError("Timezone is missing from the root")
    link(root, "etc/localtime", "/usr/share/zoneinfo/" + config["timezone"])
    write(root, "etc/machine-id", "")
    for relative in ("var/lib/dbus/machine-id", "var/lib/systemd/random-seed"):
        path = root / relative
        if path.exists() or path.is_symlink():
            path.unlink()
    for directory in ("run", "tmp", "var/tmp"):
        for child in (root / directory).iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
    link(root, "etc/resolv.conf", "/run/NetworkManager/resolv.conf")
    defaults = root / "usr/share/m4rch/home"
    if defaults.is_dir():
        shutil.copytree(defaults, root / "home" / username, dirs_exist_ok=True)


def configure_package(project, root, config):
    """Stage custom policy for makepkg, never install it directly in the root."""
    username = config["username"]
    masked = {"sshd.service", "sshd.socket", "systemd-networkd.service", "systemd-resolved.service", "sleep.target", "suspend.target", "hibernate.target", "hybrid-sleep.target", "suspend-then-hibernate.target"}
    masked.update({"systemd-networkd-varlink.socket", "systemd-resolved-monitor.socket"})
    for name in sorted(masked):
        link(root, "etc/systemd/system/" + name, "/dev/null")
    link(root, "etc/systemd/system/default.target", "/usr/lib/systemd/system/graphical.target")
    link(root, "etc/systemd/system/display-manager.service", "/usr/lib/systemd/system/sddm.service")
    for service in ("NetworkManager.service", "bluetooth.service"):
        link(root, "etc/systemd/system/multi-user.target.wants/" + service, "/usr/lib/systemd/system/" + service)
    configure_pacman(root)
    # DisplayServer controls the SDDM greeter, independently of the desktop
    # selected by Autologin.Session. Keep its working X11 framebuffer path.
    write(root, "etc/sddm.conf.d/m4rch.conf", f"""[General]
DisplayServer=x11
GreeterEnvironment=QT_QUICK_BACKEND=software,LIBGL_ALWAYS_SOFTWARE=1
[Autologin]
User={username}
Session=plasma.desktop
Relogin=false
[X11]
ServerArguments=-nolisten tcp -dpi 192
""")
    write(root, "etc/systemd/system/getty@tty2.service.d/autologin.conf", f"[Service]\nExecStart=\nExecStart=-/usr/bin/agetty --autologin {username} --noclear %I $TERM\n")
    link(root, "etc/systemd/system/getty.target.wants/getty@tty2.service", "/usr/lib/systemd/system/getty@.service")
    write(root, "etc/sudoers.d/10-m4rch", f"{username} ALL=(ALL:ALL) NOPASSWD: ALL\n", 0o440)
    (root / "etc/sudoers.d").chmod(0o750)
    write(root, "etc/systemd/system.conf.d/m4rch.conf", "[Manager]\nRuntimeWatchdogSec=off\nRebootWatchdogSec=off\n")
    write(root, "etc/systemd/logind.conf.d/m4rch.conf", "[Login]\nHandleLidSwitch=ignore\nHandleLidSwitchExternalPower=ignore\nHandleLidSwitchDocked=ignore\nHandleSuspendKey=ignore\n")
    write(root, "etc/systemd/journald.conf.d/m4rch.conf", "[Journal]\nStorage=persistent\nSystemMaxUse=128M\nRuntimeMaxUse=32M\n")
    write(root, "etc/environment.d/10-m4rch.conf", "LIBGL_ALWAYS_SOFTWARE=1\nQT_QUICK_BACKEND=software\n")
    write(root, "etc/profile.d/m4rch-software.sh", "export LIBGL_ALWAYS_SOFTWARE=1\nexport QT_QUICK_BACKEND=software\n")
    # KWin 6.7's DRM backend supports QPainter with dumb buffers on simpledrm.
    # Scope this to the Wayland compositor service: forcing KWIN_COMPOSE=Q
    # globally would also affect the separately packaged X11 fallback.
    write(root, "etc/systemd/user/plasma-kwin_wayland.service.d/m4rch-software.conf", "[Service]\nEnvironment=KWIN_COMPOSE=Q\n")
    home = "usr/share/m4rch/home"
    # Wayland always composes; retain the requested compositing preference
    # when switching to the X11 fallback as well.
    write(root, home + "/.config/kwinrc", "[Compositing]\nEnabled=true\n")
    write(root, home + "/.config/kscreenlockerrc", "[Daemon]\nAutolock=false\nLockOnResume=false\n")
    write(root, home + "/.config/kdeglobals", "[KScreen]\nScaleFactor=2\n[General]\nXftDPI=192\n")
    write(root, "etc/X11/xorg.conf.d/20-modesetting.conf", 'Section "Device"\n    Identifier "Apple framebuffer"\n    Driver "modesetting"\n    Option "AccelMethod" "none"\n    Option "ShadowFB" "true"\nEndSection\n')
    for name, template in (("m4rch-kbd-backlight", "kbd-backlight.sh"), ("m4rch-input-diagnostics", "collect-input-diagnostics.sh")):
        write(root, "usr/bin/" + name, (project / "templates" / template).read_text(), 0o755)
    write(root, "usr/bin/m4rch-enable-peripherals", (project / "templates/enable-peripherals.sh").read_text(), 0o755)
    # Type=exec releases the graphical target once the helper starts, without
    # waiting for experimental probe completion. Each group has its own status
    # and can fail independently. Alias guards keep these out of early boot.
    for group in ("platform", "usb", "nvme"):
        service = "m4rch-" + group + ".service"
        write(root, "usr/lib/systemd/system/" + service, f"""[Unit]
Description=m4rch {group} drivers
After=multi-user.target
ConditionPathExists=/sys/firmware/devicetree/base/compatible
ConditionKernelCommandLine=!arch_m4.peripherals=off
ConditionKernelCommandLine=!arch_m4.{group}=off
[Service]
Type=exec
ExecStart=/usr/bin/m4rch-enable-peripherals {group}
RemainAfterExit=yes
TimeoutStopSec=5s
[Install]
WantedBy=graphical.target
""")
        link(root, "etc/systemd/system/graphical.target.wants/" + service,
             "/usr/lib/systemd/system/" + service)


def verified_modules(project, kernel_dir):
    kit = kernel_dir / "driver-tools"
    installer = module_installer(project)
    module_manifest = installer.metadata(kit)
    if sha256(kernel_dir / "boot/Image.gz") != module_manifest["kernel_image_sha256"]:
        raise ValueError("Kernel image and driver kit do not match")
    with tarfile.open(kit / "modules.tar.gz") as archive:
        installer.archive_members(archive, module_manifest["kernel_release"])
    return kit, installer, module_manifest



def testing_initramfs(production, output):
    """Change only the hardware guard flag in the actual mkinitcpio image."""
    blob = production.read_bytes()
    offset = 0
    # mkinitcpio may prepend an uncompressed early newc archive. Keep it byte
    # identical and decompress only the following main gzip archive.
    while blob[offset:offset + 6] in (b"070701", b"070702"):
        while True:
            header = blob[offset:offset + 110]
            if len(header) != 110 or header[:6] not in (b"070701", b"070702"):
                raise ValueError("Invalid early initramfs header")
            fields = [int(header[6 + index * 8:14 + index * 8], 16) for index in range(13)]
            size, namesize = fields[6], fields[11]
            if not 0 < namesize <= 4096:
                raise ValueError("Invalid early initramfs member")
            name = blob[offset + 110:offset + 110 + namesize]
            if not name.endswith(b"\0"):
                raise ValueError("Invalid early initramfs name")
            offset = (offset + 110 + namesize + 3) & ~3
            offset = (offset + size + 3) & ~3
            if offset > len(blob):
                raise ValueError("Truncated early initramfs")
            if name == b"TRAILER!!!\0":
                break
        while offset < len(blob) and blob[offset] == 0:
            offset += 1
    raw = gzip.decompress(blob[offset:])
    needle = b"TESTING='0'\n"
    if raw.count(needle) != 1:
        raise ValueError("Production initramfs must contain one disabled testing flag")
    changed = raw.replace(needle, b"TESTING='1'\n")
    temporary = output.with_name("." + output.name + ".partial")
    with temporary.open("wb") as stream:
        stream.write(blob[:offset])
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0, compresslevel=9) as archive:
            archive.write(changed)
    temporary.replace(output)


def refresh_initramfs(project: Path, out: Path, config: dict, lock: dict, kernel_dir: Path):
    """Rebuild update payloads without changing the persistent root image."""
    from common import verify_manifest
    from firmware import check_files, final_hashes
    check_files(Path("/cache/firmware/vendorfw"), final_hashes())
    kit, installer, module_manifest = verified_modules(project, kernel_dir)
    previous = verify_manifest(out / "rootfs-manifest.json")
    for name in ("root_uuid", "boot_mib", "model", "board"):
        if previous["config"][name] != config[name]:
            raise ValueError(f"{name} changed; build a fresh rootfs before making payloads")
    # Production initramfs is generated by the installed package hook. Only
    # rebuild the separate QEMU artifact outside the root.
    if previous["kernel_release"] != module_manifest["kernel_release"]:
        raise ValueError("Kernel changed; build its packages and a fresh image, or install them with pacman inside Linux")
    testing_initramfs(out / "initramfs.cpio.gz", out / "test-initramfs.cpio.gz")
    write_json(out / "initramfs-manifest.json", {"schema": 1, "config": config, "kernel_release": module_manifest["kernel_release"], "kernel_image_sha256": module_manifest["kernel_image_sha256"], "modules_sha256": module_manifest["files"]["modules.tar.gz"]["sha256"], "files": manifest_files(out, ["initramfs.cpio.gz", "test-initramfs.cpio.gz"])})



def migrate_package_lock(config):
    """Preserve the known former FIT desktop lock when adding UEFI packages."""
    path = Path("/cache/desktop-packages/packages.lock.json")
    if not path.is_file():
        return
    previous = json.loads(path.read_text())
    if previous.get("requested") == config["packages"]:
        return
    added = {"grub", "mkinitcpio", "gptfdisk", "discover", "flatpak", "packagekit-qt6", "fakeroot"}
    paru_dependencies = {"git", "base-devel", "rust"}
    old_requested = [name for name in config["packages"] if name not in added | paru_dependencies]
    pre_paru_requested = [name for name in config["packages"] if name not in paru_dependencies]
    if previous.get("requested") not in (old_requested, pre_paru_requested):
        raise ValueError("Package selection differs from the cached transaction; preserve or remove cache/sdboot-packages/packages.lock.json before resolving a new signed transaction")
    preserved = path.with_name("packages.lock.previous-" + sha256(path)[:12] + ".json")
    if preserved.exists():
        if preserved.read_bytes() != path.read_bytes():
            raise ValueError("Previous package lock backup differs")
        path.unlink()
    else:
        path.rename(preserved)


def build(project: Path, out: Path, config: dict, lock: dict, kernel_dir: Path, *, packages_only=False):
    if os.uname().sysname != "Linux" or os.uname().machine not in ("aarch64", "arm64") or os.geteuid() != 0:
        raise ValueError("Rootfs must be built as root inside the Linux aarch64 builder")
    if out.resolve() != Path("/out"):
        raise ValueError("Mount the requested output directory at /out")
    out.mkdir(exist_ok=True)
    kit, installer, module_manifest = verified_modules(project, kernel_dir)
    source = lock["rootfs"]
    archive = download(source["url"], Path("/cache") / source["filename"], source["sha256"])
    sig = source["signature"]
    signature = download(sig["url"], Path("/cache") / (source["filename"] + ".sig"), sig["sha256"])
    keyring = Path("/work/sdboot-alarm.gpg")
    run(["gpg", "--batch", "--yes", "--dearmor", "--output", keyring, project / "keys/archlinuxarm-builder.asc"])
    result = run(["gpg", "--batch", "--no-default-keyring", "--keyring", keyring, "--status-fd", "1", "--verify", signature, archive], stdout=subprocess.PIPE, text=True)
    signatures = [line.split() for line in result.stdout.splitlines() if line.startswith("[GNUPG:] VALIDSIG ")]
    if not any(source["signer"] in (fields[2], fields[-1]) for fields in signatures):
        raise ValueError("Rootfs signature does not match the pinned build key")
    from firmware import check_files, final_hashes
    firmware = Path("/cache/firmware/vendorfw")
    check_files(firmware, final_hashes())
    with root_workspace() as workspace:
        root = workspace / "root"
        root.mkdir()
        run(["bsdtar", "--numeric-owner", "--acls", "--xattrs", "-xpf", archive, "-C", root])
        # Scope package-lock discovery to the new implementation; the old i3
        # transaction remains intact. Packages retain mandatory signatures.
        previous_project = primitives.PROJECT
        image_lock = out / "packages.lock.json"
        saved_image_lock = image_lock.read_bytes() if packages_only and image_lock.is_file() else None
        try:
            primitives.PROJECT = project / "sdboot"
            migrate_package_lock(config)
            primitives.install_packages(root, config)
        finally:
            primitives.PROJECT = previous_project
            if packages_only:
                if saved_image_lock is None:
                    image_lock.unlink(missing_ok=True)
                else:
                    image_lock.write_bytes(saved_image_lock)
        from packages import build_and_install
        build_and_install(project, root, config, lock, kernel_dir, module_manifest, out, packages_only=packages_only)
        if packages_only:
            return
        configure_root(project, root, config)
        run(["chroot", root, "chown", "-R", config["username"] + ":" + config["username"], "/home/" + config["username"]])
        run(["chroot", root, "visudo", "-cf", "/etc/sudoers"])
        for relative in ("usr/bin/firefox", "usr/bin/nmtui", "usr/bin/startplasma-wayland", "usr/bin/kwin_wayland", "usr/lib/systemd/user/plasma-kwin_wayland.service", "usr/share/wayland-sessions/plasma.desktop", "usr/bin/startplasma-x11", "usr/bin/plasma-discover", "usr/bin/flatpak", "usr/bin/paru", "usr/share/xsessions/plasmax11.desktop"):
            if not (root / relative).is_file():
                raise ValueError(f"Missing required desktop component: {relative}")
        with (out / "rootfs-packages.txt").open("w") as stream:
            run(["chroot", root, "pacman", "-Q"], stdout=stream)
        staged = out / ".rootfs.ext4.partial"
        staged.unlink(missing_ok=True)
        with staged.open("xb") as stream:
            stream.truncate(config["root_gib"] * 1024**3)
        run(["mkfs.ext4", "-q", "-F", "-L", "ARCHROOT", "-U", config["root_uuid"], "-E", "lazy_itable_init=0,lazy_journal_init=0", "-d", root, staged])
        run(["e2fsck", "-fn", staged])
        (out / "firmware").mkdir(exist_ok=True)
        for name in ("regulatory.db", "regulatory.db.p7s"):
            shutil.copyfile(root / "usr/lib/firmware" / name, out / "firmware" / name)
        staged.replace(out / "rootfs.ext4")
    write_json(out / "rootfs-manifest.json", {"schema": 1, "config": config, "rootfs_source": source, "kernel_release": module_manifest["kernel_release"], "kernel_image_sha256": module_manifest["kernel_image_sha256"], "modules_sha256": module_manifest["files"]["modules.tar.gz"]["sha256"], "hardware_tested": False, "files": manifest_files(out, ["rootfs.ext4", "rootfs-packages.txt", "packages.lock.json", "firmware/regulatory.db", "firmware/regulatory.db.p7s"])})
    refresh_initramfs(project, out, config, lock, kernel_dir)
