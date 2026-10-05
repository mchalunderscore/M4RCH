"""Execute the supported upgrade wrapper across ALPM's package-rename ordering."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib"))
sys.path.insert(0, str(PROJECT))
from sdboot.packages import PACKAGE_NAMES, boot_settings, export_update, render_boot_configuration
from sdboot.rootfs import configure_package


class PackageMigrationTests(unittest.TestCase):
    def command(self, directory, name, body):
        path = directory / name
        path.write_text("#!/bin/sh\nset -eu\n" + body + "\n")
        path.chmod(0o755)

    def map_script(self, source, root, binaries):
        mapped = (source.replace("PATH=/usr/bin:/bin:/usr/sbin:/sbin", "PATH=" + str(binaries) + ":/usr/bin:/bin")
                .replace("/usr/bin/m4rch-boot-update", str(root / "usr/bin/m4rch-boot-update"))
                .replace("/etc/", str(root / "etc") + "/")
                .replace("/usr/lib/", str(root / "usr/lib") + "/")
                .replace("/usr/share/", str(root / "usr/share") + "/")
                .replace("/run/", str(root / "run") + "/"))
        return re.sub(r"/boot(?=/|[\s\"'])", str(root / "boot"), mapped)

    def test_kit_preserves_identity_when_old_package_is_removed_before_new_install(self):
        for legacy, modified in ((True, False), (True, True), (False, False)):
            with self.subTest(legacy=legacy, modified=modified), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                root, stage, binaries, out = (base / name for name in ("root", "stage", "bin", "out"))
                for directory in (root / "etc/arch-m4", root / "run", root / "boot", binaries, out / "packages"):
                    directory.mkdir(parents=True)
                old = json.loads((PROJECT / "sdboot/config.json").read_text())
                new = dict(old, root_uuid="00000000-0000-4000-8000-000000000033")
                installed = boot_settings(old)
                config_path = root / "etc/arch-m4/boot.conf"
                original = "".join(f"{key}='{value}'\n" for key, value in installed.items())
                if modified:
                    original += "# locally preserved identity policy\n"
                config_path.write_text(original)
                (root / "etc/pacman.conf").write_text("[options]\nSigLevel = Required DatabaseOptional\n[core]\nServer = https://example.invalid/$arch\n")
                configure_package(PROJECT, stage, new)
                render_boot_configuration(PROJECT, stage, new, "7.1.3-m4rch")
                helper = stage / "usr/bin/m4rch-boot-update"
                helper.write_text(self.map_script(helper.read_text(), root, binaries))
                release = root / "usr/lib/m4rch/kernel-release"
                release.parent.mkdir(parents=True)
                release.write_text("7.1.3-m4rch\n")
                (release.parent / "board.dtbo").write_bytes(b"DT fixture")
                modules = root / "usr/lib/modules/7.1.3-m4rch"
                modules.mkdir(parents=True)
                (modules / "vmlinuz").write_bytes(b"MZ kernel fixture")
                (modules / "pkgbase").write_text("linux-m4rch\n")
                for group in ("platform", "usb", "nvme"):
                    prefix = "arch-m4" if legacy else "m4rch"
                    oldunit = root / f"etc/systemd/system/graphical.target.wants/{prefix}-{group}.service"
                    oldunit.parent.mkdir(parents=True, exist_ok=True)
                    oldunit.symlink_to(f"/usr/lib/systemd/system/{prefix}-{group}.service")
                self.command(binaries, "id", "printf '0\\n'")
                self.command(binaries, "uname", "case $1 in -s) echo Linux;; -m) echo aarch64;; esac")
                self.command(binaries, "mountpoint", "exit 0")
                self.command(binaries, "sha256sum", "exit 0")
                self.command(binaries, "findmnt", 'case "$*" in *FSTYPE*) echo vfat;; *--target\\ /) echo /dev/root;; *) echo /dev/esp;; esac')
                self.command(binaries, "blkid", f'case "$*" in *PARTUUID*) echo {installed["BOOT_PARTITION_UUID"]};; *) echo {installed["ROOT_UUID"]};; esac')
                self.command(binaries, "flock", "exit 0")
                self.command(binaries, "depmod", "exit 0")
                self.command(binaries, "mkinitcpio", 'while [ "$1" != -g ]; do shift; done; printf initramfs >"$2"')
                self.command(binaries, "grub-mkstandalone", 'while [ "$1" != -o ]; do shift; done; printf MZefi >"$2"')
                self.command(binaries, "sync", "exit 0")
                self.command(binaries, "systemctl", 'test "$*" = daemon-reload')
                # ALPM first removes a conflicting old owner. NoUpgrade must
                # already be active: pre_install in the incoming package is
                # too late for an unchanged backup file, which gets no pacsave.
                fake_pacman = binaries / "pacman"
                fake_pacman.write_text("#!" + sys.executable + "\n" + f'''
import pathlib, shutil, subprocess, sys
root = pathlib.Path({str(root)!r})
stage = pathlib.Path({str(stage)!r})
conf = pathlib.Path(sys.argv[sys.argv.index('--config') + 1]).read_text()
assert '[options]\\nNoUpgrade = etc/arch-m4/boot.conf\\n' in conf
assert 'SigLevel = Required DatabaseOptional' in conf
assert 'Server = https://example.invalid/$arch' in conf
for old_link in (root / 'etc/systemd/system/graphical.target.wants').glob('arch-m4-*.service'):
    old_link.unlink()
for path in sorted(stage.rglob('*')):
    relative = path.relative_to(stage)
    if relative.as_posix() == 'etc/arch-m4/boot.conf':
        (root / 'etc/arch-m4/boot.conf.pacnew').write_bytes(path.read_bytes())
        continue
    destination = root / relative
    if path.is_dir() and not path.is_symlink():
        destination.mkdir(parents=True, exist_ok=True)
    elif path.is_symlink():
        destination.unlink(missing_ok=True)
        destination.symlink_to(path.readlink())
    else:
        shutil.copy2(path, destination)
# Hooks are re-read after the replacement; execute the incoming helper now.
subprocess.run(['sh', str(root / 'usr/bin/m4rch-boot-update')], check=True)
''')
                fake_pacman.chmod(0o755)
                records = {}
                for name in PACKAGE_NAMES:
                    filename = name + "-1-aarch64.pkg.tar.zst"
                    data = name.encode()
                    (out / "packages" / filename).write_bytes(data)
                    records[name] = {"file": filename, "sha256": hashlib.sha256(data).hexdigest()}
                kit = out / export_update(out, records)
                runner = kit / "install.sh"
                runner.write_text(self.map_script(runner.read_text(), root, binaries))
                result = subprocess.run(["sh", runner], text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(config_path.read_text(), original)
                self.assertNotEqual((root / "etc/arch-m4/boot.conf.pacnew").read_text(), original)
                self.assertIn("root=UUID=" + old["root_uuid"], (root / "boot/grub/grub.cfg").read_text())
                self.assertNotIn(new["root_uuid"], (root / "boot/grub/grub.cfg").read_text())
                self.assertEqual((root / "boot/vmlinuz-linux-m4rch").read_bytes(), (modules / "vmlinuz").read_bytes())
                for group in ("platform", "usb", "nvme"):
                    link = root / f"etc/systemd/system/graphical.target.wants/m4rch-{group}.service"
                    self.assertEqual(os.readlink(link), f"/usr/lib/systemd/system/m4rch-{group}.service")
                    self.assertFalse((link.parent / f"arch-m4-{group}.service").is_symlink())
                self.assertFalse(list((root / "run").glob("m4rch-pacman-*")))

    def test_successful_pacman_status_does_not_hide_a_failed_boot_hook(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, binaries, out = base / "root", base / "bin", base / "out"
            for directory in (root / "etc/arch-m4", root / "run", root / "usr/bin", binaries, out / "packages"):
                directory.mkdir(parents=True)
            config = json.loads((PROJECT / "sdboot/config.json").read_text())
            identity = boot_settings(config)
            (root / "etc/arch-m4/boot.conf").write_text("".join(f"{key}='{value}'\n" for key, value in identity.items()))
            (root / "etc/pacman.conf").write_text("[options]\nSigLevel = Required DatabaseOptional\n")
            for name, body in (("id", "echo 0"), ("uname", "case $1 in -s) echo Linux;; -m) echo aarch64;; esac"),
                               ("mountpoint", "exit 0"), ("sha256sum", "exit 0"),
                               ("findmnt", 'case "$*" in *FSTYPE*) echo vfat;; *) echo /dev/fixture;; esac'),
                               ("blkid", f'case "$*" in *PARTUUID*) echo {identity["BOOT_PARTITION_UUID"]};; *) echo {identity["ROOT_UUID"]};; esac'),
                               ("pacman", "exit 0")):
                self.command(binaries, name, body)
            helper = root / "usr/bin/m4rch-boot-update"
            self.command(helper.parent, helper.name, "printf 'mkinitcpio failed; fix boot before rebooting\\n' >&2; exit 7")
            records = {}
            for name in PACKAGE_NAMES:
                filename = name + "-1-aarch64.pkg.tar.zst"
                data = name.encode()
                (out / "packages" / filename).write_bytes(data)
                records[name] = {"file": filename, "sha256": hashlib.sha256(data).hexdigest()}
            kit = out / export_update(out, records)
            runner = kit / "install.sh"
            runner.write_text(self.map_script(runner.read_text(), root, binaries))
            result = subprocess.run(["sh", runner], text=True, capture_output=True)
            self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
            self.assertNotIn("Packages installed. Reboot", result.stdout)
            self.assertIn("fix boot before rebooting", result.stderr)

    def test_direct_pacman_identity_mismatch_cannot_publish_esp_files(self):
        for field in ("ROOT_UUID", "BOOT_PARTITION_UUID"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                root, binaries = base / "root", base / "bin"
                for directory in (root / "etc/arch-m4", root / "boot", binaries):
                    directory.mkdir(parents=True)
                config = json.loads((PROJECT / "sdboot/config.json").read_text())
                actual = boot_settings(config)
                wrong = dict(actual, **{field: "00000000-0000-4000-8000-000000000044"})
                (root / "etc/arch-m4/boot.conf").write_text("".join(f"{key}='{value}'\n" for key, value in wrong.items()))
                kernel = root / "boot/vmlinuz-linux-m4rch"
                kernel.write_bytes(b"preserved working ESP kernel")
                self.command(binaries, "id", "echo 0")
                self.command(binaries, "mountpoint", "exit 0")
                self.command(binaries, "findmnt", 'case "$*" in *FSTYPE*) echo vfat;; *) echo /dev/fixture;; esac')
                self.command(binaries, "blkid", f'case "$*" in *PARTUUID*) echo {actual["BOOT_PARTITION_UUID"]};; *) echo {actual["ROOT_UUID"]};; esac')
                helper = base / "update.sh"
                helper.write_text(self.map_script((PROJECT / "packages/config-m4rch/m4rch-boot-update").read_text(), root, binaries))
                result = subprocess.run(["sh", helper], text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("transaction may already have committed; ESP files are unchanged", result.stderr)
                self.assertIn("before rebooting", result.stderr)
                self.assertEqual(kernel.read_bytes(), b"preserved working ESP kernel")

    def test_cached_mkinitcpio_parser_accepts_numeric_module_abi(self):
        package = PROJECT / "cache/sdboot-packages/mkinitcpio-42.1-1-any.pkg.tar.xz"
        if not package.is_file():
            self.skipTest("No cached mkinitcpio source package")
        with tarfile.open(package) as archive:
            text = archive.extractfile("usr/lib/initcpio/functions").read().decode()
        functions = []
        for name in ("kver_generic", "kver"):
            start = text.index(name + "() {")
            functions.append(text[start:text.index("\n}\n", start) + 3])
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary) / "Image"
            script = '\n'.join(functions) + '\nuname() { echo aarch64; }; decompress_cat() { cat "$1"; }; kver "$1"'
            for release, success in (("7.1.3-m4rch", True), ("linux-m4rch-7.1.3", False)):
                image.write_bytes(("prefix\0Linux version " + release + " (m4rch)\0suffix").encode())
                result = subprocess.run(["bash", "-O", "extglob", "-c", script, "parser", str(image)], text=True, capture_output=True)
                self.assertEqual(result.returncode == 0, success, result.stderr)
                if success:
                    self.assertEqual(result.stdout, release)


if __name__ == "__main__":
    unittest.main()
