#!/usr/bin/env python3
"""Compose frozen v17 qualifications with changed Fender helper, host and owner."""
import argparse,copy,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE))
from cold_render_contract import CONTRACT,FAMILY_KEY,REFUSED_BOOTS,RETAINED_SAMPLERS,require,sha,module_build_note,validate_receipt
from analyze_cold_render import qualify_pipeline,qualify_publication
BASE=ROOT/'out/gfx-postdraw-native-nmi-cycle/candidate'
BASE_PREP_SHA='a29f0dd3390ea3ae95e7eb5fbf0abf2f54c27a22d9dadd215d6d405e00d8a57c'
BASE_SOURCE_SHA='d1f95e0cc08d13fbc46a457f715ccc0f439afd366da1eb78360716d99543b1a7'
def pin(p):
 p=Path(p).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=sha(raw))
def checked_rows(records):
 require(bool(records),'Qualification input pins missing')
 for r in records:require(sha(Path(r['path']).read_bytes())==r['sha256'],'Composed input differs: '+r['path'])
def once(text,old,new):
 require(text.count(old)==1,'Frozen caller insertion differs');return text.replace(old,new,1)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('--fender-qualification',type=Path,required=True);p.add_argument('--host-qualification',type=Path,required=True);a=p.parse_args()
 c=a.candidate.resolve();g=c/'asc-graph-init';rp=c/'asc-root-envelope/build-receipt.json';op=c/'cold-render-preparation.json'
 require(not rp.exists() and not op.exists(),'Distinct finalization output must be new')
 bp=BASE/'cold-render-preparation.json';require(sha(bp.read_bytes())==BASE_PREP_SHA,'Frozen v17 preparation differs');old=json.loads(bp.read_text());checked_rows(old['inputs'])
 br=BASE/'asc-root-envelope/build-receipt.json';require(sha(br.read_bytes())==old['candidate_receipt_sha256'],'Frozen v17 receipt differs');receipt=json.loads(br.read_text())
 for n,h in receipt['artifact_sha256'].items():require(sha((BASE/n).read_bytes())==h,'Frozen artifact differs: '+n)
 for n,h in receipt['graph_source_sha256'].items():require(sha((BASE/'asc-graph-init'/n).read_bytes())==h,'Frozen source differs: '+n)
 sp=g/'native-fender-draw-cycle-owner-source-receipt.json';source=json.loads(sp.read_text());profile=source['profile']
 require(profile['version']==18 and profile['family']==FAMILY_KEY and profile['compile_macro']==CONTRACT['compile_macro'],'Distinct owner profile differs')
 for k,v in dict(native_Fender_enable_calls=1,native_Fender_enable_offset='0xd06030',native_Fender_enable_policy='fresh-old-and-not-six',after_fresh_control33_before_first_draw=True,explicit_transfer_hypothesis=True,native_addKicks_replayed=False,direct_SGX_kick_writes=False,scheduler_ACK_coverage_writes=False,teardown_register_cleanup=False,management_rejoin_replay=False).items():require(profile.get(k)==v,'Fender owner policy differs: '+k)
 require(source['baseline_source_receipt']['sha256']==BASE_SOURCE_SHA and sha(Path(source['baseline_source_receipt']['path']).read_bytes())==BASE_SOURCE_SHA,'Frozen owner base differs')
 for r in source['output_source_pins']:require(sha((g/r['name']).read_bytes())==r['sha256'],'Compiled source differs: '+r['name'])
 # Qualify actual production caller and every inherited C/H/Makefile byte.
 for n,h in receipt['graph_source_sha256'].items():
  expected=(BASE/'asc-graph-init'/n).read_bytes().replace(b'GFX_POSTDRAW_NATIVE_NMI_CYCLE_TRIAL',b'GFX_NATIVE_FENDER_DRAW_CYCLE_TRIAL')
  if n=='asc-graph-init.c':
   text=expected.decode();text=once(text,'#include "gfx-gravity-preasc.h"','#include "gfx-gravity-preasc.h"\n#include "gfx-native-fender-enable.h"');text=once(text,'Experimental J614s Gravity preASC plus traced draw and native timeout NMI retained cycle','Experimental J614s native Fender enable transfer plus traced draw and native timeout NMI retained cycle');expected=text.encode()
  if n=='gfx-cold-render.h':
   text=expected.decode();text=once(text,'static int gfx_cold_run(void)','static int gfx_native_fender_enable(void);\n\nstatic int gfx_cold_run(void)');text=once(text,' ret=gfx_cold_fresh_control();if(ret)goto done;\n ret=gfx_cold_publish_draw();if(ret)goto done;',' ret=gfx_cold_fresh_control();if(ret)goto done;\n ret=gfx_native_fender_enable();\n if(ret) {ret=gfx_cold_refuse("native-fender-enable",ret);goto done;}\n ret=gfx_cold_publish_draw();if(ret)goto done;');expected=text.encode()
  require((g/n).read_bytes()==expected,'Unqualified inherited source change: '+n)
 fq=json.loads(a.fender_qualification.read_text());hq=json.loads(a.host_qualification.read_text())
 for q in (fq,hq):require(q.get('passed') is True and q.get('hardware_access') is False and q.get('case_count',0)>0,'Actual changed qualification missing');checked_rows(q.get('input_pins',q.get('inputs',[])))
 require(fq['case_count']==45 and fq['maximum_mmio_writes']==1 and fq['helper_sha256']==sha((g/'gfx-native-fender-enable.h').read_bytes()),'Fender actual C qualification differs')
 require(hq['source_receipt_sha256']==sha(sp.read_bytes()) and hq['fender_qualification_sha256']==sha(a.fender_qualification.read_bytes()) and hq['actual_C_Fender_parser_qualified'] is True and hq['actual_main_flow_count']==1 and hq['early_refusal_flow_count']==2,'Changed host join differs')
 checked_rows([hq['actual_C_fender_first_operation'],hq['composed_pipeline_fixture']]);fixture=Path(hq['composed_pipeline_fixture']['path']).read_text();qualify_pipeline(fixture);qualify_publication(fixture)
 require(hq['composition']==dict(frozen_v17_C_cases=64,frozen_v17_preasc_C_cases=39,frozen_v17_host_cases=41,frozen_v17_actual_main_flows=10,new_C_fender_cases=45,unchanged_tests_repeated=False,ordered_fixture_is_composition=True,actual_caller_order_not_proved_by_fixture=True),'Frozen qualification composition differs')
 buildp=ROOT/'out/gfx-native-fender-draw-cycle/owner-build-command.json';logp=buildp.parent/'owner-build.log';build=json.loads(buildp.read_text());log=logp.read_bytes()
 require(build.get('returncode')==0 and build.get('kernel_rebuilt') is False and build.get('hardware_actions')==[] and build.get('source_receipt_sha256')==sha(sp.read_bytes()) and build.get('candidate')==str(c),'Actual owner build differs')
 require(sha(log)==build['selected_build_log_sha256'] and not any(x in log.lower() for x in (b'warning:',b'error:')),'Clean owner build log differs');checked_rows(build['kernel_build_inputs_unchanged'])
 command=(g/'.asc-graph-init.o.cmd').read_text().splitlines()[0]
 require(command.count('-DGFX_NATIVE_FENDER_DRAW_CYCLE_TRIAL')==1 and '-DGFX_POSTDRAW_NATIVE_NMI_CYCLE_TRIAL' not in command,'Compiled macro differs')
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
 inputs=[Path(r['path']) for r in old['inputs']]+[bp,br,sp,a.fender_qualification.resolve(),a.host_qualification.resolve(),buildp,logp,Path(source['source_preparer']['path']),*[HERE/n for n in ('cold_render_contract.py','frozen_source.py','run-cold-render.py','preflight-fresh.py','analyze_cold_render.py','readback.py','test-host.py','finalize-cold-render.py')]]
 require(sha(Path(source['source_preparer']['path']).read_bytes())==source['source_preparer']['sha256'],'Actual source preparer differs')
 for q in (fq,hq):inputs.extend(Path(r['path']) for r in q.get('input_pins',q.get('inputs',[])))
 prep=copy.deepcopy(old);prep.update(schema='m4rch.gfx-native-fender-draw-cycle-preparation.v1',candidate=str(c),baseline_candidate=str(BASE),owner_sha256=sha(owner.read_bytes()),owner_GNU_note_hex=note.hex(),hardware_actions=[],module_loaded=False,selected_next_hardware_candidate=True,hardware_preconditions_pending=True,automatic_pipeline=copy.deepcopy(CONTRACT),refused_boots=list(REFUSED_BOOTS),inputs=[pin(path) for path in dict.fromkeys(inputs)],qualification_composition=dict(new_C_Fender_cases=45,new_host_cases=hq['case_count'],new_actual_main_flows=1,new_early_refusal_flows=2,frozen_v17_C_cases=64,frozen_v17_preasc_C_cases=39,frozen_v17_host_cases=41,frozen_v17_actual_main_flows=10,unchanged_cases_repeated=False),actual_production_caller_order_bound=True,native_Fender_qualification_sha256=sha(a.fender_qualification.read_bytes()),qualification='One fresh owner experimentally transfers native SGX+d06030 enable (fresh old&~6, preserving all other bits) between accepted control33 and first draw, with no direct addKicks stores, ACK writes or teardown clear. Same v17 startup, 15s capture, once-only postcapture native202/NMI strictOFF and management-only rejoin remain retained. Frozen C64/preASC39/host41/10 compose unchanged; changed actual helper45 and focused host cases plus one intercepted main flow. Source bytes, production caller hook and actual module build are bound; no hardware execution, physicalOFF or DMA retirement is proved offline.')
 with rp.open('x') as out:out.write(json.dumps(receipt,indent=2)+'\n')
 prep['candidate_receipt_sha256']=sha(rp.read_bytes())
 with op.open('x') as out:out.write(json.dumps(prep,indent=2)+'\n')
 print(json.dumps(dict(candidate=str(c),owner_sha256=prep['owner_sha256'],receipt_sha256=prep['candidate_receipt_sha256'],preparation_sha256=sha(op.read_bytes()),owner_GNU_note_hex=note.hex())))
if __name__=='__main__':main()
