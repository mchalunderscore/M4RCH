// SPDX-License-Identifier: GPL-2.0-only
//! Explicit Linux absolute-counter policy. Not Apple's custom timer emulation.
//! Read this CPU source only in a future authorized fresh-session path.

#[derive(Clone, Copy, Debug)]
pub(crate) struct ArchitecturalSample {
    pub physical_counter: u64,
    pub frequency_hz: u64,
}

impl ArchitecturalSample {
    /// Preserve the architectural counter origin and scale its actual rate.
    /// Saved M4 Linux startup reports 1 GHz. Never assume CNTPCT itself is 24 MHz.
    pub(crate) fn to_linux_native_24mhz(self) -> Option<u64> {
        if self.frequency_hz == 0 { return None; }
        u64::try_from(u128::from(self.physical_counter) * 24_000_000
            / u128::from(self.frequency_hz)).ok()
    }

    /// Source proposal only. This helper is not called by any current stage.
    pub(crate) fn capture_for_future_session() -> Self {
        let frequency_hz: u64;
        let physical_counter: u64;
        // SAFETY: Read-only architectural CPU registers with no memory inputs.
        // ISB orders the counter snapshot with this future caller's work.
        unsafe { core::arch::asm!("mrs {frequency}, cntfrq_el0", "isb",
            "mrs {counter}, cntpct_el0",
            frequency = out(reg) frequency_hz, counter = out(reg) physical_counter,
            options(nostack, preserves_flags)); }
        Self { physical_counter, frequency_hz }
    }
}
