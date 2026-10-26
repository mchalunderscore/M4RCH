// SPDX-License-Identifier: GPL-2.0-only
//! AGFIKSMEventFlagMask from ordinary native TA/3D submitBuffer producers.
//! This is a scheduler event mask, not a shader-core topology mask.
//! 3D:895bfdc..895c038; TA:8a1fc5c..8a1fcbc.
#[derive(Clone,Copy)]
pub struct Inputs {
    /// Firmware configuration +0xe1c, whose native initial value is zero.
    pub firmware_e1c:u8,
    /// Native 3D descriptor+470 or TA descriptor+fd0 is non-null.
    pub descriptor_optional_owner:bool,
    /// Byte7 of accelerator configuration6d0.
    pub accelerator_6d7:u8,
}
pub fn ordinary(b:Inputs)->[u64;4] {
    let last=(u64::from(b.firmware_e1c&1)<<63)
        |(u64::from(b.descriptor_optional_owner)<<62)
        |(u64::from(b.accelerator_6d7&3!=0)<<61);
    [0,0,0,last]
}
