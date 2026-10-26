// SPDX-License-Identifier: GPL-2.0-only
//! Pure matched G16X factory input decoder. Hardware acquisition belongs to the
//! cold boot owner; no fallback words are manufactured here. Apply after the
//! complete power writer, which initializes the complete output allocation.
use super::float::F32;

pub(crate) const FUSE_PHYSICAL_BASE: u64 = 0x508374000;
pub(crate) const FUSE_WORD_OFFSETS: [usize; 5] = [0xc10, 0xc1c, 0xc20, 0xc24, 0xc28];
#[derive(Clone, Copy, Debug)]
pub(crate) struct FactoryLeakage {
    cluster: [u32; 2], core: [u32; 2], afr: u32, auxiliary: u32,
}
impl FactoryLeakage {
    /// Inputs are actual little-endian register words, in FUSE_WORD_OFFSETS
    /// order. Values zero are valid fuse values, producing positive native
    /// minimums; absence must never be encoded as five zero words.
    pub(crate) fn from_words(words: &[u32; 5]) -> Self {
        let scale = F32::from(3i32) / F32::from(2i32);
        let cluster = [1u32, 15].map(|shift|
            (F32::from(((words[0] >> shift) & 0x3fff) + 1) * scale).to_bits());
        let core = (F32::from((((words[2] >> 24) | (words[3] << 8)) & 0x3ff) + 1)
            * F32::from(3i32)).to_bits();
        Self { cluster, core: [core; 2],
            afr: F32::from(((words[1] >> 9) & 0x1fff) + 1).to_bits(),
            auxiliary: (F32::from(((words[4] >> 4) & 0xfff) + 1) * scale).to_bits() }
    }
    /// Native successful provider for two GPU clusters and one SoC die:
    /// populateChipLeakageData 89e9844 → initPowerFirmwareData 89caf20.
    pub(crate) fn write_power(&self, out: &mut [u8]) -> Option<()> {
        if out.len() < 0x6578 { return None; }
        for (offset, values) in [(0x642c, self.cluster), (0x64ac, self.core)] {
            for (i, value) in values.iter().enumerate() {
                out[offset+i*4..offset+i*4+4].copy_from_slice(&value.to_le_bytes());
            }
        }
        out[0x64fc..0x6500].copy_from_slice(&self.afr.to_le_bytes());
        out[0x6504..0x6508].copy_from_slice(&self.auxiliary.to_le_bytes());
        Some(())
    }
}
