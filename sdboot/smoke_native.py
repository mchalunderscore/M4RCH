"""Boot a disposable native SD image twice and check growth and persistence.

QEMU boots the SD GRUB through ARM64 UEFI firmware and tests userspace,
packages and growth. Apple m1n1/U-Boot, native drivers and KDE display remain
hardware tests. Production files remain unchanged.
"""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import uuid

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib"))
from common import manifest_files, run, sha256, verify_manifest, write_json
import gpt
from smoke import debugfs, dump_file, signed_package_fixture
try:
    from . import media
except ImportError:
    import media


PROBE = r'''#!/usr/bin/python3
import configparser
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import struct
import subprocess
import sys

cfg = json.loads(Path('/usr/share/arch-m4-native-smoke.json').read_text())
nonce = cfg['nonce']
user = cfg['username']
home = Path('/home') / user
state = Path('/var/lib/arch-m4-native-smoke.json')
profile = home / '.mozilla/firefox/arch-m4-smoke.default'
connection = Path('/etc/NetworkManager/system-connections/arch-m4-smoke.nmconnection')
connection_uuid = '68f7e20c-7b59-4a33-ab43-533456c4d5e1'

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def checked(command, timeout=120):
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        print(result.stdout, flush=True)
        raise RuntimeError('Command failed: ' + ' '.join(command))
    return result.stdout.strip()

def marker(kind, attempt):
    print(f'ARCHM4_NATIVE_{kind}:{nonce}:{attempt}', flush=True)

def main():
    attempt = 2 if state.exists() else 1
    root_start = int(Path('/sys/class/block/vda2/start').read_text())
    root_sectors = int(Path('/sys/class/block/vda2/size').read_text())
    disk_sectors = int(Path('/sys/class/block/vda/size').read_text())
    require(root_start == 2048 + cfg['boot_mib'] * 2048, 'root start changed')
    require(root_sectors == disk_sectors - root_start - 33, 'partition did not fill card')
    require(Path('/var/lib/arch-m4/root-capacity-sectors').read_text().strip() == str(root_sectors),
            'successful filesystem growth was not stamped with the partition capacity')
    require(root_sectors * 512 > cfg['root_gib'] * 1024**3 + 1024**3 - 4096,
            'disposable card was not expanded by one GiB')
    with open('/dev/vda2', 'rb', buffering=0) as root:
        root.seek(1024)
        sb = root.read(1024)
    require(sb[56:58] == b'\x53\xef', 'not ext4')
    count = struct.unpack_from('<I', sb, 4)[0]
    if struct.unpack_from('<I', sb, 96)[0] & 0x80:
        count |= struct.unpack_from('<I', sb, 336)[0] << 32
    block = 1024 << struct.unpack_from('<I', sb, 24)[0]
    # resize2fs can omit a tiny final group which cannot hold its own metadata.
    group = struct.unpack_from('<I', sb, 32)[0] * block
    require(0 <= root_sectors * 512 - count * block < group, 'ext4 did not fill partition')
    require(count * block >= cfg['root_gib'] * 1024**3 + 1024**3 - group,
            'ext4 did not grow by the added card capacity')
    marker('GROWTH_PASS', attempt)
    require(checked(['findmnt', '-n', '-o', 'SOURCE', '/']) == '/dev/vda2', 'not a native root')
    require(checked(['findmnt', '-n', '-o', 'SOURCE', '/boot']) == '/dev/vda1', 'boot FAT not mounted')
    for path, mode in ((Path('/boot'), 0o755), (Path('/boot/grub/grub.cfg'), 0o644)):
        metadata = path.stat()
        require(stat.S_IMODE(metadata.st_mode) == mode and metadata.st_uid == 0 and
                metadata.st_gid == 0, 'boot permissions are not readable with root-only writes')
    require(checked(['runuser', '-u', user, '--', 'test', '-r', '/boot/grub/grub.cfg']) == '',
            'ordinary user cannot read the boot configuration')
    require(socket.gethostname() == cfg['hostname'], 'wrong hostname')
    account = pwd.getpwnam(user)
    require((account.pw_uid, account.pw_gid, account.pw_gecos, account.pw_dir) ==
            (1000, 1000, cfg['full_name'], str(home)), 'wrong user identity')
    shadow = {line.split(':')[0]: line.split(':')[1]
              for line in Path('/etc/shadow').read_text().splitlines()}
    require(shadow[user] == '', 'requested user has a password')
    require(shadow['root'].startswith(('!', '*')), 'root account is not locked')
    require(checked(['runuser', '-u', user, '--', 'sudo', '-n', 'id', '-u']) == '0',
            'passwordless sudo failed')
    sddm = configparser.ConfigParser()
    sddm.read('/etc/sddm.conf.d/m4rch.conf')
    require(sddm['Autologin']['User'] == user and
            sddm['Autologin']['Session'] == 'plasma.desktop', 'KDE Wayland autologin missing')
    require(sddm['General']['DisplayServer'] == 'x11', 'working SDDM greeter changed')
    for program in ('firefox', 'nmtui', 'startplasma-wayland', 'kwin_wayland', 'startplasma-x11'):
        require(Path('/usr/bin', program).is_file(), program + ' is missing')
    require(Path('/usr/share/wayland-sessions/plasma.desktop').is_file(), 'KDE Wayland session missing')
    require(Path('/usr/share/xsessions/plasmax11.desktop').is_file(), 'KDE X11 fallback session missing')
    require('Environment=KWIN_COMPOSE=Q' in Path(
        '/etc/systemd/user/plasma-kwin_wayland.service.d/m4rch-software.conf').read_text(),
        'Wayland software compositor setting missing')
    require('Enabled=true' in (home / '.config/kwinrc').read_text(), 'KDE compositing preference missing')
    require(not checked(['systemctl', '--failed', '--no-legend', '--plain']), 'failed systemd units')
    checked(['systemctl', 'is-active', '--quiet', 'NetworkManager'])
    require(Path('/etc/pacman.d/gnupg/.arch-m4-ready').is_file(),
            'first-boot pacman initialization did not finish')
    require(checked(['getconf', '_NPROCESSORS_ONLN']) == '4', 'four CPUs are not online')
    marker('IDENTITY_PASS', attempt)

    require(checked(['uname', '-r']) == cfg['kernel_release'], 'wrong kernel')
    module_dir = Path('/usr/lib/modules') / cfg['kernel_release']
    require((module_dir / 'pkgbase').read_text().strip() == 'linux-m4rch',
            'matching kernel package identity missing')
    require(checked(['pacman', '-Qqo', str(module_dir / 'vmlinuz')]) == 'linux-m4rch',
            'kernel is not owned by pacman')
    require(checked(['pacman', '-Qqo', '/usr/bin/m4rch-boot-update']) == 'config-m4rch',
            'custom setup is not owned by pacman')
    checked(['pacman', '-Q', 'linux-m4rch', 'config-m4rch', 'paru-m4rch', 'base-devel', 'git',
             'grub', 'discover', 'flatpak'])
    require(checked(['pacman', '-Qqo', '/usr/bin/paru']) == 'paru',
            'paru is not owned by its pacman package')
    require('paru' in checked(['runuser', '-u', user, '--', 'paru', '--version']),
            'paru cannot start as Alice against the installed libalpm')
    require(checked(['runuser', '-u', user, '--', 'paru', '-Q', 'linux-m4rch']).startswith('linux-m4rch '),
            'paru cannot query the installed kernel package as Alice')
    checked(['runuser', '-u', user, '--', 'makepkg', '--version'])
    require(subprocess.run(['pacman', '-Q', 'linux-aarch64'], capture_output=True).returncode != 0,
            'generic kernel is still installed')
    checked(['m4rch-boot-update', '--check'])
    for name in ('overlay', 'fuse'):
        require(checked(['pacman', '-Qqo', checked(['modinfo', '-n', name])]) == 'linux-m4rch',
                name + ' module is not owned by pacman')
        checked(['modprobe', name])
        require(re.search(r'^' + name + r' ', Path('/proc/modules').read_text(), re.M),
                name + ' module did not load')
    checked(['modinfo', 'dwc3-apple'])
    marker('MODULES_PASS', attempt)

    if attempt == 2:
        previous = json.loads(state.read_text())
        require(previous == {'nonce': nonce, 'attempt': 1}, 'persistence marker mismatch')
        require((profile / 'user.js').read_text() == f'user_pref("arch_m4.smoke", "{nonce}:1");\n',
                'home profile did not persist')
        require((profile / 'user.js').stat().st_uid == account.pw_uid, 'home owner changed')
        require((profile / 'prefs.js').stat().st_size > 0, 'Firefox preferences missing')
        checked(['sha256sum', '-c', str(profile / 'screenshot.sha256')])
        require(connection.stat().st_mode & 0o777 == 0o600, 'network profile mode changed')
        require('psk=synthetic-' + nonce in connection.read_text(), 'network credentials lost')
        require(checked(['nmcli', '-g', 'connection.id', 'connection', 'show', connection_uuid]) ==
                'arch-m4-smoke', 'NetworkManager did not reload profile')
    else:
        checked(['install', '-d', '-o', user, '-g', user, '-m', '700', str(profile)])
        connection.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        connection.write_text('[connection]\nid=arch-m4-smoke\nuuid=' + connection_uuid +
            '\ntype=wifi\nautoconnect=false\n[wifi]\nmode=infrastructure\nssid=ARCH-M4-SMOKE-NO-NETWORK\n'
            '[wifi-security]\nkey-mgmt=wpa-psk\npsk=synthetic-' + nonce +
            '\n[ipv4]\nmethod=auto\n[ipv6]\nmethod=disabled\n')
        connection.chmod(0o600)
        checked(['nmcli', 'connection', 'load', str(connection)])

    downloader = checked(['python3', '/usr/lib/arch-m4-pacman-smoke', '--sync-as', user], timeout=360)
    require('ARCHM4_PACMAN_SYNC_PASS' in downloader, 'paru repository refresh/download was not verified')
    marker('PACMAN_PASS', attempt)
    marker('PACMAN_SYNC_PASS', attempt)
    (profile / 'user.js').write_text(f'user_pref("arch_m4.smoke", "{nonce}:{attempt}");\n')
    os.chown(profile / 'user.js', account.pw_uid, account.pw_gid)
    screenshot = home / 'firefox-smoke.png'
    checked(['runuser', '-u', user, '--', 'timeout', '180s', 'dbus-run-session', '--',
        'firefox', '--headless', '--no-remote', '--profile', str(profile), '--screenshot',
        str(screenshot), '--window-size', '640,480', 'file:///usr/share/arch-m4-smoke.html'], timeout=210)
    data = screenshot.read_bytes()
    require(data.startswith(b'\x89PNG\r\n\x1a\n') and len(data) > 2048, 'Firefox did not render a PNG')
    (profile / 'screenshot.sha256').write_text(checked(['sha256sum', str(screenshot)]) + '\n')
    os.chown(profile / 'screenshot.sha256', account.pw_uid, account.pw_gid)
    if attempt == 2:
        # Exercise the real package hooks on the mounted FAT ESP. This restores
        # the production initramfs (native SD guards), so do it on the final VM
        # boot after persistence has been checked, never on the source image.
        transaction = checked(['pacman', '-U', '--noconfirm',
            *['/usr/share/arch-m4-custom-packages/' + name for name in cfg['custom_packages']]],
            timeout=240)
        require('Updated SD UEFI boot files for ' + cfg['kernel_release'] in transaction,
                'pacman did not successfully execute the SD boot-update hook')
        require(hashlib.sha256(Path('/boot/vmlinuz-linux-m4rch').read_bytes()).digest() ==
                hashlib.sha256((module_dir / 'vmlinuz').read_bytes()).digest(),
                'pacman hook installed a mismatched kernel')
        require(Path('/boot/EFI/BOOT/BOOTAA64.EFI').read_bytes().startswith(b'MZ'),
                'pacman hook did not regenerate the EFI loader')
        require('root=UUID=' + cfg['root_uuid'] in Path('/boot/grub/grub.cfg').read_text(),
                'pacman hook lost the root UUID')
        require(Path('/boot/initramfs-linux-m4rch.img').stat().st_size > 1024 * 1024,
                'pacman hook produced an empty initramfs')
        marker('CUSTOM_PACKAGE_UPDATE_PASS', attempt)
    state.write_text(json.dumps({'nonce': nonce, 'attempt': attempt}) + '\n')
    checked(['sync'])
    marker('PASS', attempt)

try:
    main()
except Exception as error:
    print('ARCHM4_NATIVE_FAIL:' + str(error), flush=True)
finally:
    subprocess.run(['systemctl', '--no-block', 'poweroff'])
'''


