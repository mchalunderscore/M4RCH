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
scene=(a.pm/pm['files']['scene-records']['file']).read_bytes();(inp/'scene.bin').write_bytes(scene[:128]+bytes(128))
(inp/'input.json').write_text(json.dumps(manifest,indent=2)+'\n')
path=Path(private_ta_inputs.__file__).with_name('prepare-native-sksm-registers.py');spec=importlib.util.spec_from_file_location('paired',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
r=mod.prepare(a.macho,inp/'input.json',a.output/'pair');assert r['submission_ready'] is False
for kind,off in [('ta',0x20),('3d',0x28)]:
 command=(a.output/'pair'/(kind+'-construction-candidate.bin')).read_bytes();expected=tuple(int(v,0) for v in manifest[kind+'_construction']['firmware_translations']);assert struct.unpack_from('<3Q',command,off)==expected
report={'submission_ready':False,'pm_profile_sha256':sha((a.pm/'profile.json').read_bytes()),'resource_ranges':[{k:hex(v) if k.endswith('base') else v for k,v in r.items()} for r in resources],'bindings':bindings,'native_initialized_scene_record_sha256':sha(scene[:128]),'producer_counts':{k:v['encoded_records'] for k,v in r['producers'].items()},'qualification':'Actual paired native register producers and existing command/scheduler models now consume aligned PM/render descriptor and native initialized scene record. Six command translations derive from explicit host/FW resource ranges; their output bytes checked. Null translation0 is an explicit candidate hypothesis. Proposed resource FW/device aliases are not installed; host identities remain emulation inputs. Completion, command-pool/queue/event/cache lifetimes and full shader launch remain unqualified. No firmware publication or rendering.'}
(a.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
