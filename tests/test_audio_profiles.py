"""Verify the packaged UCM graph for this machine's microphone and jack."""
from pathlib import Path
import importlib.util
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'packages/alsa-ucm-conf-m4rch/files/ucm2'


class AudioProfilesTest(unittest.TestCase):
    def test_j614_microphone_and_j616_jack_profiles_are_complete(self):
        profiles = {
            'conf.d/aop_audio/MacBook Pro J614 High-Power Audio Interface.conf':
                'conf.d/aop_audio/3chan/HiFi.conf',
            'conf.d/macaudio/MacBook Pro J616 Jack.conf':
                'conf.d/macaudio/cs42l84/HiFi-jack.conf',
        }
        for name, expected in profiles.items():
            content = (ROOT / name).read_text()
            self.assertEqual(re.findall(r'File\s+"/([^"]+)"', content), [expected])
            self.assertTrue((ROOT / expected).is_file(), expected)
        self.assertIn('CaptureChannels "3"', (ROOT / profiles[next(iter(profiles))]).read_text())
        jack = (ROOT / profiles['conf.d/macaudio/MacBook Pro J616 Jack.conf']).read_text()
        self.assertIn('Headphones', jack)
        self.assertIn('Headset', jack)

    def test_package_preparation_preserves_stock_and_replaces_apple_profiles(self):
        path = ROOT.parents[2] / 'tools/prepare.py'
        spec = importlib.util.spec_from_file_location('package_prepare', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'target'
            names = ['ucm2/conf.d/USB-Audio/stock.conf',
                     'ucm2/conf.d/aop_audio/old-board.conf',
                     'ucm2/conf.d/macaudio/old-board.conf',
                     'ucm2/conf.d/t8140-aop-audio/old-board.conf']
            for name in names:
                path = root / 'usr/share/alsa' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name)
            owner = root / 'var/lib/pacman/local/alsa-ucm-conf-m4rch-1/files'
            owner.parent.mkdir(parents=True)
            owner.write_text('%FILES%\n' + ''.join('usr/share/alsa/' + n + '\n' for n in names) + '\n')
            dest = Path(tmp) / 'out'
            module.collect_alsa(root, dest)
            self.assertTrue((dest / names[0]).is_file())
            for name in names[1:]:
                self.assertFalse((dest / name).exists())
            self.assertTrue((dest / 'ucm2/conf.d/macaudio/MacBook Pro J616 Jack.conf').is_file())
            self.assertTrue((dest / 'ucm2/conf.d/aop_audio/MacBook Pro J614 High-Power Audio Interface.conf').is_file())


if __name__ == '__main__':
    unittest.main()
