// SPDX-License-Identifier: GPL-2.0-only
//! Bounded native power prefix, sample period and ARM array initialization.
//! Offsets are relative to native bundle child 4, not the donor bundle.
//! Controller images, uptime, tuning and performance policy remain incomplete.

pub(crate) const LOGICAL_BYTES: usize = 0x6578;
pub(crate) const HARDWARE_LOGICAL_BYTES: usize = 0x2718;
pub(crate) const HARDWARE_PERIOD_OFFSET: usize = 0xed8;
pub(crate) const POWER_COMPLETE: bool = false;
pub(crate) const PERIOD_CLOCKS_PER_MS: u32 = 24000;
pub(crate) const DEFAULT_PERIOD_MS: u32 = 16;

/// Literal initial stores in AGXFirmware::initPowerAndPerformanceData.
/// Float literals are serialized as bits; no floating point operation occurs.
pub(crate) const INITIAL_U32_FIELDS: &[(usize, u32)] = &[
    (0xc, 0), (0x10, 4), (0x14, 0x3f800000), (0x18, 0),
    (0x2c, 1), (0x30, 1), (0x34, 0), (0x50, 100),
    (0x5c, 0), (0x60, 4), (0x64, 0x3f800000), (0x68, 0),
    (0x6c, 1), (0x70, 1), (0x74, 0), (0x90, 100),
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct PowerData {
    pub period_aic_clocks: u32,
    pub period_ms: u32,
}

impl PowerData {
    /// Native configuration gives AIC clocks priority. When they are present,
    /// the millisecond property is not read, and milliseconds are truncated
    /// from clocks / 24000. Otherwise the optional millisecond property or the
    /// native 16 ms default supplies clocks. Malformed selected properties,
    /// zero periods and overflowing multiplication are refused here. Native
    /// unchecked overflow/zero states are not valid production inputs.
    pub(crate) fn from_adt(aic: Option<&[u8]>, ms: Option<&[u8]>) -> Option<Self> {
        let word = |bytes: &[u8]| -> Option<u32> {
            Some(u32::from_le_bytes(bytes.try_into().ok()?))
        };
        let (period_aic_clocks, period_ms) = match aic {
            Some(bytes) => {
                let clocks = word(bytes)?;
                (clocks, clocks / PERIOD_CLOCKS_PER_MS)
            }
            None => {
                let ms = match ms {
                    Some(bytes) => word(bytes)?,
                    None => DEFAULT_PERIOD_MS,
                };
                (ms.checked_mul(PERIOD_CLOCKS_PER_MS)?, ms)
            }
        };
        let value = Self { period_aic_clocks, period_ms };
        value.valid().then_some(value)
    }

    fn valid(&self) -> bool {
        self.period_aic_clocks != 0 && self.period_ms != 0
            && self.period_aic_clocks / PERIOD_CLOCKS_PER_MS == self.period_ms
    }

    /// Write the selected native producer, preserving all unknown fields.
    /// In the ARM override, sixteen fixed initialization iterations produce
    /// contiguous zero / u16 0x7fff / zero arrays. Their semantics are not
    /// inferred from the pattern, and these values are for initial creation.
    pub(crate) fn write_component(&self, out: &mut [u8]) -> Option<()> {
        if out.len() < LOGICAL_BYTES || !self.valid() { return None; }
        out[4..8].copy_from_slice(&self.period_aic_clocks.to_le_bytes());
        out[8..12].copy_from_slice(&self.period_aic_clocks.to_le_bytes());
        for &(offset, value) in INITIAL_U32_FIELDS {
            out[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
        }
        out[0xbef..0x1bef].fill(0);
        for pair in out[0x1bef..0x1fef].chunks_exact_mut(2) {
            pair.copy_from_slice(&0x7fffu16.to_le_bytes());
        }
        out[0x1fef..0x21ef].fill(0);
        Some(())
    }

    /// AGXArmFirmware::initFirmwareData stores the selected millisecond
    /// getter at native hardware + ed8, outside the power object itself.
    pub(crate) fn write_hardware_component(&self, out: &mut [u8]) -> Option<()> {
        if out.len() < HARDWARE_LOGICAL_BYTES || !self.valid() { return None; }
        out[HARDWARE_PERIOD_OFFSET..HARDWARE_PERIOD_OFFSET + 4]
            .copy_from_slice(&self.period_ms.to_le_bytes());
        Some(())
    }
}
