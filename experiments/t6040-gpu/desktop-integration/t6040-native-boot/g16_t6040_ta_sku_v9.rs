// SPDX-License-Identifier: GPL-2.0-only
//! Source-qualified primary TA opcode5/6 SKU stream, native TA9c0 command.
#[derive(Debug,PartialEq)] pub enum Error { Count, Space, Address }
fn q(b:&[u8],o:usize)->u64{u64::from_le_bytes(b[o..o+8].try_into().unwrap())}
fn w(b:&[u8],o:usize)->u32{u32::from_le_bytes(b[o..o+4].try_into().unwrap())}
fn put(b:&mut[u8],o:usize,v:u64,n:usize){b[o..o+n].copy_from_slice(&v.to_le_bytes()[..n]);}
#[derive(Clone,Copy)] pub struct Bindings {
    pub command_gpu:u64, pub translated_state:u64, pub fw_state:u64,
    pub state:u64, pub counter:u64, pub resource_type:u32, pub context_id:u32,
    pub resource_map:u64, pub feature:u8, pub channel_config:u8,
    pub timestamp_index:u32, pub stream_fw:u64,
}
fn startup(payload:&mut[u8],command:&[u8;0x9c0],d:&[u8;0x1800],b:Bindings){
    payload.fill(0);
    for(o,v)in[(0x10,b.command_gpu+0x60),(0x18,q(command,0x20)),(0x20,b.translated_state),
        (0x28,b.fw_state+4),(0x30,b.state),(0x60,b.command_gpu+0x7b2),(0x68,b.command_gpu+0x8de),
        (0x78,b.counter),(0x38,b.command_gpu+0x88a),(0x1b4,q(command,4)),
        (0x18c,q(d,0x1408)),(0x194,q(d,0x1418)),(0x1a4,b.resource_map.wrapping_add(w(d,0x1430)as u64))]{put(payload,o,v,8);}
    for(o,v)in[(0x40,w(command,0xc)),(0x44,b.resource_type),(0x48,b.context_id),
        (0x4c,w(d,0x1218)),(0x50,(d[0x1138]&1)as u32),(0x54,w(d,0x1270)),
        (0x58,w(command,0x8be)),(0x70,(d[0x113b]&1)as u32),(0x74,u32::from(d[0x960]==2)),
        (0x1bc,w(command,0x8ba)),(0x19c,w(d,0x1420)),(0x1c0,(d[0x1141]&1)as u32),
        (0x5c,(d[0x1558]&1)as u32),(0x80,(d[0x1142]&1)as u32)]{put(payload,o,v as u64,4);}
    payload[0x1ac]=b.feature&1;
    let count=w(d,0x1388)as usize;if count!=0{put(payload,0x184,count as u64,4);}
    for i in 0..count{let s=0x1288+i*16;let o=0x84+i*16;payload[o..o+12].copy_from_slice(&d[s..s+12]);payload[o+12]=d[s+12];payload[o+14..o+16].copy_from_slice(&d[s+14..s+16]);}
}
fn timestamp(record:&mut[u8],command:&[u8;0x9c0],b:Bindings,begin:bool){
    put(record,0,3|if begin{0x80000000}else{0},4);
    let pair=if q(command,0x90e)!=0||q(command,0x916)!=0{b.command_gpu+0x90e}else{0};
    let optional=if q(command,0x926)!=0{b.command_gpu+0x91e}else{0};
    for(o,v)in[(4,b.command_gpu+0x8f6),(0xc,b.command_gpu+0x8fe),
        (0x14,b.command_gpu+if begin{0x8fe}else{0x906}),(0x1c,b.state),(0x24,pair),
        (0x2c,b.command_gpu+0x95e),(0x34,b.command_gpu+0x86a),(0x3c,optional),(0x44,b.timestamp_index as u64)]{put(record,o,v,8);}
}
fn end(record:&mut[u8],command:&[u8;0x9c0],d:&[u8;0x1800],b:Bindings,relative:usize){
    record.fill(0);put(record,0,6,4);
    for(o,v)in[(4,b.translated_state),(0xc,q(command,0x20)),(0x14,b.fw_state+4),
        (0x1c,b.state),(0x24,b.command_gpu+0x88a),(0x34,b.command_gpu+0x7b2),
        (0x40,b.counter),(0x48,q(command,0x8ae)),(0x78,b.stream_fw+4+0x18c),(0x85,b.command_gpu+0x94e)]{put(record,o,v,8);}
    for(o,v)in[(0x2c,w(command,0xc)),(0x30,(d[0x1138]&1)as u32),(0x3c,(d[0x113b]&1)as u32),
        (0x50,w(command,0x8b6)),(0x80,0u32.wrapping_sub(relative as u32))]{put(record,o,v as u64,4);}
    let vector=w(d,0x1388)!=0||d[0x1390..0x13b0].iter().any(|v|*v!=0);
    if vector{record[0x58..0x78].copy_from_slice(&d[0x1390..0x13b0]);}
    record[0x84]=u8::from(vector)|((b.channel_config&3)<<2);record[0x8d]=d[0x15c0];
}
/// Caller handles native beginEncoding waits and protected-context alternative.
/// Full rounded storage is required and zeroed before command publication.
pub fn primary_stream(stream:&mut[u8],command:&mut[u8;0x9c0],d:&[u8;0x1800],b:Bindings)->Result<usize,Error>{
    if w(d,0x1388)>16{return Err(Error::Count);}
    if b.command_gpu==0||b.stream_fw==0||b.command_gpu.checked_add(0x9c0).is_none()
        ||b.fw_state.checked_add(4).is_none()||b.stream_fw.checked_add(0x400).is_none(){return Err(Error::Address);}
    let timestamps=d[0x1138]&1==0;let length=0x1cc+usize::from(timestamps)*0x98+0x94+4;let rounded=(length+63)&!63;
    if stream.len()<rounded{return Err(Error::Space);}
    put(stream,0,5,4);startup(&mut stream[4..0x1cc],command,d,b);let mut cursor=0x1cc;
    if timestamps{for begin in [true,false]{timestamp(&mut stream[cursor..cursor+0x4c],command,b,begin);cursor+=0x4c;}}
    end(&mut stream[cursor..cursor+0x94],command,d,b,cursor);cursor+=0x94;put(stream,cursor,0x40000002,4);cursor+=4;
    stream[cursor..rounded].fill(0);put(command,0x790,b.stream_fw,8);put(command,0x798,rounded as u64,4);Ok(cursor)
}