def check_log(text, nonce, attempt):
    if "ARCHM4_NATIVE_FAIL:" in text or "ARCHM4 STOP:" in text:
        raise ValueError(f"Native SD userspace boot {attempt} failed; inspect its log")
    if "error:" in text.split("[    0.000000]", 1)[0].lower():
        raise ValueError(f"Firmware or GRUB reported an error in boot {attempt}; inspect its log")
    for name in ("GROWTH_PASS", "IDENTITY_PASS", "MODULES_PASS", "PACMAN_PASS", "PACMAN_SYNC_PASS", "PASS"):
        if f"ARCHM4_NATIVE_{name}:{nonce}:{attempt}" not in text:
            raise ValueError(f"Missing {name} evidence in native boot {attempt}")
    if "ARCHM4_GRUB_UEFI_BOOT" not in text:
        raise ValueError(f"GRUB execution marker missing in boot {attempt}; inspect the firmware/GRUB log")
    if attempt == 2 and f"ARCHM4_NATIVE_CUSTOM_PACKAGE_UPDATE_PASS:{nonce}:2" not in text:
        raise ValueError("Second boot did not verify the custom pacman boot-update transaction")
    if "reboot: Power down" not in text:
        raise ValueError(f"Native boot {attempt} did not reach kernel poweroff")
    if attempt == 1 and "ARCHM4: expanding native SD root" not in text:
        raise ValueError("First boot did not execute partition growth")
    if attempt == 2 and "ARCHM4: expanding native SD root" in text:
        raise ValueError("Second boot repeated partition growth")
    if attempt == 2 and "resize2fs " in text:
        raise ValueError("Second boot repeated filesystem resizing")


