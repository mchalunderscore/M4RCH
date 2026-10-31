import gzip
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PackageWorkflowTest(unittest.TestCase):
    def test_promoted_patch_series_preserve_packaged_sources(self):
        for project in ('linux-m4rch', 'm1n1-m4rch', 'u-boot-m4rch'):
            directories = ROOT / 'packages' / project / 'promoted-source' / 'patches'
            for directory in directories.iterdir():
                names = (directory / 'series').read_text().splitlines()
                self.assertTrue(names, directory)
                self.assertTrue(all(Path(name).name == name for name in names))
                self.assertTrue(all((directory / name).stat().st_size for name in names))
                checksum = directory / 'original.sha256'
                if checksum.exists():
                    data = b''.join((directory / name).read_bytes() for name in names)
                    expected = checksum.read_text().split()[0]
                    self.assertEqual(hashlib.sha256(data).hexdigest(), expected, str(directory))
            provenance = directories.parent / 'provenance'
            if provenance.exists():
                for archive in provenance.glob('*.patch.gz'):
                    checksum = provenance / (archive.name.removesuffix('.patch.gz') + '.sha256')
                    expected = checksum.read_text().split()[0]
                    self.assertEqual(hashlib.sha256(gzip.decompress(archive.read_bytes())).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
