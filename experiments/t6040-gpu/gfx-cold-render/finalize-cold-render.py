#!/usr/bin/env python3
"""Bind a new compiled cold-render owner to actual offline source qualifications."""
import argparse,copy,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from cold_render_contract import CONTRACT,FAMILY_KEY,REFUSED_BOOTS,require,sha,module_build_note,validate_receipt
from analyze_cold_render import qualify_pipeline
from readback import RECIPE_HASHES
ROOT=HERE.parents[2]
BASE=ROOT/'out/gfx-native-ap-repeat-cycle/candidate'
BASE_RECEIPT_SHA='f9c7fe03bbf0caf3e2d72acb722dc78288e0e2bd3d8ef1f5c987114fb14263e5'
def pin(p):
 raw=p.read_bytes();return dict(path=str(p.resolve()),bytes=len(raw),sha256=sha(raw))
def checked_rows(rows):
 require(rows,'Qualification input pins missing')
 for row in rows:
  path=Path(row['path']);path=path if path.is_absolute() else ROOT/path
  require(sha(path.read_bytes())==row['sha256'],'Qualification input changed: '+str(path))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('owner_qualification',type=Path);p.add_argument('--host-qualification',type=Path,required=True);args=p.parse_args()
 c=args.candidate.resolve();g=c/'asc-graph-init';out=c/'cold-render-preparation.json';receipt_path=c/'asc-root-envelope/build-receipt.json'
 require(not out.exists() and not receipt_path.exists(),'Distinct finalization output must be new')
 base_path=BASE/'asc-root-envelope/build-receipt.json';require(sha(base_path.read_bytes())==BASE_RECEIPT_SHA,'Frozen baseline receipt changed')
 receipt=copy.deepcopy(json.loads(base_path.read_text()));source_path=g/'cold-render-owner-source-receipt.json';source=json.loads(source_path.read_text())
 require(source['profile']['version']==13 and source['profile']['compile_macro']=='GFX_COLD_RENDER_TRIAL','Cold owner source profile differs')
 for row in source['output_source_pins']:require(sha((g/row['name']).read_bytes())==row['sha256'],'Owner output changed: '+row['name'])
 cq=json.loads(args.owner_qualification.read_text());hq=json.loads(args.host_qualification.read_text())
 for q in (cq,hq):
  require(q.get('passed') is True and q.get('hardware_access') is False and q.get('case_count',0)>0,'Actual offline qualification missing');checked_rows(q.get('input_pins',q.get('inputs',[])))
 require(cq.get('source_receipt_sha256')==sha(source_path.read_bytes()),'C qualification source differs')
 require(cq.get('maximum_new_log_row_bytes',512)<=511,'C log row bound differs')
 fixture=cq['success_log_fixture'];fixture_path=Path(fixture['path']);require(sha(fixture_path.read_bytes())==fixture['sha256'],'Actual C success fixture changed')
 qualify_pipeline(fixture_path.read_text())
 require(hq.get('actual_C_success_log_qualified') is True and hq.get('actual_C_success_log_sha256')==fixture['sha256'],'Host actual C parser join missing')
 require(hq.get('source_receipt_sha256')==sha(source_path.read_bytes()),'Host qualification source differs')
 build_path=ROOT/'out/gfx-cold-render/owner-build-command.json';build=json.loads(build_path.read_text());log_path=ROOT/'out/gfx-cold-render/owner-build.log';log=log_path.read_bytes()
 require(build.get('returncode')==0 and build.get('kernel_rebuilt') is False and build.get('hardware_actions')==[],'Offline owner build provenance differs')
 require(build.get('source_receipt_sha256')==sha(source_path.read_bytes()) and build.get('candidate')==str(c),'Build source/candidate identity differs')
 require(sha(log)==build['selected_build_log_sha256'] and not any(s in log.lower() for s in (b'warning:',b'error:')),'Clean build log differs')
 checked_rows(build['kernel_build_inputs_unchanged'])
 owner=g/'asc-graph-init.ko';note=module_build_note(owner.read_bytes());modinfo=subprocess.check_output(['readelf','-p','.modinfo',str(owner)],text=True)
 require('vermagic='+receipt['kernel_release']+' SMP preempt mod_unload aarch64' in modinfo,'Owner vermagic differs')
 command=(g/'.asc-graph-init.o.cmd').read_text().splitlines()[0]
 require(command.count('-DGFX_COLD_RENDER_TRIAL')==1 and '-DGFX_NATIVE_AP_REPEAT_CYCLE_TRIAL' not in command,'Compiled cold macro differs')
 for name,h in receipt['artifact_sha256'].items():
  if name!='asc-graph-init/asc-graph-init.ko':require(sha((c/name).read_bytes())==h,'Frozen non-owner artifact changed: '+name)
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
 inputs=[base_path,source_path,args.owner_qualification.resolve(),args.host_qualification.resolve(),fixture_path,build_path,log_path,*[HERE/name for name in ('cold_render_contract.py','frozen_source.py','run-cold-render.py','preflight-fresh.py','analyze_cold_render.py','readback.py','test-host.py','finalize-cold-render.py')]]
 # Runtime checks bind the qualified host dependency closure and selected actual C fixtures.
 for q in (cq,hq):
  for row in q.get('input_pins',q.get('inputs',[])):
   path=Path(row['path']);inputs.append(path if path.is_absolute() else ROOT/path)
 for name,h in RECIPE_HASHES.items():
  path=HERE.parent/name;require(sha(path.read_bytes())==h,'Image reference recipe changed');inputs.append(path)
 # Frozen v12 C/host receipts compose unchanged allocations/native ON/RX/draw work.
 for name,h in [('owner-qualification-v8.json','68f5f2de51794d7c93cd6c4b077a4e023605b9266266db8b114290769ff99776'),('wrapper-qualification-v2.json','924d870f26bb69388c75ae581de50430ddac056d43aad9cb3a5603933fb0b385')]:
  path=BASE.parent/name;require(sha(path.read_bytes())==h,'Frozen composed qualification changed');inputs.append(path)
  frozen=json.loads(path.read_text());checked_rows(frozen.get('input_pins',frozen.get('inputs',[])))
  for row in frozen.get('input_pins',frozen.get('inputs',[])):
   fp=Path(row['path']);inputs.append(fp if fp.is_absolute() else ROOT/fp)
 prep=dict(schema='m4rch.gfx-cold-render-preparation.v1',candidate=str(c),baseline_candidate=str(BASE),owner_sha256=sha(owner.read_bytes()),owner_GNU_note_hex=note.hex(),selected_next_hardware_candidate=True,hardware_actions=[],module_loaded=False,kernel_rebuilt=False,hardware_preconditions_pending=True,
  inputs=[pin(path) for path in dict.fromkeys(inputs)],analysis_input_pins=[dict(relative='analysis-inputs/target-receipt.json',sha256=sha((c/'analysis-inputs/target-receipt.json').read_bytes()))],qualification_composition=dict(new_C_cases=cq['case_count'],new_host_cases=hq['case_count'],frozen_v12_C_cases=172,frozen_v12_host_cases=378,unchanged_cases_repeated=False),
  automatic_pipeline=CONTRACT,refused_boots=list(REFUSED_BOOTS),capture_scope='Per-phase raw register rows and output/ring change counts plus receive journal; final full objects/owned/target/completion/ring dumps. No per-phase full-page snapshots.',qualification='One future fresh cold owner may automatically prove fresh control33 then publish one retained TA/3D draw and capture15s. No active recovery, restart, submitted-work OFF/put/free or hardware result is established offline.')
 with receipt_path.open('x') as f:f.write(json.dumps(receipt,indent=2)+'\n')
 prep['candidate_receipt_sha256']=sha(receipt_path.read_bytes())
 with out.open('x') as f:f.write(json.dumps(prep,indent=2)+'\n')
 print(json.dumps(dict(candidate=str(c),owner_sha256=prep['owner_sha256'],receipt_sha256=prep['candidate_receipt_sha256'],preparation_sha256=sha(out.read_bytes()),owner_GNU_note_hex=note.hex())))
if __name__=='__main__':main()
