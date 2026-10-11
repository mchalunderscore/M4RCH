#!/usr/bin/env python3
"""Compare compiled Rust native KSM record writer to source-qualified models."""
import argparse,hashlib,json,random,struct,subprocess,sys
from pathlib import Path
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[3];sys.path.insert(0,str(ROOT/'experiments/t6040-gpu'))
from private_work_prefix import patch_work_prefix
from private_work_body import patch_work_body
from private_nop_body import convert_timestamp

def pin(p):
 p=Path(p).resolve();d=p.read_bytes();return dict(path=str(p),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())
def qualify(output):
 output.mkdir(parents=True,exist_ok=False);rng=random.Random(604008);src='#![allow(dead_code)]\n#[path='+json.dumps(str(KIT/'g16_t6040_ksm_work_v8.rs'))+'] mod n;\nfn main(){\n'
 for i in range(96):
  initial=rng.randbytes(0x200);ts=rng.getrandbits(64);qid=[0,1,63,64,126,127][i%6];prio=i%4;capacity=[1,2,3,16,128,256][i%6];previous=rng.getrandbits(64)
  ac=i%65;aa=(rng.getrandbits(43)>>5)<<5;ai=i%64;alternate=bool(i&1);extra=bool(i&2);payload=[0x7200000000+i*0x4000,0xfffffc2200000000+i*0x10000]
  deps=[(rng.getrandbits(32),j,rng.getrandbits(40)) for j in range(i%9)];qos=(i%256,(i*977)%65536,i%32);kind=i%4
  lists=[((0x7200000000+i*0x4000+j*0x720)&~31,(i+j)%127+1) for j in range(4)]
  masks=[rng.getrandbits(64) for _ in range(4)];aux=rng.getrandbits(64)
  expected,nextts=patch_work_body(patch_work_prefix(initial,ts,qid,prio,aa,ai,ac,alternate,extra,payload),ts,capacity,previous,qid,deps,previous,qos,kind,lists,masks,aux)
  # The initial argument in body is an event-machine initial epoch independent
  # of queue's previous timestamp. This qualification deliberately uses previous.
  (output/f'initial-{i}.bin').write_bytes(initial);(output/f'expected-{i}.bin').write_bytes(expected)
  ds=[]
  for event,index,epoch in deps:
   converted=convert_timestamp(epoch,event,capacity,previous)
   ds.append(f'n::Dependency{{converted_timestamp:{converted},queue_id:{index}}}')
   src+=f'assert_eq!(n::convert_timestamp({epoch},{event},{capacity},{previous}),Some({converted}));\n'
  ls=','.join(f'n::RegisterList{{gpu_address:{a},count:{c}}}' for a,c in lists)
  src+=f'let mut out=*include_bytes!({json.dumps(str(output/f"initial-{i}.bin"))}); let deps=['+','.join(ds)+'];\n'
  src+=f'let b=n::Bindings{{timestamp:{ts},queue_id:{qid},priority:{prio},capacity:{capacity},previous:{previous},command:{payload[0]},firmware_queue:{payload[1]},aperture_address:{aa},aperture_index:{ai},aperture_count:{ac},alternate_kind:{str(alternate).lower()},extra_flag:{str(extra).lower()},dependencies:&deps,qos:({qos[0]},{qos[1]},{qos[2]}),rce_kind:{kind},register_lists:[{ls}],masks:{masks},auxiliary:{aux}}};\n'
  src+=f'assert_eq!(n::write(&mut out,&b),Some({nextts}));assert_eq!(out,*include_bytes!({json.dumps(str(output/f"expected-{i}.bin"))}));\n'
  src+='let old=out;let bad=n::Bindings{queue_id:128,..b};assert_eq!(n::write(&mut out,&bad),None);assert_eq!(out,old);\n'
 src+='}\n';p=output/'test.rs';p.write_text(src)
 r=subprocess.run(['rustc','--edition=2021','-Dwarnings',str(p),'-o',str(output/'test')],capture_output=True,text=True);(output/'compile.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
 r=subprocess.run([str(output/'test')],capture_output=True,text=True);assert r.returncode==0,r.stderr
 evidence=[ROOT/'docs/evidence/2026-10-08-private-work-prefix.json',ROOT/'docs/evidence/2026-10-08-private-work-body.json']
 report=dict(schema='m4rch.native-t6040-ksm-work.v8',inputs=[pin(__file__),pin(KIT/'g16_t6040_ksm_work_v8.rs'),*[pin(ROOT/'experiments/t6040-gpu'/p) for p in ['private_work_prefix.py','private_work_body.py','private_nop_body.py','private_nop_header.py']],*[pin(p) for p in evidence]],cases=96,whole_record_bytes=512,refusal_cases=96,compiler_result=0,run_result=0,composition='Prior actualnative instruction qualifications retained; newcompiledRust comparedto same independentnumericmodels',hardware_actions=[],native_ta_fragment_generator_integrated=False,triangle_trial_ready=False)
 (output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);qualify(p.parse_args().output.resolve())
