"""Root setup checks; native partition growth is additionally exercised in QEMU."""
import json
import gzip
import hashlib
import io
import configparser
import os
from pathlib import Path
import sys
import tempfile
import tarfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from sdboot.rootfs import configure_accounts, configure_root, configure_package, verified_modules


class RootfsTests(unittest.TestCase):
    def fixture(self, root):
        for directory in ("etc", "home/alarm", "run", "tmp", "var/tmp", "usr/share/zoneinfo/Europe", "usr/lib/systemd/system"):
            (root / directory).mkdir(parents=True, exist_ok=True)
        (root / "etc/passwd").write_text("root:x:0:0:root:/root:/bin/bash\nalarm:x:1000:1000:Alarm:/home/alarm:/bin/bash\n")
        (root / "etc/shadow").write_text("root:public-password:1::::::\nalarm:public-password:1:0:99999:7:::\n")
        (root / "etc/group").write_text("root:x:0:\nwheel:x:10:alarm\nalarm:x:1000:\nvideo:x:44:alarm,other\n")
        (root / "etc/gshadow").write_text("root:!::\nwheel:!::alarm\nalarm:!::\nvideo:!::alarm,other\n")
        (root / "etc/subuid").write_text("alarm:65536:65536\n")
        (root / "usr/share/zoneinfo/Europe/London").write_bytes(b"fixture")
        (root / "usr/lib/systemd/system/systemd-networkd-varlink.socket").touch()
        (root / "usr/lib/systemd/system/systemd-resolved-monitor.socket").touch()
        (root / "home/alarm/keep-me").write_text("home contents")
        return json.loads((PROJECT / "sdboot/config.json").read_text())

    def test_fresh_kde_user_and_recovery_console(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.fixture(root)
            configure_package(PROJECT, root, config)
            configure_root(PROJECT, root, config)
            self.assertIn("alice:x:1000:1000:Alice Admin:/home/alice:/bin/bash", (root / "etc/passwd").read_text())
            self.assertNotIn("alarm:", (root / "etc/passwd").read_text())
            self.assertEqual((root / "etc/shadow").read_text().splitlines(), ["root:!:1::::::", "alice::::::::"])
            self.assertIn("video:x:44:alice,other", (root / "etc/group").read_text())
            self.assertIn("wheel:!::alice", (root / "etc/gshadow").read_text())
            self.assertEqual((root / "home/alice/keep-me").read_text(), "home contents")
            self.assertFalse((root / "home/alarm").exists())
            self.assertEqual((root / "etc/hostname").read_text(), "t6040\n")
            self.assertEqual((root / "etc/shadow").stat().st_mode & 0o777, 0o600)
            self.assertEqual((root / "etc/sudoers.d/10-m4rch").stat().st_mode & 0o777, 0o440)
            self.assertIn("alice ALL=(ALL:ALL) NOPASSWD: ALL", (root / "etc/sudoers.d/10-m4rch").read_text())
            sddm = configparser.ConfigParser()
            sddm.read(root / "etc/sddm.conf.d/m4rch.conf")
            self.assertEqual(sddm["Autologin"]["Session"], "plasma.desktop")
            self.assertEqual(sddm["Autologin"]["User"], "alice")
            self.assertEqual(sddm["General"]["DisplayServer"], "x11")
            self.assertFalse(sddm["Autologin"].getboolean("Relogin"))
            wayland_unit = root / "etc/systemd/user/plasma-kwin_wayland.service.d/m4rch-software.conf"
            self.assertIn("Environment=KWIN_COMPOSE=Q", wayland_unit.read_text())
            # Only the Wayland unit should force QPainter; X11 retains its
            # separate compositor and the shared Qt software flags.
            self.assertNotIn("KWIN_COMPOSE", (root / "etc/environment.d/10-m4rch.conf").read_text())
            self.assertNotIn("KWIN_COMPOSE", (root / "etc/profile.d/m4rch-software.sh").read_text())
            self.assertIn("--autologin alice", (root / "etc/systemd/system/getty@tty2.service.d/autologin.conf").read_text())
            self.assertIn("Enabled=true", (root / "home/alice/.config/kwinrc").read_text())
            self.assertIn("Autolock=false", (root / "home/alice/.config/kscreenlockerrc").read_text())
            self.assertIn("LIBGL_ALWAYS_SOFTWARE=1", (root / "etc/environment.d/10-m4rch.conf").read_text())
            self.assertIn("pacman-key --populate archlinuxarm", (root / "etc/systemd/system/m4rch-pacman-init.service").read_text())
            self.assertEqual(os.readlink(root / "etc/systemd/system/multi-user.target.wants/m4rch-pacman-init.service"), "/etc/systemd/system/m4rch-pacman-init.service")
            boot_fields = (root / "etc/fstab").read_text().splitlines()[1].split()
            self.assertEqual(boot_fields, ["PARTUUID=969c748a-4de0-59db-a81c-3bb8fa6862fa", "/boot", "vfat", "defaults,uid=0,gid=0,fmask=0133,dmask=0022", "0", "2"])
            self.assertNotIn("loop", (root / "etc/fstab").read_text())
            for name in ("sshd.service", "sshd.socket", "sleep.target", "systemd-networkd-varlink.socket", "systemd-resolved-monitor.socket"):
                self.assertEqual(os.readlink(root / "etc/systemd/system" / name), "/dev/null")
            self.assertTrue(os.readlink(root / "etc/systemd/system/default.target").endswith("graphical.target"))

    def test_unexpected_source_account_is_not_reassigned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.fixture(root)
            (root / "etc/passwd").write_text("root:x:0:0:root:/root:/bin/bash\nalarm:x:1001:1001:Alarm:/home/alarm:/bin/bash\n")
            original = (root / "etc/passwd").read_bytes()
            with self.assertRaisesRegex(ValueError, "UID/GID"):
                configure_accounts(root, config)
            self.assertEqual((root / "etc/passwd").read_bytes(), original)

    def test_new_user_cannot_collide_with_existing_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self.fixture(root)
            with (root / "etc/passwd").open("a") as stream:
                stream.write("alice:x:1001:1001:Existing:/home/alice:/bin/bash\n")
            with self.assertRaisesRegex(ValueError, "already exists"):
                configure_accounts(root, config)

    def test_current_driver_kit_matches_exact_kernel(self):
        from driver_tools import stage
        with tempfile.TemporaryDirectory() as temporary:
            kernel = Path(temporary)
            (kernel / "boot").mkdir()
            image = kernel / "boot/Image.gz"
            image.write_bytes(gzip.compress(b"kernel fixture"))
            modules = kernel / "modules.tar.gz"
            release = "7.1.3-m4rch"
            with tarfile.open(modules, "w:gz") as archive:
                member = tarfile.TarInfo(f"usr/lib/modules/{release}/kernel/test.ko")
                member.size = len(b"module fixture")
                archive.addfile(member, io.BytesIO(b"module fixture"))
            stage(PROJECT, kernel / "driver-tools", modules_archive=modules,
                  kernel_release=release, kernel_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                  blocked_modules=["nvme-apple"])
            kit, installer, manifest = verified_modules(PROJECT, kernel)
            self.assertEqual(manifest["kernel_release"], release)
            self.assertEqual(manifest["blocked_modules"], ["nvme-apple"])
            image.write_bytes(gzip.compress(b"different kernel"))
            with self.assertRaisesRegex(ValueError, "Kernel image and driver kit"):
                verified_modules(PROJECT, kernel)


if __name__ == "__main__":
    unittest.main()
