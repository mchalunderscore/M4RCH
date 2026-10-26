#!/usr/bin/env python3
"""Project five native descriptors into actual uploaded owner data, offline."""
import argparse,copy,hashlib,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
BASE_SHA='e1f9c5ca28373ee4508a46f112ac4cc383fb7c245baf4fea14c84913bb53d982'
PROPOSAL=ROOT/'out/gpu-gravity-normal-boot-v3/custom-v19-descriptor-proposal.json'
PROPOSAL_SHA='4fffc9d3228f21e1e0289f6d6bf524f6ff4f9e4f740357ffd6da8d2692f2f1b8'
OLD='GFX_NATIVE_FENDER_OFF_CYCLE_TRIAL';NEW='GFX_NATIVE_DESCRIPTOR_FENDER_CYCLE_TRIAL'
RECEIPT='native-descriptor-fender-cycle-owner-source-receipt.json'
ARENA_SHA='287f2c53bc6ef7ed226c4a2995b9d9904e7623acae9713af105be6b04fc690a9'
NEW_ARENA_SHA='d66603449c3a07b79388c96cb3dc192e4d37ad85e879742b0ac3e7aa2be774e8'
SELECTED=dict(version=21,native_descriptor_changed_bytes=19,native_descriptor_slots=[3,22,27,39,41],canonical_native_absent_slot27=True,unused_donor_slot27_PTE_retained=True,native_descriptor_projection_only=True,normal_T6040_boot_qualified=False,selected_next_hardware_candidate=False)
def sha(b):return hashlib.sha256(b).hexdigest()
def pin(p):
 p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=sha(b))
def require(ok,msg):
 if not ok:raise ValueError(msg)
def checked_inputs(rows):
 for r in rows:require(pin(r['path'])==r,'Frozen native input differs: '+r['path'])
def proposal():
 require(sha(PROPOSAL.read_bytes())==PROPOSAL_SHA,'Native descriptor proposal differs')
 j=json.loads(PROPOSAL.read_bytes());checked_inputs(j['inputs'])
 require(j['changed_byte_count']==19 and [r['slot'] for r in j['rows']]==[3,22,27,39,41] and j['proposed_arena_sha256']==NEW_ARENA_SHA and j['hardware_actions']==[],'Native proposal policy differs')
 qpath=next(Path(r['path']) for r in j['inputs'] if r['path'].endswith('/qualification-v1/qualification.json'));q=json.loads(qpath.read_bytes());checked_inputs(q['inputs'])
 require(q['complete'] and q['schema']=='m4rch.gravity-native-t6040-components.qualification.v3' and q['hardware_actions']==[] and q['native_descriptor_flag_slots']==[3,22,27,39,41] and q['native_absent_slots']==[27],'Native producer qualification differs')
 return j,q
def array_parts(header):
 matches=list(re.finditer(rb'(static const u8 graph_bytes\[(\d+)\]=\{\n)(.*?)(\};)',header,re.S))
 require(len(matches)==1,'Exact compiled graph array missing');m=matches[0];body=m[3]
 rows=re.findall(rb'\[(0x[0-9a-f]+)\]=(0x[0-9a-f]+),\n',body)
 require(b''.join(b'['+a+b']='+v+b',\n' for a,v in rows)==body,'Unexpected graph array grammar')
 arena=bytearray(int(m[2]));seen=set()
 for a,v in rows:
  off=int(a,16);val=int(v,16);require(off<len(arena) and off not in seen and 0<val<256,'Ambiguous graph byte initializer');seen.add(off);arena[off]=val
 return m,bytes(arena)
def project_arena(original,j):
 require(sha(original)==ARENA_SHA,'Frozen v20 and v19 arena differ')
 projected=bytearray(original)
 for r in j['rows']:
  start=int(r['arena_record_offset'],16);p=r['patch'];at=int(p['arena_offset'],16);old=bytes.fromhex(p['expected_before_hex']);new=bytes.fromhex(p['replacement_hex'])
  require(original[start:start+40].hex()==r['before_record_hex'] and len(old)==len(new)==p['bytes'] and original[at:at+len(old)]==old,'Native descriptor before guard differs: '+str(r['slot']))
  projected[at:at+len(new)]=new
  require(projected[start:start+40].hex()==r['after_record_hex'],'Native descriptor record projection differs')
 changed=[hex(i) for i,(a,b) in enumerate(zip(original,projected)) if a!=b]
 require(len(projected)==len(original) and changed==j['changed_arena_offsets'] and len(changed)==19 and sha(projected)==NEW_ARENA_SHA,'Arena changed outside exact nineteen bytes')
 return bytes(projected)
