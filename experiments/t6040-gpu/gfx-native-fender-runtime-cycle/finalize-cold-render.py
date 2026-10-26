#!/usr/bin/env python3
"""Bind a v19 runtime-active owner to unchanged Fender/strict-OFF qualifications."""
import argparse,copy,json,runpy,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE))
from cold_render_contract import CONTRACT,FAMILY_KEY,REFUSED_BOOTS,RETAINED_SAMPLERS,require,sha,module_build_note,validate_receipt
from analyze_cold_render import qualify_pipeline,qualify_publication,qualify_postdraw_cycle,rows
BASE=ROOT/'out/gfx-native-fender-draw-cycle/candidate'
BASE_PREP_SHA='c85cdc4d9f2f42f9452df3e23f6a638bfdf5806ca6408210db2f6e7e9efc6ee6'
BASE_SOURCE_SHA='45d2017114725882e7bec1bbbd60f2211888c3f5f5d7f3159174cdf0da2ce6a1'
RUNTIME_Q_SHA='e12421602d0b41e42120e5235527fd1686c1ccf4047d6167037e3f0595a2d2a8'
RUNTIME_HELPER_SHA='4e25f120981774cef205020ea8d59683c42d549477ce174af427b7b3c61d8497'
def pin(p):
 p=Path(p).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=sha(raw))
