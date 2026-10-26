// SPDX-License-Identifier: GPL-2.0-only
//! Native ordinary 3D primary SKU construction. All aliases are supplied by
//! owned runtime mappings; no donor command-relative pointers are reused.
#[derive(Debug, PartialEq)]
pub enum Error { AttachmentCount, SecondaryRequired, Space, Address }
fn q(b:&[u8],o:usize)->u64 {u64::from_le_bytes(b[o..o+8].try_into().unwrap())}
fn w(b:&[u8],o:usize)->u32 {u32::from_le_bytes(b[o..o+4].try_into().unwrap())}
fn put(b:&mut[u8],o:usize,v:u64,n:usize){b[o..o+n].copy_from_slice(&v.to_le_bytes()[..n]);}
#[derive(Clone, Copy)]
pub struct Bindings {
    pub command_gpu:u64,
    pub parameter_gpu:u64,
    pub state_fw:u64,
    pub resource_type:u32,
    pub resource_map:u64,
    pub context_id:u32,
    pub accelerator_config:u8,
    pub accelerator_feature:u8,
    pub channel_config:u8,
    pub mode:u32,
    pub timestamp_index:u32,
    /// Firmware alias of the SKU stream including its opcode7 word.
    pub stream_fw:u64,
    pub omit_end_timestamp:bool,
}
pub fn startup(stack:&mut[u8;0x300],descriptor:&[u8;0x1800],command:&[u8;0x2240],b:Bindings)->Result<(),Error> {
    let count=w(descriptor,0xa70) as usize;
    // Qualification bounds, not a general protocol attachment maximum.
    if count>16 {return Err(Error::AttachmentCount);}
    if b.accelerator_config&1!=0 && descriptor[0xc48]&1!=0 {return Err(Error::SecondaryRequired);}
    stack[0x80..0x268].fill(0);put(stack,0x2c,0,4);
    let fw_state=q(stack,0x78).wrapping_add(8);
    for (o,v) in [(0x90,b.command_gpu+0xa0),(0x98,b.parameter_gpu),(0xa0,fw_state),
        (0xa8,b.command_gpu+0x20f0),(0xb0,b.parameter_gpu+0x54),(0xb8,b.command_gpu+0x2130),
        (0xc0,b.command_gpu+0x2134),(0xc8,b.state_fw),(0xd0,b.command_gpu),
        (0xf8,b.command_gpu+0x1fd8),(0x100,b.command_gpu+0x2178),(0x11c,q(stack,0x70)),
        (0x22c,q(descriptor,0xb70)),(0x234,q(descriptor,0xb80)),
        (0x244,b.resource_map.wrapping_add(w(descriptor,0xb98) as u64)),(0x254,q(command,4))] {put(stack,o,v,8);}
    for (o,v) in [(0xd8,w(command,0xc)),(0xdc,b.resource_type),(0xe0,b.context_id),
        (0xe4,w(descriptor,0x900)),(0xe8,(descriptor[0x897]&1) as u32),(0xec,w(descriptor,0x140)),
        (0xf0,w(command,0x2158)),(0xf4,(descriptor[0xb48]&1) as u32),(0x108,(descriptor[0x895]&1) as u32),
        (0x10c,(descriptor[0x894]&1) as u32),(0x110,0),(0x118,u32::from(descriptor[0x960]==2)),
        (0x23c,w(descriptor,0xb88)),(0x25c,w(command,0x2154))] {put(stack,o,v as u64,4);}
    stack[0x24c]=b.accelerator_feature&1;stack[0x24d]=0;stack[0x260]=descriptor[0xc44];
    for (o,v) in [(0x30,b.command_gpu+0x2130),(0x38,b.parameter_gpu),(0x40,b.command_gpu+0x1fd8),
        (0x48,b.command_gpu+0x2134),(0x50,b.command_gpu+0x20f0),(0x58,fw_state),(0x68,b.state_fw)] {put(stack,o,v,8);}
    if count!=0 {put(stack,0x224,count as u64,4);}
    for i in 0..count {let s=0x970+i*16;let d=0x124+i*16;
        stack[d..d+12].copy_from_slice(&descriptor[s..s+12]);stack[d+12]=descriptor[s+12];
        stack[d+14..d+16].copy_from_slice(&descriptor[s+14..s+16]);}
    Ok(())
}
pub fn timestamp(record:&mut[u8],command:&[u8;0x2240],b:Bindings,begin:bool) {
    put(record,0,3|if begin{0x80000000}else{0},4);
    let pair=if q(command,0x21a8)!=0||q(command,0x21b0)!=0 {b.command_gpu+0x21a8}else{0};
    let optional=if q(command,0x21c0)!=0 {b.command_gpu+0x21b8}else{0};
    for (o,v) in [(4,b.command_gpu+0x2190),(0xc,b.command_gpu+0x2198),
        (0x14,b.command_gpu+if begin{0x2198}else{0x21a0}),(0x1c,b.state_fw),
        (0x24,pair),(0x2c,b.command_gpu+0x21f8),(0x34,b.command_gpu+0x2104),
        (0x3c,optional),(0x44,b.timestamp_index as u64)] {put(record,o,v,8);}
}
pub fn end(record:&mut[u8],stack:&[u8;0x300],command:&[u8;0x2240],descriptor:&[u8;0x1800],b:Bindings,byte_offset:usize) {
    put(record,0,8,4);
    let vector=w(descriptor,0xa70)!=0||(0..4).any(|i|q(descriptor,0xa78+i*8)!=0);
    for (o,v) in [(4,q(stack,0x70)),(0xc,q(command,0x2148)),(0x1c,q(stack,0x38)),(0x24,q(stack,0x60)),
        (0x30,q(stack,0x58)),(0x38,q(stack,0x30)),(0x40,q(stack,0x48)),(0x48,q(stack,0x50)),
        (0x50,q(stack,0x68)),(0x58,b.command_gpu),(0x64,q(stack,0x40)),(0x70,b.mode as u64),
        (0x98,b.stream_fw+4+0x1ac),(0xa5,b.command_gpu+0x21e8)] {put(record,o,v,8);}
    for (o,v) in [(0x14,w(command,0x2150)),(0x18,0),(0x2c,1),(0x60,w(command,0xc)),
        (0x6c,(descriptor[0x895]&1) as u32),(0xa0,0u32.wrapping_sub(byte_offset as u32)),
        (0xad,w(descriptor,0xc40)),(0xb2,w(command,0x2154)),(0xb6,0)] {put(record,o,v as u64,4);}
    if vector {record[0x78..0x98].copy_from_slice(&descriptor[0xa78..0xa98]);}else{record[0x78..0x98].fill(0);}
    record[0xa4]=u8::from(vector)|((b.channel_config&3)<<2);record[0xb1]=descriptor[0xc44];put(record,0xba,0,2);
}
/// Returns actual bytes and publishes its firmware pointer and rounded length
/// into the native command only after every primary record has been built.
/// Leading/trailing wait records and optional secondary phase belong to caller.
pub fn primary_stream(stream:&mut[u8],stack:&mut[u8;0x300],command:&mut[u8;0x2240],descriptor:&[u8;0x1800],b:Bindings)->Result<usize,Error> {
    if b.command_gpu.checked_add(0x2240).is_none() || b.parameter_gpu.checked_add(0x54).is_none()
        || b.stream_fw.checked_add(0x400).is_none() || b.command_gpu==0||b.stream_fw==0 {return Err(Error::Address);}
    let begin=descriptor[0x893]&1==0;let end_ts=!b.omit_end_timestamp;
    let length=0x1ec+usize::from(begin)*0x4c+usize::from(end_ts)*0x4c+0xbc+4;
    let rounded=(length+63)&!63;
    if stream.len()<rounded {return Err(Error::Space);}
    startup(stack,descriptor,command,b)?;
    put(stream,0,7,4);stream[4..0x1ec].copy_from_slice(&stack[0x80..0x268]);
    let mut cursor=0x1ec;
    if begin {timestamp(&mut stream[cursor..cursor+0x4c],command,b,true);cursor+=0x4c;}
    if end_ts {timestamp(&mut stream[cursor..cursor+0x4c],command,b,false);cursor+=0x4c;}
    end(&mut stream[cursor..cursor+0xbc],stack,command,descriptor,b,cursor);cursor+=0xbc;
    put(stream,cursor,0x40000002,4);cursor+=4;
    stream[cursor..rounded].fill(0);
    put(command,0x14,b.stream_fw,8);put(command,0x1c,((cursor+63)&!63) as u64,4);
    Ok(cursor)
}
