#!/usr/bin/env python3
"""Prepare owned TA/3D queue graph and KSM records, without publication.

Uses checked native common record/config models, M4 Pro state offsets from the
provided ABI, and explicitly experimental context/initialization defaults.
"""
from pathlib import Path
import argparse,json,struct,hashlib,shutil,importlib.util,sys
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('completion_pair',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
kit=Path(__file__).resolve().parent;sys.path.insert(0,str(kit));from private_scheduler_config import patch_config
sha=lambda b:hashlib.sha256(b).hexdigest();raw=a.macho.read_bytes();assert sha(raw)=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments=[];pos=32
for _ in range(struct.unpack_from('<I',raw,16)[0]):
 cmd,n=struct.unpack_from('<II',raw,pos)
 if cmd==25:segments.append(struct.unpack_from('<QQQQ',raw,pos+24))
 pos+=n
def read(va,n):
 for vm,_,off,length in segments:
  if vm<=va and va+n<=vm+length:return raw[off+va-vm:off+va-vm+n]
 raise ValueError('not file backed')
header=struct.unpack('<Q',read(0xfffffe000712d720,8))[0];vector=read(0xfffffe000712d9b0,16);assert header&0xffffffff==15
a.output.mkdir(exist_ok=False);inp=a.output/'input';shutil.copytree(a.completion_pair/'input',inp)
m=json.loads((inp/'input.json').read_text());d=bytearray((inp/'descriptor.bin').read_bytes());struct.pack_into('<Q',d,0x14e8,1);struct.pack_into('<II',d,0x210,512,0);struct.pack_into('<I',d,0x218,1);struct.pack_into('<III',d,0x21c,512,0,0);(inp/'descriptor.bin').write_bytes(d)
queues={}
for kind,qid,device,fw in [('ta',0,0x10000c8000,0xfffffc2000b18000),('3d',1,0x10000d0000,0xfffffc2000b20000)]:
 queues[kind]=dict(id=qid,device_base=device,firmware_base=fw,capacity=16,job_command_fw=0xfffffc2000802240 if kind=='ta' else 0xfffffc2000800000)
 m['scheduler'][kind]['queue'].update(id=qid,timestamp=1,previous=0,initial=0,capacity=16,pending=0)
 if kind=='ta':m['scheduler'][kind]['payload']=[hex(queues[kind]['job_command_fw']),hex(fw)]
 else:m['scheduler'][kind]['native_3d']['channel_payload']=hex(fw)
(inp/'input.json').write_text(json.dumps(m,indent=2)+'\n')
spec=importlib.util.spec_from_file_location('paired',kit/'prepare-native-sksm-registers.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);r=mod.prepare(a.macho,inp/'input.json',a.output/'pair')
basegraph=a.completion_pair/'graph';prep=json.loads((basegraph/'preparation.json').read_text());data=bytearray((basegraph/'backing.bin').read_bytes());assert prep['pages']==48 and sha(data)==prep['data_sha256']
vas=[int(x,0) for x in prep['candidate_vas']];aliases=[int(x,0) for x in prep['firmware_aliases']];reports=[]
for kind,q in queues.items():
 fw=q['firmware_base'];dev=q['device_base'];qid=q['id'];work=(a.output/'pair'/(kind+'-scheduler-common.bin')).read_bytes();assert len(work)==0x200
 assert struct.unpack_from('<2Q',work,0x10)==(q['job_command_fw'],fw)
 assert (struct.unpack_from('<Q',work,0)[0]>>42)&127==qid
 if kind=='3d':assert struct.unpack_from('<Q',work,0x28)[0]&((1<<47)-1)==1 # TA queue0/timeline1
 meta=bytearray(16384);ring=bytearray(16384);ring[:512]=work
 # Separate channel state, job pointer record/ring, context and KSM ring.
 for off,value in [(0,fw+0x100),(8,fw+0x400),(0x10,fw+0x300),(0x9c,fw+0x200)]:struct.pack_into('<Q',meta,off,value)
 struct.pack_into('<Q',meta,0x30,0xffffffffffff0000)
 for off,value in [(0x24,0xffffffff),(0x28,0),(0x2c,0),(0x38,1),(0x40,1),(0x44,0xffffffff),(0x48,qid+1)]:struct.pack_into('<I',meta,off,value)
 struct.pack_into('<I',meta,0x100+0x50,1);struct.pack_into('<I',meta,0x100+0x60,16)
 struct.pack_into('<Q',meta,0x400,q['job_command_fw']);struct.pack_into('<Q',meta,0x308,fw+0x400)
 # Borrow Gravity's base-M4 context seed only as an explicit trial hypothesis.
 meta[0x200:0x202]=b'\xff\xff';meta[0x205]=1;meta[0x226]=2;meta[0x233]=0xff
 cfg=patch_config(bytes(0x90),header,vector,(dev+16384,fw+16384),qid,0,0,[0,0],[255,0]);meta[0x1000:0x1090]=cfg
 assert struct.unpack_from('<QQ',cfg,8)==(dev+16384,fw+16384) and struct.unpack_from('<H',cfg,0x18)[0]==qid
 (a.output/(kind+'-queue-state.bin')).write_bytes(meta);(a.output/(kind+'-ksm-ring.bin')).write_bytes(ring)
 for j,page in enumerate([meta,ring]):vas.append(dev+j*16384);aliases.append(fw+j*16384);data+=page
 reports.append(dict(stage=kind,queue_id=qid,state_fw=hex(fw),pointer_record_fw=hex(fw+0x100),job_ring_fw=hex(fw+0x400),context_fw=hex(fw+0x200),ksm_ring_device=hex(dev+16384),ksm_ring_fw=hex(fw+16384),config_fw=hex(fw+0x1000),timestamp=1,job_pointer_producer=1,ksm_work_records=1,config_opcode=15))
assert len(vas)==52 and len(set(vas))==52 and len({x for x in aliases if x})==21
out=a.output/'graph';out.mkdir()
for name in ['Makefile','asc-graph-init.c','boot-contract.h','command-pool-map.h','graph-contract.h','graph-map.h','render-backing-map.h']:shutil.copy2(basegraph/name,out/name)
headerdata='#define RENDER_FW_ALIASES 1\n#define RENDER_BACKING_PAGES 52U\n#define RENDER_EXTRA_PAGES 58U\nstatic const unsigned int render_region_starts[]={0,20,21};\nstatic const unsigned int render_region_counts[]={20,1,31};\nstatic const u64 render_vas[]={'+','.join(hex(v)+'ULL' for v in vas)+'};\nstatic const u64 render_fw_aliases[]={'+','.join(hex(v)+'ULL' for v in aliases)+'};\nstatic const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n'
commands=[]
for kind in ['3d','ta']:
 b=(a.output/'pair'/(kind+'-construction-candidate.bin')).read_bytes();commands.append(b+bytes(0x2240-len(b)))
commands+=[bytes(0x2240)]*62
jhead='#define JOB_COUNT 64U\n#define COMMAND_BYTES 0x2240U\n#define POOL_BYTES 573440U\n#define POOL_PAGES 35U\n#define DEVICE_BASE 0x850000000ULL\n#define FW_BASE 0xfffffc2000800000ULL\nstatic const u8 job_bytes[JOB_COUNT][COMMAND_BYTES]={\n'+',\n'.join('{'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(b) if v)+'}' for b in commands)+'\n};\n'
(out/'render-data.h').write_text(headerdata);(out/'job-data.h').write_text(jhead);(out/'backing.bin').write_bytes(data)
prep['integrated_pair']['command_sha256']=[sha(b) for b in commands[:2]];prep.update(pages=52,bytes=len(data),data_sha256=sha(data),header_sha256=sha(headerdata.encode()),candidate_vas=[hex(v) for v in vas],firmware_aliases=[hex(v) for v in aliases],owned_scheduler=reports,qualification='Proposed owned queue state/pointer/KSM ring and paired commands; no config publication, work doorbell or rendering. Context/profile/initialization experimental.')
(out/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
report=dict(queues=reports,owned_pages=170,data_pages=52,aliases=21,producer_counts={k:v['encoded_records'] for k,v in r['producers'].items()},dependency='3D producer1 depends on TA queue0/timeline1; descriptor event512 converts to timestamp1',experimental=['M4 Pro state offsets from provided ABI; not full native state ctor proof','Base-M4 Gravity context seed; VM context association remains unverified','zero initial state/callback0 config default','queue0/1 IDs are chosen trial reservations, not allocated firmware identities'],remaining=['firmware config-command transport and acknowledgement','context seed/translation ID association','KSM doorbell and guarded-service requirements','full shader launch/stamp/event completion and readback'],submission_ready=False,hardware_trial=False)
(a.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
