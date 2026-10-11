#!/usr/bin/env python3
"""Qualify compiled native TA/3D envelopes with saved numeric producer models."""
import argparse,hashlib,json,random,struct,subprocess,sys
from pathlib import Path
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[3];sys.path.insert(0,str(ROOT/'experiments/t6040-gpu'))
import private_ta_command as t
import private_3d_command as f

def pin(p):
 p=Path(p).resolve();x=p.read_bytes();return dict(path=str(p),bytes=len(x),sha256=hashlib.sha256(x).hexdigest())
def qualify(output):
 output.mkdir(parents=True,exist_ok=False);rng=random.Random(604009);rs='#![allow(dead_code)]\n#[path='+json.dumps(str(KIT/'g16_t6040_render_envelope_v9.rs'))+'] mod n;\nfn main(){\n'
 for i in range(48):
  d=bytearray(rng.randbytes(0x1800));c=bytearray(rng.randbytes(0x600));s=rng.randbytes(0x100);source=rng.randbytes(0x400);frame=rng.randbytes(24);ta=rng.randbytes(0x9c0);frag=rng.randbytes(0x2240)
  struct.pack_into('<I',d,0x1388,i%17);struct.pack_into('<I',d,0xa70,i%17);struct.pack_into('<Q',d,0xb70,0 if i%2 else rng.getrandbits(64));c[0x5c0]=i%4
  serial=rng.getrandbits(64);addrs=[rng.getrandbits(64) for _ in range(3)];mapping=rng.getrandbits(64);x26=rng.getrandbits(64);w21=rng.getrandbits(32);w22=rng.getrandbits(32);mode=i%5;flags=i%8;counter=rng.getrandbits(32);epochs=[rng.getrandbits(64) for _ in range(2)];cap=[1,2,3,16,128,256][i%6];initial=rng.getrandbits(64)
  expected=t.header(ta,d,c,serial);expected=t.translated_resources(expected,addrs);expected=t.metadata(expected,d,c);expected=t.completion_binding(expected,d,c,mapping);expected=t.tail(expected,d,s,x26,w21,w22,t.conditional_control(d,c,mode));expected,td=t.postproducer(expected,d,c,flags)
  fe=f.header(frag,d,serial,frame);fe=f.body(fe,d,source);fe=f.tail(fe,d,s,w21,w22,counter&255);fe=f.bindings(fe,d,addrs,mapping);fe,fd=f.event_control(fe,d,c,epochs,cap,initial,counter&255,flags);fe,fd=f.aperture_records(fe,fd)
  data=dict(descriptor=bytes(d),context=bytes(c),stack=s,source=source,frame=frame,ta=ta,fragment=frag,expected_ta=expected,expected_ta_descriptor=td,expected_fragment=fe,expected_fragment_descriptor=fd)
  for name,x in data.items():(output/f'{i}-{name}.bin').write_bytes(x)
  inc=lambda name:'*include_bytes!('+json.dumps(str(output/f'{i}-{name}.bin'))+')'
  rs+=f'let original={inc("descriptor")};let mut d=original;let mut out={inc("ta")};let context={inc("context")};let stack={inc("stack")};let source={inc("source")};let frame={inc("frame")};\n'
  rs+=f'let b=n::TaBindings{{context:&context,stack:&stack,serial:{serial},firmware_translations:{addrs},completion_firmware:{mapping},x26:{x26},w21:{w21},w22:{w22},accelerator_mode:{mode},aperture_flags:{flags}}};assert_eq!(n::tiling(&mut out,&mut d,&b),Some(()));assert_eq!(out,{inc("expected_ta")});assert_eq!(d,{inc("expected_ta_descriptor")});\n'
  rs+=f'let mut d=original;let mut out={inc("fragment")};let b=n::FragmentBindings{{source:&source,frame:&frame,stack:&stack,context:&context,serial:{serial},counter:{counter},w21:{w21},w22:{w22},firmware_translations:{addrs},completion_firmware:{mapping},epochs:{epochs},capacity:{cap},initial:{initial},aperture_flags:{flags}}};assert_eq!(n::fragment(&mut out,&mut d,&b),Some(()));assert_eq!(out,{inc("expected_fragment")});assert_eq!(d,{inc("expected_fragment_descriptor")});\n'
  rs+='let oldout=out;let mut d=original;d[0xa70..0xa74].copy_from_slice(&17u32.to_le_bytes());let old=d;assert_eq!(n::fragment(&mut out,&mut d,&b),None);assert_eq!(out,oldout);assert_eq!(d,old);\n'
 rs+='}\n';p=output/'test.rs';p.write_text(rs)
 r=subprocess.run(['rustc','--edition=2021','-Dwarnings',str(p),'-o',str(output/'test')],capture_output=True,text=True);(output/'compile.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
 r=subprocess.run([str(output/'test')],capture_output=True,text=True);(output/'run.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr[:1000]
 report=dict(schema='m4rch.native-t6040-render-envelope.v9',inputs=[pin(__file__),pin(KIT/'g16_t6040_render_envelope_v9.rs'),pin(ROOT/'experiments/t6040-gpu/private_ta_command.py'),pin(ROOT/'experiments/t6040-gpu/private_3d_command.py'),pin(ROOT/'docs/evidence/2026-10-08-private-ta-command.json'),pin(ROOT/'docs/evidence/2026-10-08-private-3d-command.json')],ta_cases=48,fragment_cases=48,descriptor_output_compared=True,fragment_refusals_before_write=48,compile_result=0,run_result=0,scope='Native construction envelope only, with suppliednativeRCEbytes; source-qualifiedmodelscomposed, notrerun',remaining=['NativeTA/3DRCE generatorsmusttranslate actual runtimeRenderParameters into descriptorfields','Bind actual submissioncontext/stackfieldroles to realtimeline/completion/notifierowners','Use nativeWork200/DMmicrosequence anddependency48/BM18 inruntimepublication'],hardware_actions=[],triangle_trial_ready=False)
 (output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);qualify(p.parse_args().output.resolve())
