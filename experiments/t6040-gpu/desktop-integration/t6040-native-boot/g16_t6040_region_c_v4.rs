// SPDX-License-Identifier: GPL-2.0-only
//! Bounded initial Region C component from the matched 25G83 native producer.
//! The constructor's child descriptor supplies e58 logical bytes. Its shared
//! allocation rounds to a 16 KiB page in this profile. Full Region C inputs,
//! callbacks and Linux mapping-policy translation are still incomplete.

pub(crate) const LOGICAL_BYTES: usize = 0xe58;
pub(crate) const BACKING_BYTES: usize = 0x4000;
pub(crate) const REGION_C_COMPLETE: bool = false;
pub(crate) const GPU_IDLE_DEFAULT_MS: u32 = 2;
pub(crate) const FENDER_IDLE_DEFAULT_MS: u32 = 40;

/// Only literal initial stores proved in the generic and ARM constructors.
/// Unaligned stores retain their native widths. Field semantics are not
/// invented from their offsets; these are not runtime reset/cleanup values.
pub(crate) const INITIAL_U32_FIELDS: &[(usize, u32)] = &[
    (0x4, 0), (0x8, 0), (0x10, 0), (0x14, 0), (0x18, 0), (0x1c, 0),
    (0x3c, 120), (0x40, 0), (0x44, 0), (0x48, 0), (0x4c, 0), (0x50, 0),
    (0x5a, 0), (0x9c, 0), (0xa0, 0), (0x7ec, 1), (0x9c4, 0),
    (0x9dc, 0), (0xe29, 0), (0xe3d, 1), (0xe41, 0), (0xe45, 0), (0xe49, 0),
];
pub(crate) const INITIAL_U8_FIELDS: &[(usize, u8)] = &[(0xe1c, 0)];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct RegionC {
    pub gpu_idle_off_ms: u32,
    pub fender_idle_off_ms: u32,
}

impl RegionC {
    /// Original ADT data is LE. Absent properties select the native defaults;
    /// a present malformed property is refused rather than treated as absent.
    /// Native initial construction loads one u32 and does not impose a range
    /// on its value. Runtime delay-setter override state is a separate owner.
    pub(crate) fn from_adt(gpu: Option<&[u8]>, fender: Option<&[u8]>) -> Option<Self> {
        let word = |bytes: Option<&[u8]>, default: u32| -> Option<u32> {
            match bytes {
                None => Some(default),
                Some(bytes) => Some(u32::from_le_bytes(bytes.try_into().ok()?)),
            }
        };
        Some(Self { gpu_idle_off_ms: word(gpu, GPU_IDLE_DEFAULT_MS)?,
                    fender_idle_off_ms: word(fender, FENDER_IDLE_DEFAULT_MS)? })
    }

    pub(crate) fn native_defaults() -> Self {
        Self { gpu_idle_off_ms: GPU_IDLE_DEFAULT_MS,
               fender_idle_off_ms: FENDER_IDLE_DEFAULT_MS }
    }

    /// Serialize the proved component into already owned initial backing.
    /// All unqualified bytes, allocation padding and caller sentinels survive.
    /// This produces component evidence; REGION_C_COMPLETE remains a required
    /// rejection gate for returning a complete object to normal startup.
    pub(crate) fn write_component(&self, out: &mut [u8]) -> Option<()> {
        if out.len() < LOGICAL_BYTES { return None; }
        for &(offset, value) in INITIAL_U32_FIELDS {
            out[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
        }
        for &(offset, value) in INITIAL_U8_FIELDS {
            out[offset] = value;
        }
        out[0x9b8..0x9bc].copy_from_slice(&self.gpu_idle_off_ms.to_le_bytes());
        out[0x9bc..0x9c0].copy_from_slice(&self.fender_idle_off_ms.to_le_bytes());
        Some(())
    }
}
