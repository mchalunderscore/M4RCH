// SPDX-License-Identifier: GPL-2.0-only
//! Native firmware fields share one Linux architectural physical-counter origin.
//! Matched Apple ADT establishes 24 MHz native tick rate. Apple custom timer
//! and per-CPU epoch offset are not emulated by this explicit Linux provider.

pub(crate) const NATIVE_RATE_HZ: u64 = 24_000_000;
pub(crate) const MIN_ARCH_RATE_HZ: u64 = 1_000_000;
pub(crate) const MAX_ARCH_RATE_HZ: u64 = 10_000_000_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct Snapshot {
    pub raw_counter: u64,
    pub frequency_hz: u64,
    pub native_absolute_ticks: u64,
    pub architectural_ns: u64,
}

/// Exact rational floor conversion without u128 division or losing the epoch.
/// This agrees with the qualified C future-trial provider, including refusal.
pub(crate) fn scale(counter: u64, frequency_hz: u64, rate: u64) -> Option<u64> {
    if !(MIN_ARCH_RATE_HZ..=MAX_ARCH_RATE_HZ).contains(&frequency_hz)
        || rate == 0 || rate > 1_000_000_000 { return None; }
    let whole = counter / frequency_hz;
    let remainder = counter % frequency_hz;
    whole.checked_mul(rate)?.checked_add(remainder.checked_mul(rate)? / frequency_hz)
}

impl Snapshot {
    /// RAM-only constructor for qualification and source-bound clock records.
    pub(crate) fn from_sample(raw_counter: u64, frequency_hz: u64) -> Option<Self> {
        Some(Self { raw_counter, frequency_hz,
            native_absolute_ticks: scale(raw_counter, frequency_hz, NATIVE_RATE_HZ)?,
            architectural_ns: scale(raw_counter, frequency_hz, 1_000_000_000)?,
        })
    }

    /// Future authorized session only; never called by offline qualification.
    pub(crate) fn capture() -> Option<Self> {
        let frequency_hz: u64;
        let raw_counter: u64;
        // SAFETY: Standard read-only architectural CPU registers. ISB orders
        // the snapshot; no custom Apple register or memory pointer is accessed.
        unsafe { core::arch::asm!("mrs {frequency}, cntfrq_el0", "isb",
            "mrs {counter}, cntpct_el0",
            frequency = out(reg) frequency_hz, counter = out(reg) raw_counter,
            options(nostack, preserves_flags)); }
        Self::from_sample(raw_counter, frequency_hz)
    }
}
