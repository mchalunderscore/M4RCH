import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PackageWorkflowTest(unittest.TestCase):
    def test_preparation_build_validation_and_installer_cover_same_packages(self):
        tree = ast.parse((ROOT / 'packages/tools/prepare.py').read_text())
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'NAMES' for t in n.targets))
        expected = set(ast.literal_eval(assignment.value))
        build = (ROOT / 'packages/tools/build.sh').read_text()
        validate = (ROOT / 'packages/tools/validate.sh').read_text()
        install = (ROOT / 'packages/install.sh').read_text()
        for script in (build, validate):
            lists = [set(match.split()) for match in
                     re.findall(r'for name in ([^;\n]+); do', script)]
            self.assertIn(expected, lists)
        match = re.search(r'names=\((.*?)\)', install, re.S)
        self.assertIsNotNone(match)
        self.assertEqual(expected, set(match.group(1).split()))
        self.assertIn('power-profiles-daemon-m4rch', expected)
        self.assertTrue(expected.isdisjoint({'muvm-m4rch', 'fex-emu-m4rch',
                                             'fex-rootfs-debian-m4rch'}))

    def test_validation_targets_the_packaged_kernel_release(self):
        recipe = (ROOT / 'packages/linux-m4rch/PKGBUILD').read_text()
        validation = (ROOT / 'packages/tools/validate.sh').read_text()
        release = re.search(r'usr/lib/modules/([^/]+)/vmlinuz', recipe).group(1)
        self.assertIn('/usr/lib/modules/' + release + '/vmlinuz', validation)
        self.assertIn('modprobe.blacklist=snd_soc_tas2764,snd_soc_tas2770', validation)


if __name__ == '__main__':
    unittest.main()
