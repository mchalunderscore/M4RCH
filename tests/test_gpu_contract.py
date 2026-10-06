from pathlib import Path
import importlib.util,struct,unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('gpu_contract',ROOT/'experiments/t6040-gpu/contract.py');gpu=importlib.util.module_from_spec(spec);spec.loader.exec_module(gpu)
class Contract(unittest.TestCase):
 def test_two_tables_preserve_independent_voltage_values(self):
  raw=struct.pack('<IIIIIIII',0,125,100,600,0,125,100,590)
  rows=gpu.tables(raw,2,2);self.assertEqual(rows[0][1]['voltage_raw'],600);self.assertEqual(rows[1][1]['voltage_raw'],590)
 def test_grouping_preserves_cluster_voltage_and_indexes(self):
  core=[{'frequency_hz':0,'voltage_raw':125},{'frequency_hz':100000000,'voltage_raw':600},{'frequency_hz':120000000,'voltage_raw':600}]
  sram=[{'frequency_hz':r['frequency_hz'],'voltage_raw':810} for r in core]
  a=gpu.ladder(core,sram);self.assertEqual(a[1]['index_high'],2);self.assertEqual(a[1]['index_low'],1);self.assertEqual(a[1]['core_voltage_raw'],600)
 def test_grouping_rejects_sram_voltage_change_within_core_group(self):
  core=[{'frequency_hz':100000000,'voltage_raw':600},{'frequency_hz':120000000,'voltage_raw':600}]
  sram=[{'frequency_hz':100000000,'voltage_raw':810},{'frequency_hz':120000000,'voltage_raw':820}]
  with self.assertRaises(ValueError):gpu.ladder(core,sram)
 def test_reject_truncated_and_extra_rows(self):
  for raw in (b'',b'\0'*7,b'\0'*24):
   with self.assertRaises(ValueError):gpu.tables(raw,1,2)
 def test_little_endian_adt_counts(self):self.assertEqual(gpu.uint({'count':b'\x10\0\0\0'},'count'),16)
 def test_reject_unknown_scalar_width(self):
  with self.assertRaises(ValueError):gpu.uint({'count':b'\x10'},'count')
 def test_identify_patch_blocks_t6040_firmware_before_dispatch(self):
  patch=(ROOT/'patches/gravity-t6040-identify-only.patch').read_text();self.assertIn('chip_id == 0x6040 && *module_parameters::probe_only.value() == 0',patch);self.assertIn('return Err(ENOTSUPP)',patch);self.assertIn('default: 1',patch);self.assertIn('const SGX_SIZE: usize = 0xd04020',patch);self.assertNotIn('+            gpu_variant:',patch)
if __name__=='__main__':unittest.main()
