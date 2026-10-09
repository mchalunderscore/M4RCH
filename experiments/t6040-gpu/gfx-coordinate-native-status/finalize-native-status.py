#!/usr/bin/env python3
"""Bind the distinct built native STATUS0 owner and offline qualifications.

No build, load, sysfs write or hardware action. Frozen execution bridge is input
only; native predicates, phram guard and once-only existing draw are separate.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from gfx_native_status_contract import CONTRACT,FAMILY_KEY,validate_receipt

BASE_SHA='8489e87beb21c23e3fb9b5735652c0966f3dc7d881280875f49f27ef4fd8b8eb'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path):return {'path':str(path.resolve()),'sha256':sha(path)}


def check_inputs(q):
 for row in q.get('inputs',q.get('files',[])):
  p=Path(row['path']);p=p if p.is_absolute() else ROOT/p
  assert sha(p)==row['sha256'],str(p)


def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('candidate',type=Path);ap.add_argument('owner_qualification',type=Path)
 args=ap.parse_args();candidate=args.candidate.resolve();base=ROOT/'out/gfx-coordinate-execution/candidate'
 bpath=base/'asc-root-envelope/build-receipt.json';assert sha(bpath)==BASE_SHA
 b=json.loads(bpath.read_text());graph=candidate/'asc-graph-init'
 for name,expected in b['artifact_sha256'].items():
  assert sha(base/name)==expected,name
  if name!='asc-graph-init/asc-graph-init.ko':assert sha(candidate/name)==expected,name
 for name,expected in b['graph_source_sha256'].items():
  assert sha(base/'asc-graph-init'/name)==expected,name
  if name not in ['Makefile','gfx-coordinate-core.h','gfx-coordinate-owner.h']:
   assert sha(graph/name)==expected,name
 for name,key in [('graph-before.bin','graph_fixture_sha256'),('graph-receipt.json','graph_receipt_sha256')]:assert sha(graph/name)==b[key]
 source_path=graph/'native-status-owner-source-receipt.json';source=json.loads(source_path.read_text())
 assert source['hardware_actions']==[] and source['build_actions']==[]
 assert source['changed_files']==['Makefile','gfx-coordinate-core.h','gfx-coordinate-owner.h']
 for row in source['input_source_pins']:assert sha(base/'asc-graph-init'/row['name'])==row['sha256'],row['name']
 for row in source['output_source_pins']:assert sha(graph/row['name'])==row['sha256'],row['name']
 assert sha(graph/'gfx-coordinate-core.h')==sha(HERE/'gfx-coordinate-core.h')
 assert sha(graph/'gfx-coordinate-owner.h')==sha(HERE/'gfx-coordinate-owner.h')
 qualification_paths=[ROOT/'out/gfx-coordinate-native-status'/name for name in
  ['core-qualification.json','parser-qualification.json','wrapper-qualification.json']]
 for p in qualification_paths:
  q=json.loads(p.read_text());assert q['passed'] is True and q['hardware_access'] is False
  check_inputs(q)
 owner=json.loads(args.owner_qualification.read_text());check_inputs(owner)
 assert owner['hardware_actions']==[] and owner['ASan_UBSan'] is True
 assert owner['adapter_sha256']==sha(graph/'gfx-coordinate-owner.h')
 assert owner['core_sha256']==sha(graph/'gfx-coordinate-core.h')
 flashq=ROOT/'out/gfx-coordinate-native-status/flash-guard-qualification.json'
 flash=json.loads(flashq.read_text());assert flash['hardware_access'] is False and flash['cases_passed']==60
 assert flash['source_sha256']==sha(HERE/'flash-layout-guard.py')
 assert flash['test_sha256']==sha(HERE/'test-flash-layout-guard.py')
 assert flash['baseline_sha256']==sha(HERE.parent/'gfx-native-coordinate-trial/linux-dt-contract.json')
 inherited=ROOT/'out/gfx-coordinate-execution/dispatcher-qualification.json'
 iq=json.loads(inherited.read_text());assert iq['passed'] and iq['hardware_access'] is False and iq['case_count']==178;check_inputs(iq)
 transform_path=ROOT/'experiments/t6040-gpu/gfx-coordinate-execution/prepare-execution-owner.py'
 spec=importlib.util.spec_from_file_location('qualified_execution_transform',transform_path)
 transform=importlib.util.module_from_spec(spec);spec.loader.exec_module(transform)
 frozen_cycle=ROOT/'out/gfx-native-coordinate/candidate/asc-graph-init/recovery-cycle.h'
 assert transform.transform_dispatcher(frozen_cycle.read_text())==(graph/'recovery-cycle.h').read_text()
 analysis_inputs=[('asc-graph-init/preparation.json','c22c59c0735c84554f954f581f94978894a9c78e87b6ec06f8f7ba8c763580db'),
  ('analysis-inputs/target-receipt.json','c6008f792f60569d9ff186168c397a90b221586bd6f30cb6190647232441befa')]
 for name,expected in analysis_inputs:assert sha(candidate/name)==expected,name
 draw=json.loads((graph/'preparation.json').read_text());assert draw['pages']==56 and draw['data_sha256']==sha(graph/'backing.bin')
 assert draw['target_receipt_sha256']==analysis_inputs[1][1]
 tools=[ROOT/'experiments/t6040-gpu/analyze-owned-work.py',ROOT/'experiments/t6040-gpu/check-first-render-readback.py',HERE/'analyze-execution.py']
 assert sha(tools[0])=='3a3bb4447c02a60d161c156beca6709b25a710b6800dd0142138b036f976558f'
 assert sha(tools[1])=='e5fe5791767e205af97667a751783ce7ec00624330f3c2eeacd53dd70514afc6'
 make=(graph/'Makefile').read_text()
 assert all('-D'+flag in make for flag in ['GFX_COORDINATED_EXECUTION_TRIAL','GFX_NATIVE_COORDINATED_SCOPE_TRIAL','GFX_NATIVE_STATUS_ZERO_TRIAL'])
 assert 'GFX_RESET_NATIVE_SEQUENCE_TRIAL' not in make
 log=ROOT/'out/gfx-coordinate-native-status/owner-build.log';assert 'warning:' not in log.read_text() and 'error:' not in log.read_text()
 module=graph/'asc-graph-init.ko';vermagic=subprocess.check_output(['modinfo','-F','vermagic',str(module)],text=True).strip();assert vermagic.startswith(b['kernel_release']+' ')
 imports=subprocess.check_output(['llvm-nm','-u',str(module)],text=True)
 assert all(n in imports for n in ['apple_pmgr_t6040_gfx_snapshot','__pm_runtime_suspend','of_find_all_nodes'])
 assert all(n not in imports for n in ['apple_pmgr_t6040_gfx_native_probe','apple_pmgr_t6040_gfx_checked_pulse'])
 receipt=copy.deepcopy(b);receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko']=sha(module)
 for name in receipt['graph_source_sha256']:receipt['graph_source_sha256'][name]=sha(graph/name)
 trial=receipt['graph_recovery_trial'];trial.pop('gfx_coordinated_execution_scope');trial[FAMILY_KEY]=CONTRACT
 assert validate_receipt(receipt)
 output=candidate/'asc-root-envelope/build-receipt.json'
 with output.open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 files=[bpath,base/'execution-preparation.json',source_path,args.owner_qualification,flashq,inherited,log,Path(__file__),
  ROOT/'docs/evidence/2026-10-09-gfx-coordinate-status-zero-live.json',
  ROOT/'docs/evidence/2026-10-09-native-status0-and-flash-guard.json']+qualification_paths+[HERE/n for n in
  ['gfx_native_status_contract.py','run-root-native-status.py','run-native-status.py','flash-layout-guard.py','prepare-native-status-owner.py','preflight-fresh.py']]
 prepared={'schema':'m4rch.gfx-native-status-preparation.v1','baseline_candidate':str(base),'baseline_receipt_sha256':BASE_SHA,
  'candidate':str(candidate),'candidate_receipt_sha256':sha(output),'owner_sha256':sha(module),'vermagic':vermagic,
  'inputs':[pin(p) for p in files],'actual_module_imports':imports.splitlines(),
  'artifact_count':len(receipt['artifact_sha256']),'owner_source_count':len(receipt['graph_source_sha256']),
  'analysis_input_pins':[{'relative':n,'sha256':h} for n,h in analysis_inputs],'analysis_tool_pins':[pin(p) for p in tools],
  'source_changes_from_execution_bridge':source['changed_files'],'other_seven_helpers_unchanged':True,
  'graph_draw_dispatcher_lifetime_unchanged':True,'frozen_candidates_unchanged':True,
  'hardware_actions':[],'module_loaded':False,'kernel_rebuilt':False,'boot_configuration_changed':False,
  'hardware_preconditions_pending':True,'selected_next_hardware_candidate':True,
  'recovery_teardown_rendering_verified':False,
  'qualification':'Ready only for fresh normal boot preflight and ONE cold attempt. Native STATUS0 skips ACK after REQ; no inactivity/retirement claim. Four successful idle recoveries and trace-off gate ONE existing draw; otherwise qualified no-work STOP/OFF contingency. Work intent closes STOP/OFF/restart/free/unload. All failures retain ownership.'}
 path=candidate/'native-status-preparation.json'
 with path.open('x') as f:json.dump(prepared,f,indent=2);f.write('\n')
 print(json.dumps({'preparation':str(path),'owner_sha256':sha(module),'receipt_sha256':sha(output),'hardware_actions':[]}))


if __name__=='__main__':main()
