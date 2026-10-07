"""Destructive migration planning must stay inside the owner's reserved span."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('nvme_migration', ROOT / 'tools/nvme/migrate.py')
nvme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nvme)

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.before = dict(label='gpt', unit='sectors', sectorsize=4096, device='/dev/nvme0n1', id='disk-guid', partitions=[
            dict(node='/dev/nvme0n1p2', start=128006, size=88378906, type='apfs-type', uuid='protected', name='macOS', attrs='GUID:60'),
            dict(node='/dev/nvme0n1p7', start=88507136, size=31238914, type=nvme.BASIC_TYPE, uuid='reserved', name='M4RCH_ROOT')])
        self.plan = dict(reservation_uuid='reserved', reservation_offset=88507136*4096,
                         reservation_bytes=31238914*4096, esp_bytes=1024**3,
                         esp_uuid='esp', root_partition_uuid='root',
                         before=[dict(uuid=p['uuid'], offset=p['start']*4096, bytes=p['size']*4096) for p in self.before['partitions']])
        self.after = copy.deepcopy(self.before)
        self.after['partitions'][1] = dict(node='/dev/nvme0n1p7', start=88507136, size=262144, type=nvme.ESP_TYPE, uuid='esp')
        self.after['partitions'].append(dict(node='/dev/nvme0n1p1', start=88769280, size=30976770, type=nvme.ROOT_TYPE, uuid='root'))

    def test_split_exactly_covers_reservation(self):
        self.assertEqual(nvme.verify_split(self.plan, self.before, self.after), ['/dev/nvme0n1p7', '/dev/nvme0n1p1'])
        esp, root = self.after['partitions'][1:]
        old = self.before['partitions'][1]
        self.assertEqual(esp['start'] + esp['size'], root['start'])
        self.assertEqual(root['start'] + root['size'], old['start'] + old['size'])

    def test_reject_protected_geometry_name_and_attributes_changes(self):
        for key, value in [('start', 1), ('size', 1), ('type', nvme.ROOT_TYPE), ('attrs', ''), ('name', 'changed')]:
            with self.subTest(key=key):
                after = copy.deepcopy(self.after)
                after['partitions'][0][key] = value
                with self.assertRaises(ValueError): nvme.verify_split(self.plan, self.before, after)

    def test_reject_partition_outside_span_or_wrong_uuid_type_slot(self):
        for key, value in [('start', 88769281), ('size', 30976771), ('uuid', 'other'), ('type', nvme.BASIC_TYPE), ('node', '/dev/nvme0n1p8')]:
            with self.subTest(key=key):
                after = copy.deepcopy(self.after)
                after['partitions'][2][key] = value
                with self.assertRaises(ValueError): nvme.verify_split(self.plan, self.before, after)

    def test_reject_added_partition_or_changed_disk_identity(self):
        after = copy.deepcopy(self.after)
        after['id'] = 'other'
        with self.assertRaises(ValueError): nvme.verify_split(self.plan, self.before, after)
        after = copy.deepcopy(self.after)
        after['partitions'].append(dict(node='/dev/nvme0n1p9', start=1, size=1, uuid='extra', type=nvme.ROOT_TYPE))
        with self.assertRaises(ValueError): nvme.verify_split(self.plan, self.before, after)

    def test_reject_reservation_inventory_or_type_drift(self):
        for modify in ('bounds', 'inventory', 'type'):
            with self.subTest(modify=modify):
                before = copy.deepcopy(self.before)
                if modify == 'bounds': before['partitions'][1]['size'] += 1
                if modify == 'inventory': before['partitions'].pop(0)
                if modify == 'type': before['partitions'][1]['type'] = nvme.ROOT_TYPE
                with self.assertRaises(ValueError): nvme.proposed(self.plan, before)

if __name__ == '__main__': unittest.main()
