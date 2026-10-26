#!/usr/bin/env python3
"""Bind a new compiled cold-render owner to actual offline source qualifications."""
import argparse,copy,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from cold_render_contract import CONTRACT,FAMILY_KEY,REFUSED_BOOTS,RETAINED_SAMPLERS,validate_recipe_backing,require,sha,module_build_note,validate_receipt
from analyze_cold_render import qualify_pipeline,qualify_trace_preserved,qualify_postdraw_cycle,qualify_gravity_preasc
from readback import RECIPE_HASHES
ROOT=HERE.parents[2]
BASE=ROOT/'out/gfx-cold-render/candidate-v2'
BASE_RECEIPT_SHA='89175955c8981047707c983ea2f4fb7cfc79e71374ac9a8548e7afea6c33a172'
def pin(p):
 raw=p.read_bytes();return dict(path=str(p.resolve()),bytes=len(raw),sha256=sha(raw))
def checked_rows(rows):
 require(rows,'Qualification input pins missing')
 for row in rows:
  path=Path(row['path']);path=path if path.is_absolute() else ROOT/path
  require(sha(path.read_bytes())==row['sha256'],'Qualification input changed: '+str(path))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('owner_qualification',type=Path);p.add_argument('--preasc-qualification',type=Path,required=True);p.add_argument('--host-qualification',type=Path,required=True);args=p.parse_args()
 c=args.candidate.resolve();g=c/'asc-graph-init';out=c/'cold-render-preparation.json';receipt_path=c/'asc-root-envelope/build-receipt.json'
 require(not out.exists() and not receipt_path.exists(),'Distinct finalization output must be new')
 base_path=BASE/'asc-root-envelope/build-receipt.json';require(sha(base_path.read_bytes())==BASE_RECEIPT_SHA,'Frozen baseline receipt changed')
 receipt=copy.deepcopy(json.loads(base_path.read_text()));source_path=g/'postdraw-native-nmi-cycle-owner-source-receipt.json';source=json.loads(source_path.read_text())
 require(source['profile']['version']==17 and source['profile']['compile_macro']=='GFX_POSTDRAW_NATIVE_NMI_CYCLE_TRIAL','Cold owner source profile differs')
 for row in source['output_source_pins']:require(sha((g/row['name']).read_bytes())==row['sha256'],'Owner output changed: '+row['name'])
 cq=json.loads(args.owner_qualification.read_text());hq=json.loads(args.host_qualification.read_text());sq=json.loads(args.preasc_qualification.read_text())
 for q in (cq,hq,sq):
  require(q.get('passed') is True and q.get('hardware_access') is False and q.get('case_count',0)>0,'Actual offline qualification missing');checked_rows(q.get('input_pins',q.get('inputs',[])))
 require(cq.get('source_receipt_sha256')==sha(source_path.read_bytes()),'C qualification source differs')
 require(cq.get('maximum_new_log_row_bytes',512)<=511,'C log row bound differs')
 fixture=cq['success_log_fixture'];fixture_path=Path(fixture['path']);require(sha(fixture_path.read_bytes())==fixture['sha256'],'Actual C success fixture changed')
 preasc_fixture=sq['success_log_fixture'];preasc_path=Path(preasc_fixture['path']);require(sha(preasc_path.read_bytes())==preasc_fixture['sha256'],'Actual Gravity C prefix fixture changed')
 require(sq.get('prepared_helper_sha256')==sha((g/'gfx-gravity-preasc.h').read_bytes()),'Gravity prefix qualification differs from prepared owner')
 qualify_gravity_preasc(preasc_path.read_text())
 qualify_pipeline(preasc_path.read_text()+fixture_path.read_text())
 qualify_trace_preserved(fixture_path.read_text())
 cycle_fixture=cq.get('cycle_success_log_fixture',fixture);cycle_path=Path(cycle_fixture['path']);require(sha(cycle_path.read_bytes())==cycle_fixture['sha256'],'Actual C cycle fixture changed')
 from cold_render_contract import rows
 cycle_rows=rows(cycle_path.read_text(),'gfx-postdraw-native-cycle');require(cycle_rows,'Actual C cycle fixture rows missing')
 qualify_postdraw_cycle(cycle_path.read_text(),cycle_rows[0]['capture_token'])
 nmi_fixture=cq['cycle_nmi_success_log_fixture'];nmi_path=Path(nmi_fixture['path']);require(sha(nmi_path.read_bytes())==nmi_fixture['sha256'],'Actual NMI fixture changed')
 nmi_rows=rows(nmi_path.read_text(),'gfx-postdraw-native-cycle');require(nmi_rows,'Actual NMI cycle rows missing')
 qualify_postdraw_cycle(nmi_path.read_text(),nmi_rows[0]['capture_token'])
 require(hq.get('actual_C_nmi_cycle_log_qualified') is True and hq.get('actual_C_nmi_cycle_log_sha256')==nmi_fixture['sha256'],'Host actual NMI cycle parser join missing')
 require(hq.get('actual_C_preasc_log_qualified') is True and hq.get('actual_C_preasc_log_sha256')==preasc_fixture['sha256'],'Host actual Gravity prefix parser join missing')
 require(hq.get('actual_C_cycle_log_qualified') is True and hq.get('actual_C_cycle_log_sha256')==cycle_fixture['sha256'],'Host actual C cycle parser join missing')
 require(hq.get('actual_C_success_log_qualified') is True and hq.get('actual_C_success_log_sha256')==fixture['sha256'],'Host actual C parser join missing')
 require(hq.get('actual_C_preserved_trace_qualified') is True,'Host actual C trace preservation join missing')
 require(hq.get('source_receipt_sha256')==sha(source_path.read_bytes()),'Host qualification source differs')
 build_path=ROOT/'out/gfx-postdraw-native-nmi-cycle/owner-build-command.json';build=json.loads(build_path.read_text());log_path=ROOT/'out/gfx-postdraw-native-nmi-cycle/owner-build.log';log=log_path.read_bytes()
 require(build.get('returncode')==0 and build.get('kernel_rebuilt') is False and build.get('hardware_actions')==[],'Offline owner build provenance differs')
 require(build.get('source_receipt_sha256')==sha(source_path.read_bytes()) and build.get('candidate')==str(c),'Build source/candidate identity differs')
 require(sha(log)==build['selected_build_log_sha256'] and not any(s in log.lower() for s in (b'warning:',b'error:')),'Clean build log differs')
 checked_rows(build['kernel_build_inputs_unchanged'])
 owner=g/'asc-graph-init.ko';note=module_build_note(owner.read_bytes());modinfo=subprocess.check_output(['readelf','-p','.modinfo',str(owner)],text=True)
 require('vermagic='+receipt['kernel_release']+' SMP preempt mod_unload aarch64' in modinfo,'Owner vermagic differs')
 command=(g/'.asc-graph-init.o.cmd').read_text().splitlines()[0]
 require(command.count('-DGFX_POSTDRAW_NATIVE_NMI_CYCLE_TRIAL')==1 and '-DGFX_COLD_RENDER_TRIAL' not in command and '-DGFX_NATIVE_AP_REPEAT_CYCLE_TRIAL' not in command,'Compiled cold macro differs')
 for name,h in receipt['artifact_sha256'].items():
  if name not in ('asc-graph-init/asc-graph-init.ko','sample-pagetables/gpu-data-sample.ko'):require(sha((c/name).read_bytes())==h,'Frozen non-owner artifact changed: '+name)
 for spec in RETAINED_SAMPLERS:
  require(sha((c/spec['module']).read_bytes())==spec['module_sha256'],'Fixed retained RAM sampler differs')
  receipt['artifact_sha256'][spec['module']]=spec['module_sha256']
 receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko']=sha(owner.read_bytes())
 receipt['graph_source_sha256']={row['name']:row['sha256'] for row in source['output_source_pins'] if row['name'].endswith(('.c','.h')) or row['name']=='Makefile'}
 receipt['graph_fixture_sha256']=sha((g/'graph-before.bin').read_bytes());receipt['graph_receipt_sha256']=sha((g/'graph-receipt.json').read_bytes())
 require(receipt['graph_fixture_sha256']==json.loads(base_path.read_text())['graph_fixture_sha256'],'Frozen draw graph changed')
 trial=receipt['graph_recovery_trial']
 for key in list(trial):
  if key.endswith('_scope'):del trial[key]
 trial.update(cycles=0,work_submitted=False);trial[FAMILY_KEY]=copy.deepcopy(CONTRACT)
 receipt.update(graph_submit_work=False,graph_release_on_shutdown=False,hardware_trial_performed=False)
 validate_receipt(receipt)
 recipe_path=ROOT/'out/gfx-native-dispatch-contract/recipe-v1/receipt.json'
 recipe=validate_recipe_backing(g,recipe_path)
 sampler_dir=ROOT/'out/gfx-native-dispatch-contract/retained-pt-eff8-v1'
 sampler_build_path=sampler_dir/'build.json';sampler_build=json.loads(sampler_build_path.read_text())
 require(sampler_build.get('returncode')==0 and sampler_build.get('hardware_actions')==[] and sampler_build.get('kernel_rebuilt') is False and sampler_build.get('GPU_RAM_MMIO_power_writes') is False and sampler_build.get('exact_range')==['0x105fff78000','0x40000'],'Reserved page-table sampler custody differs')
 require(sampler_build['module_sha256']==RETAINED_SAMPLERS[1]['module_sha256'],'Page-table sampler build differs')
 for relative,h in [('sampler/gpu-data-sample.c',sampler_build['source_changed_sha256']),('sampler/gpu-data-sample.ko',sampler_build['module_sha256']),('build.log',sampler_build['build_log_sha256'])]:
  require(sha((sampler_dir/relative).read_bytes())==h,'Page-table sampler custody changed: '+relative)
 inputs=[recipe_path,sampler_build_path,*[sampler_dir/name for name in ('sampler/gpu-data-sample.c','sampler/sample-contract.h','sampler/gpu-data-sample.ko','build.log')],base_path,source_path,args.owner_qualification.resolve(),args.host_qualification.resolve(),args.preasc_qualification.resolve(),fixture_path,cycle_path,nmi_path,preasc_path,build_path,log_path,*[HERE/name for name in ('cold_render_contract.py','frozen_source.py','run-cold-render.py','preflight-fresh.py','analyze_cold_render.py','readback.py','test-host.py','finalize-cold-render.py')]]
 # Runtime checks bind the qualified host dependency closure and selected actual C fixtures.
 for q in (cq,hq,sq):
  for row in q.get('input_pins',q.get('inputs',[])):
   path=Path(row['path']);inputs.append(path if path.is_absolute() else ROOT/path)
 for name,h in RECIPE_HASHES.items():
  path=HERE.parent/name;require(sha(path.read_bytes())==h,'Image reference recipe changed');inputs.append(path)
 v14_path=ROOT/'out/gfx-cold-render-pause-release/wrapper-qualification-v2.json'
 require(sha(v14_path.read_bytes())=='17e3bc979eab7e4443c56b57a45d1341d544f10a36660614ad2f1c34787f2387','Frozen v14 host qualification changed');inputs.append(v14_path)
 v14=json.loads(v14_path.read_text());checked_rows(v14['inputs'])
 inputs.extend(Path(r['path']) for r in v14['inputs'])
 v15_path=ROOT/'out/gfx-native-dispatch-contract/host-qualification-v2.json'
 require(sha(v15_path.read_bytes())=='71c17999000bfe01085274fc0761a8a2516628efb2f770ff0e737e6e297e0d2d','Frozen v15 host qualification changed');inputs.append(v15_path)
 v15=json.loads(v15_path.read_text());checked_rows(v15['inputs']);inputs.extend(Path(r['path']) for r in v15['inputs'])
 # Frozen v12 C/host receipts compose unchanged allocations/native ON/RX/draw work.
 for name,h in [('owner-qualification-v8.json','deea9356799207aba1d07c08c6858a2200abaf8ff3d5189d0ae401d9c89b0cf2'),('wrapper-qualification-v4.json','ce085fb9c4cd5c89cc908ab7e2c726053cb00ee7e57ad788ce712cdb795923ce')]:
  path=BASE.parent/name;require(sha(path.read_bytes())==h,'Frozen composed qualification changed');inputs.append(path)
  frozen=json.loads(path.read_text());checked_rows(frozen.get('input_pins',frozen.get('inputs',[])))
  for row in frozen.get('input_pins',frozen.get('inputs',[])):
   fp=Path(row['path']);inputs.append(fp if fp.is_absolute() else ROOT/fp)
 prep=dict(schema='m4rch.gfx-postdraw-native-nmi-cycle-preparation.v1',candidate=str(c),baseline_candidate=str(BASE),owner_sha256=sha(owner.read_bytes()),owner_GNU_note_hex=note.hex(),selected_next_hardware_candidate=True,hardware_actions=[],module_loaded=False,kernel_rebuilt=False,hardware_preconditions_pending=True,
  inputs=[pin(path) for path in dict.fromkeys(inputs)],analysis_input_pins=[dict(relative='analysis-inputs/target-receipt.json',sha256=sha((c/'analysis-inputs/target-receipt.json').read_bytes()))],qualification_composition=dict(new_C_cases=cq['case_count'],new_preasc_C_cases=sq['case_count'],new_host_cases=hq['case_count'],frozen_v13_C_cases=56,frozen_v13_host_cases=74,frozen_v14_host_cases=51,frozen_v15_host_cases=35,unchanged_cases_repeated=False),
  recipe_receipt_sha256=sha(recipe_path.read_bytes()),backing_changed_byte_count=recipe['changed_byte_count'],fixed_retained_RAM_samplers=list(RETAINED_SAMPLERS),automatic_pipeline=CONTRACT,refused_boots=list(REFUSED_BOOTS),capture_scope='Per-phase raw register rows and output/ring change counts plus receive journal; final full objects/owned/target/completion/ring dumps then disjoint fixed reserved RAM DATA and page tables, regardless of log association. Pre-cycle evidence isimmutable; later typednative cycle/logs remain separate. No current PC or IOP cache writeback proof.',qualification='One future fresh cold owner may automatically prove fresh control33, keep trace3 throughcontrol, then publish one retained TA/3D draw with the four native config getter bytes and capture15s. After complete immutable rawcapture, one source-bound postdraw202 with nativeNMI only on a qualified ACK timeout, strictidle/OFF+PMput and optionalmanagement-only ON is admitted. No backing free, app/root/work replay, secondcycle or rendering/retirement result is established offline.')
 with receipt_path.open('x') as f:f.write(json.dumps(receipt,indent=2)+'\n')
 prep['candidate_receipt_sha256']=sha(receipt_path.read_bytes())
 with out.open('x') as f:f.write(json.dumps(prep,indent=2)+'\n')
 print(json.dumps(dict(candidate=str(c),owner_sha256=prep['owner_sha256'],receipt_sha256=prep['candidate_receipt_sha256'],preparation_sha256=sha(out.read_bytes()),owner_GNU_note_hex=note.hex())))
if __name__=='__main__':main()