def inject(project, root, work, settings, packages, custom_packages):
    script, service, config, html = (work / name for name in
                                    ("probe.py", "probe.service", "probe.json", "page.html"))
    script.write_text(PROBE)
    config.write_text(json.dumps(settings))
    service.write_text("""[Unit]
Description=Disposable native SD growth and persistence check
After=local-fs.target boot.mount systemd-remount-fs.service NetworkManager.service m4rch-pacman-init.service
Requires=boot.mount
[Service]
Type=oneshot
TimeoutStartSec=780
ExecStart=/usr/bin/python3 /usr/lib/arch-m4-native-smoke
StandardOutput=journal+console
StandardError=journal+console
[Install]
WantedBy=multi-user.target
""")
    html.write_text('<!doctype html><meta charset="utf-8"><title>m4rch</title>'
                   '<style>body{background:#edf4ff;color:#163466;font:32px sans-serif;padding:32px}</style>'
                   '<h1>Firefox on m4rch</h1><p>Native SD root persistence test.</p>')
    files = [(script, "/usr/lib/arch-m4-native-smoke"),
             (service, "/etc/systemd/system/arch-m4-native-smoke.service"),
             (config, "/usr/share/arch-m4-native-smoke.json"),
             (html, "/usr/share/arch-m4-smoke.html"),
             (project / "tests/fixtures/pacman-download.py", "/usr/lib/arch-m4-pacman-smoke")]
    files += [(path, "/usr/share/arch-m4-smoke-package/" + path.name) for path in packages]
    files += [(path, "/usr/share/arch-m4-custom-packages/" + path.name) for path in custom_packages]
    commands = ["mkdir /usr/share/arch-m4-smoke-package",
                "mkdir /usr/share/arch-m4-custom-packages",
                "rm /etc/systemd/system/default.target",
                "symlink /etc/systemd/system/default.target /usr/lib/systemd/system/multi-user.target",
                "mkdir /etc/systemd/system/multi-user.target.wants",
                "symlink /etc/systemd/system/multi-user.target.wants/arch-m4-native-smoke.service /etc/systemd/system/arch-m4-native-smoke.service"]
    commands += [f"write {source} {target}" for source, target in files]
    debugfs(root, commands, work)
    for index, (source, target) in enumerate(files):
        if dump_file(root, target, work / f"readback-{index}") != source.read_bytes():
            raise ValueError(f"Disposable probe readback failed: {target}")


