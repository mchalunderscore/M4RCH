#!/usr/bin/env python3
"""Feed checked aligned native PM/target fields into existing paired command construction."""
import argparse,json,struct,hashlib,importlib.util,sys,shutil
from pathlib import Path
import private_ta_inputs
sys.path.insert(0,str(Path(private_ta_inputs.__file__).parent))
from private_ta_inputs import load_ta_render_target
p=argparse.ArgumentParser();p.add_argument('macho',type=Path);p.add_argument('base',type=Path);p.add_argument('combined',type=Path);p.add_argument('pm',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
sha=lambda b:hashlib.sha256(b).hexdigest()
r=json.loads((a.combined/'receipt.json').read_text());pm=json.loads((a.pm/'profile.json').read_text())
assert r['submission_ready'] is False and pm['submission_ready'] is False
assert r['pm_profile_sha256']==sha((a.pm/'profile.json').read_bytes())
for name,entry in r['files'].items():
 b=(a.combined/name).read_bytes();assert len(b)==entry['bytes'] and sha(b)==entry['sha256']
a.output.mkdir(exist_ok=False);input_dir=a.output/'input';input_dir.mkdir()
for f in a.base.iterdir():
 if f.is_file():shutil.copy2(f,input_dir/f.name)
desc=bytearray((a.base/'descriptor.bin').read_bytes());combined=(a.combined/'combined-ta-render-pm-fields-fixture.bin').read_bytes();source=(a.combined/'render-target-packed-source-fixture.bin').read_bytes()
bases={('primary',0x160):0xfffffc2000a00000,('primary',0x158):0x1000040000,('support',0x160):0xfffffc2000a20000,('support',0x158):0x1000060000,('retain',0x20):0}
service=lambda r,s:bases[r,s]
zero=load_ta_render_target(bytes(0x1800),source,service);dirty=load_ta_render_target(bytes([255])*0x1800,source,service)
written={i for i,(x,y) in enumerate(zip(zero,dirty)) if x==y}
for field in pm['native_descriptor_fields']:
 off=int(field['offset'],0);written.update(range(off,off+field['bytes']))
for i in written:desc[i]=combined[i]
assert all(desc[i]==combined[i] for i in written)
# Supply the candidate64x64 common dimensions through the already checked
# native payload-copy window, retaining base explicit shader/state fixtures.
payload=bytearray((a.base/'payload.bin').read_bytes());struct.pack_into('<Q',payload,0x18,0x1000000000);struct.pack_into('<II',payload,0x2d0+0x1c8,64,64)
path=Path(private_ta_inputs.__file__).with_name('audit-private-ta-generator.py');ns={'__file__':str(path),'__name__':'pair_composition'};old=sys.argv
try:
 sys.argv=[str(path),str(a.macho),str(a.output/'unused.json'),str(a.output/'unused.json')]
 exec(compile(path.read_text().split("counts={'complete_ta_producer'")[0],str(path),'exec'),ns)
finally:sys.argv=old
inner=ns['ns'];m=ns['m'];c=ns['c'];D=ns['D'];P=0x238000;W=0x23c000;start,end=0xfffffe0008998198,0xfffffe0008998504
m.mem_map(0xfffffe0008998000,4096);m.mem_write(start,inner['read'](start,end-start));m.mem_write(D,bytes(desc));m.mem_write(P,bytes(payload));wrapper=bytearray(0x300);struct.pack_into('<Q',wrapper,0x18,P);m.mem_write(W,bytes(wrapper))
for reg in inner['regs']:m.reg_write(reg,0)
for reg,value in [(c.UC_ARM64_REG_X25,D),(c.UC_ARM64_REG_X23,D+0x79c),(c.UC_ARM64_REG_X26,W),(c.UC_ARM64_REG_SP,inner['STACK'])]:m.reg_write(reg,value)
m.emu_start(start,end,count=3000);assert m.reg_read(c.UC_ARM64_REG_PC)==end
from private_render_setup import copy_payload
prepared=bytes(m.mem_read(D,0x1800));assert prepared==copy_payload(desc,payload)
assert all(prepared[i]==combined[i] for i in written)
(input_dir/'descriptor.bin').write_bytes(prepared);(input_dir/'payload.bin').write_bytes(payload);(input_dir/'render-target-source.bin').write_bytes(source)
manifest=json.loads((a.base/'memory-input.json').read_text());(input_dir/'input.json').write_text(json.dumps(manifest,indent=2)+'\n')
path=Path(private_ta_inputs.__file__).with_name('prepare-native-sksm-registers.py');spec=importlib.util.spec_from_file_location('paired',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
result=mod.prepare(a.macho,input_dir/'input.json',a.output/'pair');assert result['submission_ready'] is False
records=result['producers']['ta']['lists'][0]['records'];expected=[(0x1c038,1,bases['primary',0x160]),(0x1c9c8,0,bases['primary',0x160]),(0x1c078,1,bases['primary',0x160]+4096),(0x1c9d8,0,bases['primary',0x160]+4096)]
for reg,flag,value in expected:assert [int(e['value'],0) for e in records if int(e['register'],0)==reg and e['flag']==flag]==[value]
report={'submission_ready':False,'base_descriptor_sha256':sha((a.base/'descriptor.bin').read_bytes()),'combined_receipt_sha256':sha((a.combined/'receipt.json').read_bytes()),'pm_profile_sha256':sha((a.pm/'profile.json').read_bytes()),'patched_native_field_bytes':len(written),'payload_native_comparison':True,'firmware_register_values_checked':4,'producer_counts':{k:v['encoded_records'] for k,v in result['producers'].items()},'qualification':'Aligned native PM/target fields merged into previously constructor/payload-prepared descriptor using checked target-write mask and explicit PM fields; native payload copy preserves all merged fields. Actual paired SKSM native register producers execute; existing construction/event/aperture/scheduler models compose over their output. Four expected native target register values checked. Base fixture shader/state sources, translation/completion/queue/pool/parameter service identities remain supplied; no actual FW mapping/publication/cache/GPU lookup or pixels. Candidate is not submission-ready.'}
(a.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
