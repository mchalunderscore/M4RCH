// SPDX-License-Identifier: GPL-2.0-only
//! Connected ordinary native RCE -> envelope -> SKU -> scheduler construction.
//! All backing is borrowed from the caller. On any error discard outputs;
//! publication and retained PM/resource/lifetime ownership remain caller duties.
use super::{g16_t6040_rce_ram_v9 as rce,g16_t6040_render_envelope_v9 as envelope,
    g16_t6040_ta_sku_v9 as ta,g16_t6040_fragment_sku_v9 as fragment,
    g16_t6040_ksm_work_v8 as ksm,g16_t6040_work_layout_v9 as layout};
#[derive(Debug,PartialEq)]
pub enum Error { Address, Registers, Producer, Envelope, Stream, Scheduler }
pub struct ResultInfo {pub stream_bytes:usize,pub next_timeline:u64}
fn q(b:&[u8],o:usize)->u64{u64::from_le_bytes(b[o..o+8].try_into().unwrap())}
fn h(b:&[u8],o:usize)->u16{u16::from_le_bytes(b[o..o+2].try_into().unwrap())}
fn w(b:&[u8],o:usize)->u32{u32::from_le_bytes(b[o..o+4].try_into().unwrap())}
/// Read actual native exported counts; never substitute fixed triangle counts.
fn lists(command:&[u8],descriptor:&[u8],device:u64,tiling:bool)->Result<[ksm::RegisterList;4],Error>{
    let mut out=[ksm::RegisterList{gpu_address:0,count:0};4];
    for i in 0..if tiling{1}else{4}{
        let offset=if tiling{0x60}else{0xa0+i*0x720};
        let meta=if tiling{0x760}else{0x7a0+i*0x720};
        let export=if tiling{0x1568}else{0x828+i*16};
        let pointer=q(command,meta);let backing=h(command,meta+8);let bytes=h(command,meta+10);
        let count=h(descriptor,export+8);
        if pointer!=device.checked_add(offset as u64).ok_or(Error::Address)?
            ||q(descriptor,export)!=pointer ||u32::from(bytes)!=u32::from(backing)*12
            ||count>backing ||count>=128 ||pointer&31!=0
            ||offset+usize::from(bytes)>if tiling{0x760}else{offset+0x70c}{return Err(Error::Registers);}
        out[i]=ksm::RegisterList{gpu_address:if count==0{0}else{pointer},count:count as u8};
    }
    Ok(out)
}
fn schedule(out:&mut[u8;0x200],command:&[u8],descriptor:&[u8],stage:layout::Stage,
    b:&mut ksm::Bindings<'_>,tiling:bool)->Result<u64,Error>{
    b.register_lists=lists(command,descriptor,stage.command.device,tiling)?;
    b.command=stage.command.firmware;
    let off=if tiling{0x13b0}else{0xa98};
    let count=w(descriptor,off+12);
    if count>64{return Err(Error::Scheduler);}
    b.aperture_count=count as u8;
    b.aperture_index=if count==0{0}else{u8::try_from(w(descriptor,off+8)).map_err(|_|Error::Scheduler)?};
    b.aperture_address=if count==0{0}else{q(descriptor,off)};
    out.fill(0);
    ksm::write(out,b).ok_or(Error::Scheduler)
}
pub fn tiling(backing:&mut rce::Backing<'_>,construction:&envelope::TaBindings<'_>,
    sku:ta::Bindings,stream:&mut[u8],stage:layout::Stage,scheduler:&mut ksm::Bindings<'_>,
    record:&mut[u8;0x200])->Result<ResultInfo,Error>{
    if backing.providers.command_gpu!=stage.command.device||sku.command_gpu!=stage.command.device
        ||sku.stream_fw!=stage.sku_fw||stream.len()>layout::SKU_CAPACITY{return Err(Error::Address);}
    backing.produce(rce::Kind::Tiling).map_err(|_|Error::Producer)?;
    envelope::tiling(&mut backing.command[..0x9c0],backing.descriptor,construction).ok_or(Error::Envelope)?;
    let command:&mut[u8;0x9c0]=(&mut backing.command[..0x9c0]).try_into().map_err(|_|Error::Envelope)?;
    let stream_bytes=ta::primary_stream(stream,command,backing.descriptor,sku).map_err(|_|Error::Stream)?;
    let next_timeline=schedule(record,command,backing.descriptor,stage,scheduler,true)?;
    Ok(ResultInfo{stream_bytes,next_timeline})
}
pub fn fragment(backing:&mut rce::Backing<'_>,construction:&envelope::FragmentBindings<'_>,
    sku:fragment::Bindings,stream:&mut[u8],sku_stack:&mut[u8;0x300],stage:layout::Stage,
    scheduler:&mut ksm::Bindings<'_>,record:&mut[u8;0x200])->Result<ResultInfo,Error>{
    if backing.providers.command_gpu!=stage.command.device||sku.command_gpu!=stage.command.device
        ||sku.stream_fw!=stage.sku_fw||stream.len()>layout::SKU_CAPACITY{return Err(Error::Address);}
    backing.produce(rce::Kind::Fragment).map_err(|_|Error::Producer)?;
    envelope::fragment(&mut backing.command[..0x2240],backing.descriptor,construction).ok_or(Error::Envelope)?;
    let command:&mut[u8;0x2240]=(&mut backing.command[..0x2240]).try_into().map_err(|_|Error::Envelope)?;
    let stream_bytes=fragment::primary_stream(stream,sku_stack,command,backing.descriptor,sku).map_err(|_|Error::Stream)?;
    let next_timeline=schedule(record,command,backing.descriptor,stage,scheduler,false)?;
    Ok(ResultInfo{stream_bytes,next_timeline})
}