def extract_partition(image, partition, destination):
    first = partition["first_lba"] * 512
    size = (partition["last_lba"] - partition["first_lba"] + 1) * 512
    with image.open("rb") as source, destination.open("wb") as output:
        source.seek(first)
        remaining = size
        while remaining:
            data = source.read(min(4 * 1024**2, remaining))
            if not data:
                raise ValueError("Truncated disposable partition")
            if data.strip(b"\0"):
                output.write(data)
            else:
                output.seek(len(data), os.SEEK_CUR)
            remaining -= len(data)
        output.truncate(size)


def qemu_boot(image, log, timeout=650):
    firmware = Path("/usr/share/qemu-efi-aarch64/QEMU_EFI.fd")
    if not firmware.is_file():
        raise ValueError("Install ARM64 QEMU UEFI firmware to test the real GRUB path")
    command = ["qemu-system-aarch64", "-machine", "virt,gic-version=3", "-cpu", "max",
               "-accel", "tcg,thread=multi", "-smp", "4", "-m", "2048",
               "-display", "none", "-monitor", "none", "-serial", "stdio", "-no-reboot",
               "-nic", "none", "-bios", str(firmware),
               "-drive", f"if=none,id=sdroot,file={image},format=raw,cache=writeback",
               "-device", "virtio-blk-device,drive=sdroot,bootindex=0"]
    started = last_progress = time.monotonic()
    print(f"Booting disposable native SD root; log: {log}", flush=True)
    with log.open("wb") as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                # The rescue shell deliberately never exits on its own. Stop
                # this VM promptly instead of waiting out the whole timeout.
                if b"ARCHM4 STOP:" in log.read_bytes():
                    raise ValueError(f"Native initramfs stopped; inspect {log}")
                now = time.monotonic()
                if now - started > timeout:
                    raise ValueError(f"QEMU exceeded {timeout} seconds; inspect {log}")
                if now - last_progress >= 30:
                    print(f"QEMU is still running ({int(now - started)} seconds); log: {log}", flush=True)
                    last_progress = now
                time.sleep(1)
            if process.returncode:
                raise ValueError(f"QEMU exited with status {process.returncode}; inspect {log}")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    return round(time.monotonic() - started, 2)


