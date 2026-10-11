// SPDX-License-Identifier: GPL-2.0-only
//! Bounded providers for the locally translated native integer RCE producer.
//! Synthetic CPU identities never become device mappings. Device aliases come
//! from the caller's owned command/resource allocations.
use super::g16_native_rce_semantic_v9::{self as native, Error, Ram, State};

#[derive(Clone, Copy)]
pub struct Providers {
    pub gpu_clusters: u32,
    pub address_bit47: bool,
    /// Native accelerator6d0 bit16 becomes TA PPP register bit9.
    pub ppp_bit9: bool,
    pub descriptor_policy: u8,
    pub fragment_policy: u8,
    pub controller_mode: u32,
    pub controller_feature: u32,
    pub command_gpu: u64,
    pub parameter_gpu: u64,
}
#[derive(Clone, Copy)]
pub enum Kind { Tiling, Fragment }

/// Caller owns all output and scratch storage and discards output on any error.
/// Context/scene are immutable typed lookup inputs, separate from the submit
/// context used later by the construction envelope.
pub struct Backing<'a> {
    pub command: &'a mut [u8; 0x3000],
    pub descriptor: &'a mut [u8; 0x1800],
    pub scratch: &'a mut [u8; 0x400],
    pub context: &'a [u8; 0x100],
    pub scene: &'a [u8; 0x100],
    pub providers: Providers,
}
fn scalar(bytes: &[u8], n: usize) -> u64 {
    let mut b=[0;8]; b[..n].copy_from_slice(&bytes[..n]); u64::from_le_bytes(b)
}
fn offset(a: u64, n: usize, base: u64, length: usize) -> Option<usize> {
    let off=a.checked_sub(base)? as usize;
    (off.checked_add(n)? <= length).then_some(off)
}
impl Ram for Backing<'_> {
    fn load(&mut self, a:u64, n:usize)->Result<u64,Error> {
        if n==0 || n>8 { return Err(Error::Unmapped); }
        if let Some(o)=offset(a,n,0x222000,0x3000) {return Ok(scalar(&self.command[o..],n));}
        if let Some(o)=offset(a,n,0x226000,0x1800) {return Ok(scalar(&self.descriptor[o..],n));}
        if let Some(o)=offset(a,n,0x24dc00,0x400) {return Ok(scalar(&self.scratch[o..],n));}
        if let Some(o)=offset(a,n,0x22c000,0x100) {return Ok(scalar(&self.context[o..],n));}
        if let Some(o)=offset(a,n,0x238000,0x100) {return Ok(scalar(&self.scene[o..],n));}
        let value=match (a,n) {
            (0x200000,8)=>0x22a000,
            (0x2004e4,4)=>self.providers.gpu_clusters as u64,
            (0x2005b0,8)=>0x228000,
            (0x2006d0,8)=>(u64::from(self.providers.address_bit47)<<47)|(u64::from(self.providers.ppp_bit9)<<16),
            (0x2006d9,1)=>self.providers.descriptor_policy as u64,
            // Linux does not install Apple's optional CPU register overrides.
            (0x20ed48,1)|(0x20ed4c,8)|(0x20ed54,8)=>0,
            (0x20f598,8)=>0x22c000,
            (0x2111a8,1)=>self.providers.fragment_policy as u64,
            (0x228380,8)=>0x229000,
            (0x229980,4)=>self.providers.controller_mode as u64,
            (0x229810,4)=>self.providers.controller_feature as u64,
            (0x22b0e8,8)=>0xfffffe00089e7fe4,
            (0x22b0f0,8)=>0xfffffe00089e7fd8,
            (0x22d030,8)=>0x22e000,
            (0x22e058,8)=>0x22f000,
            (0x22f000,8)=>0x230000,
            (0x230158,8)=>0x231000,
            (0xfffffe000712d7d0,8)=>0x400000000,
            (0xfffffe000712d7f0,8)=>0x100000000,
            (0xfffffe0007ead480,8)=>0xfffffe00089df714,
            (0xfffffe0007ead488,8)=>0xfffffe00089df6ec,
            _=>return Err(Error::Unmapped),
        };
        Ok(value)
    }
    fn store(&mut self,a:u64,n:usize,v:u64)->Result<(),Error> {
        if n==0 || n>8 {return Err(Error::Unmapped);}
        let bytes=v.to_le_bytes();
        if let Some(o)=offset(a,n,0x222000,0x3000) {self.command[o..o+n].copy_from_slice(&bytes[..n]);return Ok(());}
        if let Some(o)=offset(a,n,0x226000,0x1800) {self.descriptor[o..o+n].copy_from_slice(&bytes[..n]);return Ok(());}
        if let Some(o)=offset(a,n,0x24dc00,0x400) {self.scratch[o..o+n].copy_from_slice(&bytes[..n]);return Ok(());}
        Err(Error::Unmapped)
    }
}
impl Backing<'_> {
    pub fn produce(&mut self, kind:Kind)->Result<(),Error> {
        let p=self.providers;
        if !(1..=2).contains(&p.gpu_clusters) || p.command_gpu==0
            || p.command_gpu&63!=0 || p.parameter_gpu==0
            || p.command_gpu.checked_add(0x3000).is_none()
            || p.descriptor_policy>1 || p.fragment_policy>1 || p.controller_mode>1 {
            return Err(Error::Unmapped);
        }
        // CPU service identities remain internal. The descriptor is not a
        // firmware command and these fields are never used as device pointers.
        for (o,v) in [(0x190,0x22c000u64),(0xb90,0x22d000),(0x918,0x238000),
            (0x1230,0x238000),(0x1428,0x22d000),(0xfa0,p.command_gpu),(0x440,p.command_gpu)] {
            self.descriptor[o..o+8].copy_from_slice(&v.to_le_bytes());
        }
        self.scratch.fill(0);
        let mut s=State::new(match kind {Kind::Tiling=>0xfffffe00089dd2c4,Kind::Fragment=>0xfffffe00089df73c});
        s.r[0]=0x200000; s.r[1]=0x222000; s.r[2]=0x226000;
        s.r[31]=0x24e000; s.r[30]=0x24f000;
        native::produce(self,&mut s,0x24f000,p.parameter_gpu)?;
        if s.r[31]!=0x24e000 {return Err(Error::Trap);}
        Ok(())
    }
}
