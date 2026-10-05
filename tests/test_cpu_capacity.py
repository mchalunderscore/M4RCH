import struct
from pathlib import Path
import tempfile
import unittest
from sdboot.cpu_capacity import check_nodes, verify, E_PATHS, P_PATHS, DT_VALUES, MAX_KHZ, NORMALIZED


class CapacityTests(unittest.TestCase):
    def test_complete_overlay_and_missing_or_wrong_cpu(self):
        nodes = {p: {'compatible': b'apple,sawtooth\0', 'capacity-dmips-mhz': struct.pack('>I', 864)} for p in E_PATHS}
        nodes.update({p: {'compatible': b'apple,everest\0', 'capacity-dmips-mhz': struct.pack('>I', 1024)} for p in P_PATHS})
        self.assertEqual(check_nodes(nodes)['expected_normalized'], {'E': 496, 'P': 1024})
        nodes[P_PATHS[0]]['compatible'] = b'apple,sawtooth\0'
        with self.assertRaisesRegex(ValueError, 'CPU class'): check_nodes(nodes)
        del nodes[P_PATHS[0]]
        with self.assertRaises(ValueError): check_nodes(nodes)

    def test_runtime_acceptance_rejects_missing_equal_and_malformed_capacities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for n in range(12):
                cls = 'E' if n < 4 else 'P'
                cpu = root / 'devices/system/cpu' / ('cpu' + str(n))
                files = {'regs/identification/midr_el1': hex((0x54 if cls == 'E' else 0x55) << 4),
                         'of_node/capacity-dmips-mhz': struct.pack('>I', DT_VALUES[cls]),
                         'cpu_capacity': str(NORMALIZED[cls]), 'cpufreq/cpuinfo_max_freq': str(MAX_KHZ[cls])}
                for name, data in files.items():
                    p = cpu / name; p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(data if isinstance(data, bytes) else data.encode())
            self.assertTrue(verify(root)['pass'])
            p = root / 'devices/system/cpu/cpu0/cpu_capacity'
            p.write_text('1024'); self.assertFalse(verify(root)['pass'])
            p.unlink(); self.assertFalse(verify(root)['pass'])
            p.write_text('496')
            (p.parent / 'of_node/capacity-dmips-mhz').write_bytes(b'\x01')
            self.assertFalse(verify(root)['pass'])
