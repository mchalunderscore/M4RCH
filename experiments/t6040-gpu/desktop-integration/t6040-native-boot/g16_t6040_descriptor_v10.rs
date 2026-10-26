// SPDX-License-Identifier: GPL-2.0-only
//! Named per-render fields for the native descriptor, with separate TA conversion.
//! The companion provider module binds lifecycle and policy per phase.
use super::g16_render::Parameters;
pub(crate) const COMPLETE: bool = false; // Full caller integration remains gated.

/// Native loadTARenderTargetMemoryData uses resource virtual slot 0x160.
/// Matched subclasses return user/aperture-relative device addresses.
/// Caller must use the qualified resource-address conversion, not FW-root aliases.
#[derive(Clone, Copy)]
pub(crate) struct UserAddresses {
    pub(crate) tilemap: u64,
    pub(crate) layer_metadata: u64,
    pub(crate) heap_metadata: u64,
    pub(crate) tpc: u64,
    pub(crate) encoder: u64,
    pub(crate) deflake_1: u64,
    pub(crate) deflake_2: u64,
    pub(crate) deflake_3: u64,
}
impl UserAddresses {
    /// Addresses come from the same retained resource mappings as fragment
    /// device addresses, converted by the matched native aperture getter.
    pub(crate) fn from_mappings(values: [super::g16_t6040_resource_address_v9::Address;8])->Self {
        Self {tilemap:values[0].user,layer_metadata:values[1].user,
            heap_metadata:values[2].user,tpc:values[3].user,encoder:values[4].user,
            deflake_1:values[5].user,deflake_2:values[6].user,deflake_3:values[7].user}
    }
}
fn q(out: &mut [u8;0x1800], offset:usize, value:u64) {
    out[offset..offset+8].copy_from_slice(&value.to_le_bytes());
}
fn w(out: &mut [u8;0x1800], offset:usize, value:u64) -> Option<()> {
    let value=u32::try_from(value).ok()?;
    out[offset..offset+4].copy_from_slice(&value.to_le_bytes()); Some(())
}

/// Produce the known native descriptor fields from a real render's values.
/// No command, CPU lookup pointer or fixed-triangle descriptor is imported.
/// COMPLETE remains false until the caller binds all remaining native inputs.
pub(crate) fn build_into(out:&mut [u8;0x1800], p:&Parameters, ta:&UserAddresses)->Option<()> {
    if !p.valid() || ta.encoder==0 || ta.encoder&3!=0
        || ta.heap_metadata==0 || ta.heap_metadata&63!=0
        || p.heapmeta&63!=0 || p.depth_bias_array&3!=0
        || p.scissor_array&3!=0 || p.occlusion_query_base&7!=0
        || ta.deflake_3&63!=0 {return None;}
    out.fill(0);
    let tx=p.width.div_ceil(32); let ty=p.height.div_ceil(32);
    let mx=(tx.div_ceil(4)+3)&!3; let my=(ty.div_ceil(4)+3)&!3;
    let ux=32/p.utile_width; let uy=32/p.utile_height;
    let size1=(5*mx*my*ux*uy).div_ceil(4);
    let size2=mx*my; let size3=2*mx*my*ux*uy;
    let screen=((ty-1)<<12)|(tx-1);
    // Correlation is by native register identity and exact field transformation,
    // checked against the native loaders and descriptor dependency traces.
    for (o,v) in [
        (0xff0,ta.encoder),(0x1090,ta.deflake_1),(0x1098,ta.deflake_2),
        (0x1050,ta.deflake_3),(0x1148,ta.tpc),(0x1160,ta.tilemap),
        (0x1178,ta.layer_metadata),(0x1188,ta.heap_metadata),
        (0x11f0,p.utile_config),(0x11f8,p.multisample_control),
        (0x4b0,p.depth_bias_array),(0x4b8,p.scissor_array),
        (0x4c0,p.occlusion_query_base),(0x608,p.load_pipeline_bind),
        (0x610,p.load_pipeline),(0x760,p.store_pipeline_bind),(0x768,p.store_pipeline),
        (0x638,p.partial_load_pipeline_bind),(0x640,p.partial_load_pipeline),
        (0x780,p.partial_store_pipeline_bind),(0x788,p.partial_store_pipeline),
        (0x648,p.depth_flags),(0x660,p.depth_dimensions),
        (0x668,p.depth_buffer),(0x670,p.depth_buffer),
        (0x680,p.stencil_buffer),(0x688,p.stencil_buffer),
        (0x6c8,p.depth_stride),(0x6d0,p.depth_stride),
        (0x6d8,p.stencil_stride),(0x6e0,p.stencil_stride),
        (0x6e8,p.depth_aux_buffer),(0x6f0,p.depth_aux_buffer),
        (0x700,p.depth_aux_stride),(0x708,p.depth_aux_stride),
        (0x710,p.stencil_aux_buffer),(0x718,p.stencil_aux_buffer),
        (0x728,p.stencil_aux_stride),(0x730,p.stencil_aux_stride),
        (0x738,p.aux_fb),(0x748,p.aux_fb_flags),
        (0x750,(p.height<<32)|p.width),(0x758,p.aux_fb_page_count),
        (0x8a0,p.tilemap),(0x8a8,if p.layermeta==0 {p.heapmeta}else{p.layermeta}),
        (0x8b0,p.heapmeta),(0x8b8,p.multisample_control),
    ] {q(out,o,v);}
    // Native target loader copies u32 geometry fields. Samples/layers are inputs
    // to native producer decisions, rather than preencoded donor register bits.
    for (o,v) in [(0x4a4,p.utile_width),(0x4a8,p.utile_height),(0x8c8,p.samples),
        (0x8d0,(my*uy)|((mx*ux)<<16)),(0x8d4,screen),
        (0x8e0,p.merge_upper_x_bits),(0x8e4,p.merge_upper_y_bits),
        (0x8f0,p.layers),(0x8f4,size1),
        (0x1168,size1),(0x1158,size3),(0x1180,p.layers),
        (0x1200,(p.width-1)|((p.height-1)<<16)),(0x1204,screen),
        (0x1208,3*mx|((2*mx)<<9)|(mx<<18)),
        (0x120c,3*my|((2*my)<<9)|(my<<18)),(0x1210,size2),
        (0x7a8,p.depth_clear_value_bits),(0x7ac,p.stencil_clear_value)] {
        w(out,o,v)?;
    }
    // TIB encoding is caller attachment policy, copied by the native common
    // record. Hardware acceptance and extra native policy bits remain separate.
    let blocks=p.tib_blocks&0x3f;
    let tib=if p.samples==1 {blocks} else {
        ((p.samples*if p.tib_blocks>32 {2}else{1})<<16)|blocks
    };
    q(out,0x740,tib);
    Some(())
}

/// Host convenience only; kernel runtime uses build_into with retained backing.
pub(crate) fn build(p:&Parameters,ta:&UserAddresses)->Option<[u8;0x1800]> {
    let mut out=[0;0x1800];build_into(&mut out,p,ta)?;Some(out)
}
