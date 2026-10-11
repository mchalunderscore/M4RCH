// SPDX-License-Identifier: GPL-2.0-only
//! Native TA SKSM buffer-manager initialization at 8a1f294..8a1f2fc.
//! Manager block count resides in its retained backing, never in this record.
#[derive(Clone,Copy)] pub struct Bindings {
    pub descriptor_1274:u32,
    pub descriptor_1218:u32,
    /// Result of the native converter for descriptor1220; caller owns manager.
    pub manager_fw:u64,
    pub caller_word_21:u32,
}
pub fn write(out:&mut[u8;0x18],b:Bindings)->Option<()> {
    if b.manager_fw==0{return None;}
    out[..4].copy_from_slice(&5u32.to_le_bytes());
    out[4..8].copy_from_slice(&b.descriptor_1274.to_le_bytes());
    out[8..0xc].copy_from_slice(&b.descriptor_1218.to_le_bytes());
    out[0xc..0x14].copy_from_slice(&b.manager_fw.to_le_bytes());
    out[0x14..0x18].copy_from_slice(&b.caller_word_21.to_le_bytes());Some(())
}
