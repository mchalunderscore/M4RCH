#!/usr/bin/env python3
"""Bind saved class1 publication source and captures; no execution or hardware."""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HOST_SHA='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
def pin(p):
 p=Path(p);b=p.read_bytes();return dict(path=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def main():
 host=Path('/boot/GPUC003/private-apple/com.apple.AGXG16X');b=host.read_bytes();assert hashlib.sha256(b).hexdigest()==HOST_SHA
 segments=[];pos=32
 for _ in range(struct.unpack_from('<I',b,16)[0]):
  cmd,size=struct.unpack_from('<II',b,pos)
  if cmd==25:segments.append(struct.unpack_from('<QQQQ',b,pos+24))
  pos+=size
 def read(a,n):
  a+=0xfffffe0000000000;rows=[b[o+a-v:o+a-v+n] for v,vs,o,s in segments if v<=a and a+n<=v+s];assert len(rows)==1;return rows[0]
 captured=ROOT/'out/gfx-native-fender-off-cycle/candidate/asc-graph-init/boot-09a48fe3-925a-46d9-b99b-b9aecc71e6f3/text.bin';fw=captured.read_bytes()
 table=read(0x712e084,56);assert table==fw[0x58850:0x58888] and table[10]==1 and table[22]==0 and table[34]==0
 vtable=read(0x7ea9118,8);target=0x7004000+(struct.unpack('<Q',vtable)[0]&0xffffffff);assert target==0x89b7cf8
 ranges=[]
 for a,z,purpose in [(0x89a6924,0x89a6b34,'complete device-control admission/copy/class/producer return'),(0x89b7cf8,0x89b7d18,'packed assertion increment plus DMB ISH'),(0x89b58a0,0x89b58b0,'device-control setWriteIndex'),(0x89cd9b0,0x89cd9f4,'RegionC mapped pointer to root+20')]:
  ranges.append(dict(begin=hex(a),end_exclusive=hex(z),bytes=z-a,sha256=hashlib.sha256(read(a,z-a)).hexdigest(),purpose=purpose))
 franges=[]
 for a,z,purpose in [(0x3884,0x3930,'assertion snapshot and activation predicate before record dispatch'),(0x39e0,0x3a1c,'class table dispatch'),(0x514c,0x5180,'class1 consumed count before read advancement')]:
  franges.append(dict(begin=hex(a),end_exclusive=hex(z),bytes=z-a,sha256=hashlib.sha256(fw[a:z]).hexdigest(),purpose=purpose))
 raw=[]
 for kit,boot in [('gfx-native-fender-off-cycle','09a48fe3-925a-46d9-b99b-b9aecc71e6f3'),('gfx-native-fender-runtime-cycle','f4a7b737-ed3d-4851-8fcd-cac56eb233d7')]:
  path=ROOT/'out'/kit/'candidate/asc-graph-init';receipt=path/'graph-receipt.json';j=json.loads(receipt.read_bytes());objects={o['name']:o for o in j['objects']};base=int(j['base'],16)
  for n in ['objects-before.bin','objects-after.bin']:
   file=path/('boot-'+boot)/n;q=file.read_bytes();c=objects['region_c']['arena_offset'];s=objects['status_b']['arena_offset'];assert c==0xc000 and s==0x40000
   assert struct.unpack_from('<Q',q,0x20)[0]==base+c and struct.unpack_from('<Q',q,0xb0)[0]==base+s
   assertion=struct.unpack_from('<I',q,c+0xe51)[0];consumed=struct.unpack_from('<I',q,s+0xe438)[0];assert assertion==consumed==0
   raw.append(dict(boot=boot,capture=pin(file),graph_receipt=pin(receipt),root_region_c=hex(base+c),root_status_b=hex(base+s),assertion_offset=hex(c+0xe51),assertion=assertion,consumed_offset=hex(s+0xe438),consumed=consumed,sealed_precycle=n=='objects-after.bin',postcycle=False))
 v22=ROOT/'out/gfx-native-idle-policy-fender-cycle/prepared-owner-v1';r=json.loads((v22/'graph-receipt.json').read_bytes());o={x['name']:x for x in r['objects']}
 report=dict(schema='m4rch.native-power-assertion-publication.v1',hardware_access=False,hardware_actions=[],apple_code_executed=False,emulation_rerun=False,inputs=[pin(p) for p in [host,captured,ROOT/'out/private-apple/agx-disassembly.txt',ROOT/'out/private-apple/live-text.dis',ROOT/'docs/evidence/2026-10-09-abi-reference-recheck.md',ROOT/'docs/evidence/2026-10-11-gfx-native-gpu-idle-control-abi.json',v22/'native-idle-policy-fender-cycle-owner-source-receipt.json',v22/'gfx-native-idle-policy.h',v22/'recovery-cycle.h',Path(__file__)]],native_ranges=ranges,firmware_ranges=franges,class_table=dict(native='0x712e084',firmware='0x58850',bytes=56,sha256=hashlib.sha256(table).hexdigest(),values=list(table),tables_equal=True,opcode10_decimal_class=1,opcode22_decimal_class=0,opcode34_decimal_class=0),native_virtual_binding=dict(class_name='AGXArmFirmwareASC',symbol='__ZTV17AGXArmFirmwareASC',vtable='0x7ea8668',address_point='0x7ea8678',slot='0xaa0',entry='0x7ea9118',entry_sha256=hashlib.sha256(vtable).hexdigest(),target=hex(target),method='AGXArmFirmware::incrementSchedulerGPUCorePwrAssertCounter'),native_publication=dict(admission='(write+1)&0xff must differ from read, otherwise native workloop wait before copy',record_copy='0x89a6a70..0x89a6a7c',class_read='0x89a6a98..0x89a6aa8',class_gate='0x89a6aac TBZ bit0 skips only for class0 in matched table',increment_call='0x89a6ad4',counter_cpu_parent='AGXArmFirmware+0x380',counter_offset='0xe51',counter_width_bits=32,unaligned=True,operation='u32 wrapping add1, non-atomic LDR/ADD/STR; workloop serialized',increment_store='0x89b7d0c',increment_barrier='0x89b7d10 DMB ISH',outer_barrier='0x89a6ad8 DMB ISH',producer_call='0x89a6b10, setWriteIndex((old+1)&0xff)',producer_leaf='0x89b58a0: ring+8 CPU state pointer; STR W1 at state+0x20',order=['copy64','increment host assertion for class1','DMB ISH','producer'],direct_cache_clean_in_leaf=False),firmware_semantics=dict(assertion_parent='root+0x20 copied to global0x195748',counter_offset='0xe51',consumed_parent='root+0xb0 copied to global0x18ee70',consumed_offset='0xe438',activation='0x3900..0x3924 compares consumed!=assertion and calls0x33a68 unless earlier native-power state gate bypasses; inequality is admission to activation, not completion',consumed_update='0x514c..0x5164 nonzero class increments u32 once after dispatch',read_advance='0x5170..0x517c increments read modulo256 after consumed increment',completion='fresh exact consumed baseline+1 and read/prefetch/producer34; assertion alone never proves processing/off/retirement'),candidate_binding=dict(graph_receipt=pin(v22/'graph-receipt.json'),region_c_object=o['region_c'],status_b_object=o['status_b'],assertion_arena_offset='0xce51',root_region_c_va='0xfffffc200010c000',cache_line_offset='0xce40',assertion_bytes_do_not_cross_64byte_line=True,baseline='fresh assertion==consumed before any write',near_wrap='Native wraps modulo2^32; this trial refuses baseline>=UINT_MAX-1 before any record store to preserve v22 invalid-word guards',linux_publication='Owned host page write via memcpy (avoids unaligned u32 UB), inherited recovery_clean emits DMBISH then DC CVAC then DSBSY, fresh cache-invalidated memcpy readback, fresh pointer/access/cursors before producer; Linux cache transfer is separate from native coherent allocation',initial_root_refresh='u32 opcode0x16, class0, leaves assertion unchanged',selected_v22_mutated=False),saved_raw_counters=raw,correction=dict(issue='v22 adds class1 opcode0a but omitted native host assertion increment',new_candidate='distinct v23; frozen v22/old captures unchanged',protocol='Record copy/clean/readback -> one assertion increment/clean/readback -> producer34 -> one EP33 class84',failure='An ambiguous assertion attempt retains unknown and publishes no producer/EP33; no rollback/retry/free',caller_bool_and_before202_order='explicit experimental transfer remains unchanged',strict_OFF_and_work_accounting='unchanged'))
 output=ROOT/'docs/evidence/2026-10-11-gfx-native-power-assertion-publication.json';output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(pin(output)))
if __name__=='__main__':main()
