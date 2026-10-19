// SPDX-License-Identifier: GPL-2.0-only
//! Joined native integer RCE -> command envelope -> SKU -> KSM200 construction.
//! The runtime binds descriptors and all views of retained resources first.
//! Output is published only by the owning runtime after this returns success.
use super::{g16_t6040_rce_ram_v9 as rce,g16_t6040_render_envelope_v9 as envelope,
    g16_t6040_ta_sku_v9 as ta_sku,g16_t6040_fragment_sku_v9 as fragment_sku,
    g16_t6040_ksm_work_v8 as ksm};
#[derive(Debug,PartialEq)] pub enum Error { Binding, Rce, Envelope, Sku, Scheduler }
#[derive(Clone,Copy)] pub enum Phase { Tiling,Fragment }
fn q(b:&[u8],o:usize)->u64{u64::from_le_bytes(b[o..o+8].try_into().unwrap())}
fn h(b:&[u8],o:usize)->u16{u16::from_le_bytes(b[o..o+2].try_into().unwrap())}
/// Read the actual native producer's exported descriptors, preserving each
/// phase's native count (which can omit backing-only trailing records).
pub fn lists(d:&[u8;0x1800],command:&[u8;0x3000],gpu:u64,phase:Phase)->Option<[ksm::RegisterList;4]>{
    let mut out=[ksm::RegisterList{gpu_address:0,count:0};4];
    let count=match phase{Phase::Tiling=>1,Phase::Fragment=>4};
    for (i,r) in out.iter_mut().enumerate().take(count){
        let (data,meta,export)=match phase{Phase::Tiling=>(0x60,0x760,0x1568),Phase::Fragment=>(0xa0+i*0x720,0x7a0+i*0x720,0x828+i*16)};
        let backing=h(command,meta+8);let bytes=h(command,meta+10);let used=h(d,export+8);
        let expected=gpu.checked_add(data as u64)?;
        if q(command,meta)!=expected||q(d,export)!=expected||bytes as usize!=backing as usize*12
            ||used>backing||used>=128||used==0 {return None;}
        *r=ksm::RegisterList{gpu_address:expected,count:used as u8};
    }Some(out)
}
pub struct Buffers<'a>{
    pub command:&'a mut[u8;0x3000],pub descriptor:&'a mut[u8;0x1800],
    pub scratch:&'a mut[u8;0x400],pub context:&'a[u8;0x100],pub scene:&'a[u8;0x100],
    pub stream:&'a mut[u8],pub scheduler:&'a mut[u8;0x200],
}
fn scheduler(out:&mut[u8;0x200],d:&[u8;0x1800],command:&[u8;0x3000],gpu:u64,phase:Phase,b:&ksm::Bindings<'_>)->Result<u64,Error>{
    let registers=lists(d,command,gpu,phase).ok_or(Error::Binding)?;
    let (rce_meta,aperture)=match phase{Phase::Tiling=>(0x1560,0x13b0),Phase::Fragment=>(0x820,0xa98)};
    let aperture_count=u8::try_from(u32::from_le_bytes(d[aperture+12..aperture+16].try_into().unwrap())).map_err(|_|Error::Binding)?;
    let derived=ksm::Bindings{timestamp:b.timestamp,queue_id:b.queue_id,priority:b.priority,capacity:b.capacity,
        previous:b.previous,command:b.command,firmware_queue:b.firmware_queue,
        aperture_address:if aperture_count==0{0}else{q(d,aperture)},aperture_index:b.aperture_index,
        aperture_count,alternate_kind:b.alternate_kind,extra_flag:b.extra_flag,dependencies:b.dependencies,
        qos:b.qos,rce_kind:(q(d,rce_meta)&3)as u8,register_lists:registers,masks:b.masks,auxiliary:b.auxiliary};
    out.fill(0);ksm::write(out,&derived).ok_or(Error::Scheduler)
}
pub fn tiling(buffers:&mut Buffers<'_>,providers:rce::Providers,
    construction:&envelope::TaBindings<'_>,sku:ta_sku::Bindings,work:&ksm::Bindings<'_>)->Result<u64,Error>{
    if providers.command_gpu!=sku.command_gpu||work.command==0{return Err(Error::Binding);}
    rce::Backing{command:buffers.command,descriptor:buffers.descriptor,scratch:buffers.scratch,
        context:buffers.context,scene:buffers.scene,providers}.produce(rce::Kind::Tiling).map_err(|_|Error::Rce)?;
    let command:&mut[u8;0x9c0]=(&mut buffers.command[..0x9c0]).try_into().map_err(|_|Error::Binding)?;
    envelope::tiling(command,buffers.descriptor,construction).ok_or(Error::Envelope)?;
    ta_sku::primary_stream(buffers.stream,command,buffers.descriptor,sku).map_err(|_|Error::Sku)?;
    scheduler(buffers.scheduler,buffers.descriptor,buffers.command,providers.command_gpu,Phase::Tiling,work)
}
pub fn fragment(buffers:&mut Buffers<'_>,providers:rce::Providers,
    construction:&envelope::FragmentBindings<'_>,sku:fragment_sku::Bindings,
    sku_stack:&mut[u8;0x300],work:&ksm::Bindings<'_>)->Result<u64,Error>{
    if providers.command_gpu!=sku.command_gpu||work.command==0{return Err(Error::Binding);}
    rce::Backing{command:buffers.command,descriptor:buffers.descriptor,scratch:buffers.scratch,
        context:buffers.context,scene:buffers.scene,providers}.produce(rce::Kind::Fragment).map_err(|_|Error::Rce)?;
    let command:&mut[u8;0x2240]=(&mut buffers.command[..0x2240]).try_into().map_err(|_|Error::Binding)?;
    envelope::fragment(command,buffers.descriptor,construction).ok_or(Error::Envelope)?;
    fragment_sku::primary_stream(buffers.stream,sku_stack,command,buffers.descriptor,sku).map_err(|_|Error::Sku)?;
    scheduler(buffers.scheduler,buffers.descriptor,buffers.command,providers.command_gpu,Phase::Fragment,work)
}
