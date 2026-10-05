"""Contract tests for the package/UEFI integration, not the old FIT installer."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import uuid

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "lib"))
sys.path.insert(0, str(PROJECT))
from sdboot.packages import boot_settings, export_update, make_source_archive, render_boot_configuration, stage_update_diagnostics, kernel_package_version, verify_package_owner
from sdboot.rootfs import testing_initramfs
from image import newc


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((PROJECT / "sdboot/config.json").read_text())

    def test_update_kit_names_only_current_packages_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            (out / "packages").mkdir()
            records = {}
            for name in ("linux-m4rch", "config-m4rch", "grub-m4rch", "paru-m4rch"):
                filename = name + "-1-aarch64.pkg.tar.zst"
                data = (name + " package fixture").encode()
                (out / "packages" / filename).write_bytes(data)
                records[name] = {"file": filename, "sha256": hashlib.sha256(data).hexdigest()}
            (out / "packages/config-m4rch-OLD-aarch64.pkg.tar.zst").write_bytes(b"obsolete")
            kit = out / export_update(out, records)
            self.assertEqual(len(list(kit.glob("*.pkg.tar.zst"))), 4)
            script = (kit / "install.sh").read_text()
            self.assertNotIn("OLD", script)
            self.assertNotIn("*", script)
            self.assertLess(script.index("sha256sum -c"), script.index("pacman -U"))
            self.assertLess(script.index("NoUpgrade = etc/arch-m4/boot.conf"), script.index("pacman -U"))
            subprocess.run(["sh", "-n", str(kit / "install.sh")], check=True)
            subprocess.run(["sh", "-n", str(kit / "diagnose.sh")], check=True)
            self.assertEqual((kit / "diagnose.sh").read_bytes(),
                             (PROJECT / "templates/update-diagnostics.sh").read_bytes())
            self.assertEqual((kit / "m4rch-driver-diagnostics").read_bytes(),
                             (PROJECT / "templates/collect-driver-diagnostics.sh").read_bytes())
            checksums = (kit / "DIAGNOSTICS-SHA256SUMS").read_text().splitlines()
            for line in checksums:
                digest, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256((kit / name).read_bytes()).hexdigest(), digest)
            for record in records.values():
                self.assertEqual(hashlib.sha256((kit / record["file"]).read_bytes()).hexdigest(), record["sha256"])
                self.assertIn(record["file"], script)
            (out / "packages" / records["grub-m4rch"]["file"]).write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "changed after verification"):
                export_update(out, records)

    def test_diagnostic_staging_rejects_links_before_overwriting_other_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            kit = root / "kit"
            kit.mkdir()
            preserved = root / "preserved"
            preserved.write_text("existing unrelated file")
            (kit / "m4rch-driver-diagnostics").symlink_to(preserved)
            with self.assertRaisesRegex(ValueError, "regular file"):
                stage_update_diagnostics(kit)
            self.assertEqual(preserved.read_text(), "existing unrelated file")
            self.assertFalse((kit / "diagnose.sh").exists())

    def test_installed_policy_uses_same_esp_identity_as_gpt(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            render_boot_configuration(PROJECT, stage, self.config, "7.1-test")
            settings = boot_settings(self.config)
            identity = uuid.uuid5(uuid.UUID(self.config["root_uuid"]), "arch-m4-uefi-v2:boot")
            self.assertEqual(settings["BOOT_PARTITION_UUID"], str(identity))
            serial = identity.hex[:8].upper()
            grub = (stage / "usr/share/m4rch/grub-embedded.cfg.in").read_text()
            self.assertIn("@BOOT_FAT_UUID@", grub)
            self.assertIn("configfile ($root)/grub/grub.cfg", grub)
            self.assertNotIn("set prefix=", grub)
            menu = (stage / "usr/share/m4rch/grub.cfg.in").read_text()
            self.assertIn("linux /vmlinuz-linux-m4rch root=UUID=@ROOT_UUID@", menu)
            self.assertNotIn(self.config["root_uuid"], menu)
            self.assertIn("initrd /initramfs-linux-m4rch.img", menu)
            self.assertNotIn("devicetree", menu)  # preserve m1n1's live EFI DT

    def test_hook_guards_before_kernel_transaction_and_updates_after(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            render_boot_configuration(PROJECT, stage, self.config, "7.1-test")
            pre = (stage / "usr/share/libalpm/hooks/50-m4rch-boot-check.hook").read_text()
            post = (stage / "usr/share/libalpm/hooks/99-m4rch-boot-update.hook").read_text()
            self.assertIn("When=PreTransaction", pre)
            self.assertIn("AbortOnFail", pre)
            self.assertIn("m4rch-boot-update --check", pre)
            self.assertIn("When=PostTransaction", post)
            self.assertIn("Target=grub", post)
            self.assertIn("Target=linux-m4rch", post)
            for name in ("config-m4rch", "grub-m4rch", "linux-t6040", "arch-m4-config"):
                self.assertIn("Target=" + name + "\n", pre)
                self.assertIn("Target=" + name + "\n", post)
            self.assertIn("Target=usr/lib/firmware/*", pre)
            self.assertIn("Target=usr/lib/firmware/*", post)
            self.assertTrue((stage / "etc/pacman.d/hooks/90-mkinitcpio-install.hook").is_symlink())
            script = stage / "usr/bin/m4rch-boot-update"
            subprocess.run(["sh", "-n", str(script)], check=True)

    def test_normal_versions_and_package_owner_require_current_recipe(self):
        self.assertEqual(kernel_package_version("7.1.3-m4rch"), "7.1.3")
        for invalid in ("linux-m4rch-7.1.3", "7.1.3-arch-m4-experimental", "7.1.3-m4rch-dirty"):
            with self.assertRaises(ValueError):
                kernel_package_version(invalid)
        with patch("sdboot.packages.subprocess.check_output", return_value="linux-m4rch\n"):
            verify_package_owner("/test-root", "/kernel", "linux-m4rch")
        for incorrect in ("linux-t6040", "linux", ""):
            with patch("sdboot.packages.subprocess.check_output", return_value=incorrect):
                with self.assertRaisesRegex(ValueError, "Wrong package owner"):
                    verify_package_owner("/test-root", "/kernel", "linux-m4rch")

    def test_custom_recipes_replace_previous_package_names(self):
        for name, old in (("linux-m4rch", "linux-t6040"), ("config-m4rch", "arch-m4-config"),
                          ("grub-m4rch", "grub"), ("paru-m4rch", "paru")):
            recipe = (PROJECT / "packages" / name / "PKGBUILD").read_text()
            self.assertIn("pkgname=" + name + "\n", recipe)
            for field in ("provides", "conflicts", "replaces"):
                import re
                value = re.search(r"^" + field + r"=\(([^\n]*)\)", recipe, re.MULTILINE)
                self.assertIsNotNone(value, (name, field))
                self.assertIn(old, value[1])

    def test_source_archives_normalize_metadata_and_include_dotfiles(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            stage = base / "stage"
            (stage / "etc").mkdir(parents=True)
            (stage / "etc/.setting").write_text("setting\n")
            (stage / "etc/link").symlink_to("/dev/null")
            first, second = base / "first.tar.gz", base / "second.tar.gz"
            make_source_archive(stage, first, 1000)
            make_source_archive(stage, second, 1000)
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())
            with tarfile.open(first) as archive:
                self.assertIn("payload/etc/.setting", archive.getnames())
                for member in archive:
                    self.assertEqual((member.uid, member.gid, member.mtime), (0, 0, 1000))

    def test_initramfs_never_replaces_pacman_owned_module_tree(self):
        script = (PROJECT / "sdboot/init").read_text()
        self.assertIn("$release_dir/pkgbase", script)
        self.assertNotIn("tar -x", script)
        self.assertNotIn("/modules/kernel.tar.gz", script)
        self.assertNotIn("mv \"$stage/usr/lib/modules", script)
        self.assertIn("root-capacity-sectors", script)
        self.assertIn("/sbin/resize2fs", script)

    def test_test_image_changes_only_production_guard_and_preserves_early_cpio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            early = root / "early"
            early.mkdir()
            (early / "early_cpio").write_text("1\n")
            tree = root / "main"
            (tree / "etc").mkdir(parents=True)
            (tree / "etc/sdboot.conf").write_text("ROOT_UUID='fixed'\nTESTING='0'\n")
            (tree / "init").write_text("#!/bin/sh\necho actual-production-init\n")
            raw = newc(tree, 1000)
            prefix = newc(early, 1000)
            production, testing = root / "production.img", root / "testing.img"
            production.write_bytes(prefix + gzip.compress(raw, mtime=0))
            testing_initramfs(production, testing)
            self.assertEqual(testing.read_bytes()[:len(prefix)], prefix)
            unpacked = gzip.decompress(testing.read_bytes()[len(prefix):])
            self.assertEqual(unpacked, raw.replace(b"TESTING='0'\n", b"TESTING='1'\n"))
            self.assertEqual(gzip.decompress(production.read_bytes()[len(prefix):]), raw)

    def test_paru_recipe_declares_all_pinned_sources(self):
        metadata = PROJECT / "packages/paru-m4rch/source.json"
        pin = json.loads(metadata.read_text())
        recipe = (PROJECT / "packages/paru-m4rch/PKGBUILD").read_text()
        self.assertIn("pkgver=" + pin["version"], recipe)
        self.assertIn("_commit=" + pin["revision"], recipe)
        self.assertIn(pin["sha256"], recipe)
        self.assertIn(pin["cargo_lock_sha256"], recipe)
        self.assertIn(hashlib.sha256(metadata.read_bytes()).hexdigest(), recipe)
        self.assertIn("'source.json'", recipe)
        self.assertIn('"$srcdir/source.json"', recipe)
        self.assertIn("cargo fetch --locked", recipe)
        self.assertIn("cargo build --frozen", recipe)
        self.assertEqual(pin["libalpm_major"], 16)
        source = PROJECT / "cache/paru" / pin["filename"]
        if source.is_file():
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), pin["sha256"])
            with tarfile.open(source) as archive:
                data = archive.extractfile("paru-" + pin["revision"] + "/Cargo.lock").read()
                self.assertEqual(hashlib.sha256(data).hexdigest(), pin["cargo_lock_sha256"])

    def test_desktop_and_build_prerequisites_are_selected(self):
        self.assertTrue({"grub", "mkinitcpio", "discover", "flatpak", "packagekit-qt6", "fakeroot", "git", "base-devel", "rust"} <= set(self.config["packages"]))


if __name__ == "__main__":
    unittest.main()
