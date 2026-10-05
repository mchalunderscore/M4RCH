import tempfile
from pathlib import Path
import unittest
from sdboot.left_usb_activate import digest, replace


class LeftUsbActivationTests(unittest.TestCase):
    def test_atomic_replacement_and_link_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'staged.dtbo';target=root/'board.dtbo'
            source.write_bytes(b'candidate');target.write_bytes(b'previous')
            replace(source,target)
            self.assertEqual(digest(source),digest(target))
            link=root/'link';link.symlink_to(source)
            with self.assertRaisesRegex(ValueError,'Not a regular file'):digest(link)
            self.assertEqual(sorted(path.name for path in root.iterdir()),['board.dtbo','link','staged.dtbo'])
