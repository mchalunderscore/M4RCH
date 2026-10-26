#!/usr/bin/env python3
"""Offline admission and snapshot qualification; never accesses the live GPU."""
import argparse,copy,importlib.util,json,sys
from pathlib import Path
from unittest.mock import patch
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[2];sys.path.insert(0,str(KIT));import cold_render_contract as c
from adt import parse
def module(n,p):s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 p=argparse.ArgumentParser();p.add_argument('--candidate',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();assert not a.output.exists()
 runner=module('v24runner',KIT/'run-cold-render.py');preflight=module('v24preflight',KIT/'preflight-fresh.py');cases=[]
 def check(name,fn,ok=True):
  try:result=fn();passed=result is not False
  except (ValueError,KeyError,TypeError,OSError):passed=False
  assert passed==ok,name;cases.append(dict(case=name,passed=True))
 r=c.validate_candidate(a.candidate);check('actual-candidate-pins',lambda:c.validate_candidate(a.candidate))
 leaves=json.loads((a.candidate/'asc-graph-init/graph-receipt.json').read_text())['mmio_leaves']
 for leaf in leaves:check('actual-MMIO-'+hex(leaf['physical']),lambda l=leaf:runner.qualified_mmio_leaf(l))
 for leaf in leaves:
  if leaf['physical']==0x5003c0000 or 0x500658000<=leaf['physical']<0x500668000:
   bad=dict(leaf,readonly=False);check('telemetry-refuses-write-'+hex(leaf['physical']),lambda l=bad:runner.qualified_mmio_leaf(l),False)
   bad=dict(leaf,gpu_va=leaf['gpu_va']+0x1000);check('telemetry-refuses-alias-'+hex(leaf['physical']),lambda l=bad:runner.qualified_mmio_leaf(l),False)
 check('owner-parameters',lambda:runner.owner_parameters(r,graph=True)==['run_gate=2','observe_ms=5000','resident_session=1'])
 for key,value in [('joined_owned_pages',174),('graph_release_on_shutdown',True),('graph_submit_work',True)]:
  bad=copy.deepcopy(r);bad[key]=value;check('receipt-refuses-'+key,lambda b=bad:c.validate_receipt(b),False)
 for opts in ({},{'graph':True,'arena':True},{'graph':True,'warm_restart':True}):check('owner-refuses-'+str(opts),lambda o=opts:runner.owner_parameters(r,**o),False)
 manifest=json.loads((KIT/'power-adt-manifest.json').read_text());raw=Path(manifest['source']).read_bytes();tree=parse(raw);check('actual53-raw-ADT-and19-absent-defaults',lambda:c.qualify_adt(tree))
 for key in manifest['properties']:
  bad=copy.deepcopy(tree);v=bad['/device-tree/arm-io/sgx'][key];bad['/device-tree/arm-io/sgx'][key]=v+b'\0';check('ADT-refuses-modified-'+key,lambda b=bad:c.qualify_adt(b),False)
 for key in manifest['absent_constructor_properties']:
  bad=copy.deepcopy(tree);bad['/device-tree/arm-io/sgx'][key]=bytes(4);check('ADT-refuses-new-default-'+key,lambda b=bad:c.qualify_adt(b),False)
 for boot in c.REFUSED_BOOTS:
  with patch.object(Path,'read_text',return_value=boot),patch.object(c,'validate_candidate',side_effect=AssertionError('Candidate read before consumed boot refusal')):
   check('fresh-preflight-refuses-consumed-'+boot,preflight.early_boot,False)
 with patch.object(Path,'read_text',return_value='14343c22-f598-4eae-974a-b0edf7009530'),patch.object(runner,'validate_candidate',side_effect=AssertionError('Candidate read before refusal')),patch.object(sys,'argv',['runner',str(a.candidate),'--run','--graph']):check('main-refuses-current-consumed-before-candidate',runner.main,False)
 seed=(a.candidate/'asc-graph-init/graph-before.bin').read_bytes();snapshot=bytes((i*71+13)%256 for i in range(39884));image=runner.initialized_graph(seed,snapshot);extents=[(0x30000,0x6578),(0x8000,0x2718),(0xc000,0xe58),(0x4f100,0xe4)]
 assert all(a+n<=b or b+m<=a for i,(a,n) in enumerate(extents) for b,m in extents[i+1:]);cursor=0;mask=bytearray(len(seed))
 for off,n in extents:assert image[off:off+n]==snapshot[cursor:cursor+n];mask[off:off+n]=bytes([1])*n;cursor+=n
 assert all(x==y for x,y,m in zip(seed,image,mask) if not m);cases.append(dict(case='four-disjoint-owner-overlay-exact39884-no-other-byte-change',passed=True))
 for x,y in [(seed[:-1],snapshot),(seed,snapshot[:-1]),(seed,snapshot+b'\0')]:check('overlay-refuses-wrong-size-'+str((len(x),len(y))),lambda x=x,y=y:runner.initialized_graph(x,y),False)
 sources=[Path(__file__),KIT/'run-cold-render.py',KIT/'cold_render_contract.py',KIT/'preflight-fresh.py',KIT/'power-adt-manifest.json',a.candidate/'asc-root-envelope/build-receipt.json',a.candidate/'cold-render-preparation.json']
 report=dict(schema='m4rch.native-full-power-launcher-qualification.v24',passed=True,case_count=len(cases),cases=cases,input_pins=[dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=c.sha(p.read_bytes())) for p in sources],hardware_access=False,hardware_actions=[],module_loaded=False,ready=False)
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,case_count=len(cases),output=str(a.output))))
if __name__=='__main__':main()
