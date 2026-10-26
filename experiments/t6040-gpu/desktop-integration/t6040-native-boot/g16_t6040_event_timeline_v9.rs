// SPDX-License-Identifier: GPL-2.0-only
//! Retained Linux event identity joined to Apple's event-to-HW converter.
//! Linux chooses one event per native entry and an initial owner counter. This
//! does not assert Apple's accelerator ee48 initialization or callback policy.
#[derive(Clone,Copy,Debug,PartialEq)]
pub struct Identity {pub event:u32,pub epoch:u64,pub timeline:u64,pub previous:u64}
pub fn identity(initial:u64,completed_ordinals:u64)->Option<Identity> {
    // Each ordinal owns one entry in a 256-slot native scheduler. Both signed
    // event banks use this generation's epoch; no arbitrary epoch1 seed.
    if initial>>40!=0 {return None;}
    let ordinal=completed_ordinals.checked_add(1)?;
    let event=(ordinal as u32).wrapping_shl(8);
    let epoch=ordinal>>24;
    let timeline=crate::g16_t6040_ksm_work_v8::convert_timestamp(epoch,event,256,initial)?;
    Some(Identity{event,epoch,timeline,previous:timeline.wrapping_sub(1)&((1u64<<40)-1)})
}
