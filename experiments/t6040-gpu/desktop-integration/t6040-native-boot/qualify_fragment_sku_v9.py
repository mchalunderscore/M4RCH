#!/usr/bin/env python3
"""Compile the native 3D primary SKU writer and compare complete publication."""
from pathlib import Path
import sys,random,struct,subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[4];KIT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'experiments/t6040-gpu'))
from private_sku_startup import build
from private_sku_records import startup,timestamp
from private_sku_end import primary
OUT=ROOT/'out/gpu-gravity-native-fragment-sku-v9-qualification';OUT.mkdir(exist_ok=True)
rs='''#[path="COMPONENT"] mod sku;
use std::{env,fs};
fn q(b:&[u8],o:usize)->u64{u64::from_le_bytes(b[o..o+8].try_into().unwrap())}
fn main(){let a:Vec<String>=env::args().collect();let d=fs::read(&a[1]).unwrap();let descriptor:[u8;0x1800]=d[..0x1800].try_into().unwrap();let mut command:[u8;0x2240]=d[0x1800..0x3a40].try_into().unwrap();let mut stack:[u8;0x300]=d[0x3a40..0x3d40].try_into().unwrap();let mut stream=d[0x3d40..0x4140].to_vec();let v=&d[0x4140..];let b=sku::Bindings{command_gpu:q(v,0),parameter_gpu:q(v,8),state_fw:q(v,16),resource_type:q(v,24) as u32,resource_map:q(v,32),context_id:q(v,40) as u32,accelerator_config:q(v,48) as u8,accelerator_feature:q(v,56) as u8,channel_config:q(v,64) as u8,mode:q(v,72) as u32,timestamp_index:q(v,80) as u32,stream_fw:q(v,88),omit_end_timestamp:q(v,96)!=0};let n=sku::primary_stream(&mut stream,&mut stack,&mut command,&descriptor,b).unwrap();let mut short=vec![0xa5u8;n];let before_stack=stack;let before_command=command;assert_eq!(sku::primary_stream(&mut short,&mut stack,&mut command,&descriptor,b),Err(sku::Error::Space));assert_eq!(stack,before_stack);assert_eq!(command,before_command);assert!(short.iter().all(|x|*x==0xa5));let mut o=Vec::new();o.extend_from_slice(&stack);o.extend_from_slice(&command);o.extend_from_slice(&stream);o.extend_from_slice(&(n as u32).to_le_bytes());fs::write(&a[2],o).unwrap();}
'''.replace('COMPONENT',str(KIT/'g16_t6040_fragment_sku_v9.rs'))
(OUT/'host.rs').write_text(rs);subprocess.run(['rustc','--edition=2021','-Dwarnings',str(OUT/'host.rs'),'-o',str(OUT/'host')],check=True)
rng=random.Random(604109);cases=[]
for i in range(96):
 desc=bytearray(rng.randbytes(0x1800));cmd=bytearray(rng.randbytes(0x2240));stack=bytearray(rng.randbytes(0x300));stream=bytearray(rng.randbytes(0x400))
 struct.pack_into('<I',cmd,0,1);struct.pack_into('<I',desc,0xa70,i%17);desc[0xc48]=0;desc[0x893]=i%2
 gpu=0x830000000+i*0x10000;pm=0x840000000+i*0x20000;state=0x850000000+i*0x30000;resource=rng.getrandbits(32);mapping=0x860000000+i*0x1000;context=i*19;config=i&254;feature=i*3;channel=i*5;mode=i%4;index=i*7;fw=0xfffffc2001000000+i*0x1000;omit=(i//2)%2
 values=[gpu,pm,state,resource,mapping,context,config,feature,channel,mode,index,fw,omit]
 (OUT/'input.bin').write_bytes(desc+cmd+stack+stream+struct.pack('<13Q',*values))
 expected_stack,secondary=build(stack,desc,cmd,gpu,pm,state,resource,mapping,context,config,feature);assert secondary==0
 expected=bytearray(stream);expected[:0x1ec]=startup(expected[:0x1ec],expected_stack[0x80:0x268]);off=0x1ec
 if not desc[0x893]&1:expected[off:off+0x4c]=timestamp(expected[off:off+0x4c],cmd,index,gpu,state,True);off+=0x4c
 if not omit:expected[off:off+0x4c]=timestamp(expected[off:off+0x4c],cmd,index,gpu,state,False);off+=0x4c
 expected[off:off+0xbc]=primary(expected[off:off+0xbc],expected_stack,cmd,desc,gpu,fw+4,mode,channel,0,0,off);off+=0xbc
 struct.pack_into('<I',expected,off,0x40000002);off+=4
 expected[off:(off+63)&~63]=bytes(((off+63)&~63)-off)
 expected_cmd=bytearray(cmd);struct.pack_into('<Q',expected_cmd,0x14,fw);struct.pack_into('<I',expected_cmd,0x1c,(off+63)&~63)
 subprocess.run([str(OUT/'host'),str(OUT/'input.bin'),str(OUT/'actual.bin')],check=True)
 want=expected_stack+expected_cmd+expected+struct.pack('<I',off);actual=(OUT/'actual.bin').read_bytes()
 if actual!=want:raise ValueError((i,[hex(j) for j in range(len(want)) if want[j]!=actual[j]][:16]))
 cases.append(dict(case=i,attachment_count=i%17,length=off,sha256=hashlib.sha256(actual).hexdigest()))
files=[KIT/'g16_t6040_fragment_sku_v9.rs',Path(__file__),ROOT/'experiments/t6040-gpu/private_sku_startup.py',ROOT/'experiments/t6040-gpu/private_sku_end.py',ROOT/'experiments/t6040-gpu/private_sku_records.py']
report=dict(count=len(cases),prewrite_rounded_extent_refusals=len(cases),poisoned_padding_cleared=True,cases=cases,inputs=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files],qualification='Compiled Rust primary ordinary 3D SKU startup, optional native timestamp records, opcode8, finish and command firmware pointer/rounded size publication. Complete stack, command and stream compare to independently written models previously compared with connected actual native stream. Random payloads and per-job aliases/counts/policy. Optional secondary phase explicitly refused; caller wait and completion semantics remain separate. No live GPU.')
(OUT/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print('96 complete native primary 3D SKU outputs matched')
