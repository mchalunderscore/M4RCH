#!/usr/bin/env python3
"""Derive command translations from explicit host/FW resource ranges, offline only."""
import argparse,json,struct,hashlib,shutil,sys,importlib.util
from pathlib import Path
import private_ta_inputs
sys.path.insert(0,str(Path(private_ta_inputs.__file__).parent))
p=argparse.ArgumentParser();p.add_argument('macho',type=Path);p.add_argument('aligned_pair',type=Path);p.add_argument('pm',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
sha=lambda b:hashlib.sha256(b).hexdigest();pm=json.loads((a.pm/'profile.json').read_text());assert pm['submission_ready'] is False
for entry in pm['files'].values():
 b=(a.pm/entry['file']).read_bytes();assert sha(b)==entry['sha256'] and len(b)==entry['bytes']
resources=[]
for name,fw,dev in [('aux-records',0xfffffc2000a80000,0x10000a8000),('scene-records',0xfffffc2000ac0000,0x10000ac000)]:
 assert fw>>48==0xffff and fw%16384==0 and dev%16384==0
 entry=pm['files'][name];resources.append(dict(name=name,host_base=int(entry['fixture_cpu_address'],0),bytes=entry['bytes'],fw_base=fw,device_base=dev))
# This null behavior is an explicit candidate hypothesis, not a qualified native translator.
def translate(host):
 if host==0:return 0
 matches=[r for r in resources if r['host_base']<=host<r['host_base']+r['bytes']]
 if len(matches)!=1:raise ValueError('host pointer is not in a unique declared resource: '+hex(host))
 r=matches[0];return r['fw_base']+host-r['host_base']
a.output.mkdir(exist_ok=False);inp=a.output/'input';shutil.copytree(a.aligned_pair/'input',inp)
desc=(inp/'descriptor.bin').read_bytes();manifest=json.loads((inp/'input.json').read_text());bindings=[]
for kind,offsets in [('ta',(0x1220,0x1228,0x1250)),('3d',(0x908,0x910,0x938))]:
 values=[]
 for off in offsets:
  host=struct.unpack_from('<Q',desc,off)[0];fw=translate(host);values.append(hex(fw));bindings.append(dict(stage=kind,descriptor_offset=hex(off),host_value=hex(host),translated_value=hex(fw),null_candidate=host==0))
 manifest[kind+'_construction']['firmware_translations']=values
# Producer's CPU scene lookup now consumes the checked native initialized record,
# retaining its own emulation relocation; no raw whole host object uploaded.
scene_native=(a.pm/pm['files']['scene-records']['file']).read_bytes()
scene_candidate=bytearray(len(scene_native))
for j in range(pm['capacities']['scene_records']):
 # Experimental registration result points to our declared page-list device VA.
 # Zero untouched fields explicitly; never reuse randomized inherited bytes.
 struct.pack_into('<Q',scene_candidate,j*128,0x10000a0000)
 struct.pack_into('<Q',scene_candidate,j*128+0x28,int(pm['mapping_candidates']['scene'],0))
 struct.pack_into('<Q',scene_candidate,j*128+0x4c,1)
scene=bytes(scene_candidate);(inp/'scene.bin').write_bytes(scene[:128]+bytes(128))
(a.output/'scene-resource-candidate.bin').write_bytes(scene)
(a.output/'aux-resource-candidate.bin').write_bytes(bytes(pm['files']['aux-records']['bytes']))
manifest['ta_command_gpu']='0x850002240'
manifest['scheduler']['ta']['payload']=['0xfffffc2000802240',0]
(inp/'input.json').write_text(json.dumps(manifest,indent=2)+'\n')
path=Path(private_ta_inputs.__file__).with_name('prepare-native-sksm-registers.py');spec=importlib.util.spec_from_file_location('paired',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
import unicorn
accesses={};original_produce=mod.produce
def observed_produce(ns,kind,*args):
 reads=[]
 def memory_read(m,access,address,size,value,user):
  if 0x238000<=address<0x238100:reads.append((address-0x238000,size,hex(m.reg_read(ns['c'].UC_ARM64_REG_PC))))
 handle=ns['m'].hook_add(unicorn.UC_HOOK_MEM_READ,memory_read)
 try:return original_produce(ns,kind,*args)
 finally:
  ns['m'].hook_del(handle);accesses[kind]=sorted(set(reads))
mod.produce=observed_produce
r=mod.prepare(a.macho,inp/'input.json',a.output/'pair');assert r['submission_ready'] is False
for kind,off in [('ta',0x20),('3d',0x28)]:
 command=(a.output/'pair'/(kind+'-construction-candidate.bin')).read_bytes();expected=tuple(int(v,0) for v in manifest[kind+'_construction']['firmware_translations']);assert struct.unpack_from('<3Q',command,off)==expected
expected_scene_registers=[('ta',0x1ca30,0,0xfffffc2000b00000),('ta',0x16c38,1,0xfffffc2000b00000),('3d',0x1ca28,0,0xfffffc2000b00000)]
for kind,reg,flag,value in expected_scene_registers:
 records=[e for ls in r['producers'][kind]['lists'] for e in ls['records']]
 assert any(int(e['register'],0)==reg and e['flag']==flag and int(e['value'],0)==value for e in records)
report={'submission_ready':False,'pm_profile_sha256':sha((a.pm/'profile.json').read_bytes()),'resource_ranges':[{k:hex(v) if k.endswith('base') else v for k,v in r.items()} for r in resources],'bindings':bindings,'native_initialized_scene_record_sha256':sha(scene_native[:128]),'experimental_scene_record_sha256':sha(scene[:128]),'experimental_initialization':{'scene0':'page-list device VA; registration semantics unqualified','scene28':'native checked setupSceneState mapping output','scene4c':'generation1 candidate','remaining_scene_bytes':'zero hypothesis','aux_records':'zero hypothesis'},'scene_reads':accesses,'producer_counts':{k:v['encoded_records'] for k,v in r['producers'].items()},'qualification':'Actual paired native register producers and existing command/scheduler models now consume aligned PM/render descriptor and explicit experimental scene record with native-derived scene mapping and candidate page-list registration address. Six command translations derive from explicit host/FW resource ranges; their output bytes checked. Null translation0 is an explicit candidate hypothesis. Proposed resource FW/device aliases are not installed; host identities remain emulation inputs. Completion, command-pool/queue/event/cache lifetimes and full shader launch remain unqualified. No firmware publication or rendering.'}
(a.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