def project_source(outputs):
 """Original frozen-v20 relative-path/bytes projection; no writes/build/hardware."""
 outputs=dict(outputs);j,q=proposal();original=outputs['graph-before.bin'];new=project_arena(original,j)
 v19arena=Path(next(r['path'] for r in j['inputs'] if r['path'].endswith('/graph-before.bin'))).read_bytes();require(original==v19arena,'Frozen v20 graph must equal proposal v19 graph')
 header=outputs['graph-contract.h'];m,compiled=array_parts(header);require(compiled==original,'Baseline compiled owner bytes differ from graph-before')
 body=b''.join(('[%s]=%s,\n'%(hex(i),hex(v))).encode() for i,v in enumerate(new) if v)
 outputs['graph-contract.h']=header[:m.start(3)]+body+header[m.end(3):];require(array_parts(outputs['graph-contract.h'])[1]==new,'Compiled owner graph projection differs')
 outputs['graph-before.bin']=new
 for n,b in list(outputs.items()):
  if n.endswith(('.c','.h')) or n=='Makefile':outputs[n]=b.replace(OLD.encode(),NEW.encode())
 c=outputs['asc-graph-init.c'];old=b'Experimental J614s native Fender disable before OFF plus traced draw and native timeout NMI retained cycle';require(c.count(old)==1,'Frozen module description differs');outputs['asc-graph-init.c']=c.replace(old,b'Experimental J614s native descriptor correction plus Fender draw and retained native NMI OFF cycle',1)
 for n in ('preparation.json','graph-receipt.json'):
  meta=json.loads(outputs[n]);previous=meta.pop('native_fender_off_cycle_trial');previous.update(SELECTED);meta['native_descriptor_fender_cycle_trial']=previous;meta['cold_render_trial']['version']=21
  meta['native_descriptor_correction']=dict(proposal_sha256=PROPOSAL_SHA,changed_byte_count=19,changed_arena_offsets=j['changed_arena_offsets'],canonical_native_absent_slot27=True,unused_donor_PTE_retained=dict(physical='0x288d0c000',gpu_va='0xfffffc2000f0c000',writable=False,descriptor_references_leaf=False),descriptor_flags_are_independent_of_PTE_write_permission=True,mappings_changed=False,backing_changed=False,slot3_geometry_still_zero=True,hardware_actions=[],selected_next_hardware_candidate=False)
  if n=='graph-receipt.json':
   require(meta['arena_sha256']==ARENA_SHA,'Baseline graph metadata hash differs');meta['arena_sha256']=sha(new)
   hw=next(o for o in meta['objects'] if o['name']=='hardware');require(hw['arena_offset']==0x8000,'Hardware arena offset differs');hw['input_sha256']=sha(new[hw['arena_offset']:hw['arena_offset']+hw['input_bytes']]);require(hw['input_sha256']==j['proposed_hardware_input_sha256'],'Hardware object hash differs')
   require(sha(json.dumps(meta['mmio_leaves'],sort_keys=True).encode())==j['unchanged_mmio_leaves_sha256'],'MMIO leaf bindings differ')
   for r in j['rows']:
    matches=[d for d in meta['mmio_descriptors'] if d['slot']==r['slot']]
    require(len(matches)<=1,'Duplicate MMIO descriptor metadata')
    if matches:d=matches[0]
    else:d=dict(slot=r['slot'],physical='0x0',gpu_va='0x0',size='0x0',readonly=True,mapped_pages=0,effective_writable_pages=[]);meta['mmio_descriptors'].append(d)
    d.update(serialized_native_flags=2,serialized_stride=hex(r['after']['stride']),serialized_relative=hex(r['after']['relative']),serialized_trailing=r['after']['trailing'],readonly_is_mapping_policy=True)
    if r['slot']==27:d.update(physical='0x0',gpu_va='0x0',size='0x0',mapped_pages=0,effective_writable_pages=[],canonical_native_absent=True,role_qualification='Actual qualified native v3 producer emits zero geometry and flags2; unused donor leaf remains retained')
    if r['slot']==3:d['role_qualification']='Native flags2 with existing zero geometry; native MCC mappings still absent'
  else:meta['qualification']='Offline native descriptor projection: exactly19 arena bytes, compiled graph upload and metadata agree; draw/backing/mappings/Fender/NMI/strictOFF remain inherited v20. Unselected pending v20 hardware outcome.'
  outputs[n]=(json.dumps(meta,indent=2)+'\n').encode()
 return outputs
def prepare(source,destination):
 source=source.resolve();destination=destination.resolve();require(not destination.exists() and source!=destination and source not in destination.parents,'Distinct absent destination required')
 receipt=source/'native-fender-off-cycle-owner-source-receipt.json';require(sha(receipt.read_bytes())==BASE_SHA,'Frozen v20 source receipt differs');old=json.loads(receipt.read_bytes());original={}
 for r in old['output_source_pins']:
  b=(source/r['name']).read_bytes();require(sha(b)==r['sha256'],'Frozen source differs: '+r['name']);original[r['name']]=b
 outputs=project_source(original);j,q=proposal();profile=dict(old['profile']);profile.update(SELECTED);profile.update(family='gfx_native_descriptor_fender_cycle_scope',compile_macro=NEW)
 destination.mkdir(parents=True)
 for n,b in outputs.items():(destination/n).write_bytes(b)
 for n,b in original.items():require((source/n).read_bytes()==b,'Frozen source mutated')
 pins=[pin(PROPOSAL),*j['inputs'],*q['inputs']];unique={p['path']:p for p in pins}
 result=dict(schema='m4rch.native-descriptor-fender-cycle-owner-source.v1',source=str(source),source_path=str(source),destination=str(destination),baseline_source_receipt=pin(receipt),source_preparer=pin(Path(__file__)),native_input_pins=list(unique.values()),descriptor_projection=copy.deepcopy(j),input_source_pins=old['output_source_pins'],reused_helper_pins=old['reused_helper_pins'],output_source_pins=[dict(name=n,sha256=sha(b)) for n,b in outputs.items()],changed_files=sorted(n for n in outputs if outputs[n]!=original[n]),added_files=[],removed_files=[],profile=profile,hardware_actions=[],build_actions=[],selected_next_hardware_candidate=False,qualification='Exactly19 descriptor bytes reach graph-before and compiled graph_bytes uploaded by inherited init_joined_graph; unchanged unused donor PTE, mappings,174 pages,backing/shader/work and Fender/NMI/strictOFF. Actual binary/compiled-array qualification required before root finalization; unselected.')
 with (destination/RECEIPT).open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();j=prepare(a.source,a.destination);print(json.dumps(dict(receipt=str(a.destination/RECEIPT),sha256=sha((a.destination/RECEIPT).read_bytes()),changed_files=j['changed_files'],selected_next_hardware_candidate=False)))
