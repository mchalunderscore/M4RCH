import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT / 'sdboot'), str(PROJECT / 'lib')]
import gravity_loader
from common import manifest_files, sha256, write_json
from split_loader import ESP_UUID
spec = importlib.util.spec_from_file_location('setup_gravity_split', PROJECT / 'scripts/setup-split-boot.py')
setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)


class GravityLoaderTests(unittest.TestCase):
    def test_pinned_patch_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root / 'profiles').mkdir(); (root / 'patches').mkdir()
            profile = gravity_loader.profile_inputs(PROJECT)
            for source in profile['sources'].values():
                (root / source['patch']).write_bytes((PROJECT / source['patch']).read_bytes())
            write_json(root / 'profiles/gravity-loader.json', profile)
            self.assertEqual(gravity_loader.profile_inputs(root), profile)
            path = root / profile['sources']['m1n1']['patch']
            path.write_bytes(path.read_bytes() + b'altered')
            with self.assertRaisesRegex(ValueError, 'checksum differs'):
                gravity_loader.profile_inputs(root)

    def test_stage2_must_match_enrolled_prefix_and_esp(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); original = root / 'split-loader'; original.mkdir()
            (original / 'loader.bin').write_bytes(b'enrolled prefix')
            candidate = root / 'gravity-loader'; candidate.mkdir()
            (candidate / 'boot.bin').write_bytes(b'candidate')
            manifest = {'schema': 1, 'kind': 'j614s-gravity-stage2', 'stage2_path': 'boot.bin',
                        'inputs': {'esp_partuuid': ESP_UUID, 'stage1_sha256': sha256(original / 'loader.bin')},
                        'files': manifest_files(candidate, ['boot.bin'])}
            path = candidate / 'loader-manifest.json'; write_json(path, manifest)
            source, receipt = setup.stage2_source(root, True)
            self.assertEqual(source, candidate / 'boot.bin')
            for key, value in [('stage1_sha256', 'wrong'), ('esp_partuuid', 'wrong')]:
                bad = json.loads(json.dumps(manifest)); bad['inputs'][key] = value; write_json(path, bad)
                with self.assertRaisesRegex(ValueError, 'contract'):
                    setup.stage2_source(root, True)
            write_json(path, manifest); (candidate / 'boot.bin').write_bytes(b'corrupt')
            with self.assertRaises(ValueError): setup.stage2_source(root, True)
