#!/usr/bin/env python3
"""Execute pinned G16 Rust serializers offline, producing a complete donor job.

This is a source-compatible comparison candidate, not a T6040 submission gate.
Only our adapter and receipts are exported; donor source remains in its repo.
"""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('linux',type=Path);p.add_argument('draw',type=Path);p.add_argument('target',type=Path);p.add_argument('output',type=Path);p.add_argument('receipt',type=Path);a=p.parse_args()
head=subprocess.check_output(['git','-C',str(a.linux),'rev-parse','HEAD'],text=True).strip()
if head!='3b85d81f656af14d0fc4bea3eef87fe040c424f9':raise ValueError('Unqualified kernel source')
src=a.linux/'drivers/gpu/drm/asahi/g16_render.rs';stamp=src.with_name('g16_stamp.rs')
if not src.exists() or not stamp.exists():raise ValueError('G16 serializers missing')
target=json.loads((a.target/'receipt.json').read_text());draw=json.loads((a.draw/'receipt.json').read_text())
assert int(target['shader_base'],0)==int(draw['shader_base'],0)==1<<40
assert target['draw_receipt_sha256']==hashlib.sha256((a.draw/'receipt.json').read_bytes()).hexdigest()
a.output.mkdir(parents=True,exist_ok=False)
# Compile the actual source file via a path module, without copying/reimplementing it.
# F32 reproduces the kernel software float's normal finite division in CPU userspace.
rs='''
#![allow(dead_code)]
mod float {
 #[derive(Clone,Copy)] pub struct F32(f32);
 impl F32 { pub fn from_bits(v:u32)->Self{Self(f32::from_bits(v))} pub fn to_bits(self)->u32{self.0.to_bits()} }
 impl From<u32> for F32 {fn from(v:u32)->Self{Self(v as f32)}}
 impl std::ops::Div for F32 {type Output=Self;fn div(self,b:Self)->Self{Self(self.0/b.0)}}
}
'''
rs+=f'#[path={json.dumps(str(src.resolve()))}] mod render;\n#[path={json.dumps(str(stamp.resolve()))}] mod g16_stamp;\n'
rs+='''
fn write(dir:&std::path::Path,name:&str,b:&[u8]){std::fs::write(dir.join(name),b).unwrap();}
fn regs(dir:&std::path::Path,name:&str,r:&[(u32,u64)]){
 let s=r.iter().map(|(n,v)|format!("{:x} {:x}\\n",n,v)).collect::<String>();write(dir,name,s.as_bytes());
}
fn main(){
 let args:Vec<String>=std::env::args().collect();let dir=std::path::Path::new(&args[1]);
 let mut p=render::Parameters::default();let start=0x1001000000;let end=render::CONTEXT_BASE+(1<<32);
 p.set_private(start,end).unwrap();p.width=64;p.height=64;p.layers=1;p.samples=1;p.utile_width=32;p.utile_height=32;
 p.sample_size=4;p.tib_blocks=2;p.utile_config=0xa000;p.multisample_control=0;p.tile_config=0x280;
 p.ppp_control=0x202;p.encoder=0x1000003000;p.scissor_array=0x1000002000;p.depth_bias_array=0x1000002040;
 p.aux_fb_flags=0xc000;p.aux_fb_page_count=0x100000;p.load_pipeline=(1<<40)+0x30c00;p.load_pipeline_bind=0xffff800000000000;
 p.store_pipeline=(1<<40)+0x30800;p.store_pipeline_bind=0;
 p.partial_load_pipeline=p.load_pipeline;p.partial_load_pipeline_bind=p.load_pipeline_bind;
 p.partial_store_pipeline=p.store_pipeline;p.partial_store_pipeline_bind=0;
 p.request_tvb_growth=true;p.tiling_admission=7;p.fragment_admission=7;p.cycle=0x240030;
 p.tiling_gate=0xa900400020;p.fragment_gate=0xd500400020;
 p.tiling_lifecycle=0x08009f520900a6bb;p.fragment_lifecycle=0x08009f520900a6ba;
 p.tiling_work_stamp=0x120;p.fragment_work_stamp=0x121;p.completion_control=4;p.layermeta=p.heapmeta;
 let a=render::Addresses::bootstrap();assert!(p.valid());
 write(dir,"ta-work.bin",&p.tiling_work(&a).unwrap());write(dir,"3d-work.bin",&p.fragment_work(&a).unwrap());
 write(dir,"ta-microsequence.bin",&a.tiling_microsequence());write(dir,"3d-microsequence.bin",&a.fragment_microsequence());
 write(dir,"ta-prelude.bin",&a.tiling_prelude(11));write(dir,"3d-prelude.bin",&a.fragment_prelude());
 regs(dir,"ta-registers.txt",&p.tiling_registers().unwrap());regs(dir,"3d-registers.txt",&p.fragment_registers().unwrap());
 let pool=render::OperandPool::new(start,end).unwrap();let mut b=[0;0x4000];
 let mut ranges=String::new();let mut nonzero=0;
 for offset in (0..render::PRIVATE_SIZE).step_by(0x4000){
  render::private_page(&pool,offset,&mut b).unwrap();
  if b.iter().any(|v|*v!=0){write(dir,&format!("private-{:x}.bin",offset),&b);nonzero+=1;}
 }
 for (va,off,len) in render::private_aliases(&pool){ranges+=&format!("{:x} {:x} {:x}\\n",va,off,len);}
 write(dir,"private-aliases.txt",ranges.as_bytes());
 for (va,len) in a.private_regions(){for offset in (0..len).step_by(0x4000){
  a.private_page(va+offset as u64,&mut b).unwrap();write(dir,&format!("transport-{:x}.bin",va+offset as u64),&b);
 }}
 write(dir,"operand-support.bin",&pool.support(3,a.render_shared_state));
 let (tilemap,tpc)=p.scratch_sizes().unwrap();
 println!("{} {} {} {} {}",render::PRIVATE_SIZE,tilemap,tpc,nonzero,pool.end().unwrap());
 // Exercise the source's scratch-size/parameter acceptance through dimensions,
 // samples, utiles and layers; numeric independent comparisons follow in Python.
 let mut sweep=String::new();
 for w in [1u64,31,32,33,64,255,256,16384]{for h in [1u64,33,64,129,16384]{
  for (ux,uy) in [(32u64,32u64),(32,16),(16,16)]{for samples in [1u64,2,4]{for layers in [1u64,2,4]{
   p.width=w;p.height=h;p.samples=samples;p.layers=layers;p.utile_width=ux;p.utile_height=uy;
   let (t,c)=p.scratch_sizes().unwrap();sweep+=&format!("{} {} {} {} {} {} {} {}\\n",w,h,ux,uy,samples,layers,t,c);
  }}}
 }}write(dir,"scratch-sweep.txt",sweep.as_bytes());
}
'''
adapter=a.output/'source-adapter.rs';adapter.write_text(rs);exe=a.output/'source-adapter'
subprocess.run(['rustc','--edition=2021','-D','warnings','-O',str(adapter),'-o',str(exe)],check=True)
run=subprocess.run([str(exe.resolve()),str(a.output.resolve())],check=True,text=True,capture_output=True)
private_size,tilemap,tpc,nonzero,pool_end=map(int,run.stdout.split())
counts={'scratch_geometry':0,'packed_registers':0,'work_microsequence_links':0}
for line in (a.output/'scratch-sweep.txt').read_text().splitlines():
 w,h,ux,uy,samples,layers,t,c=map(int,line.split());tx=(w+31)//32;ty=(h+31)//32;mx=(((tx+3)//4)+3)&~3;my=(((ty+3)//4)+3)&~3
 mul=mx*my*(32//ux)*(32//uy);expected_t=(5*mul//4*64*layers+16383)&~16383;expected_c=(2*mul*64*layers+16383)&~16383
 assert (t,c)==(expected_t,expected_c);counts['scratch_geometry']+=1
registers={}
for stage,name,offset in [('ta','ta-work.bin',0x40),('3d','3d-work.bin',0x80)]:
 records=[tuple(int(v,16) for v in line.split()) for line in (a.output/(stage+'-registers.txt')).read_text().splitlines()]
 work=(a.output/name).read_bytes();packed=b''.join(struct.pack('<IQ',r,v) for r,v in records)
 assert work[offset:offset+len(packed)]==packed;counts['packed_registers']+=len(records)
 registers[stage]=[{'register':hex(r),'flag':r&1,'value':hex(v)} for r,v in records]
links=[('ta-work.bin',0x770,0xfffffc20c03a2340),('3d-work.bin',0x14,0xfffffc20c0469680),('ta-microsequence.bin',0x14,0xfffffc20c006a940+0x40),('3d-microsequence.bin',0x14,0xfffffc20c0161b40+0x80)]
for name,off,value in links:assert struct.unpack_from('<Q',(a.output/name).read_bytes(),off)[0]==value;counts['work_microsequence_links']+=1
report={'kernel_commit':head,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'stamp_source_sha256':hashlib.sha256(stamp.read_bytes()).hexdigest(),'adapter_sha256':hashlib.sha256(rs.encode()).hexdigest(),'target_receipt_sha256':hashlib.sha256((a.target/'receipt.json').read_bytes()).hexdigest(),'draw_receipt_sha256':hashlib.sha256((a.draw/'receipt.json').read_bytes()).hexdigest(),'comparisons':counts,'storage':{'private_bytes':private_size,'tilemap_bytes':tilemap,'tpc_bytes':tpc,'nonzero_private_pages':nonzero,'pool_end':hex(pool_end)},'registers':registers,'files':{x.name:{'bytes':x.stat().st_size,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in a.output.glob('*.bin')},'qualification':'Actual pinned G16 donor Rust render serializers execute in CPU userspace. Work records, microsequences, preludes, register lists and initialized sparse storage produced. Scratch sizes independently checked for 1080 cases; packed register bytes and selected cross-links checked. This donor is T8132, not qualified T6040. Bootstrap addresses, pool sizes, 11-block TVB, queue/event/context identity and lifecycle constants require adaptation to our graph. Parameters include explicit candidate constants; source validity only checks bounds, not firmware/GPU readiness. No live mapping or command submission. No GPU completion/readback proof. Full job files must not be directly submitted on T6040.'}
a.receipt.write_text(json.dumps(report,indent=2)+'\n');(a.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(counts,report['storage'])
