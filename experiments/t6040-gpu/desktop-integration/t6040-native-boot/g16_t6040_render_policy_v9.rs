// SPDX-License-Identifier: GPL-2.0-only
//! Ordinary Mesa render policy -> source-native descriptor controls.
use super::g16_render::Parameters;
#[derive(Clone,Copy,Debug,PartialEq)]
pub(crate) struct Ordinary {
    /// descriptor113a selects native special clamp recipe600e, never ordinary2.
    pub(crate) special_clamp: bool,
    /// descriptor1140 bit0 is the register OpenGL bit.
    pub(crate) opengl: bool,
    /// accelerator6d0 bit16 becomes the fixed point format bit9.
    pub(crate) fixed_point: bool,
    pub(crate) sample_bytes: u64,
    pub(crate) tib_blocks: u64,
    pub(crate) tib_encoding: u64,
    pub(crate) process_empty_tiles: bool,
}
impl Ordinary {
    /// Accept ordinary Mesa PPP fields exactly; refuse unrepresentable default
    /// point size and unsupported disabled W-clamp instead of dropping them.
    pub(crate) fn from_parameters(p:&Parameters)->Option<Self> {
        if !p.valid() || p.ppp_control&!0x203!=0 || p.ppp_control&2==0
            || p.sample_size>128 || p.sample_size&7!=0 {return None;}
        let bytes=p.sample_size.checked_mul(p.utile_width)?
            .checked_mul(p.utile_height)?.checked_mul(p.samples)?;
        let blocks=bytes.checked_add(2047)?/2048;
        if blocks>64 || blocks!=p.tib_blocks {return None;}
        let encoding=if p.samples==1 {blocks&63} else {
            ((p.samples*if blocks>32 {2}else{1})<<16)|(blocks&63)
        };
        // Native tile policy encodes layer mode and process-empty separately.
        let tile_config=0x280|u64::from(p.layers>1)
            |if p.process_empty_tiles {0x10000}else{0};
        if p.tile_config!=tile_config {return None;}
        Some(Self {special_clamp:false,opengl:p.ppp_control&1!=0,
            fixed_point:p.ppp_control&0x200!=0,sample_bytes:p.sample_size,
            tib_blocks:blocks,tib_encoding:encoding,process_empty_tiles:p.process_empty_tiles})
    }
    pub(crate) fn write_descriptor(&self,out:&mut [u8;0x1800]) {
        out[0x113a]=u8::from(self.special_clamp);
        out[0x1140]=u8::from(self.opengl);
        out[0x88d]=u8::from(self.process_empty_tiles);
        // Primary tile-control bit16 is descriptor88d bit0. The separate
        // partial phase88e/88f flags remain controller-owned.
        out[0x740..0x748].copy_from_slice(&self.tib_encoding.to_le_bytes());
    }
}
