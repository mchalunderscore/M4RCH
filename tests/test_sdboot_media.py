"""Regular-file tests only: none of these tests opens a physical disk."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdboot import media


CONFIG = {"root_uuid": "a0418040-b5b3-4ae8-9288-1c7c6dbda604",
          "boot_mib": 64, "root_gib": 1}


def esp_fixture(out, config=CONFIG):
    base = out / "esp"
    efi = bytearray(512)
    efi[:2] = b"MZ"
    struct.pack_into("<I", efi, 0x3c, 0x80)
    efi[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", efi, 0x84, 0xaa64)
    kernel = bytearray(4096)
    kernel[56:60] = b"ARM\x64"
    data = {"EFI/BOOT/BOOTAA64.EFI": efi, "vmlinuz-linux-m4rch": kernel,
            "initramfs-linux-m4rch.img": b"compressed archive",
            "grub/grub.cfg": b"menuentry Arch {}\n", "dtbs/board.dtbo": b"overlay"}
    files = {}
    for name, content in data.items():
        target = base / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        files["esp/" + name] = media._file_info(target)
    (out / "payload-manifest.json").write_text(json.dumps({
        "layout": media.LAYOUT, "config": config, "files": files}))
    return {name.removeprefix("esp/"): info for name, info in files.items()}


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)

    def image(self, boot=2 * media.MIB, root=4 * media.MIB):
        path = self.work / "disk.img"
        layout = media.geometry(boot, root)
        with path.open("w+b") as stream:
            stream.truncate(layout["bytes"])
            media.write_gpt(stream, layout, media.identities(CONFIG))
        return path, layout

    def test_gpt_contains_exact_native_layout_and_stable_distinct_ids(self):
        path, layout = self.image()
        table = media.gpt.inspect(path)
        self.assertEqual(table["bytes"], layout["bytes"])
        self.assertEqual([p["type_guid"] for p in table["partitions"]],
                         [media.ESP, media.LINUX])
        self.assertEqual([p["name"] for p in table["partitions"]],
                         ["ARCHBOOT", "ARCHROOT"])
        self.assertEqual(table["partitions"][0]["first_lba"], 2048)
        self.assertEqual(table["partitions"][1]["first_lba"], 6144)
        ids = media.identities(CONFIG)
        self.assertEqual(ids, media.identities(CONFIG))
        self.assertEqual(len(set(ids[key] for key in (
            "disk_guid", "boot_partition_uuid", "root_partition_uuid"))), 3)
        self.assertEqual(table["disk_guid"], ids["disk_guid"])

    def test_larger_card_relocation_keeps_root_geometry_ready_for_growth(self):
        path, layout = self.image()
        original = media.gpt.inspect(path)
        with path.open("r+b") as stream:
            stream.truncate(32 * media.MIB)
        grown = media.gpt.relocate(path, 32 * media.MIB)
        self.assertEqual(grown["partitions"], original["partitions"])
        self.assertEqual(grown["backup_header_lba"], 32 * media.MIB // 512 - 1)
        self.assertGreater(grown["last_usable_lba"], layout["root_last_lba"])
        self.assertLess(grown["partitions"][0]["last_lba"],
                        grown["partitions"][1]["first_lba"])

    def test_geometry_refuses_nonpositive_or_unaligned_sizes(self):
        for size in (0, -1, True, media.MIB + 512):
            with self.subTest(size=size), self.assertRaises(ValueError):
                media.geometry(size, media.MIB)

    def test_write_gpt_refuses_wrong_image_extent(self):
        path, layout = self.image()
        with path.open("r+b") as stream:
            stream.truncate(layout["bytes"] + 512)
            with self.assertRaisesRegex(ValueError, "extent"):
                media.write_gpt(stream, layout, media.identities(CONFIG))

    def test_esp_requires_complete_manifest_and_standard_arm64_boot_files(self):
        expected = esp_fixture(self.work)
        self.assertEqual(media._esp(self.work, CONFIG), expected)
        (self.work / "esp/vmlinuz-linux-m4rch").write_bytes(b"incomplete")
        with self.assertRaisesRegex(ValueError, "manifest"):
            media._esp(self.work, CONFIG)

    def test_esp_refuses_escape_symlinks_and_extra_untracked_files(self):
        esp_fixture(self.work)
        (self.work / "esp/foreign").symlink_to(self.work / "payload-manifest.json")
        with self.assertRaisesRegex(ValueError, "non-regular"):
            media._esp(self.work, CONFIG)
        (self.work / "esp/foreign").unlink()
        (self.work / "esp/untracked").write_text("unexpected")
        with self.assertRaisesRegex(ValueError, "manifest"):
            media._esp(self.work, CONFIG)

    def test_esp_refuses_wrong_architecture_even_when_hash_matches(self):
        esp_fixture(self.work)
        target = self.work / "esp/EFI/BOOT/BOOTAA64.EFI"
        content = bytearray(target.read_bytes())
        struct.pack_into("<H", content, 0x84, 0x8664)
        target.write_bytes(content)
        manifest = json.loads((self.work / "payload-manifest.json").read_text())
        manifest["files"]["esp/EFI/BOOT/BOOTAA64.EFI"] = media._file_info(target)
        (self.work / "payload-manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "AArch64"):
            media._esp(self.work, CONFIG)

    def test_esp_rejects_truncated_pe_header_without_struct_exception(self):
        esp_fixture(self.work)
        target = self.work / "esp/EFI/BOOT/BOOTAA64.EFI"
        content = bytearray(target.read_bytes())
        struct.pack_into("<I", content, 0x3c, len(content) - 1)
        target.write_bytes(content)
        manifest = json.loads((self.work / "payload-manifest.json").read_text())
        manifest["files"]["esp/EFI/BOOT/BOOTAA64.EFI"] = media._file_info(target)
        (self.work / "payload-manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "PE executable"):
            media._esp(self.work, CONFIG)

    def test_esp_refuses_case_insensitive_collisions_on_fat(self):
        esp_fixture(self.work)
        # This host may itself be case insensitive; a mocked directory entry
        # still exercises the FAT collision independently of host semantics.
        base = self.work / "esp"
        lower = base / "vmlinuz-linux-m4rch"
        upper = base / "VMLINUZ-LINUX-M4RCH"
        upper.write_bytes(lower.read_bytes())
        with patch.object(Path, "rglob", return_value=[lower, upper]):
            with self.assertRaisesRegex(ValueError, "duplicate"):
                media._esp(self.work, CONFIG)

    def test_new_layout_does_not_reuse_fit_card_ids(self):
        ids = media.identities(CONFIG)
        for name, purpose in (("disk_guid", "disk"), ("boot_partition_uuid", "boot"),
                              ("root_partition_uuid", "root")):
            old = uuid.uuid5(uuid.UUID(CONFIG["root_uuid"]), "arch-m4-sdboot-v1:" + purpose)
            self.assertNotEqual(ids[name], str(old).upper())
        serial = uuid.UUID(ids["boot_partition_uuid"]).hex[:8].upper()
        self.assertEqual(media.boot_fat_uuid(CONFIG), serial[:4] + "-" + serial[4:])

    def test_sparse_copy_preserves_nonzero_data_and_hash(self):
        source = self.work / "source"
        data = b"A" * media.MIB + b"\0" * (8 * media.MIB) + b"B" * media.MIB
        source.write_bytes(data)
        dest = self.work / "copy"
        with dest.open("w+b") as stream:
            stream.truncate(len(data) + 512)
            result = media._copy_partition(source, stream, 512)
        self.assertEqual(dest.read_bytes(), b"\0" * 512 + data)
        self.assertEqual(result, {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    def test_ext4_checks_uuid_label_and_extents(self):
        path = self.work / "ext4"
        data = bytearray(2048)
        data[1080:1082] = b"\x53\xef"
        struct.pack_into("<I", data, 1120, 0x40)
        data[1128:1144] = uuid.UUID(CONFIG["root_uuid"]).bytes
        data[1144:1152] = b"ARCHROOT"
        path.write_bytes(data)
        with path.open("rb") as stream:
            self.assertEqual(media._ext4(stream),
                             {"uuid": CONFIG["root_uuid"], "label": "ARCHROOT"})
        data[1120] = 0
        path.write_bytes(data)
        with path.open("rb") as stream, self.assertRaisesRegex(ValueError, "extents"):
            media._ext4(stream)

    def test_manifest_refuses_mismatched_config_before_image_access(self):
        (self.work / "card-manifest.json").write_text(json.dumps({"layout": media.LAYOUT, "config": {}}))
        with self.assertRaisesRegex(ValueError, "stale"):
            media._manifest(self.work, CONFIG)

    def test_flash_refuses_internal_disk_before_confirmation_or_raw_access(self):
        with patch.object(media, "_require_macos"), \
                patch.object(media, "_manifest", return_value={"files": {"m4rch.img": {
                    "bytes": 1024, "sha256": "0" * 64}}}), \
                patch.object(media, "DiskUtil") as disks, \
                patch("card.confirm") as confirm, \
                patch("card.exclusive_disk") as opened:
            disks.return_value.inspect_target.side_effect = ValueError("current System or Data")
            with self.assertRaisesRegex(ValueError, "System or Data"):
                media.flash(self.work, CONFIG, "/dev/disk0")
        confirm.assert_not_called()
        opened.assert_not_called()

    def test_flash_refuses_short_or_non512_card_before_confirmation(self):
        manifest = {"files": {"m4rch.img": {"bytes": 4096, "sha256": "0" * 64}}}
        for size, block_size in ((2048, 512), (8192, 4096)):
            with self.subTest(size=size, block_size=block_size), \
                    patch.object(media, "_require_macos"), \
                    patch.object(media, "_manifest", return_value=manifest), \
                    patch.object(media, "DiskUtil") as disks, \
                    patch("card.confirm") as confirm, \
                    patch("card.exclusive_disk") as opened:
                disks.return_value.inspect_target.return_value = {
                    "bytes": size, "fingerprint": {"DeviceBlockSize": block_size}}
                with self.assertRaises(ValueError):
                    media.flash(self.work, CONFIG, "/dev/disk9")
            confirm.assert_not_called()
            opened.assert_not_called()

    @unittest.skipUnless(sys.platform == "linux" and all(shutil.which(tool) for tool in
                         ("mkfs.ext4", "mkfs.vfat", "mcopy", "mmd")), "Linux filesystem tools required")
    def test_compose_real_filesystems_and_verify_embedded_esp_and_root(self):
        files = esp_fixture(self.work)
        root = self.work / "rootfs.ext4"
        with root.open("wb") as stream:
            stream.truncate(media.GIB)
        subprocess.run(["mkfs.ext4", "-q", "-F", "-U", CONFIG["root_uuid"],
                        "-L", "ARCHROOT", root], check=True)
        manifest = media.compose(self.work, CONFIG)
        self.assertEqual(media._manifest(self.work, CONFIG), manifest)
        image = self.work / "m4rch.img"
        table = media.gpt.inspect(image)
        copied = self.work / "readback"
        offset = table["partitions"][0]["first_lba"] * 512
        with image.open("rb") as stream:
            stream.seek(offset + 67)  # FAT32 BPB volume serial number.
            serial = struct.unpack("<I", stream.read(4))[0]
        expected_serial = int(media.boot_fat_uuid(CONFIG).replace("-", ""), 16)
        self.assertEqual(serial, expected_serial)
        for relative, expected in files.items():
            subprocess.run(["mcopy", "-i", f"{image}@@{offset}", "::/" + relative, copied], check=True)
            self.assertEqual(media._file_info(copied), expected)
            copied.unlink()
        with image.open("rb") as stream:
            self.assertEqual(media._ext4(stream, table["partitions"][1]["first_lba"] * 512),
                             {"uuid": CONFIG["root_uuid"], "label": "ARCHROOT"})
        self.assertEqual(manifest["card"]["root_partition_uuid"], table["partitions"][1]["guid"])
        self.assertFalse(list(self.work.glob(".media-*")))


if __name__ == "__main__":
    unittest.main()
