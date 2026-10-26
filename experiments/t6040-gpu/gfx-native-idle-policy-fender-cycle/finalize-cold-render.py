#!/usr/bin/env python3
"""Bind the unselected v22 owner to native policy source and frozen v21/v20 scopes."""
import argparse,copy,json,runpy,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE))
from cold_render_contract import CONTRACT,FAMILY_KEY,REFUSED_BOOTS,require,sha,module_build_note,validate_receipt,validate_descriptor_data
BASE=ROOT/'out/gfx-native-descriptor-fender-cycle/candidate'
BASE_PREP_SHA='f41ec01f92b7b8eee47ae15fa5a77e10b2b85bd89e0bad376905b212d507ce3c'
BASE_SOURCE_SHA='d9c3abf1deff7d0a72c4229877598ec35b6c3a8fed7344b6ffca99b189b9c5f0'
FROZEN=HERE.parent/'gfx-native-descriptor-fender-cycle'
ELF_READER=runpy.run_path(str(FROZEN/'finalize-cold-render.py'),run_name='frozen_v21_ELF_reader')['actual_ELF_graph_bytes']
def pin(p):
 p=Path(p);p=p.resolve() if p.is_absolute() else (ROOT/p).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=sha(raw))
def checked(rows):
 require(bool(rows),'Qualification input pins missing')
 for r in rows:
  actual=pin(r['path']);require(actual['sha256']==r['sha256'] and ('bytes' not in r or actual['bytes']==r['bytes']),'Composed input differs: '+r['path'])
