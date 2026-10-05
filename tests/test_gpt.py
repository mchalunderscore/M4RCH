from pathlib import Path
import stat
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import Mock, patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import gpt


def crc(data):
    return zlib.crc32(data) & 0xffffffff


def header(current, alternate, table, sectors, table_crc, count=128):
    raw = bytearray(512)
    gpt.HEADER.pack_into(raw, 0, b"EFI PART", 0x10000, 92, 0, 0,
                        current, alternate, 34, sectors - 34,
                        uuid.UUID("74885f30-725b-4ad9-9e06-7a3b8b632fed").bytes_le,
                        table, count, 128, table_crc)
    struct.pack_into("<I", raw, 16, crc(raw[:92]))
    return bytes(raw)


def fixture(sectors=256, entries=None, count=128):
    table = bytearray(count * 128)
    if entries is None:
        entries = [(40, 100)]
    for index, (start, end) in enumerate(entries):
        offset = 128 * index
        table[offset:offset + 16] = uuid.UUID("7c3457ef-0000-11aa-aa11-00306543ecac").bytes_le
        table[offset + 16:offset + 32] = uuid.UUID(int=index + 1).bytes_le
        struct.pack_into("<QQQ", table, offset + 32, start, end, 0)
        table[offset + 56:offset + 64] = "Test".encode("utf-16-le")
    data = bytearray(sectors * 512)
    data[450] = 0xee
    struct.pack_into("<II", data, 454, 1, sectors - 1)
    data[510:512] = b"\x55\xaa"
    table_sectors = (len(table) + 511) // 512
    backup_offset = (sectors - 1 - table_sectors) * 512
    data[512:1024] = header(1, sectors - 1, 2, sectors, crc(table), count)
    data[1024:1024 + len(table)] = table
    data[backup_offset:backup_offset + len(table)] = table
    data[-512:] = header(sectors - 1, 1, sectors - 1 - table_sectors,
                        sectors, crc(table), count)
    data[40 * 512:41 * 512] = b"partition data".ljust(512, b"!")
    return bytes(data)


class GPTTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "disk.img"
        self.path.write_bytes(fixture())

    def tearDown(self):
        self.temporary.cleanup()

    def test_inspects_both_gpt_copies_and_partition_bounds(self):
        result = gpt.inspect(self.path)
        self.assertEqual(result["bytes"], 256 * 512)
        self.assertEqual(result["backup_header_lba"], 255)
        self.assertEqual(result["partitions"][0]["first_lba"], 40)
        self.assertEqual(result["partitions"][0]["last_lba"], 100)
        self.assertEqual(result["partitions"][0]["name"], "Test")

    def test_rejects_corrupt_primary_backup_and_partition_table(self):
        for offset in (512 + 24, 255 * 512 + 24, 1024 + 56, 223 * 512 + 56):
            with self.subTest(offset=offset):
                data = bytearray(fixture())
                data[offset] ^= 1
                self.path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "CRC|backup"):
                    gpt.inspect(self.path)

    def test_rejects_hybrid_mbr_and_invalid_protective_length(self):
        for offset in (466, 458):
            with self.subTest(offset=offset):
                data = bytearray(fixture())
                data[offset] ^= 1
                self.path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "MBR"):
                    gpt.inspect(self.path)

    def test_rejects_partition_outside_usable_range_and_overlap(self):
        for entries in ([(30, 100)], [(40, 224)], [(40, 100), (100, 150)]):
            with self.subTest(entries=entries):
                self.path.write_bytes(fixture(entries=entries))
                with self.assertRaisesRegex(ValueError, "outside|overlap"):
                    gpt.inspect(self.path)

    def test_rejects_duplicate_partition_identifiers_with_valid_crcs(self):
        data = bytearray(fixture(entries=[(40, 100), (101, 150)]))
        table = bytearray(data[1024:1024 + 16384])
        table[144:160] = table[16:32]
        data[1024:1024 + len(table)] = table
        data[-512 - len(table):-512] = table
        data[512:1024] = header(1, 255, 2, 256, crc(table))
        data[-512:] = header(255, 1, 223, 256, crc(table))
        self.path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "duplicated"):
            gpt.inspect(self.path)

    def test_rejects_truncation_unsupported_sectors_and_backing_size_mismatch(self):
        with self.assertRaises(ValueError):
            gpt.inspect(self.path, sector_size=4096)
        with self.assertRaises(ValueError):
            gpt.inspect(self.path, total_bytes=512 * 512)
        for size in (255 * 512, 256 * 512 - 1):
            with self.subTest(size=size):
                self.path.write_bytes(fixture()[:size])
                with self.assertRaises(ValueError):
                    gpt.inspect(self.path)

    def test_relocation_moves_backup_and_preserves_all_partition_bytes(self):
        original = self.path.read_bytes()
        before = gpt.inspect(self.path)
        self.path.write_bytes(original + bytes(256 * 512))
        with self.assertRaises(ValueError):
            gpt.inspect(self.path)
        after = gpt.relocate(self.path, 512 * 512)
        self.assertEqual(after, gpt.inspect(self.path))
        self.assertEqual(after["backup_header_lba"], 511)
        self.assertEqual(after["last_usable_lba"], 478)
        self.assertEqual(before["partitions"], after["partitions"])
        self.assertEqual(before["entries_crc32"], after["entries_crc32"])
        changed = self.path.read_bytes()
        self.assertEqual(changed[1024:len(original)], original[1024:])
        self.assertEqual(changed[446:458], original[446:458])
        self.assertEqual(struct.unpack_from("<I", changed, 458)[0], 511)

    def test_relocation_writes_only_new_backup_pmbr_and_primary(self):
        self.path.write_bytes(fixture() + bytes(256 * 512))
        writes = []
        real_write = gpt._write

        def recorded(stream, offset, data):
            writes.append((offset, len(data)))
            real_write(stream, offset, data)

        with patch("gpt._write", side_effect=recorded):
            gpt.relocate(self.path, 512 * 512)
        self.assertEqual(writes, [(479 * 512, 16384), (511 * 512, 512), (0, 512), (512, 512)])

    def test_stream_relocation_keeps_descriptor_and_partition_contents(self):
        original = self.path.read_bytes()
        before = gpt.inspect(self.path)
        self.path.write_bytes(original + bytes(256 * 512))
        with self.path.open("r+b", buffering=0) as stream, \
                patch("gpt._open", side_effect=AssertionError("must not reopen")):
            descriptor = stream.fileno()
            after = gpt.relocate_stream(stream, 512 * 512)
            self.assertFalse(stream.closed)
            self.assertEqual(stream.fileno(), descriptor)
            self.assertEqual(after, gpt.inspect_stream(stream, total_bytes=512 * 512))
            self.assertFalse(stream.closed)
            stream.seek(1024)
            self.assertEqual(stream.read(len(original) - 1024), original[1024:])
        self.assertEqual(after["partitions"], before["partitions"])
        self.assertEqual(after["entries_crc32"], before["entries_crc32"])

    def test_stream_validation_errors_do_not_close_descriptor_or_write(self):
        original = self.path.read_bytes()
        with self.path.open("r+b", buffering=0) as stream, patch("gpt._write") as write:
            for operation in (gpt.inspect_stream, gpt.relocate_stream):
                with self.subTest(operation=operation.__name__), self.assertRaises(ValueError):
                    operation(stream, total_bytes=256 * 512, sector_size=4096)
                self.assertFalse(stream.closed)
            with self.assertRaises(ValueError):
                gpt.relocate_stream(stream, total_bytes=512 * 512)
            self.assertFalse(stream.closed)
        write.assert_not_called()
        self.assertEqual(self.path.read_bytes(), original)

    def test_short_entry_array_reads_remain_sector_aligned(self):
        self.path.write_bytes(fixture(count=1) + bytes(256 * 512))
        real_read = gpt._read

        def aligned_read(stream, offset, size, limit):
            self.assertEqual(offset % 512, 0)
            self.assertEqual(size % 512, 0)
            return real_read(stream, offset, size, limit)

        with patch("gpt._read", side_effect=aligned_read):
            result = gpt.relocate(self.path, 512 * 512)
            self.assertEqual(result, gpt.inspect(self.path))
        self.assertEqual(result["entry_count"], 1)

    def test_failed_backup_sync_prevents_primary_metadata_writes(self):
        original = fixture() + bytes(256 * 512)
        self.path.write_bytes(original)
        real_write = gpt._write
        writes = []

        def recorded(stream, offset, data):
            writes.append((offset, len(data)))
            real_write(stream, offset, data)

        with patch("gpt._write", side_effect=recorded), \
                patch("gpt.sync_disk", side_effect=OSError("cache sync failed")), \
                self.assertRaisesRegex(OSError, "cache sync failed"):
            gpt.relocate(self.path, 512 * 512)
        self.assertEqual(writes, [(479 * 512, 16384), (511 * 512, 512)])
        self.assertEqual(self.path.read_bytes()[:1024], original[:1024])

    def test_relocation_rejects_shrinking_or_corrupt_source_before_writing(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt):
                if corrupt:
                    data = bytearray(fixture() + bytes(256 * 512))
                    data[255 * 512 + 16] ^= 1
                    self.path.write_bytes(data)
                    total = 512 * 512
                else:
                    self.path.write_bytes(fixture()[:255 * 512])
                    total = 255 * 512
                before = self.path.read_bytes()
                with patch("gpt._write") as write, self.assertRaises(ValueError):
                    gpt.relocate(self.path, total)
                write.assert_not_called()
                self.assertEqual(self.path.read_bytes(), before)

    def test_already_matching_target_is_validated_without_writes(self):
        with patch("gpt._write") as write:
            result = gpt.relocate(self.path, 256 * 512)
        write.assert_not_called()
        self.assertEqual(result, gpt.inspect(self.path))


