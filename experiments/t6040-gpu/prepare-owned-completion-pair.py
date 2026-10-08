#!/usr/bin/env python3
"""Join completion/SPM device and firmware aliases to paired native producers.

Both services traverse one parent resource, with mapping handles+58/+50.
Same-physical backing and zero initialization are explicit experiment hypotheses.
No publication, queue submission, completion or GPU execution.
"""
from pathlib import Path
import argparse,shutil,json,struct,hashlib,importlib.util,sys
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('pair',type=Path);p.add_argument('backing',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
kit=Path(__file__).resolve().parent;sys.path.insert(0,str(kit));sha=lambda b:hashlib.sha256(b).hexdigest()
device=0x10000c4000;firmware=0xfffffc2000b14000
a.output.mkdir(exist_ok=False);inp=a.output/'input';shutil.copytree(a.pair/'input',inp)
manifest=json.loads((inp/'input.json').read_text());manifest['parameter_gpu']=hex(device)
for kind in ['ta','3d']:manifest[kind+'_construction']['completion_mapping_address']=hex(firmware)
desc=bytearray((inp/'descriptor.bin').read_bytes());struct.pack_into('<I',desc,0x1430,0);struct.pack_into('<I',desc,0xb98,0x40);(inp/'descriptor.bin').write_bytes(desc)
(inp/'input.json').write_text(json.dumps(manifest,indent=2)+'\n')
spec=importlib.util.spec_from_file_location('paired',kit/'prepare-native-sksm-registers.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
import unicorn
calls=[];original=mod.produce
def observed(ns,kind,*args):
 def instruction(m,pc,size,user):
  word=struct.unpack('<I',m.mem_read(pc,4))[0]
  if word&0xfffffc00==0xd73f0800:
   reg=ns['regs'][(word>>5)&31]
   if m.reg_read(reg)==0x231000:
    c=ns['c'];returned=m.reg_read(c.UC_ARM64_REG_X0);assert returned==device;calls.append(dict(stage=kind,pc=hex(pc),resource_checked_by_existing_service_hook=hex(ns['R3']),returned_device_va=hex(returned)))
 h=ns['m'].hook_add(unicorn.UC_HOOK_CODE,instruction)
 try:return original(ns,kind,*args)
 finally:ns['m'].hook_del(h)
mod.produce=observed
r=mod.prepare(a.macho,inp/'input.json',a.output/'pair');assert len(calls)==2
for kind,reg,offset in [('ta',0x14318,0),('3d',0x14080,0x40)]:
 records=[e for ls in r['producers'][kind]['lists'] for e in ls['records']]
 expected=((device+offset)&0x7ffffffffc0)|1
 assert any(int(e['register'],0)==reg and e['flag']==0 and int(e['value'],0)==expected for e in records),(kind,hex(expected))
ta=(a.output/'pair/ta-construction-candidate.bin').read_bytes();assert struct.unpack_from('<Q',ta,0x945)[0]==firmware
# Do not invent the optional3D notification identity. Its native condition stays clear.
assert struct.unpack_from('<Q',desc,0xb70)[0]==0 and r['3d_construction']['completion_mapping_present'] is False
base=json.loads((a.backing/'preparation.json').read_text());data=(a.backing/'backing.bin').read_bytes();assert base['pages']==47 and sha(data)==base['data_sha256']
vas=[int(v,0) for v in base['candidate_vas']]+[device];aliases=[int(v,0) for v in base['firmware_aliases']]+[firmware];data+=bytes(16384)
assert len(set(vas))==48 and len({v for v in aliases if v})==17
out=a.output/'graph';out.mkdir()
for name in ['Makefile','asc-graph-init.c','boot-contract.h','command-pool-map.h','graph-contract.h','graph-map.h','render-backing-map.h']:shutil.copy2(a.backing/name,out/name)
header='#define RENDER_FW_ALIASES 1\n#define RENDER_BACKING_PAGES 48U\n#define RENDER_EXTRA_PAGES 54U\nstatic const unsigned int render_region_starts[]={0,20,21};\nstatic const unsigned int render_region_counts[]={20,1,27};\nstatic const u64 render_vas[]={'+','.join(hex(v)+'ULL' for v in vas)+'};\nstatic const u64 render_fw_aliases[]={'+','.join(hex(v)+'ULL' for v in aliases)+'};\nstatic const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n'
commands=[]
for kind in ['3d','ta']:
 b=(a.output/'pair'/(kind+'-construction-candidate.bin')).read_bytes();assert len(b)<=(0x2240);commands.append(b+bytes(0x2240-len(b)))
commands+=[bytes(0x2240)]*62
jhead='#define JOB_COUNT 64U\n#define COMMAND_BYTES 0x2240U\n#define POOL_BYTES 573440U\n#define POOL_PAGES 35U\n#define DEVICE_BASE 0x850000000ULL\n#define FW_BASE 0xfffffc2000800000ULL\nstatic const u8 job_bytes[JOB_COUNT][COMMAND_BYTES]={\n'+',\n'.join('{'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(b) if v)+'}' for b in commands)+'\n};\n'
(out/'render-data.h').write_text(header);(out/'job-data.h').write_text(jhead);(out/'backing.bin').write_bytes(data)
base['integrated_pair']['command_sha256']=[sha(b) for b in commands[:2]]
base.update(pages=48,bytes=len(data),data_sha256=sha(data),header_sha256=sha(header.encode()),candidate_vas=[hex(v) for v in vas],firmware_aliases=[hex(v) for v in aliases],completion_backing=dict(device=hex(device),firmware=hex(firmware),bytes=16384,ta_offset=0,three_d_spm_offset=64,three_d_conditional_completion_enabled=False,initialization='zero experiment hypothesis; same physical resource aliases'),qualification='Paired native producer completion/SPM addresses bind to proposed owned same-physical GPU/FW page. Offline prepared graph only; no queued work or completion.')
(out/'preparation.json').write_text(json.dumps(base,indent=2)+'\n')
report=dict(map_calls=calls,producer_counts={k:v['encoded_records'] for k,v in r['producers'].items()},completion_backing=base['completion_backing'],data_pages=48,total_owned_pages=166,aliases=17,submission_ready=False,qualification=base['qualification'],remaining=['live alias allocation/context publication','work-channel queue identity/doorbell binding','full shader launch and TA/3D ordering','completion records/event identity, coherent readback and teardown'])
(a.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
