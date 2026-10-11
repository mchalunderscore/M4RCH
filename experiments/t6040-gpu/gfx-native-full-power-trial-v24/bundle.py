#!/usr/bin/env python3
"""Build a distinct offline v24 bundle; never loads modules or writes boot state."""
import argparse,hashlib,importlib.util,json,shutil,sys
from pathlib import Path
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pin(p):p=Path(p).resolve();return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
def bundle(source,stage,destination,build_receipt=None):
 source,stage,destination=map(lambda p:Path(p).resolve(),(source,stage,destination))
 build_receipt=Path(build_receipt).resolve() if build_receipt else ROOT/'out/gfx-native-full-power-trial-v24/module-build-v8.json'
 build=json.loads(build_receipt.read_text())
 assert build['returncode']==0 and build['module']['sha256']==sha(stage/'asc-graph-init.ko')
 if destination.exists():raise ValueError('Frozen candidate already exists')
 shutil.copytree(source,destination,ignore=lambda d,n:[x for x in n if x.startswith('boot-')])
 shutil.rmtree(destination/'asc-graph-init');shutil.copytree(stage,destination/'asc-graph-init')
 sys.path.insert(0,str(KIT));import cold_render_contract as contract
 receipt=json.loads((destination/'asc-root-envelope/build-receipt.json').read_text())
 trial=receipt['graph_recovery_trial'];trial.pop('gfx_native_power_assertion_fender_cycle_scope',None);trial[contract.FAMILY_KEY]=contract.CONTRACT
 receipt['joined_owned_pages']=176;receipt['module_sha256']=sha(stage/'asc-graph-init.ko')
 receipt['graph_source_sha256']={p.name:sha(p) for p in stage.iterdir() if p.is_file() and (p.suffix in ('.h','.c','.rs','.S','.bin') or p.name=='Makefile') and not p.name.endswith('.mod.c')}
 receipt['artifact_sha256']={name:sha(destination/name) for name in receipt['artifact_sha256']}
 receipt['graph_receipt_sha256']=sha(stage/'graph-receipt.json');receipt['graph_fixture_sha256']=sha(stage/'graph-before.bin')
 receipt['hardware_trial_performed']=False;receipt['v24_module_build_receipt']=pin(build_receipt)
 (destination/'asc-root-envelope/build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 inputs=[KIT/'bundle.py',KIT/'run-cold-render.py',KIT/'preflight-fresh.py',KIT/'cold_render_contract.py',KIT/'readback.py',KIT/'analyze_cold_render.py',KIT/'power-adt-manifest.json',build_receipt]
 prep=json.loads((source/'cold-render-preparation.json').read_text())
 prep.update(schema='m4rch.gfx-native-full-power-trial-v24-preparation.v1',candidate=str(destination),baseline_candidate=str(source),owner_sha256=sha(stage/'asc-graph-init.ko'),owner_GNU_note_hex=contract.module_build_note((stage/'asc-graph-init.ko').read_bytes()).hex(),selected_next_hardware_candidate=False,hardware_actions=[],module_loaded=False,kernel_rebuilt=False,inputs=[pin(p) for p in inputs],candidate_receipt_sha256=sha(destination/'asc-root-envelope/build-receipt.json'),refused_boots=list(contract.REFUSED_BOOTS),selection='Await root review; fresh boot required',strict_management_rejoin_ON_unchanged=False,v24_full_power_dynamic_before_capture=True,v24_owned_pages=176,v24_graph_object_pages=69,v24_OFF_terminal=True,hardware_ready=False)
 prep['qualification_composition']['v24_actual_module_build']=pin(build_receipt)
 (destination/'cold-render-preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
 contract.validate_candidate(destination)
 return dict(candidate=str(destination),owner_sha256=sha(stage/'asc-graph-init.ko'),receipt=pin(destination/'asc-root-envelope/build-receipt.json'),preparation=pin(destination/'cold-render-preparation.json'),ready=False,hardware_actions=[])
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--stage',required=True);p.add_argument('--destination',required=True);p.add_argument('--build-receipt');a=p.parse_args();print(json.dumps(bundle(a.source,a.stage,a.destination,a.build_receipt)))
