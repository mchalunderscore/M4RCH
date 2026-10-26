#!/usr/bin/env python3
"""Offline exact native PM models versus actual portable Rust constructor."""
import argparse,hashlib,json,struct,subprocess,sys
from pathlib import Path
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[3];sys.path.insert(0,str(KIT.parents[1]))
from private_pm_reset import reset_hw,reset_pm
from private_pm_scene_setup import scene_setup
# Inputs vary scene/state/capacity/geometry/addresses; no fixed render fixtures.
def pin(p):p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();a.output.mkdir(exist_ok=False,parents=True)
 source=KIT/'g16_t6040_pm_v9.rs';rust=a.output/'test.rs';exe=a.output/'test'
 rust.write_text('''#![allow(dead_code)]
#[path="'''+str(source)+'''"]mod pm;use pm::*;
fn main(){let dir=std::env::args().nth(1).unwrap();for i in 0..96usize {
 let g=Geometry{scene_count:(1+i%36)as u32,state_count:(1+i%8)as u32,capacity:(2+i%31)as u32,initial_blocks:1+(i%((2+i%31)-1))as u32,page_factor:4,registration_stride:4<<(i%4),scene_stride:0x80+((i%7)*0x40)as u64,extra_scene_stride:i&1!=0,parameter_field_1d4:1+i as u32,native_count_154:3+i as u32,native_count_15c:5+i as u32,support_count:4*(2+i%31)as u32};
 let plan=AllocationPlan::new(g).unwrap();assert!(plan.mapped_bytes&0x3fff==0);let mut end=0;for p in plan.roles{assert_eq!(p.offset,end);assert_eq!(p.mapped_bytes&0x3fff,0);assert!(p.logical_bytes<=p.mapped_bytes);end+=p.mapped_bytes;}assert_eq!(end,plan.mapped_bytes);let rv=plan.views(0xfffffc2300000000,0x1004000000,0x1004000000).unwrap();assert!(rv.scene(g,0).is_some());assert!(plan.views(0,0x1004000000,0x1004000000).is_none());
 let b=SceneBudget{memory_bytes:0x123456+i as u64*0x9876,divisor_units:1+(i%7)as u64,fixed_bytes:0x80,bytes_per_unit:0x40,alignment:0x40,groups:1+(i%6)as u32,group_shift:(i%4)as u32,group_allowance:i&1!=0};let bs=b.stride().unwrap();std::fs::write(format!("{}/{}/budget.bin",dir,i),bs.to_le_bytes()).unwrap();assert!(SceneBudget{divisor_units:0,..b}.stride().is_none());assert!(SceneBudget{alignment:3,..b}.stride().is_none());
 let e=g.extents().unwrap();let resource=|k:usize|Resource{device:0x1001000000+k as u64*0x100000,user:0x2001000000+k as u64*0x100000,firmware:0xfffffc2200100000+k as u64*0x100000,bytes:0x100000};
 let r=OwnedRoles{hw_state:resource(0),counter:resource(1),config:resource(2),aux:resource(3),scenes:resource(4),block_frames:resource(5),page_list:resource(6),discard:resource(7),scene_payload:resource(8),pool_a:resource(9),pool_b:resource(10)};
 let blocks=(0..g.initial_blocks).map(|j|0x1008000000+i as u64*0x800000+j as u64*0x28000).collect::<Vec<_>>();
 let(mut hw,mut count,mut cfg,mut aux,mut scenes,mut frames,mut pages)=(vec![0u8;0xc0],vec![0u8;4],vec![0u8;0x80],vec![0u8;e.aux],vec![0u8;e.scenes],vec![0u8;e.block_frames],vec![0u8;e.page_list]);
 initialize(g,r,&blocks,&mut Images{hw_state:&mut hw,counter:&mut count,config:&mut cfg,aux:&mut aux,scenes:&mut scenes,block_frames:&mut frames,page_list:&mut pages}).unwrap();
 for (n,b)in[("hw",hw),("counter",count),("cfg",cfg),("aux",aux),("scenes",scenes),("frames",frames),("pages",pages)]{std::fs::write(format!("{}/{}/{}.bin",dir,i,n),b).unwrap();}
 let mut d=[0xa5u8;0x1800];let v=bind_descriptor(&mut d,g,r,(i as u32)%g.scene_count).unwrap();std::fs::write(format!("{}/{}/descriptor.bin",dir,i),d).unwrap();let t=translations(v);let mut raw=Vec::new();for x in t{raw.extend_from_slice(&x.to_le_bytes());}std::fs::write(format!("{}/{}/translations.bin",dir,i),raw).unwrap();
 assert!(initialize(g,r,&blocks[..blocks.len()-1],&mut Images{hw_state:&mut [0;0xc0],counter:&mut[0;4],config:&mut[0;0x80],aux:&mut[],scenes:&mut[],block_frames:&mut[],page_list:&mut[]}).is_none());
 let mut bad=g;bad.capacity=1;assert!(bad.extents().is_none());bad=g;bad.initial_blocks=g.capacity;assert!(bad.extents().is_none());let mut badr=r;badr.aux=badr.scenes;assert!(badr.scene(g,0).is_none());assert!(r.scene(g,g.scene_count).is_none());
}
}''')
 for i in range(96):(a.output/str(i)).mkdir()
 cmd=['rustc','--edition=2021','-Dwarnings',str(rust),'-o',str(exe)];subprocess.run(cmd,check=True,capture_output=True);subprocess.run([str(exe),str(a.output)],check=True)
 def w(b,o,v):struct.pack_into('<I',b,o,v)
 def q(b,o,v):struct.pack_into('<Q',b,o,v)
 cases=[]
 for i in range(96):
  n=1+i%36;states=1+i%8;cap=2+i%31;blocks=1+i%(cap-1);stride=0x80+(i%7)*0x40;regstride=4<<(i%4);extra=bool(i&1)
  device=lambda k:0x1001000000+k*0x100000;user=lambda k:0x2001000000+k*0x100000;fw=lambda k:0xfffffc2200100000+k*0x100000
  pm=bytearray(0x300);gpu=bytearray(0x19000);manager=bytearray(0x100);q(manager,0x60,fw(1));q(pm,0x70,0x20000)
  for o,v in [(0x148,cap),(0x154,3+i),(0x15c,5+i),(0x1d4,1+i),(0x60,states),(0x1d8,4)]:w(pm,o,v)
  for o,v in [(0xc0,fw(5)),(0xc8,fw(2)),(0xa0,device(2)+0x40),(0x1e8,1),(0x1f0,stride),(0x1f8,0),(0x200,0x40)]:q(pm,o,v)
  _,hw,counter=reset_hw(manager,pm,bytes(0xc0),bytes(4),user(6),fw(6),device(6),device(7),cap*4)
  hw=bytearray(hw);w(hw,0x34,blocks*4);w(hw,0x54,blocks*4-1);w(hw,0x3c,blocks);w(hw,0x40,0)
  _,cfg=reset_pm(pm,bytes(0x80));cfg=bytearray(cfg);w(cfg,0,blocks)
  w(gpu,0x718,n);q(gpu,0x11188,0x800000);gpu[0xed48]=int(extra)
  _,_,scenes,actual_stride,total=scene_setup(pm,gpu,bytes(0x80),bytes(n*0x80),dict(block_alloc=1,scene_alloc=2,resource=3,discard_resource=4),list(range(blocks)),device(8),0)
  assert actual_stride==stride and total==stride*(states+extra);scenes=bytearray(scenes)
  bpm=bytearray(pm);bgpu=bytearray(gpu);q(bgpu,0x11188,0x123456+i*0x9876);w(bgpu,0x4e4,1+i%6);w(bpm,0x64,i%4);w(bpm,0x68,i&1);q(bpm,0x1e8,1+i%7);q(bpm,0x1f0,0x80);q(bpm,0x1f8,0x40)
  _,_,_,budget_stride,_=scene_setup(bpm,bgpu,bytes(0x80),bytes(n*0x80),dict(block_alloc=1,scene_alloc=2,resource=3,discard_resource=4),[],device(8),0)
  assert(a.output/str(i)/'budget.bin').read_bytes()==struct.pack('<Q',budget_stride)
  for j in range(n):q(scenes,j*0x80,fw(9)+j*regstride);q(scenes,j*0x80+8,fw(10)+j*regstride)
  frames=bytearray(cap*8);pages=bytearray(cap*16)
  for j in range(blocks):
   frame=(0x1008000000+i*0x800000+j*0x28000)>>15;w(frames,j*8,frame)
   for k in range(4):w(pages,(j*4+k)*4,frame+k)
  expected={'hw':hw,'counter':counter,'cfg':cfg,'aux':bytes(n*0x80+0x40),'scenes':scenes,'frames':frames,'pages':pages}
  for name,data in expected.items():assert(a.output/str(i)/(name+'.bin')).read_bytes()==data,(i,name)
  d=bytearray([0xa5])*0x1800;index=i%n
  for o,v in [(0x1220,user(0)),(0x908,user(0)),(0x1228,user(3)+index*0x80),(0x910,user(3)+index*0x80),(0x1230,user(4)+index*0x80),(0x918,user(4)+index*0x80),(0x1250,user(3)+n*0x80),(0x938,user(3)+n*0x80)]:q(d,o,v)
  for o,v in[(0x1258,1+i),(0x948,1+i),(0x1268,index)]:w(d,o,v)
  assert(a.output/str(i)/'descriptor.bin').read_bytes()==d
  assert(a.output/str(i)/'translations.bin').read_bytes()==struct.pack('<3Q',fw(0),fw(3)+index*0x80,fw(3)+n*0x80)
  cases.append(dict(case=i,scenes=n,states=states,capacity=cap,blocks=blocks,scene_stride=stride,extra_scene_stride=extra,whole_components=7,descriptor_whole=True,translations_exact=True))
 inputs=[source,rust,Path(__file__),ROOT/'experiments/t6040-gpu/private_pm_reset.py',ROOT/'experiments/t6040-gpu/private_pm_scene_setup.py',ROOT/'docs/evidence/2026-10-08-private-pm-native-hwpb.json',ROOT/'docs/evidence/2026-10-08-private-pm-concrete-job.json']
 report=dict(schema='m4rch.native-pm-borrowed-constructor.v9',passed=True,cases=cases,refusals_per_case=8,compile_command=cmd,inputs=[pin(p)for p in inputs],hardware_actions=[],actual_native_evidence_composed=True,triangle_fixture_used=False,linux_owned_backing_identity_required=True,ready=False)
 (a.output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=96,refusals=768)))
if __name__=='__main__':main()
