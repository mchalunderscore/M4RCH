#!/usr/bin/env python3
"""Bind unselected v21 actual compiled descriptor data to frozen v20 behavior."""
import argparse,copy,json,runpy,struct,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE))
from cold_render_contract import CONTRACT,FAMILY_KEY,REFUSED_BOOTS,require,sha,module_build_note,validate_receipt,validate_descriptor_data
BASE=ROOT/'out/gfx-native-fender-off-cycle/candidate'
BASE_PREP_SHA='933a9a7b731e341375a433f55e1a540b88f51fbe5c98f752fcff3f93c14c231b'
BASE_SOURCE_SHA='e1f9c5ca28373ee4508a46f112ac4cc383fb7c245baf4fea14c84913bb53d982'
V20_C_SHA='473c469f18401dc820a756527b1297c36bf7a4ffb0d43f63ae9ed413123e8705'
V20_HOST_SHA='2c752cb488921c5a94411f00255749543f4a53e762363b008ee1fd25ad99fa3a'
def pin(p):
 p=Path(p).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=sha(raw))
def checked(rows):
 require(bool(rows),'Qualification input pins missing')
 for r in rows:require(sha(Path(r['path']).read_bytes())==r['sha256'],'Composed input differs: '+r['path'])
def actual_ELF_graph_bytes(raw):
 """Read the actual graph_bytes object from a little-endian ELF64 symbol table."""
 require(raw[:7]==b'\x7fELF\x02\x01\x01','Actual owner array requires little-endian ELF64')
 header=struct.unpack_from('<HHIQQQIHHHHHH',raw,16);sections=[struct.unpack_from('<IIQQQQIIQQ',raw,header[5]+i*header[10]) for i in range(header[11])];found=[]
 for table in sections:
  if table[1]!=2:continue
  names_section=sections[table[6]];names=raw[names_section[4]:names_section[4]+names_section[5]];require(table[9]==24,'ELF symbol width differs')
  for at in range(table[4],table[4]+table[5],24):
   name,info,other,index,value,size=struct.unpack_from('<IBBHQQ',raw,at)
   if names[name:].split(b'\0',1)[0]!=b'graph_bytes':continue
   require(info&15==1 and index<len(sections) and size==1130496,'Compiled graph object extent differs');section=sections[index];start=section[4]+value-section[3];require(start>=section[4] and start+size<=section[4]+section[5],'Compiled graph object outside section');found.append(raw[start:start+size])
 require(len(found)==1,'Exactly one actual ELF graph_bytes symbol required');return found[0]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('--descriptor-qualification',type=Path,required=True);p.add_argument('--host-qualification',type=Path,required=True);a=p.parse_args()
 c=a.candidate.resolve();g=c/'asc-graph-init';rp=c/'asc-root-envelope/build-receipt.json';op=c/'cold-render-preparation.json';require(not rp.exists() and not op.exists(),'Distinct finalization output must be new')
 bp=BASE/'cold-render-preparation.json';require(sha(bp.read_bytes())==BASE_PREP_SHA,'Frozen v20 preparation differs');old=json.loads(bp.read_bytes());checked(old['inputs'])
 br=BASE/'asc-root-envelope/build-receipt.json';require(sha(br.read_bytes())==old['candidate_receipt_sha256'],'Frozen v20 build receipt differs');receipt=json.loads(br.read_bytes())
 for n,h in receipt['artifact_sha256'].items():require(sha((BASE/n).read_bytes())==h,'Frozen artifact differs: '+n)
 for n,h in receipt['graph_source_sha256'].items():require(sha((BASE/'asc-graph-init'/n).read_bytes())==h,'Frozen source differs: '+n)
 sp=g/'native-descriptor-fender-cycle-owner-source-receipt.json';source=json.loads(sp.read_bytes());profile=source['profile'];require(profile['version']==21 and profile['family']==FAMILY_KEY and profile['compile_macro']==CONTRACT['compile_macro'] and source['selected_next_hardware_candidate'] is False,'Distinct unselected owner profile differs')
 bspec=source['baseline_source_receipt'];require(bspec['sha256']==BASE_SOURCE_SHA and sha(Path(bspec['path']).read_bytes())==BASE_SOURCE_SHA,'Frozen owner base differs');bs=json.loads(Path(bspec['path']).read_bytes());original={}
 for r in bs['output_source_pins']:
  b=(Path(bspec['path']).parent/r['name']).read_bytes();require(sha(b)==r['sha256'],'Frozen projection input differs: '+r['name']);original[r['name']]=b
 for r in source['output_source_pins']:require(sha((g/r['name']).read_bytes())==r['sha256'],'Actual owner source differs: '+r['name'])
 preparer=Path(source['source_preparer']['path']);require(preparer.resolve()==(HERE/'prepare-descriptor-owner.py').resolve() and sha(preparer.read_bytes())==source['source_preparer']['sha256'],'Actual source preparer differs');checked(source['native_input_pins'])
 projected=runpy.run_path(str(preparer),run_name='descriptor_owner_projection')['project_source'](original)
 require(set(projected)=={r['name'] for r in source['output_source_pins']},'Unexpected source extent')
 for n,b in projected.items():require((g/n).read_bytes()==b,'Unqualified owner projection: '+n)
 validate_descriptor_data(g);before=original['graph-before.bin'];after=(g/'graph-before.bin').read_bytes();delta=[dict(offset=hex(i),before=x,after=y) for i,(x,y) in enumerate(zip(before,after)) if x!=y]
 require(len(before)==len(after) and len(delta)==19 and [d['offset'] for d in delta]==source['descriptor_projection']['changed_arena_offsets'],'Actual graph change differs from nineteen bytes')
 require((g/'backing.bin').read_bytes()==(BASE/'asc-graph-init/backing.bin').read_bytes(),'Native four-byte work recipe changed')
 for n in ['graph-map.h','render-data.h','render-backing-map.h','job-data.h','joined-context-init.h','command-pool-map.h']:require((g/n).read_bytes()==original[n],'Mapping/backing/shader/work upload changed: '+n)
 for n in ['gfx-native-fender-enable.h','gfx-native-runtime-state.h','gfx-native-fender-disable.h','gfx-postdraw-native-nmi-cycle.h','gfx-cold-render.h']:
  require((g/n).read_bytes()==original[n].replace(b'GFX_NATIVE_FENDER_OFF_CYCLE_TRIAL',b'GFX_NATIVE_DESCRIPTOR_FENDER_CYCLE_TRIAL'),'Operation changed beyond macro: '+n)
 dq=json.loads(a.descriptor_qualification.read_bytes());hq=json.loads(a.host_qualification.read_bytes())
 require(dq['passed'] is True and dq['hardware_access'] is False and dq['hardware_actions']==[] and dq['kernel_build'] is False and dq['changed_byte_count']==19 and dq['source_receipt_sha256']==sha(sp.read_bytes()) and dq['changed_bytes']==delta,'Actual descriptor data qualification differs');checked(dq['inputs']);checked([dq['actual_compiled_array']]);require(Path(dq['actual_compiled_array']['path']).read_bytes()==after,'Actual compiled C data differs')
 require(hq['passed'] is True and hq['hardware_access'] is False and hq['source_receipt_sha256']==sha(sp.read_bytes()) and hq['descriptor_qualification_sha256']==sha(a.descriptor_qualification.read_bytes()) and hq['actual_main_flow_count']==1 and hq['early_refusal_flow_count']==2,'Focused changed host join differs');checked(hq['inputs'])
 frozen=[]
 for path,digest,count in [(ROOT/'out/gfx-native-fender-off-cycle/fender-off-qualification-v1.json',V20_C_SHA,65),(ROOT/'out/gfx-native-fender-off-cycle/host-qualification-v1.json',V20_HOST_SHA,27)]:
  q=json.loads(path.read_bytes());require(sha(path.read_bytes())==digest and q['passed'] and q['case_count']==count,'Frozen v20 qualification differs');checked(q.get('input_pins',q.get('inputs')));frozen.append(path)
 buildp=ROOT/'out/gfx-native-descriptor-fender-cycle/owner-build-command.json';logp=buildp.parent/'owner-build.log';build=json.loads(buildp.read_bytes());log=logp.read_bytes()
 require(build['returncode']==0 and build['kernel_rebuilt'] is False and build['hardware_actions']==[] and build['source_receipt_sha256']==sha(sp.read_bytes()) and build['candidate']==str(c),'Actual owner build differs');require(sha(log)==build['selected_build_log_sha256'] and not any(x in log.lower() for x in [b'warning:',b'error:']),'Clean module build log differs');checked(build['kernel_build_inputs_unchanged'])
 command=(g/'.asc-graph-init.o.cmd').read_text().splitlines()[0];require(command.count('-DGFX_NATIVE_DESCRIPTOR_FENDER_CYCLE_TRIAL')==1 and '-DGFX_NATIVE_FENDER_OFF_CYCLE_TRIAL' not in command,'Compiled macro differs')
 owner=g/'asc-graph-init.ko';note=module_build_note(owner.read_bytes());require(actual_ELF_graph_bytes(owner.read_bytes())==after,'Actual compiled owner graph_bytes differs from corrected upload arena');modinfo=subprocess.check_output(['readelf','-p','.modinfo',str(owner)],text=True);require('vermagic='+receipt['kernel_release']+' SMP preempt mod_unload aarch64' in modinfo,'Owner vermagic differs')
 for n,h in receipt['artifact_sha256'].items():
  if n!='asc-graph-init/asc-graph-init.ko':require(sha((c/n).read_bytes())==h,'Inherited artifact differs: '+n)
 receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko']=sha(owner.read_bytes());receipt['graph_source_sha256']={r['name']:r['sha256'] for r in source['output_source_pins'] if r['name'].endswith(('.c','.h')) or r['name']=='Makefile'};receipt['graph_fixture_sha256']=sha(after);receipt['graph_receipt_sha256']=sha((g/'graph-receipt.json').read_bytes())
 trial=receipt['graph_recovery_trial']
 for k in list(trial):
  if k.endswith('_scope'):del trial[k]
 trial[FAMILY_KEY]=copy.deepcopy(CONTRACT);receipt['hardware_trial_performed']=False;validate_receipt(receipt)
 inputs=[Path(r['path']) for r in old['inputs']]+[bp,br,sp,a.descriptor_qualification.resolve(),a.host_qualification.resolve(),buildp,logp,*frozen,*[HERE/n for n in ['cold_render_contract.py','frozen_source.py','run-cold-render.py','preflight-fresh.py','analyze_cold_render.py','readback.py','test-host.py','finalize-cold-render.py','prepare-descriptor-owner.py','qualify-descriptors.py','README.md']]]
 for q in [dq,hq]:inputs.extend(Path(r['path']) for r in q['inputs'])
 inputs.extend(Path(r['path']) for r in source['native_input_pins'])
 composition=copy.deepcopy(old['qualification_composition']);composition.update(frozen_v20_Fender_OFF_C_cases=65,frozen_v20_host_cases=27,frozen_v20_actual_main_flows=1,new_descriptor_data_cases=dq['case_count'],new_host_cases=hq['case_count'],new_actual_main_flows=1,new_early_refusal_flows=2,unchanged_cases_repeated=False)
 prep=copy.deepcopy(old);prep.update(schema='m4rch.gfx-native-descriptor-fender-cycle-preparation.v1',candidate=str(c),baseline_candidate=str(BASE),owner_sha256=sha(owner.read_bytes()),owner_GNU_note_hex=note.hex(),hardware_actions=[],module_loaded=False,selected_next_hardware_candidate=False,selection='unselected-awaiting-v20-hardware-outcome',hardware_preconditions_pending=True,automatic_pipeline=copy.deepcopy(CONTRACT),refused_boots=list(REFUSED_BOOTS),inputs=[pin(p) for p in dict.fromkeys(inputs)],qualification_composition=composition,native_descriptor_qualification_sha256=sha(a.descriptor_qualification.read_bytes()),native_descriptor_proposal_sha256=source['native_input_pins'][0]['sha256'],graph_changed_byte_count=19,canonical_native_absent_slot27=True,unused_donor_slot27_PTE_retained=True,qualification='Unselected v21 actual owner uploads exactly19 native descriptor correction bytes; compiled C whole array agrees with arena and object/MMIO metadata. All mappings/PTEs/174 ownership/backing/shader/work/Fender/runtime/NMI/strictOFF/freshON are frozen v20. Frozen qualifications composed; new actual binary/Carray data checks and one intercepted host main flow bound. No pixels, physicalOFF or DMA retirement proved offline.')
 with rp.open('x') as f:f.write(json.dumps(receipt,indent=2)+'\n')
 prep['candidate_receipt_sha256']=sha(rp.read_bytes())
 with op.open('x') as f:f.write(json.dumps(prep,indent=2)+'\n')
 print(json.dumps(dict(candidate=str(c),owner_sha256=prep['owner_sha256'],receipt_sha256=prep['candidate_receipt_sha256'],preparation_sha256=sha(op.read_bytes()),selected_next_hardware_candidate=False)))
if __name__=='__main__':main()
