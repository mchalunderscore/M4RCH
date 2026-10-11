// SPDX-License-Identifier: GPL-2.0-only
//! Native ordinary event dependency. Initialization barriers are separate.
pub const BYTES: usize = 0x48;
#[derive(Clone, Copy)]
pub struct Bindings {
    pub stamp_base: u64,
    pub stamp_offset: u32,
    /// Source-converted producer hardware timeline, not a completion stamp.
    pub hardware_timestamp: u64,
    pub hardware_queue: u32,
    pub wait_value: u32,
    pub producer_event: u32,
    pub consumer_stamp: u32,
    pub uuid: u64,
    pub selected_event: i32,
}
fn put(out: &mut [u8; BYTES], offset: usize, value: u64, width: usize) {
    out[offset..offset+width].copy_from_slice(&value.to_le_bytes()[..width]);
}
/// Matches native stores, preserving fields the producer does not write.
/// Caller supplies zeroed fresh backing or a source-proven reusable record,
/// and retains the producer stamp, timeline and queue identity through wait.
pub fn write(out: &mut [u8; BYTES], b: Bindings) {
    put(out,0,4,4);
    put(out,4,b.stamp_base.wrapping_add(u64::from(b.stamp_offset)),8);
    put(out,0xc,b.hardware_timestamp,8);
    put(out,0x14,u64::from(b.hardware_queue),4);
    put(out,0x18,u64::from(b.wait_value),4);
    put(out,0x24,u64::from(b.producer_event),4);
    put(out,0x28,u64::from(b.consumer_stamp),4);
    put(out,0x2c,b.uuid,8);
    put(out,0x34,1,4);
    put(out,0x3c,0,4);
    let selected=b.selected_event != -1 && b.selected_event as u32 == b.producer_event;
    put(out,0x40,u64::from(selected),4);
}