class DiskSyncTests(unittest.TestCase):
    def sync_calls(self, platform, mode, failure=None):
        stream = Mock()
        stream.fileno.return_value = 42
        events = []
        stream.flush.side_effect = lambda: events.append("flush")

        def ioctl(descriptor, request):
            self.assertEqual(descriptor, 42)
            self.assertEqual(request, 0x20006416)
            events.append("ioctl")
            if failure:
                raise failure

        with patch("gpt.sys.platform", platform), \
                patch("gpt.os.fstat", return_value=SimpleNamespace(st_mode=mode)), \
                patch("gpt.os.fsync", side_effect=lambda fd: events.append(("fsync", fd))), \
                patch("gpt.fcntl.ioctl", side_effect=ioctl):
            gpt.sync_disk(stream)
        return events

    def test_darwin_raw_device_uses_media_cache_ioctl(self):
        self.assertEqual(self.sync_calls("darwin", stat.S_IFCHR), ["flush", "ioctl"])

    def test_darwin_block_device_flushes_buffers_then_media_cache(self):
        self.assertEqual(self.sync_calls("darwin", stat.S_IFBLK),
                         ["flush", ("fsync", 42), "ioctl"])

    def test_regular_images_and_other_platforms_use_fsync(self):
        for platform, mode in (("darwin", stat.S_IFREG), ("linux", stat.S_IFREG),
                               ("linux", stat.S_IFBLK)):
            with self.subTest(platform=platform, mode=mode):
                self.assertEqual(self.sync_calls(platform, mode), ["flush", ("fsync", 42)])

    def test_media_cache_failure_propagates(self):
        with self.assertRaisesRegex(OSError, "unsupported cache sync"):
            self.sync_calls("darwin", stat.S_IFCHR, OSError("unsupported cache sync"))


if __name__ == "__main__":
    unittest.main()
