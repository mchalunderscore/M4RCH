#!/usr/bin/env python3
"""Compiled native TA SKU against source-qualified whole-stream model."""
from pathlib import Path
import sys,random,struct,subprocess,json,hashlib
R=Path(__file__).resolve().parents[4];K=Path(__file__).parent;sys.path.insert(0,str(R/'experiments/t6040-gpu'))
from private_ta_sku_v9 import stream
O=R/'out/gpu-gravity-native-ta-sku-v9-qualification';O.mkdir(exist_ok=True)
rs='''#[path="COMPONENT"] mod sku;use std::{env,fs};
fn q(b:&[u8],o:usize)->u64{u64::from_le_bytes(b[o..o+8].try_into().unwrap())}
fn main(){let a:Vec<String>=env::args().collect();let d=fs::read(&a[1]).unwrap();let desc:[u8;0x1800]=d[..0x1800].try_into().unwrap();let mut cmd:[u8;0x9c0]=d[0x1800..0x21c0].try_into().unwrap();let mut stream=d[0x21c0..0x25c0].to_vec();let v=&d[0x25c0..];let b=sku::Bindings{command_gpu:q(v,0),translated_state:q(v,8),fw_state:q(v,16),state:q(v,24),counter:q(v,32),resource_type:q(v,40) as u32,context_id:q(v,48) as u32,resource_map:q(v,56),feature:q(v,64) as u8,channel_config:q(v,72) as u8,timestamp_index:q(v,80) as u32,stream_fw:q(v,88)};let n=sku::primary_stream(&mut stream,&mut cmd,&desc,b).unwrap();let mut short=vec![0xa5u8;n];let before=cmd;assert_eq!(sku::primary_stream(&mut short,&mut cmd,&desc,b),Err(sku::Error::Space));assert_eq!(cmd,before);assert!(short.iter().all(|v|*v==0xa5));let mut out=Vec::new();out.extend_from_slice(&cmd);out.extend_from_slice(&stream);out.extend_from_slice(&(n as u32).to_le_bytes());fs::write(&a[2],out).unwrap();}
'''.replace('COMPONENT',str(K/'g16_t6040_ta_sku_v9.rs'))
(O/'host.rs').write_text(rs);subprocess.run(['rustc','--edition=2021','-Dwarnings',str(O/'host.rs'),'-o',str(O/'host')],check=True)
rng=random.Random(604122);cases=[]
for i in range(96):
 desc=bytearray(rng.randbytes(0x1800));cmd=bytearray(rng.randbytes(0x9c0));initial=rng.randbytes(0x400);struct.pack_into('<I',cmd,0,0);struct.pack_into('<I',desc,0x1388,i%17);desc[0x1138]=i%2
 names=['command_gpu','translated_state','fw_state','state','counter','resource_type','context_id','resource_map','feature','channel_config','timestamp_index','stream_fw']
 values=[0x830000000+i*0x10000,0xfffffc2001000000+i*0x1000,0xfffffc2002000000+i*0x1000,0xfffffc2003000000+i*0x1000,rng.getrandbits(64),i*13,i*17,0x840000000+i*0x2000,i*3,i*5,i*7,0xfffffc2004000000+i*0x1000];b=dict(zip(names,values))
 (O/'input.bin').write_bytes(desc+cmd+initial+struct.pack('<12Q',*values));expected,expected_cmd,n=stream(initial,cmd,desc,b);expected=bytearray(expected);expected[n:(n+63)&~63]=bytes(((n+63)&~63)-n)
 subprocess.run([str(O/'host'),str(O/'input.bin'),str(O/'actual.bin')],check=True);actual=(O/'actual.bin').read_bytes();want=expected_cmd+expected+struct.pack('<I',n)
 if actual!=want:raise ValueError((i,[hex(j) for j in range(len(want)) if want[j]!=actual[j]][:16]))
 cases.append(dict(case=i,count=i%17,length=n,sha256=hashlib.sha256(actual).hexdigest()))
files=[K/'g16_t6040_ta_sku_v9.rs',Path(__file__),R/'experiments/t6040-gpu/private_ta_sku_v9.py',K/'audit_ta_sku_v9.py',R/'out/gpu-gravity-native-ta-sku-v9-source/qualification.json']
report=dict(count=len(cases),prewrite_rounded_extent_refusals=len(cases),poisoned_padding_cleared=True,cases=cases,inputs=[dict(path=str(p.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in files],qualification='Compiled Rust primary TA opcode5, optional actual TA timestamp layouts, opcode6, finish and native command790/798 publication. Full command+stream matches model proved against actual core plus timestamp and finishEncode helpers. Generic aliases and 0..16 aperture records. Caller beginEncoding wait/protected-context alternate excluded; no hardware execution.')
(O/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print('96 complete native TA SKU outputs and rounded-space refusals matched')
