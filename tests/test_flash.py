import hashlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import card
from card_disk import DiskUtil
import gpt
from test_gpt import fixture


class FlashWriteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.image = Path(self.temporary.name) / "source.img"
        self.image.write_bytes(fixture())
        self.disk = self.image.with_name("target.img")
        self.disk.write_bytes(bytes(512 * 512))
        self.size = self.image.stat().st_size
        self.digest = hashlib.sha256(self.image.read_bytes()).hexdigest()

    def test_copy_sync_readback_and_gpt_use_one_held_descriptor(self):
        original = gpt.inspect(self.image)
        events = []
        sync, relocate = gpt.sync_disk, gpt.relocate_stream
        with self.disk.open("r+b", buffering=0) as stream:
            descriptor = stream.fileno()

            def synchronized(actual):
                self.assertIs(actual, stream)
                self.assertEqual(actual.fileno(), descriptor)
                events.append("sync")
                sync(actual)

            def relocated(actual, capacity):
                self.assertIs(actual, stream)
                events.append("relocate")
                return relocate(actual, capacity)

            with patch("gpt._open", side_effect=AssertionError("raw device reopened")), \
                    patch("gpt.sync_disk", side_effect=synchronized), \
                    patch("gpt.relocate_stream", side_effect=relocated):
                card.write_and_verify_image(self.image, stream, self.size, self.digest, 512 * 512)
            self.assertFalse(stream.closed)
        self.assertEqual(events, ["sync", "relocate", "sync", "sync"])
        self.assertEqual(gpt.inspect(self.disk)["partitions"], original["partitions"])
        self.assertEqual(self.disk.read_bytes()[1024:self.size], self.image.read_bytes()[1024:])

    def test_short_writes_preserve_every_byte(self):
        class ShortWrites(io.BytesIO):
            def write(self, data):
                return super().write(data[:512])

        stream = ShortWrites(bytes(512 * 512))
        with patch("gpt.sync_disk"), patch("gpt.relocate_stream") as relocate:
            card.write_and_verify_image(self.image, stream, self.size, self.digest, 512 * 512)
        self.assertEqual(stream.getvalue()[:self.size], self.image.read_bytes())
        relocate.assert_called_once_with(stream, 512 * 512)

    def test_hash_failure_never_relocates_gpt(self):
        with self.disk.open("r+b", buffering=0) as stream, \
                patch("gpt.relocate_stream") as relocate, \
                self.assertRaisesRegex(ValueError, "SHA-256"):
            card.write_and_verify_image(self.image, stream, self.size, "0" * 64, 512 * 512)
        relocate.assert_not_called()
        self.assertEqual(self.disk.read_bytes()[:self.size], self.image.read_bytes())

    def test_stalled_write_and_changed_source_size_never_relocate(self):
        for failure in ("stalled", "changed-size"):
            with self.subTest(failure=failure), patch("gpt.sync_disk") as sync, \
                    patch("gpt.relocate_stream") as relocate:
                stream = io.BytesIO(bytes(512 * 512))
                size = self.size
                if failure == "stalled":
                    stream.write = Mock(return_value=0)
                else:
                    size += 512
                with self.assertRaises((OSError, ValueError)):
                    card.write_and_verify_image(self.image, stream, size, self.digest, 512 * 512)
                sync.assert_not_called()
                relocate.assert_not_called()

    def test_exclusive_descriptor_is_held_until_body_finishes(self):
        descriptor = os.open(self.disk, os.O_RDWR)
        dutil = Mock(spec=DiskUtil)
        summary = {"device": "disk4"}
        # This Darwin-only flag is mocked alongside open; no device is opened.
        exlock = getattr(os, "O_EXLOCK", 0x20)
        with patch.object(card.os, "O_EXLOCK", exlock, create=True), \
                patch("card.os.open", return_value=descriptor) as opened:
            with self.assertRaisesRegex(RuntimeError, "operation failed"):
                with card.exclusive_disk(dutil, summary, {}) as stream:
                    self.assertEqual(stream.fileno(), descriptor)
                    self.assertFalse(stream.closed)
                    raise RuntimeError("operation failed")
        self.assertTrue(stream.closed)
        with self.assertRaises(OSError):
            os.fstat(descriptor)
        opened.assert_called_once_with("/dev/rdisk4", os.O_RDWR | os.O_NOFOLLOW | exlock | os.O_NONBLOCK)
        self.assertEqual(dutil.assert_unchanged.call_count, 2)
        dutil.run.assert_called_once_with("unmountDisk", "disk4")


if __name__ == "__main__":
    unittest.main()