def actual_ELF_graph_bytes(raw):return ELF_READER(raw)
def frozen_qualification(path,digest,count):
 q=json.loads(path.read_bytes());require(sha(path.read_bytes())==digest and q['passed'] and q['case_count']==count,'Frozen qualification differs')
 require(q.get('hardware_access',False) is False and q.get('hardware_actions',[])==[],'Frozen offline scope differs')
 checked(q.get('input_pins',q.get('inputs')));return q
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('--idle-policy-qualification',type=Path,required=True);p.add_argument('--host-qualification',type=Path,required=True);a=p.parse_args()
 c=a.candidate.resolve();g=c/'asc-graph-init';rp=c/'asc-root-envelope/build-receipt.json';op=c/'cold-render-preparation.json'
 require(not rp.exists() and not op.exists(),'Distinct finalization output must be new')
 bp=BASE/'cold-render-preparation.json';require(sha(bp.read_bytes())==BASE_PREP_SHA,'Frozen v21 preparation differs');old=json.loads(bp.read_bytes());checked(old['inputs'])
 br=BASE/'asc-root-envelope/build-receipt.json';require(sha(br.read_bytes())==old['candidate_receipt_sha256'],'Frozen v21 build receipt differs');receipt=json.loads(br.read_bytes())
 for n,h in receipt['artifact_sha256'].items():require(sha((BASE/n).read_bytes())==h,'Frozen artifact differs: '+n)
 for n,h in receipt['graph_source_sha256'].items():require(sha((BASE/'asc-graph-init'/n).read_bytes())==h,'Frozen source differs: '+n)
 sp=g/'native-idle-policy-fender-cycle-owner-source-receipt.json';source=json.loads(sp.read_bytes());profile=source['profile']
 require(profile['version']==22 and profile['family']==FAMILY_KEY and profile['compile_macro']==CONTRACT['compile_macro'] and source['selected_next_hardware_candidate'] is False,'Distinct unselected owner profile differs')
 bspec=source['baseline_source_receipt'];require(bspec['sha256']==BASE_SOURCE_SHA and sha(Path(bspec['path']).read_bytes())==BASE_SOURCE_SHA,'Frozen owner base differs');bs=json.loads(Path(bspec['path']).read_bytes());original={}
 for r in bs['output_source_pins']:
  require('/' not in r['name'],'Frozen source name differs');b=(Path(bspec['path']).parent/r['name']).read_bytes();require(sha(b)==r['sha256'],'Frozen projection input differs: '+r['name']);original[r['name']]=b
 for r in source['output_source_pins']:require('/' not in r['name'] and sha((g/r['name']).read_bytes())==r['sha256'],'Actual owner source differs: '+r['name'])
 preparer=Path(source['source_preparer']['path']);require(preparer.resolve()==(HERE/'prepare-idle-policy-owner.py').resolve() and sha(preparer.read_bytes())==source['source_preparer']['sha256'],'Actual source preparer differs');checked(source['native_abi_pins'])
 for r in source['native_abi_pins']:
  abi=json.loads(Path(r['path']).read_bytes());checked(abi.get('inputs',abi.get('input_pins')))
 projected=runpy.run_path(str(preparer),run_name='idle_policy_owner_projection')['project_source'](original)
 require(set(projected)=={r['name'] for r in source['output_source_pins']},'Unexpected source extent')
 for n,b in projected.items():require((g/n).read_bytes()==b,'Unqualified owner projection: '+n)
 validate_descriptor_data(g)
 after=(g/'graph-before.bin').read_bytes();require(after==original['graph-before.bin'],'Native nineteen-byte arena correction changed in v22')
 require((g/'backing.bin').read_bytes()==original['backing.bin'],'Native four-byte work recipe changed')
 for n in ['graph-map.h','render-data.h','render-backing-map.h','job-data.h','joined-context-init.h','command-pool-map.h']:
  require((g/n).read_bytes()==original[n],'Mapping/backing/shader/work upload changed: '+n)
 cq=json.loads(a.idle_policy_qualification.read_bytes());hq=json.loads(a.host_qualification.read_bytes())
 require(cq['passed'] is True and cq['hardware_access'] is False and cq['hardware_actions']==[] and cq['kernel_build'] is False and cq['source_receipt_sha256']==sha(sp.read_bytes()) and cq['case_count']>0,'Actual native policy C qualification differs');checked(cq.get('input_pins',cq.get('inputs')))
 require(hq['passed'] is True and hq['hardware_access'] is False and hq['hardware_actions']==[] and hq['source_receipt_sha256']==sha(sp.read_bytes()) and hq['idle_policy_qualification_sha256']==sha(a.idle_policy_qualification.read_bytes()) and hq['actual_main_flow_count']>=1 and hq['early_refusal_flow_count']==2,'Focused host join differs');checked(hq['inputs'])
 dqpath=ROOT/'out/gfx-native-descriptor-fender-cycle/descriptor-qualification-v1.json';dq=frozen_qualification(dqpath,old['native_descriptor_qualification_sha256'],19)
 # Host v2 differs from v1 only by qualified finalizer source closure; its
 # exact pin is obtained from the frozen preparation rather than guessed.
 hqpath=next(Path(r['path']) for r in old['inputs'] if r['path'].endswith('/gfx-native-descriptor-fender-cycle/host-qualification-v2.json'))
 hqpin=next(r for r in old['inputs'] if r['path']==str(hqpath));frozen_hq=frozen_qualification(hqpath,hqpin['sha256'],9)
 buildp=ROOT/'out/gfx-native-idle-policy-fender-cycle/owner-build-command.json';logp=buildp.parent/'owner-build.log';build=json.loads(buildp.read_bytes());log=logp.read_bytes()
 require(build['returncode']==0 and build['kernel_rebuilt'] is False and build['hardware_actions']==[] and build['source_receipt_sha256']==sha(sp.read_bytes()) and build['candidate']==str(c),'Actual owner build differs')
 require(sha(log)==build['selected_build_log_sha256'] and not any(x in log.lower() for x in [b'warning:',b'error:']),'Clean module build log differs');checked(build['kernel_build_inputs_unchanged'])
 command=(g/'.asc-graph-init.o.cmd').read_text().splitlines()[0];require(command.count('-D'+CONTRACT['compile_macro'])==1 and '-DGFX_NATIVE_DESCRIPTOR_FENDER_CYCLE_TRIAL' not in command,'Compiled macro differs')
 owner=g/'asc-graph-init.ko';note=module_build_note(owner.read_bytes());require(actual_ELF_graph_bytes(owner.read_bytes())==after,'Actual compiled owner graph_bytes differs from native corrected arena')
 modinfo=subprocess.check_output(['readelf','-p','.modinfo',str(owner)],text=True);require('vermagic='+receipt['kernel_release']+' SMP preempt mod_unload aarch64' in modinfo,'Owner vermagic differs')
 for n,h in receipt['artifact_sha256'].items():
  if n!='asc-graph-init/asc-graph-init.ko':require(sha((c/n).read_bytes())==h,'Inherited artifact differs: '+n)
 receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko']=sha(owner.read_bytes());receipt['graph_source_sha256']={r['name']:r['sha256'] for r in source['output_source_pins'] if r['name'].endswith(('.c','.h')) or r['name']=='Makefile'};receipt['graph_fixture_sha256']=sha(after);receipt['graph_receipt_sha256']=sha((g/'graph-receipt.json').read_bytes())
 trial=receipt['graph_recovery_trial']
 for k in list(trial):
  if k.endswith('_scope'):del trial[k]
 trial[FAMILY_KEY]=copy.deepcopy(CONTRACT);receipt['hardware_trial_performed']=False;validate_receipt(receipt)
 names=['cold_render_contract.py','frozen_source.py','run-cold-render.py','preflight-fresh.py','analyze_cold_render.py','readback.py','test-host.py','finalize-cold-render.py','prepare-idle-policy-owner.py','gfx-native-idle-policy.h','test-idle-policy.py','README.md']
 inputs=[Path(r['path']) for r in old['inputs']]+[bp,br,sp,a.idle_policy_qualification.resolve(),a.host_qualification.resolve(),buildp,logp,dqpath,hqpath,*[HERE/n for n in names]]
 for q in [cq,hq]:inputs.extend(Path(r['path']) for r in q.get('input_pins',q.get('inputs')))
 inputs.extend(Path(r['path']) for r in source['native_abi_pins'])
 composition=copy.deepcopy(old['qualification_composition']);composition.update(frozen_v21_descriptor_data_cases=19,frozen_v21_host_cases=9,frozen_v21_actual_main_flows=1,new_idle_policy_C_cases=cq['case_count'],new_host_cases=hq['case_count'],new_actual_main_flows=hq['actual_main_flow_count'],new_early_refusal_flows=2,unchanged_cases_repeated=False)
 prep=copy.deepcopy(old);prep.update(schema='m4rch.gfx-native-idle-policy-fender-cycle-preparation.v1',candidate=str(c),baseline_candidate=str(BASE),owner_sha256=sha(owner.read_bytes()),owner_GNU_note_hex=note.hex(),hardware_actions=[],module_loaded=False,selected_next_hardware_candidate=False,selection='unselected-awaiting-root-review',hardware_preconditions_pending=True,automatic_pipeline=copy.deepcopy(CONTRACT),refused_boots=list(REFUSED_BOOTS),inputs=[pin(p) for p in dict.fromkeys(inputs)],qualification_composition=composition,native_idle_policy_qualification_sha256=sha(a.idle_policy_qualification.read_bytes()),native_descriptor_qualification_sha256=sha(dqpath.read_bytes()),graph_changed_byte_count=19,canonical_native_absent_slot27=True,unused_donor_slot27_PTE_retained=True,qualification='Unselected v22 combines frozen nineteen descriptor bytes with one native opcode0a/bool1 policy publication after immutable capture and before sole202. Clean command/off-word timeouts continue teardown; unsafe/ambiguous state refuses retained. Policy processing, firmware GPU-off,202/NMI/CPUstop,Fender and strictOFF/accounting remain separately reported. Frozen v21/v20 scopes composed; no GPU execution or retirement proved offline.')
 with rp.open('x') as f:f.write(json.dumps(receipt,indent=2)+'\n')
 prep['candidate_receipt_sha256']=sha(rp.read_bytes())
 with op.open('x') as f:f.write(json.dumps(prep,indent=2)+'\n')
 print(json.dumps(dict(candidate=str(c),owner_sha256=prep['owner_sha256'],receipt_sha256=prep['candidate_receipt_sha256'],preparation_sha256=sha(op.read_bytes()),selected_next_hardware_candidate=False)))
if __name__=='__main__':main()
