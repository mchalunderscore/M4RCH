// SPDX-License-Identifier: GPL-2.0-only
//! Firmware transport notification for an already encoded hardware KSM entry.
//! Publish this record's firmware address through the channel pointer ring;
//! the separate 0x200 KSM entry belongs to the hardware scheduler entry ring.
//! Covers the accelerator ee5f bit0-clear ordinary caller path only.
pub const BACKING_BYTES:usize=24;
pub const WRITTEN_BYTES:usize=21;
#[derive(Clone,Copy)]
pub enum Kind { Tiling, Fragment }
pub struct Bindings {
    pub kind:Kind,
    pub firmware_queue_id:u32,
    pub descriptor_count:u32,
    pub scheduler_mode:u32,
    /// The original timestamp returned by encode*KickEntry, not its next counter.
    pub submitted_timeline:u64,
}
/// Source stores intentionally truncate queue/count/mode and preserve the tail.
/// The 24-byte backing is our aligned retained allocation, not a claim about
/// the driver's original allocation extent. Short buffers refuse before writes.
pub fn write(out:&mut[u8],b:&Bindings)->Option<()> {
    if out.len()<BACKING_BYTES{return None;}
    out[0..4].copy_from_slice(&14u32.to_le_bytes());
    out[4..6].copy_from_slice(&(b.firmware_queue_id as u16).to_le_bytes());
    out[6..8].copy_from_slice(&(b.descriptor_count as u16).to_le_bytes());
    out[8]=b.scheduler_mode as u8;
    out[9..17].copy_from_slice(&b.submitted_timeline.to_le_bytes());
    out[17..21].copy_from_slice(&(match b.kind{Kind::Tiling=>0u32,Kind::Fragment=>1u32}).to_le_bytes());
    Some(())
}
