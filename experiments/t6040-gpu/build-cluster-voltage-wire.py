#!/usr/bin/env python3
"""Cross-check fresh ADT group decoding in Python/Rust; emit offline wire inputs.
No frequency-profile assignment, power estimates, hardware access or startup.
"""
import argparse,hashlib,json,struct,subprocess,tempfile
from pathlib import Path
import adt,contract
p=argparse.ArgumentParser(description=__doc__);p.add_argument('adt',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
kit=Path(__file__).resolve().parent;raw=a.adt.read_bytes();n=adt.parse(raw)['/device-tree/arm-io/sgx'];count=int.from_bytes(n['perf-state-count'],'little');clusters=int.from_bytes(n['perf-state-table-count'],'little')
if clusters!=2:raise ValueError('Expected two observed cluster tables')
cores=contract.tables(n['perf-states'],count,clusters);srams=contract.tables(n['perf-states-sram'],count,clusters)
expected=[contract.ladder(c,s) for c,s in zip(cores,srams)]
if any(len(x)!=11 for x in expected):raise ValueError('Eleven wire rows not established by observed groups')
arrays=''
for cluster in range(2):
 for label,t in [('CORE',cores[cluster]),('SRAM',srams[cluster])]:
  pairs=','.join(f"({r['frequency_hz']},{r['voltage_raw']})" for r in t)
  arrays+=f'const {label}{cluster}: &[(u32,u32)] = &[{pairs}];\n'
source='#![allow(dead_code)]\n'+f'#[path={json.dumps(str(kit/"profile.rs"))}] mod profile;\n#[path={json.dumps(str(kit/"g16s_abi.rs"))}] mod abi;\n'+arrays+'''
fn main() {
 let mut core=[[0u32;11];2]; let mut sram=[[0u32;11];2];
 for (cluster,(c,s)) in [(CORE0,SRAM0),(CORE1,SRAM1)].iter().enumerate() {
  let mut rows=[profile::Step::default();16];
  assert_eq!(profile::ladder(c,s,&mut rows),Some(11));
  for (row,r) in rows[..11].iter().enumerate() {
   println!("{} {} {} {} {} {} {} {}",cluster,row,r.low_mhz,r.high_mhz,r.low_index,r.high_index,r.core_voltage,r.sram_voltage);
   core[cluster][row]=r.core_voltage;sram[cluster][row]=r.sram_voltage;
  }
 }
 let mut bytes=Vec::from(abi::voltages(&core));bytes.extend(abi::voltages(&sram));
 std::fs::write(std::env::args().nth(1).unwrap(),bytes).unwrap();
}
'''
a.output.mkdir(exist_ok=True,parents=True);binary=a.output/'cluster-voltage-wire.bin'
with tempfile.TemporaryDirectory() as tmp:
 src=Path(tmp)/'check.rs';exe=Path(tmp)/'check';src.write_text(source)
 subprocess.run(['rustc','--edition=2021',str(src),'-o',str(exe)],check=True)
 lines=subprocess.check_output([str(exe),str(binary)],text=True).splitlines()
for line in lines:
 c,row,low,high,li,hi,cv,sv=map(int,line.split());r=expected[c][row]
 if [low,high,li,hi,cv,sv]!=[r[k] for k in ['frequency_low_mhz','frequency_high_mhz','index_low','index_high','core_voltage_raw','sram_voltage_raw']]:raise ValueError('Independent decoder disagreement')
wire=binary.read_bytes()
for field,offset in [('core_voltage_raw',0),('sram_voltage_raw',0x400)]:
 for row in range(11):
  words=struct.unpack_from('<16I',wire,offset+row*0x40)
  if list(words[:2])!=[expected[c][row][field] for c in range(2)] or any(words[2:]):raise ValueError('Wire columns disagree with independent decoded input')
 if any(wire[offset+11*0x40:offset+16*0x40]):raise ValueError('Unused storage slots are not zero')
if len(wire)!=0x800:raise ValueError('Unexpected full storage extent')
r={'storage_slots_per_array':16,'tail_slots_zero':True,'adt_sha256':hashlib.sha256(raw).hexdigest(),'raw_rows_per_cluster':count,'voltage_groups_per_cluster':[len(x) for x in expected],'cluster_ladders':expected,'wire_sha256':hashlib.sha256(wire).hexdigest(),'wire_bytes':len(wire),'rust_python_decoder_agreement':True,'wire_columns_checked':True,'qualification':'Two standalone candidate core/SRAM arrays only. No assignment to profiles A/B, full hardware construction, calibrated power table or firmware acceptance.'}
(a.output/'receipt.json').write_text(json.dumps(r,indent=2)+'\n');print('Both decoders agree: 16 rows -> 11 groups per cluster; all wire columns verified.')
