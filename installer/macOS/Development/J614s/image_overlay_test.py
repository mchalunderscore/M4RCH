import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import build_m4rch_grub

HERE = Path(__file__).resolve().parent
OVERLAY = HERE / "image-overlay/etc"


class OverlayTests(unittest.TestCase):
    def test_grub_dropin_preserves_existing_arguments_and_promoted_j614s_options(self):
        dropin = OVERLAY / "default/grub.d/50-m4rch.cfg"
        result = subprocess.run(
            [
                "/bin/bash",
                "-eu",
                "-c",
                'GRUB_CMDLINE_LINUX="rootflags=subvol=root"; source "$1"; printf "%s" "$GRUB_CMDLINE_LINUX"',
                "grub-test",
                str(dropin),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(
            result.stdout,
            "rootflags=subvol=root " + build_m4rch_grub.BOOT_OPTIONS.decode(),
        )

    def test_generic_m1n1_updates_are_disabled(self):
        config = (OVERLAY / "default/update-m1n1").read_text()
        self.assertIn("M1N1_UPDATE_DISABLED=1", config.splitlines())

    def test_stock_sep_loader_and_timer_are_masked(self):
        units = OVERLAY / "systemd/system"
        for name in ("aurora-sep.service", "aurora-sep.timer"):
            self.assertTrue((units / name).is_symlink())
            self.assertEqual(os.readlink(units / name), "/dev/null")

    def test_promoted_board_options_disable_unqualified_speaker_amplifiers(self):
        board = (HERE / "image-overlay/usr/lib/modprobe.d/m4rch-j614s.conf").read_text()
        self.assertIn("options asahi t6040_16core=1", board.splitlines())
        self.assertIn("blacklist snd_soc_tas2764", board.splitlines())
        self.assertIn("blacklist snd_soc_tas2770", board.splitlines())
        config = (OVERLAY / "mkinitcpio-m4rch.conf").read_text()
        self.assertIn(
            "FILES+=(/usr/lib/modprobe.d/m4rch-j614s.conf)", config.splitlines()
        )

    def test_separate_config_preserves_hooks_and_includes_m4_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "mkinitcpio.conf").write_text(
                "MODULES=()\nHOOKS=(base autodetect)\n"
            )
            dropins = root / "mkinitcpio.conf.d"
            dropins.mkdir()
            (dropins / "90-aurora.conf").write_text(
                "HOOKS=(base systemd asahi aurora-vendor block sd-encrypt aurora-root filesystems fsck)\n"
            )
            (dropins / "90-aurora-audio.conf").write_text("MODULES+=(snd-seq)\n")
            source = (
                (OVERLAY / "mkinitcpio-m4rch.conf")
                .read_text()
                .replace("/etc/", str(root) + "/")
            )
            config = root / "candidate.conf"
            config.write_text(source)
            command = 'source "$1"; printf "%s\\n" "${MODULES[@]}" "--" "${HOOKS[@]}"'
            result = subprocess.run(
                ["/bin/bash", "-e", "-c", command, "overlay-test", str(config)],
                capture_output=True,
                text=True,
                check=True,
                env={"PATH": os.defpath},
            )
            modules, hooks = result.stdout.split("--\n")
            self.assertEqual(
                modules.splitlines(),
                [
                    "snd-seq",
                    "btrfs",
                    "nvme-apple",
                    "apple-sart",
                    "dm-crypt",
                    "dm-integrity",
                    "xts",
                ],
            )
            self.assertIn("sd-encrypt", hooks.splitlines())
            self.assertIn("aurora-root", hooks.splitlines())
            self.assertNotIn("autodetect", hooks.splitlines())

    def test_preset_selects_only_its_custom_config_and_matching_kernel(self):
        preset = OVERLAY / "mkinitcpio.d/linux-m4rch.preset"
        command = (
            'source "$1"; printf "%s\\n" "$ALL_config" "$ALL_kver" "$default_image"'
        )
        result = subprocess.run(
            ["/bin/bash", "-e", "-c", command, "overlay-test", str(preset)],
            capture_output=True,
            text=True,
            check=True,
            env={"PATH": os.defpath},
        )
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "/etc/mkinitcpio-m4rch.conf",
                "/boot/vmlinuz-linux-m4rch",
                "/boot/initramfs-linux-m4rch.img",
            ],
        )


if __name__ == "__main__":
    unittest.main()