def checked_rows(records):
 require(bool(records),'Qualification input pins missing')
 for r in records:require(sha(Path(r['path']).read_bytes())==r['sha256'],'Composed input differs: '+r['path'])
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('--runtime-qualification',type=Path,required=True);p.add_argument('--host-qualification',type=Path,required=True);a=p.parse_args()
 c=a.candidate.resolve();g=c/'asc-graph-init';rp=c/'asc-root-envelope/build-receipt.json';op=c/'cold-render-preparation.json'
 require(not rp.exists() and not op.exists(),'Distinct finalization output must be new')
 bp=BASE/'cold-render-preparation.json';require(sha(bp.read_bytes())==BASE_PREP_SHA,'Frozen v18 preparation differs');old=json.loads(bp.read_text());checked_rows(old['inputs'])
 br=BASE/'asc-root-envelope/build-receipt.json';require(sha(br.read_bytes())==old['candidate_receipt_sha256'],'Frozen v18 receipt differs');receipt=json.loads(br.read_text())
 for n,h in receipt['artifact_sha256'].items():require(sha((BASE/n).read_bytes())==h,'Frozen artifact differs: '+n)
 for n,h in receipt['graph_source_sha256'].items():require(sha((BASE/'asc-graph-init'/n).read_bytes())==h,'Frozen source differs: '+n)
 sp=g/'native-fender-runtime-cycle-owner-source-receipt.json';source=json.loads(sp.read_text());profile=source['profile']
 require(profile['version']==19 and profile['family']==FAMILY_KEY and profile['compile_macro']==CONTRACT['compile_macro'],'Distinct owner profile differs')
 for k,v in dict(native_Fender_enable_calls=1,native_Fender_enable_offset='0xd06030',native_Fender_enable_policy='fresh-old-and-not-six',after_fresh_control33_before_first_draw=True,explicit_transfer_hypothesis=True,native_addKicks_replayed=False,direct_SGX_kick_writes=False,scheduler_ACK_coverage_writes=False,teardown_register_cleanup=False,management_rejoin_replay=False).items():require(profile.get(k)==v,'Retained Fender policy differs: '+k)
 bspec=source['baseline_source_receipt'];require(bspec['sha256']==BASE_SOURCE_SHA and sha(Path(bspec['path']).read_bytes())==BASE_SOURCE_SHA,'Frozen owner base differs')
 base_source=json.loads(Path(bspec['path']).read_text());original={}
 for r in base_source['output_source_pins']:
  path=Path(bspec['path']).parent/r['name'];require(sha(path.read_bytes())==r['sha256'],'Frozen projection input differs '+r['name']);original[r['name']]=path.read_bytes()
 for r in source['output_source_pins']:require(sha((g/r['name']).read_bytes())==r['sha256'],'Compiled source differs: '+r['name'])
 preparer=Path(source['source_preparer']['path']);require(preparer.resolve()==(HERE/'prepare-runtime-owner.py').resolve() and sha(preparer.read_bytes())==source['source_preparer']['sha256'],'Actual source preparer differs')
 # Pure preparer projects exact v18 bytes through only the selected read-only
 # physical/application hooks. Its source is separately pinned in this receipt.
 project=runpy.run_path(str(preparer),run_name='qualification_source_projection')['project_source'];projected=project(original)
 inherited_names=[n for n in original if n.endswith(('.c','.h')) or n=='Makefile']
 for n in inherited_names:require((g/n).read_bytes()==projected[n],'Unqualified inherited source change: '+n)
 require(sha((g/'gfx-native-runtime-state.h').read_bytes())==RUNTIME_HELPER_SHA and (g/'gfx-native-runtime-state.h').read_bytes()==projected['gfx-native-runtime-state.h'],'Selected runtime helper differs')
 require((g/'gfx-native-fender-enable.h').read_bytes()==original['gfx-native-fender-enable.h'].replace(b'GFX_NATIVE_FENDER_DRAW_CYCLE_TRIAL',b'GFX_NATIVE_FENDER_RUNTIME_CYCLE_TRIAL'),'Fender operation changed beyond macro')
 require((g/'gfx-postdraw-native-nmi-cycle.h').read_bytes()==projected['gfx-postdraw-native-nmi-cycle.h'],'Native cycle caller differs')
 rq=json.loads(a.runtime_qualification.read_text());hq=json.loads(a.host_qualification.read_text())
 require(sha(a.runtime_qualification.read_bytes())==RUNTIME_Q_SHA and rq.get('passed') is True and rq.get('hardware_actions')==[] and rq.get('case_count')==829 and rq.get('compiler_returncode')==0 and rq.get('helper_sha256')==RUNTIME_HELPER_SHA,'Actual changed C qualification differs');checked_rows(rq['input_pins'])
 require(hq.get('passed') is True and hq.get('hardware_access') is False and hq.get('case_count',0)>0,'Actual changed host qualification missing');checked_rows(hq['inputs'])
 require(hq['source_receipt_sha256']==sha(sp.read_bytes()) and hq['runtime_qualification_sha256']==RUNTIME_Q_SHA and hq['actual_C_runtime_parser_qualified'] is True and hq['actual_main_flow_count']==1 and hq['early_refusal_flow_count']==4,'Changed host join differs')
 checked_rows([*hq['actual_C_runtime_success_fixtures'],hq['composed_pipeline_fixture'],hq['composed_cycle_fixture']]);fixture=Path(hq['composed_pipeline_fixture']['path']).read_text();qualify_pipeline(fixture);qualify_publication(fixture)
 cycle=Path(hq['composed_cycle_fixture']['path']).read_text();token=rows(cycle,'gfx-postdraw-native-cycle')[0]['capture_token'];first=next(i for i,line in enumerate(cycle.splitlines(True)) if 'm4rch gfx-postdraw-native-cycle:' in line);qualify_postdraw_cycle(''.join(cycle.splitlines(True)[first:]),token)
 composition=dict(frozen_v17_C_cases=64,frozen_v17_preasc_C_cases=39,frozen_v17_host_cases=41,frozen_v17_actual_main_flows=10,frozen_v18_Fender_C_cases=45,frozen_v18_host_cases=21,frozen_v18_actual_main_flows=1,new_C_runtime_cases=829,unchanged_tests_repeated=False,ordered_fixture_is_composition=True,actual_caller_order_not_proved_by_fixture=True)
 require(hq['composition']==composition,'Frozen qualification composition differs')
 buildp=ROOT/'out/gfx-native-fender-runtime-cycle/owner-build-command.json';logp=buildp.parent/'owner-build.log';build=json.loads(buildp.read_text());log=logp.read_bytes()
 require(build.get('returncode')==0 and build.get('kernel_rebuilt') is False and build.get('hardware_actions')==[] and build.get('source_receipt_sha256')==sha(sp.read_bytes()) and build.get('candidate')==str(c),'Actual owner build differs')
 require(sha(log)==build['selected_build_log_sha256'] and not any(x in log.lower() for x in (b'warning:',b'error:')),'Clean owner build log differs');checked_rows(build['kernel_build_inputs_unchanged'])
 command=(g/'.asc-graph-init.o.cmd').read_text().splitlines()[0]
 require(command.count('-DGFX_NATIVE_FENDER_RUNTIME_CYCLE_TRIAL')==1 and '-DGFX_NATIVE_FENDER_DRAW_CYCLE_TRIAL' not in command,'Compiled macro differs')
 owner=g/'asc-graph-init.ko';note=module_build_note(owner.read_bytes());modinfo=subprocess.check_output(['readelf','-p','.modinfo',str(owner)],text=True)
 require('vermagic='+receipt['kernel_release']+' SMP preempt mod_unload aarch64' in modinfo,'Owner vermagic differs')
 for n,h in receipt['artifact_sha256'].items():
  if n!='asc-graph-init/asc-graph-init.ko':require(sha((c/n).read_bytes())==h,'Inherited non-owner artifact differs: '+n)
 receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko']=sha(owner.read_bytes())
 receipt['graph_source_sha256']={r['name']:r['sha256'] for r in source['output_source_pins'] if r['name'].endswith(('.c','.h')) or r['name']=='Makefile'}
 receipt['graph_fixture_sha256']=sha((g/'graph-before.bin').read_bytes());require(receipt['graph_fixture_sha256']==json.loads(br.read_text())['graph_fixture_sha256'],'Draw graph changed')
 receipt['graph_receipt_sha256']=sha((g/'graph-receipt.json').read_bytes());require((g/'backing.bin').read_bytes()==(BASE/'asc-graph-init/backing.bin').read_bytes(),'Native four-byte draw recipe changed')
 trial=receipt['graph_recovery_trial']
 for k in list(trial):
  if k.endswith('_scope'):del trial[k]
 trial[FAMILY_KEY]=copy.deepcopy(CONTRACT);receipt.update(hardware_trial_performed=False);validate_receipt(receipt)
 inputs=[Path(r['path']) for r in old['inputs']]+[bp,br,sp,a.runtime_qualification.resolve(),a.host_qualification.resolve(),buildp,logp,preparer,*[HERE/n for n in ('cold_render_contract.py','frozen_source.py','run-cold-render.py','preflight-fresh.py','analyze_cold_render.py','readback.py','test-host.py','finalize-cold-render.py')]]
 for q in (rq,hq):inputs.extend(Path(r['path']) for r in q.get('input_pins',q.get('inputs',[])))
 prep=copy.deepcopy(old);prep.update(schema='m4rch.gfx-native-fender-runtime-cycle-preparation.v1',candidate=str(c),baseline_candidate=str(BASE),owner_sha256=sha(owner.read_bytes()),owner_GNU_note_hex=note.hex(),hardware_actions=[],module_loaded=False,selected_next_hardware_candidate=True,hardware_preconditions_pending=True,automatic_pipeline=copy.deepcopy(CONTRACT),refused_boots=list(REFUSED_BOOTS),inputs=[pin(path) for path in dict.fromkeys(inputs)],qualification_composition=dict(new_C_runtime_cases=829,new_host_cases=hq['case_count'],new_actual_main_flows=1,new_early_refusal_flows=4,frozen_v18_Fender_C_cases=45,frozen_v18_host_cases=21,frozen_v18_actual_main_flows=1,frozen_v17_C_cases=64,frozen_v17_preasc_C_cases=39,frozen_v17_host_cases=41,frozen_v17_actual_main_flows=10,unchanged_cases_repeated=False),actual_production_caller_order_bound=True,native_runtime_qualification_sha256=RUNTIME_Q_SHA,native_runtime_read_only=True,strict_physical_OFF_unchanged=True,strict_management_rejoin_ON_unchanged=True,qualification='After accepted control33 and exact native Fender enable, one fresh owner uses a read-only physical runtime predicate: TARGETf, no RESET/DISABLE/BUSY/PSRESET, ACTUAL0/4/f, AUTO mandatory for gated0/4. Earlier cold startup/Fender and postcycle cold ON remain strictFF. Application operands are unchanged with exact refusal diagnostics. Same v18 one draw, 15s capture, immutable capture before once-only native202/NMI cycle, strict physicalOFF/accounting and management-only rejoin. Frozen Fender45/host21/1 and C64/preASC39/host41/10 are composed; changed actual helper829 and focused host cases/one main flow, exact source projection and actual module build are bound. No GPU execution, physicalOFF or DMA retirement proved offline.')
 with rp.open('x') as out:out.write(json.dumps(receipt,indent=2)+'\n')
 prep['candidate_receipt_sha256']=sha(rp.read_bytes())
 with op.open('x') as out:out.write(json.dumps(prep,indent=2)+'\n')
 print(json.dumps(dict(candidate=str(c),owner_sha256=prep['owner_sha256'],receipt_sha256=prep['candidate_receipt_sha256'],preparation_sha256=sha(op.read_bytes()),owner_GNU_note_hex=note.hex())))
if __name__=='__main__':main()
