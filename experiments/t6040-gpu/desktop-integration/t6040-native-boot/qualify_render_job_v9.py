#!/usr/bin/env python3
"""Offline composed native render-job qualification; no hardware or publication."""
import json,subprocess,hashlib
from pathlib import Path
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[3]
OUT=ROOT/'out/gpu-gravity-native-render-job-v9-qualification-v6';OUT.mkdir(exist_ok=False)
base=ROOT/'out/gpu-gravity-normal-boot-v9-clock/source/linux/drivers/gpu/drm/asahi/g16_render.rs'
(OUT/'parameters.rs').write_text(base.read_text().split('pub(crate) fn pack_registers')[0])
rs='''#![allow(dead_code)]
#[path="BASE"] mod g16_render;
#[path="KIT/g16_t6040_descriptor_v10.rs"] mod g16_t6040_descriptor_v10;
use g16_t6040_descriptor_v10 as descriptor;
#[path="ROOT/out/private-apple/native-rce-semantic-v9.rs"] mod g16_native_rce_semantic_v9;
#[path="KIT/g16_t6040_rce_ram_v9.rs"] mod g16_t6040_rce_ram_v9;
use g16_t6040_rce_ram_v9 as typed;
#[path="KIT/g16_t6040_descriptor_provider_v10.rs"] mod provider;
#[path="KIT/g16_t6040_render_envelope_v9.rs"] mod g16_t6040_render_envelope_v9;
use g16_t6040_render_envelope_v9 as envelope;
#[path="KIT/g16_t6040_render_policy_v9.rs"] mod g16_t6040_render_policy_v9;
#[path="KIT/g16_t6040_resource_address_v9.rs"] mod g16_t6040_resource_address_v9;
#[path="KIT/g16_t6040_render_job_v9.rs"] mod job;
#[path="KIT/g16_t6040_postkick_v9.rs"] mod g16_t6040_postkick_v9;
#[path="KIT/g16_t6040_ta_sku_v9.rs"] mod g16_t6040_ta_sku_v9;
#[path="KIT/g16_t6040_fragment_sku_v9.rs"] mod g16_t6040_fragment_sku_v9;
#[path="KIT/g16_t6040_ksm_work_v8.rs"] mod g16_t6040_ksm_work_v8;
#[path="KIT/g16_t6040_work_layout_v9.rs"] mod g16_t6040_work_layout_v9;
fn q(x:&[u8],o:usize)->u64{u64::from_le_bytes(x[o..o+8].try_into().unwrap())}
fn w(x:&[u8],o:usize)->u32{u32::from_le_bytes(x[o..o+4].try_into().unwrap())}
fn h(x:&[u8],o:usize)->u16{u16::from_le_bytes(x[o..o+2].try_into().unwrap())}
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

  for kind in [typed::Kind::Tiling,typed::Kind::Fragment] {
   let phase=match kind {typed::Kind::Tiling=>provider::Phase::Tiling,typed::Kind::Fragment=>provider::Phase::Fragment};
   let policy=provider::Policy {experimental_linux_lifecycle:true,scene_header:0x80001+(i%36)*4,
    context_special_mode:false,tiling_initial_barrier:i%2!=0,suppress_ta_timestamps:i%3!=0,
    suppress_fragment_timestamps:i%2!=0,descriptor_113b:0,descriptor_1141:0,descriptor_1142:0};
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
   let layout=g16_t6040_work_layout_v9::Layout::new(0xfffffc2200000000+i*0x1c000).unwrap();
   let stage=layout.stages[match kind {typed::Kind::Tiling=>0,typed::Kind::Fragment=>1}];
   let mut descriptor=input.descriptor;let mut command=input.command;let mut scratch=[0;0x400];

   let context=input.context;let scene=input.scene;
   let providers=typed::Providers{gpu_clusters:2,address_bit47:false,ppp_bit9:provider::required_ppp_bit9(&p).unwrap(),descriptor_policy:0,
    fragment_policy:0,controller_mode:0,controller_feature:0,
    command_gpu:stage.command.device,parameter_gpu:input.status_resource_gpu};
   let envelope_context=[0;0x600];let stack=[0;0x100];
   let deps=[g16_t6040_ksm_work_v8::Dependency{converted_timestamp:i*256,queue_id:1}];
   let mut scheduler=g16_t6040_ksm_work_v8::Bindings{timestamp:0x1000+i,queue_id:(i%24)as u8,
    priority:(i%4)as u8,capacity:256,previous:i,command:0,firmware_queue:0xfffffc2000400000+i*0x1000,
    aperture_address:0,aperture_index:0,aperture_count:0,alternate_kind:false,extra_flag:false,
    dependencies:&deps,qos:(i as u8,16,2),rce_kind:match kind{typed::Kind::Tiling=>0,typed::Kind::Fragment=>1},
    register_lists:[g16_t6040_ksm_work_v8::RegisterList{gpu_address:0,count:0};4],
    masks:[0xff,0xff,0,0],auxiliary:stage.shared_state_fw};
   let mut record=[0xa5;0x200];let mut stream=[0xa5;0x2000];let mut sku_stack=[0;0x300];
   let ta_construction=envelope::TaBindings{context:&envelope_context,stack:&stack,serial:i,
    firmware_translations:[stage.shared_state_fw,stage.driver_stamp_fw,layout.bm_fw],
    completion_firmware:providers.parameter_gpu,x26:stage.driver_stamp_fw,w21:1,w22:2,
    accelerator_mode:0,aperture_flags:0};
   let source=[0;0x400];let frame=[0;24];
   let fragment_construction=envelope::FragmentBindings{source:&source,frame:&frame,stack:&stack,
    context:&envelope_context,serial:i,counter:i as u32,w21:1,w22:2,
    firmware_translations:[stage.shared_state_fw,stage.driver_stamp_fw,layout.bm_fw],
    completion_firmware:providers.parameter_gpu,epochs:[1,2],capacity:256,initial:i,aperture_flags:0};
   let ta_sku=g16_t6040_ta_sku_v9::Bindings{command_gpu:stage.command.device,
    translated_state:stage.shared_state_fw,fw_state:stage.shared_state_fw,state:stage.shared_state_fw+0x100,
    counter:stage.driver_stamp_fw,resource_type:0,context_id:1,resource_map:providers.parameter_gpu,
    feature:0,channel_config:0,timestamp_index:i as u32,stream_fw:stage.sku_fw};
   let fragment_sku=g16_t6040_fragment_sku_v9::Bindings{command_gpu:stage.command.device,
    parameter_gpu:stage.shared_state_fw,state_fw:stage.shared_state_fw+0x100,
    resource_type:0,resource_map:providers.parameter_gpu,context_id:1,
    accelerator_config:0,accelerator_feature:0,channel_config:0,mode:0,
    timestamp_index:i as u32,stream_fw:stage.sku_fw,omit_end_timestamp:i%3==0};
   let mut backing=typed::Backing{command:&mut command,descriptor:&mut descriptor,scratch:&mut scratch,
    context:&context,scene:&scene,providers};
   let result=match kind{
    typed::Kind::Tiling=>job::tiling(&mut backing,&ta_construction,ta_sku,&mut stream,stage,&mut scheduler,&mut record),
    typed::Kind::Fragment=>job::fragment(&mut backing,&fragment_construction,fragment_sku,&mut stream,
     &mut sku_stack,stage,&mut scheduler,&mut record)}.unwrap();
   assert_eq!(result.submitted_timeline,scheduler.timestamp);
   // Supplied accumulated descriptor count is tested for exact native truncation;
   // this does not fabricate an event baseline or assert padding count is zero.
   let descriptor_count=(i as u32)*0x10001+1;let mode=0x100+i as u32;
   let original_queue=scheduler.queue_id;let original_timestamp=scheduler.timestamp;
   scheduler.queue_id^=1;scheduler.timestamp+=1;
   let mut transport=[0xa5;32];result.write_transport(&mut transport,descriptor_count,mode).unwrap();
   assert_eq!(w(&transport,0),14);assert_eq!(h(&transport,4),original_queue as u16);
   assert_eq!(h(&transport,6),descriptor_count as u16);assert_eq!(transport[8],mode as u8);
   assert_eq!(q(&transport,9),original_timestamp);
   assert_eq!(w(&transport,17),match kind{typed::Kind::Tiling=>0,typed::Kind::Fragment=>1});
   assert!(transport[21..].iter().all(|v|*v==0xa5));
   let mut short_transport=[0xa5;23];assert!(result.write_transport(&mut short_transport,descriptor_count,mode).is_none());
   assert_eq!(short_transport,[0xa5;23]);
   assert_eq!(h(&transport,4)as u64,(q(&record,0)>>42)&127);
   scheduler.queue_id=original_queue;scheduler.timestamp=original_timestamp;
   let rounded=(result.stream_bytes+63)&!63;
   println!("STREAM {} {} {} {}",i,match kind{typed::Kind::Tiling=>"ta",typed::Kind::Fragment=>"3d"},result.stream_bytes,rounded);
   assert!(result.stream_bytes<=rounded && rounded<=stream.len());
   assert_eq!(w(&stream,result.stream_bytes-4),0x40000002);
   assert!(stream[result.stream_bytes..rounded].iter().all(|v|*v==0));
   assert!(stream[rounded..].iter().all(|v|*v==0xa5));
   let (sku_pointer,sku_length,lowword,nlists)=match kind{
    typed::Kind::Tiling=>(0x790,0x798,0x8ce,1),typed::Kind::Fragment=>(0x14,0x1c,0x2168,4)};
   assert_eq!(q(&command,sku_pointer),stage.sku_fw);assert_eq!(w(&command,sku_length)as usize,rounded);
   assert_eq!(q(&command,lowword),match kind{typed::Kind::Tiling=>p.tiling_lifecycle,typed::Kind::Fragment=>p.fragment_lifecycle}&0xffff_ffff);
   assert_eq!(q(&record,0x10),stage.command.firmware);assert_eq!(q(&record,0x18),scheduler.firmware_queue);
   let expected_timeline=(scheduler.timestamp&0xffffff0000000000)|((scheduler.timestamp+if scheduler.timestamp&255==255{256}else{0})&0xffffffff00)|((scheduler.timestamp+1)%256);
   assert_eq!(result.next_timeline,expected_timeline);
   for index in 0..4 {
    let (count,pointer)=if index<nlists {
     let off=if nlists==1{0x60}else{0xa0+index*0x720};
     let meta=if nlists==1{0x760}else{0x7a0+index*0x720};
     let export=if nlists==1{0x1568}else{0x828+index*16};
     let backing=h(&command,meta+8);let count=h(&descriptor,export+8);
     assert_eq!(q(&command,meta),stage.command.device+off as u64);
     assert_eq!(q(&descriptor,export),q(&command,meta));
     assert_eq!(h(&command,meta+10)as u32,backing as u32*12);assert!(count<=backing);
     (count,if count==0{0}else{q(&descriptor,export)})
    }else{(0,0)};
    let encoded=q(&record,0x150+index*8);
    assert_eq!((encoded>>43)&127,count as u64);
    assert_eq!(encoded&((1<<38)-1),(pointer>>5)&((1<<38)-1));
    assert_eq!(scheduler.register_lists[index].count,count as u8);
    println!("META {} {} {} {} {}",i,if nlists==1{"ta"}else{"3d"},index,count,if index<nlists{h(&command,if nlists==1{0x768}else{0x7a8+index*0x720})}else{0});
   }
   // Address refusals happen before any mutation. Later failures discard all
   // outputs; the harness never treats internal SKU publication as queue send.
   let saved_command=command;let saved_descriptor=descriptor;let saved_record=record;let saved_stream=stream;
   let mut wrong=stage;wrong.command.device+=32;
   let mut backing=typed::Backing{command:&mut command,descriptor:&mut descriptor,scratch:&mut scratch,context:&context,scene:&scene,providers};
   let bad=match kind{typed::Kind::Tiling=>job::tiling(&mut backing,&ta_construction,ta_sku,&mut stream,wrong,&mut scheduler,&mut record),
    typed::Kind::Fragment=>job::fragment(&mut backing,&fragment_construction,fragment_sku,&mut stream,&mut sku_stack,wrong,&mut scheduler,&mut record)};
   assert!(matches!(bad,Err(job::Error::Address)));assert_eq!(command,saved_command);assert_eq!(descriptor,saved_descriptor);assert_eq!(record,saved_record);assert_eq!(stream,saved_stream);
   // Insufficient SKU extent must not publish its pointer or scheduler record.
   command=input.command;descriptor=input.descriptor;record=[0xa5;0x200];let mut short=[0xa5;0x100];
   let mut backing=typed::Backing{command:&mut command,descriptor:&mut descriptor,scratch:&mut scratch,context:&context,scene:&scene,providers};
   let bad=match kind{typed::Kind::Tiling=>job::tiling(&mut backing,&ta_construction,ta_sku,&mut short,stage,&mut scheduler,&mut record),
    typed::Kind::Fragment=>job::fragment(&mut backing,&fragment_construction,fragment_sku,&mut short,&mut sku_stack,stage,&mut scheduler,&mut record)};
   assert!(matches!(bad,Err(job::Error::Stream)));assert_ne!(q(&command,sku_pointer),stage.sku_fw);assert!(record.iter().all(|v|*v==0xa5));assert!(short.iter().all(|v|*v==0xa5));
   // Scheduler validation can fail after internal command construction; none
   // of those partially built buffers are publishable on Err.
   command=input.command;descriptor=input.descriptor;record=[0xa5;0x200];scheduler.priority=4;
   let mut backing=typed::Backing{command:&mut command,descriptor:&mut descriptor,scratch:&mut scratch,context:&context,scene:&scene,providers};
   let bad=match kind{typed::Kind::Tiling=>job::tiling(&mut backing,&ta_construction,ta_sku,&mut stream,stage,&mut scheduler,&mut record),
    typed::Kind::Fragment=>job::fragment(&mut backing,&fragment_construction,fragment_sku,&mut stream,&mut sku_stack,stage,&mut scheduler,&mut record)};
   assert!(matches!(bad,Err(job::Error::Scheduler)));assert!(record.iter().all(|v|*v==0));
   command=saved_command;
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
compile=subprocess.run(['rustc','--edition=2021','-Dwarnings','-Copt-level=2',str(OUT/'named-host.rs'),'-o',str(OUT/'named-host')],capture_output=True,text=True)
(OUT/'compile.log').write_text(compile.stdout+compile.stderr);assert compile.returncode==0,compile.stderr
run=subprocess.run([str(OUT/'named-host')],capture_output=True,text=True);(OUT/'run.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr
sizes=[1,31,32,33,65,127,640,1024,8193,16384]; checks=0
metadata=[];stream_extents=[]
for line in run.stdout.splitlines():
 words=line.split();
 if words[0]=='META':
  metadata.append({'render':int(words[1]),'phase':words[2],'lane':int(words[3]),'exported_count':int(words[4]),'backing_count':int(words[5])});continue
 if words[0]=='STREAM':
  stream_extents.append({'render':int(words[1]),'phase':words[2],'actual_bytes':int(words[3]),'rounded_bytes':int(words[4])});continue
 i=int(words[0]);kind=words[1];regs={}
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
assert len(metadata)==320 and len(stream_extents)==80
assert len({row['exported_count'] for row in metadata if row['phase']=='ta' and row['lane']==0})>1
assert all(row['exported_count']<=row['backing_count'] for row in metadata)
# Reuse existing native component qualifications only when their exact module
# pins match. These are prior comparisons, not new native runs in this test.
component_evidence=[]
for directory,module in [('gpu-gravity-render-envelope-v9-qualification','g16_t6040_render_envelope_v9.rs'),('gpu-gravity-native-ta-sku-v9-qualification','g16_t6040_ta_sku_v9.rs'),('gpu-gravity-native-fragment-sku-v9-qualification','g16_t6040_fragment_sku_v9.rs'),('gpu-gravity-ksm-work-v8-qualification','g16_t6040_ksm_work_v8.rs')]:
 evidence=ROOT/'out'/directory/'qualification.json';payload=json.loads(evidence.read_text())
 matches=[entry for entry in payload['inputs'] if Path(entry['path']).name==module]
 assert len(matches)==1 and matches[0]['sha256']==pin(KIT/module)['sha256'],(directory,module,'module source differs from saved comparison')
 component_evidence.append(pin(evidence))
report={'schema':'m4rch.native-render-job.qualification.v9','compile_returncode':compile.returncode,
 'run_returncode':run.returncode,'renders':40,'native_producer_runs':80,'named_register_checks':checks,
 'refusals':600,'borrowed_writer_whole_output_checks':80,'connected_RCE_envelope_lifecycle_checks':80,'composed_postkick_transport_checks':80,'short_transport_prewrite_refusals':80,'submitted_original_timeline_checks':80,'composed_jobs':80,'job_failure_cases':240,'ksm_list_metadata_checks':320,'SKU_extent_checks':80,'complete':False,'runtime_enabled':False,'hardware_actions':[],
 'component_native_evidence':component_evidence,'register_metadata':metadata,'stream_extents':stream_extents,
 'ordinary_descriptor_subtype':0,'scope_exclusions':['Nonordinary descriptor subtype injection excluded; no Linux Parameters source binding.','Synthetic alias plans are not retained kernel allocations.'],
 'pins':[pin(p) for p in [Path(__file__),KIT/'g16_t6040_descriptor_v10.rs',base,KIT/'g16_t6040_rce_ram_v9.rs',KIT/'g16_t6040_descriptor_provider_v10.rs',KIT/'g16_t6040_resource_address_v9.rs',KIT/'g16_t6040_render_policy_v9.rs',KIT/'g16_t6040_render_envelope_v9.rs',KIT/'g16_t6040_render_job_v9.rs',KIT/'g16_t6040_postkick_v9.rs',KIT/'g16_t6040_work_layout_v9.rs',KIT/'g16_t6040_ksm_work_v8.rs',KIT/'g16_t6040_ta_sku_v9.rs',KIT/'g16_t6040_fragment_sku_v9.rs',ROOT/'out/private-apple/native-rce-semantic-v9.rs',ROOT/'out/gpu-gravity-native-descriptor-policy-v9/dependency-trace.json']],
 'unresolved':['Native TA user/aperture conversion now source-qualified; actual owning aperture base remains caller-retained mapping input.',
 'Admission/cycle/gate/lifecycle/stamp/status fields now bound through descriptor/context/scene/command inputs; lifecycle low word explicitly Linux experimental policy.',
 'PM scene/resource CPU lookup inputs and sampler/residency construction require typed owned providers.',
 'Ordinary Mesa PPP2/3/202/203, sample_size->TIB and tile policy are now typed and qualified; nonordinary disabled clamp/default point size and nonzero samplers explicitly refuse.',
 'Partial pipeline fields are copied using native processRenderSetup evidence; conditional phase flags still need integration.'],
 'scope':'Actual connected RCE->envelope->SKU->KSM assembler with dynamic Mesa parameters/layout VAs; no retained resource ownership, queue publication, or hardware acceptance.'}
(OUT/'named-qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('pins','register_metadata','stream_extents','component_native_evidence')}))
