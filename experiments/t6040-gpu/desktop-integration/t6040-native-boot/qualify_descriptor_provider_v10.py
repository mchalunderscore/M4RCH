#!/usr/bin/env python3
"""Bounded named native descriptor correlation; never a completeness claim."""
import json,subprocess,hashlib
from pathlib import Path
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[3]
OUT=ROOT/'out/gpu-gravity-native-descriptor-provider-v10-qualification-v4';OUT.mkdir(exist_ok=False)
base=ROOT/'out/gpu-gravity-normal-boot-v9-clock/source/linux/drivers/gpu/drm/asahi/g16_render.rs'
(OUT/'parameters.rs').write_text(base.read_text().split('pub(crate) fn pack_registers')[0])
rs='''#![allow(dead_code)]
#[path="BASE"] mod g16_render;
#[path="KIT/g16_t6040_descriptor_v10.rs"] mod g16_t6040_descriptor_v10;
use g16_t6040_descriptor_v10 as descriptor;
#[path="ROOT/out/private-apple/native-rce-semantic-v9.rs"] mod g16_native_rce_semantic_v9;
#[path="KIT/g16_t6040_rce_ram_v9.rs"] mod typed;
#[path="KIT/g16_t6040_descriptor_provider_v10.rs"] mod provider;
#[path="KIT/g16_t6040_render_envelope_v9.rs"] mod envelope;
#[path="KIT/g16_t6040_render_policy_v9.rs"] mod g16_t6040_render_policy_v9;
#[path="KIT/g16_t6040_resource_address_v9.rs"] mod g16_t6040_resource_address_v9;
fn main(){
 assert!(!descriptor::COMPLETE);
 let sizes=[1u64,31,32,33,65,127,640,1024,8193,16384];
 for i in 0..40u64 {
  let a=0x20000000+i*0x10000;
  let p=g16_render::Parameters {
   width:sizes[i as usize%10],height:sizes[(i as usize*3+1)%10],layers:1+i%4,
   utile_width:if i%3==0 {16}else{32},utile_height:if i%3<2 {16}else{32},
   samples:[1,2,4][i as usize%3],sample_size:8+(i%4)*8,
   tib_blocks:((8+(i%4)*8)*(if i%3==0 {16}else{32})*(if i%3<2 {16}else{32})*[1,2,4][i as usize%3]).div_ceil(2048),
   ppp_control:2|((i%2)<<9)|((i/2)%2),process_empty_tiles:i%2!=0,
   tile_config:0x280|u64::from(1+i%4>1)|if i%2!=0 {0x10000}else{0},
   tilemap:a,heapmeta:a+0x4000,layermeta:a+0x8000,tpc:a+0xc000,
   encoder:a+0x10000,deflake_1:a+0x14000,deflake_2:a+0x18000,deflake_3:a+0x1c000,
   depth_bias_array:a+0x20000,scissor_array:a+0x24000,occlusion_query_base:a+0x28000,
   load_pipeline:a+0x30000,load_pipeline_bind:0x80000000+i,
   store_pipeline:a+0x34000,store_pipeline_bind:0x90000000+i,
   partial_load_pipeline:a+0x38000,partial_load_pipeline_bind:0xa0000000+i,
   partial_store_pipeline:a+0x3c000,partial_store_pipeline_bind:0xb0000000+i,
   depth_buffer:a+0x40000,stencil_buffer:a+0x44000,depth_stride:256+i*64,
   stencil_stride:64+i*16,depth_aux_buffer:a+0x48000,stencil_aux_buffer:a+0x4c000,
   depth_aux_stride:32+i*8,stencil_aux_stride:16+i*4,depth_flags:0x400+i,
   depth_dimensions:0x3000200+i,depth_clear_value_bits:0x3f800000+i,
   stencil_clear_value:i,aux_fb:a+0x50000,aux_fb_flags:0x100+i,
   aux_fb_page_count:1+i,merge_upper_x_bits:0x3f000000+i,
   merge_upper_y_bits:0x3e000000+i,utile_config:0x1000+i,
   multisample_control:0x8000+i,
   cycle:0x240000+i*0x30,scene_slot:i%36,
   tiling_admission:7+i,fragment_admission:7+i,
   tiling_gate:(0xa9+i)<<32|0x00400020,fragment_gate:(0xd5+i)<<32|0x00400020,
   tiling_lifecycle:(0x08009f52+i)<<32|0x0900a6bb,
   fragment_lifecycle:(0x08009f52+i)<<32|0x0900a6ba,
   tiling_work_stamp:0x120+(i%31),fragment_work_stamp:0x121+(i%31),
   ta_status:0x100100000+i*0x10000,fragment_status:0x100200000+i*0x10000,
   completion_control:4+i,..Default::default()
  };
  let ta=descriptor::UserAddresses{tilemap:0xfffffc2000200000+i*0x10000,
   layer_metadata:0xfffffc2000300000+i*0x10000,heap_metadata:0xfffffc2000400000+i*0x10000,
   tpc:0xfffffc2000500000+i*0x10000,encoder:p.encoder,
   deflake_1:p.deflake_1,deflake_2:p.deflake_2,deflake_3:p.deflake_3};
  let d=descriptor::build(&p,&ta).unwrap();
  for kind in [typed::Kind::Tiling,typed::Kind::Fragment] {
   let phase=match kind {typed::Kind::Tiling=>provider::Phase::Tiling,typed::Kind::Fragment=>provider::Phase::Fragment};
   let policy=provider::Policy {experimental_linux_lifecycle:true,scene_header:0x80001+(i%36)*4,
    context_special_mode:false,tiling_initial_barrier:true,suppress_ta_timestamps:true,
    suppress_fragment_timestamps:true,descriptor_113b:0,descriptor_1141:0,descriptor_1142:0};
   let input=provider::prepare(&p,&ta,phase,policy).unwrap();
   let mut dd=[0;0x1800];let mut cc=[0;0x3000];let mut cx=[0;0x100];let mut sc=[0;0x100];
   let addr=provider::prepare_into(&mut dd,&mut cc,&mut cx,&mut sc,&p,&ta,phase,policy).unwrap();
   assert_eq!(dd,input.descriptor);assert_eq!(cc,input.command);assert_eq!(cx,input.context);assert_eq!(sc,input.scene);assert_eq!(addr,input.status_resource_gpu);
   let mut bad=p;bad.ppp_control|=0x100;
   assert!(provider::prepare_into(&mut dd,&mut cc,&mut cx,&mut sc,&bad,&ta,phase,policy).is_none());
   let mut bad=p;bad.tib_blocks^=1;
   assert!(provider::prepare_into(&mut dd,&mut cc,&mut cx,&mut sc,&bad,&ta,phase,policy).is_none());
   let mut bad=p;bad.tile_config^=0x10000;
   assert!(provider::prepare_into(&mut dd,&mut cc,&mut cx,&mut sc,&bad,&ta,phase,policy).is_none());
   let mut bad=p;bad.sampler_array=0x1000;bad.sampler_count=1;
   assert!(provider::prepare_into(&mut dd,&mut cc,&mut cx,&mut sc,&bad,&ta,phase,policy).is_none());
   let mut bad=p;bad.tiling_work_stamp=0x140;bad.fragment_work_stamp=0x140;
   assert!(provider::prepare_into(&mut dd,&mut cc,&mut cx,&mut sc,&bad,&ta,phase,policy).is_none());
   let mut bad_policy=policy;bad_policy.experimental_linux_lifecycle=false;
   assert!(provider::prepare_into(&mut dd,&mut cc,&mut cx,&mut sc,&p,&ta,phase,bad_policy).is_none());
   let mut descriptor=input.descriptor;let mut command=input.command;let mut scratch=[0;0x400];
   let context=input.context;let scene=input.scene;
   let providers=typed::Providers{gpu_clusters:2,address_bit47:false,ppp_bit9:provider::required_ppp_bit9(&p).unwrap(),descriptor_policy:0,
    fragment_policy:0,controller_mode:0,controller_feature:0,
    command_gpu:0xfffffc2000600000+i*0x10000,parameter_gpu:input.status_resource_gpu};
   let mut b=typed::Backing{command:&mut command,descriptor:&mut descriptor,scratch:&mut scratch,
    context:&context,scene:&scene,providers};b.produce(kind).unwrap();
   let envelope_context=[0;0x600];let stack=[0;0x100];
   match kind {
    typed::Kind::Tiling=>{
     let binding=envelope::TaBindings{context:&envelope_context,stack:&stack,serial:i,
      firmware_translations:[0;3],completion_firmware:providers.parameter_gpu,x26:0,w21:0,w22:0,
      accelerator_mode:0,aperture_flags:0};
     envelope::tiling(&mut command[..envelope::TA_BYTES],&mut descriptor,&binding).unwrap();
     assert_eq!(u64::from_le_bytes(command[0x8ce..0x8d6].try_into().unwrap()),p.tiling_lifecycle&0xffff_ffff);
    },
    typed::Kind::Fragment=>{
     let source=[0;0x400];let frame=[0;24];
     let binding=envelope::FragmentBindings{source:&source,frame:&frame,stack:&stack,
      context:&envelope_context,serial:i,counter:i as u32,w21:0,w22:0,
      firmware_translations:[0;3],completion_firmware:providers.parameter_gpu,
      epochs:[1,1],capacity:256,initial:0,aperture_flags:0};
     envelope::fragment(&mut command[..envelope::FRAGMENT_BYTES],&mut descriptor,&binding).unwrap();
     assert_eq!(u64::from_le_bytes(command[0x2168..0x2170].try_into().unwrap()),p.fragment_lifecycle&0xffff_ffff);
    }
   }
   let (off,meta,label)=match kind{typed::Kind::Tiling=>(0x60,0x768,"ta"),typed::Kind::Fragment=>(0xa0,0x7a8,"3d")};
   let n=u16::from_le_bytes(command[meta..meta+2].try_into().unwrap()) as usize;
   print!("{} {}",i,label);
   for j in 0..n {let o=off+j*12;let h=u32::from_le_bytes(command[o..o+4].try_into().unwrap());
    let v=u64::from_le_bytes(command[o+4..o+12].try_into().unwrap());print!(" {:x}:{:x}",h&0x3fff8,v);}
   println!();
  }
  let mut bad=p;bad.width=0;assert!(descriptor::build(&bad,&ta).is_none());
  let mut bad=p;bad.depth_clear_value_bits=1<<32;assert!(descriptor::build(&bad,&ta).is_none());
  let mut bad=ta;bad.heap_metadata|=1;assert!(descriptor::build(&p,&bad).is_none());
 }
}
'''.replace('BASE',str(OUT/'parameters.rs')).replace('KIT',str(KIT)).replace('ROOT',str(ROOT))
(OUT/'named-host.rs').write_text(rs)
compile=subprocess.run(['rustc','--edition=2021','-Awarnings','-Copt-level=2',str(OUT/'named-host.rs'),'-o',str(OUT/'named-host')],capture_output=True,text=True)
(OUT/'compile.log').write_text(compile.stdout+compile.stderr);assert compile.returncode==0,compile.stderr
run=subprocess.run([str(OUT/'named-host')],capture_output=True,text=True);(OUT/'run.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr
sizes=[1,31,32,33,65,127,640,1024,8193,16384]; checks=0
for line in run.stdout.splitlines():
 words=line.split();i=int(words[0]);kind=words[1];regs={}
 for word in words[2:]:
  k,v=word.split(':');regs.setdefault(int(k,16),[]).append(int(v,16))
 a=0x20000000+i*0x10000;width=sizes[i%10];height=sizes[(i*3+1)%10]
 ux=2 if i%3==0 else 1;uy=2 if i%3<2 else 1
 tx=(width+31)//32;ty=(height+31)//32;mx=((tx+3)//4+3)&~3;my=((ty+3)//4+3)&~3
 screen=(ty-1)<<12|tx-1;size1=(5*mx*my*ux*uy+3)//4
 if kind=='ta':
  expected={0x10120:2|((i%2)<<9)|((i//2)%2),0x1ca30:0x240000+i*0x30,0x1c830:7+i,0xa5a0:(0xa9+i)<<32|0x00400020,0x1ca10:(0x08009f52+i)<<32|0x0900a6bb,0x14320:0x120+i%31,0x14308:4+i,0x14318:(0x100100000+i*0x10000)|1,0x1c038:0xfffffc2000200000+i*0x10000,0x1c078:0xfffffc2000300000+i*0x10000,
   0x1c030:0xfffffc2000400000+i*0x10000|1<<63,0x1c0a0:0xfffffc2000500000+i*0x10000,
   0x10128:(width-1)|((height-1)<<16),0x101b8:screen,
   0x1c068:3*mx|((2*mx)<<9)|(mx<<18),0x1c070:3*my|((2*my)<<9)|(my<<18),
   0x1c080:mx*my,0x1c0a8:2*mx*my*ux*uy,0x1c0b0:size1,
   0x10148:0x1000+i,0x10138:0x8000+i,0x10110:a+0x14000,0x10118:a+0x18000}
 else:
  sample_bytes=8+i%4*8; samples=[1,2,4][i%3]
  blocks=(sample_bytes*(16 if i%3==0 else 32)*(16 if i%3<2 else 32)*samples+2047)//2048
  tib=(blocks&63) if samples==1 else ((samples*(2 if blocks>32 else 1))<<16)|(blocks&63)
  expected={0x10038:0x280|(1 if 1+i%4>1 else 0)|(0x10000 if i%2 else 0),0x10050:tib,0x1ca28:0x240000+i*0x30,0x1c838:7+i,0xa5a8:(0xd5+i)<<32|0x00400020,0x160e0:(0x08009f52+i)<<32|0x0900a6ba,0x10420:0x121+i%31,0x14048:4+i,0x14080:(0x100200000+i*0x10000)|1,0x15210:(height<<32)|width,0x100b0:(my*uy)|((mx*ux)<<16),0x100d8:screen,
   0x16428:a,0x16060:a+0x8000,0x16098:a+0x4000,
   0x15100:a+0x20000,0x15108:a+0x24000,0x15310:a+0x28000,
   0x15368:0x80000000+i,0x15370:a+0x30000,0x15378:0x90000000+i,0x15380:a+0x34000,
   0x15318:0x400+i,0x15320:0x3000200+i,0x15328:a+0x40000,0x15338:a+0x44000,
   0x15400:256+i*64,0x15408:64+i*16,0x153c0:a+0x48000,0x153d0:a+0x4c000,
   0x15410:32+i*8,0x15418:16+i*4,0x16460:a+0x50000,
   0x15020:0x100+i,0x15048:1+i,0x15130:0x3f000000+i,0x15138:0x3e000000+i}
 for reg,value in expected.items():
  assert value in regs.get(reg,[]),(i,kind,hex(reg),hex(value),list(map(hex,regs.get(reg,[]))))
  checks+=1
pin=lambda p:{'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
report={'schema':'native-named-descriptor-provider-v10.qualification.v4','compile_returncode':compile.returncode,
 'run_returncode':run.returncode,'renders':40,'native_producer_runs':80,'named_register_checks':checks,
 'refusals':600,'borrowed_writer_whole_output_checks':80,'connected_RCE_envelope_lifecycle_checks':80,'complete':False,'runtime_enabled':False,'hardware_actions':[],
 'pins':[pin(p) for p in [Path(__file__),KIT/'g16_t6040_descriptor_v10.rs',base,KIT/'g16_t6040_rce_ram_v9.rs',KIT/'g16_t6040_descriptor_provider_v10.rs',KIT/'g16_t6040_resource_address_v9.rs',KIT/'g16_t6040_render_policy_v9.rs',KIT/'g16_t6040_render_envelope_v9.rs',ROOT/'out/private-apple/native-rce-semantic-v9.rs',ROOT/'out/gpu-gravity-native-descriptor-policy-v9/dependency-trace.json']],
 'unresolved':['Native TA user/aperture conversion now source-qualified; actual owning aperture base remains caller-retained mapping input.',
 'Admission/cycle/gate/lifecycle/stamp/status fields now bound through descriptor/context/scene/command inputs; lifecycle low word explicitly Linux experimental policy.',
 'PM scene/resource CPU lookup inputs and sampler/residency construction require typed owned providers.',
 'Ordinary Mesa PPP2/3/202/203, sample_size->TIB and tile policy are now typed and qualified; nonordinary disabled clamp/default point size and nonzero samplers explicitly refuse.',
 'Partial pipeline fields are copied using native processRenderSetup evidence; conditional phase flags still need integration.'],
 'scope':'Borrowed ordinary Mesa descriptor/provider: dynamic parameters and PPP/sample/tile policy through portable native producer; caller/SKU/kernel join and hardware acceptance remain separate.'}
(OUT/'named-qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='pins'}))