def build(project, out, config, lock, kernel_dir):
    report = out / "smoke"
    report.mkdir(exist_ok=True)
    manifest = report / "manifest.json"
    write_json(manifest, {"status": "running", "hardware_tested": False})
    try:
        source = verify_manifest(out / "rootfs-manifest.json")
        init = verify_manifest(out / "initramfs-manifest.json")
        verify_manifest(out / "payload-manifest.json")
        custom = verify_manifest(out / "custom-packages-manifest.json")
        if source["config"] != config or init["config"] != config or custom["config"] != config:
            raise ValueError("Smoke input configuration is stale")
        if sha256(kernel_dir / "boot/Image.gz") != init["kernel_image_sha256"]:
            raise ValueError("Smoke kernel and initramfs do not match")
        nonce = str(uuid.uuid4())
        packages = signed_package_fixture(out / "packages.lock.json", Path("/cache/desktop-packages"))
        custom_packages = [out / "packages" / record["file"]
                           for record in custom["packages"].values()]
        with tempfile.TemporaryDirectory(prefix="sd-smoke-", dir="/work") as temporary:
            work = Path(temporary)
            root = work / "rootfs.ext4"
            run(["cp", "--reflink=auto", "--sparse=always", out / "rootfs.ext4", root])
            settings = dict(config, nonce=nonce, kernel_release=init["kernel_release"],
                            modules_sha256=init["modules_sha256"],
                            custom_packages=[path.name for path in custom_packages])
            inject(project, root, work, settings, packages, custom_packages)
            run(["e2fsck", "-fn", root])
            shutil.copytree(out / "esp", work / "esp")
            shutil.copyfile(out / "test-initramfs.cpio.gz", work / "esp/initramfs-linux-m4rch.img")
            grub = work / "esp/grub/grub.cfg"
            grub.write_text("set timeout=0\nset default=0\nterminal_output console\nmenuentry 'm4rch UEFI smoke' {\n"
                            "  echo ARCHM4_GRUB_UEFI_BOOT\n"
                            "  linux /vmlinuz-linux-m4rch console=ttyAMA0 rdinit=/init root=/dev/vda2 rw panic=-1 idle=nop arm64.nowfxt\n"
                            "  initrd /initramfs-linux-m4rch.img\n}\n")
            paths = sorted(str(path.relative_to(work)) for path in (work / "esp").rglob("*") if path.is_file())
            write_json(work / "payload-manifest.json", {"layout": media.LAYOUT, "config": config,
                       "files": manifest_files(work, paths)})
            initial = media.compose(work, config)
            image = work / "m4rch.img"
            with image.open("r+b") as stream:
                stream.truncate(image.stat().st_size + 1024**3)
            durations = []
            for attempt in (1, 2):
                log = report / f"boot-{attempt}.log"
                durations.append(qemu_boot(image, log, timeout=900))
                check_log(log.read_text(errors="replace"), nonce, attempt)
                table = gpt.inspect(image)
                if table["partitions"][0] != initial["gpt"]["partitions"][0]:
                    raise ValueError("Growing root changed the boot partition")
                if table["partitions"][1]["last_lba"] != image.stat().st_size // 512 - 34:
                    raise ValueError("Growing root left unused card capacity")
                with (report / f"fsck-{attempt}.log").open("wb") as stream:
                    for partition, name, command in ((table["partitions"][0], "audit.fat", ["fsck.fat", "-n"]),
                                                     (table["partitions"][1], "audit.ext4", ["e2fsck", "-fn"])):
                        audited = work / name
                        extract_partition(image, partition, audited)
                        run([*command, audited], stdout=stream, stderr=subprocess.STDOUT)
                observed = json.loads(dump_file(work / "audit.ext4", "/var/lib/arch-m4-native-smoke.json",
                                               work / f"state-{attempt}"))
                if observed != {"nonce": nonce, "attempt": attempt}:
                    raise ValueError("Independent persistence readback failed")
                (work / "audit.fat").unlink()
                (work / "audit.ext4").unlink()
            files = [f"{kind}-{attempt}.log" for kind in ("boot", "fsck") for attempt in (1, 2)]
            write_json(manifest, {"schema": 1, "status": "passed", "test": "qemu-uefi-grub-native-sd-root",
                "hardware_tested": False, "apple_sd_loader_tested": False, "kde_display_tested": False,
                "root_image_sha256": source["files"]["rootfs.ext4"]["sha256"],
                "kernel_sha256": init["kernel_image_sha256"], "test_initramfs_sha256": sha256(out / "test-initramfs.cpio.gz"),
                "partition_and_ext4_growth_verified": True, "second_boot_growth_idempotent": True,
                "user_identity_and_passwordless_sudo_verified": True, "matching_modules_load_verified": True,
                "pacman_owns_kernel_modules_and_setup_verified": True, "uefi_grub_boot_verified": True,
                "custom_pacman_boot_update_transaction_verified": True,
                "paru_runs_as_default_user_verified": True,
                "paru_repository_refresh_and_signed_install_verified": True,
                "signed_sandboxed_package_install_verified": True, "firefox_headless_render_verified": True,
                "home_and_network_profile_persistence_verified": True, "clean_shutdowns": 2,
                "boot_seconds": durations, "files": manifest_files(report, files)})
    except BaseException as error:
        write_json(manifest, {"status": "failed", "hardware_tested": False, "error": str(error)})
        raise
