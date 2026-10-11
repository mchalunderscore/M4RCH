// SPDX-License-Identifier: GPL-2.0-only
//! Native G16X controller configuration and generic power lifecycle.
//!
//! This is the native child-4 object, never a donor bundle-relative layout.
//! Provider-independent configuration can be produced before the fuse and
//! absolute-time providers exist. The complete ARM override is still closed.

use super::float::F32;

pub(crate) const LOGICAL_BYTES: usize = 0x6578;
pub(crate) const HARDWARE_LOGICAL_BYTES: usize = 0x2718;
pub(crate) const REGION_C_LOGICAL_BYTES: usize = 0xe58;
pub(crate) const POWER_COMPLETE: bool = false;
pub(crate) const PERIOD_CLOCKS_PER_MS: u32 = 24000;
pub(crate) const DEFAULT_PERIOD_MS: u32 = 16;
pub(crate) const PERF_ROWS: usize = 16;
pub(crate) const CONTROLLER_IMAGE_BYTES: usize = 0x160;
pub(crate) const CONTROLLER_IMAGE_OFFSET: usize = 0xa0;
pub(crate) const HARDWARE_PERIOD_OFFSET: usize = 0xed8;

/// Native setupConfig optional raw words. The max-power properties are
/// intermediate inputs: G16X's calculated maximum subsequently overwrites them.
pub(crate) const OPTIONAL_WORD_PROPERTIES: &[&str] = &[
    "gpu-pwr-sample-period-aic-clks", "gpu-power-sample-period",
    "gpu-num-perf-states", "gpu-pwr-min-duty-cycle",
    "gpu-device-max-power", "gpu-max-power", "gpu-pwr-filter-time-constant",
    "gpu-pwr-integral-gain", "gpu-pwr-integral-min-clamp",
    "gpu-pwr-proportional-gain", "gpu-perf-base-pstate",
    "gpu-perf-tgt-utilization", "gpu-perf-dz",
    "gpu-perf-filter-time-constant", "gpu-perf-filter-time-constant2",
    "gpu-perf-filter-drop-threshold", "gpu-perf-integral-gain",
    "gpu-perf-integral-gain2", "gpu-perf-integral-min-clamp",
    "gpu-perf-proportional-gain", "gpu-perf-proportional-gain2",
    "gpu-perf-limiter-filter-time-constant",
];

pub(crate) const INITIAL_U32_FIELDS: &[(usize, u32)] = &[
    (0xc, 0), (0x10, 4), (0x14, 0x3f800000), (0x18, 0),
    (0x2c, 1), (0x30, 1), (0x34, 0), (0x50, 100),
    (0x5c, 0), (0x60, 4), (0x64, 0x3f800000), (0x68, 0),
    (0x6c, 1), (0x70, 1), (0x74, 0), (0x90, 100),
];

#[derive(Clone, Copy, Debug)]
pub(crate) struct PowerData {
    pub period_aic_clocks: u32,
    pub period_ms: u32,
    pub main_hz: [u32; PERF_ROWS],
    pub maximum_index: u32,
    pub minimum_duty: u32,
    pub base_index: u32,
    pub intermediate_maximum_property: Option<u32>,
    power_filter: u32,
    power_ki: u32,
    power_minimum: i32,
    power_kp: u32,
    perf_filters: [u32; 2],
    perf_drop_threshold: u32,
    perf_ki: [u32; 2],
    perf_minimum: i32,
    perf_kp: [u32; 2],
    target_utilization: u32,
    deadzone: u32,
    limiter_filter: u32,
}

/// These are required owned provider results, not ADT aliases or defaults.
/// Maximum power is the G16X fuse/voltage/topology calculation's final result.
/// Absolute ticks must use the firmware's time domain; Linux nanoseconds are
/// not interchangeable with the matched mach_absolute_time implementation.
#[derive(Clone, Copy, Debug)]
pub(crate) struct LifecycleProviders {
    pub calculated_maximum_power_mw: u32,
    pub native_absolute_ticks: u64,
    pub preserved_6530: [u8; 8],
    pub preserved_2888: [u8; 48],
}

impl LifecycleProviders {
    /// Capture the exact ARM-owned ranges before the generic full-object clear.
    /// A fresh native zeroed allocation naturally supplies zero ranges here;
    /// a reinitialization must capture its current owned bytes instead.
    pub(crate) fn capture(power: &[u8], maximum: u32, ticks: u64) -> Option<Self> {
        if power.len() < LOGICAL_BYTES || maximum == 0 || maximum > i32::MAX as u32 {
            return None;
        }
        Some(Self {
            calculated_maximum_power_mw: maximum,
            native_absolute_ticks: ticks,
            preserved_6530: power[0x6530..0x6538].try_into().ok()?,
            preserved_2888: power[0x2888..0x28b8].try_into().ok()?,
        })
    }
}

fn put32(out: &mut [u8], offset: usize, value: u32) {
    out[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
}

fn putf(out: &mut [u8], offset: usize, value: F32) {
    put32(out, offset, value.to_bits());
}

fn filters(count: u32) -> (F32, F32) {
    // Match UCvtF followed by subtraction and division, including the order of
    // conversion. Kernel software floating point keeps FPU use out of this path.
    let value = F32::from(count);
    ((value - F32::from(1u32)) / value, F32::from(1u32) / value)
}

impl PowerData {
    /// Inputs are original SGX ADT byte properties. Production exports them as
    /// exact apple,sgx-* aliases; no renamed artificial maximum-power property
    /// is accepted. This bounded producer selects the captured 2 x 16 main
    /// table geometry. Voltage-group count is not the performance cap.
    pub(crate) fn from_adt(properties: &[(&str, &[u8])]) -> Option<Self> {
        let property = |name: &str| -> Option<Option<&[u8]>> {
            let mut found = None;
            for &(key, value) in properties {
                if key == name {
                    if found.is_some() { return None; }
                    found = Some(value);
                }
            }
            Some(found)
        };
        let word = |name: &str, default: u32| -> Option<u32> {
            match property(name)? {
                Some(raw) => Some(u32::from_le_bytes(raw.try_into().ok()?)),
                None => Some(default),
            }
        };
        let count_raw = property("perf-state-count")??;
        let count = u32::from_le_bytes(count_raw.try_into().ok()?);
        let tables_raw = property("perf-state-table-count")??;
        let tables = u32::from_le_bytes(tables_raw.try_into().ok()?);
        if count != PERF_ROWS as u32 || tables != 2 { return None; }
        let maximum_index = count - 1;
        if word("gpu-num-perf-states", maximum_index)? != maximum_index { return None; }
        let rows = property("perf-states")??;
        if rows.len() != PERF_ROWS * 2 * 8 { return None; }
        let mut main_hz = [0u32; PERF_ROWS];
        for i in 0..PERF_ROWS {
            main_hz[i] = u32::from_le_bytes(rows[i * 8..i * 8 + 4].try_into().ok()?);
            let second = u32::from_le_bytes(
                rows[(PERF_ROWS + i) * 8..(PERF_ROWS + i) * 8 + 4].try_into().ok()?);
            if main_hz[i] != second { return None; }
        }
        if main_hz[PERF_ROWS - 1] == 0 { return None; }
        let (period_aic_clocks, period_ms) = match property("gpu-pwr-sample-period-aic-clks")? {
            Some(raw) => {
                let clocks = u32::from_le_bytes(raw.try_into().ok()?);
                (clocks, clocks / PERIOD_CLOCKS_PER_MS)
            }
            None => {
                let ms = word("gpu-power-sample-period", DEFAULT_PERIOD_MS)?;
                (ms.checked_mul(PERIOD_CLOCKS_PER_MS)?, ms)
            }
        };
        if period_aic_clocks == 0 || period_ms == 0 { return None; }
        let intermediate_maximum_property = match property("gpu-device-max-power")? {
            Some(raw) => Some(u32::from_le_bytes(raw.try_into().ok()?)),
            None => match property("gpu-max-power")? {
                Some(raw) => Some(u32::from_le_bytes(raw.try_into().ok()?)),
                None => None,
            },
        };
        let value = Self {
            period_aic_clocks, period_ms, main_hz, maximum_index,
            minimum_duty: word("gpu-pwr-min-duty-cycle", 40)?,
            base_index: word("gpu-perf-base-pstate", 1)?,
            intermediate_maximum_property,
            power_filter: word("gpu-pwr-filter-time-constant", 313)?,
            power_ki: word("gpu-pwr-integral-gain", 0x3ca59586)?,
            power_minimum: word("gpu-pwr-integral-min-clamp", 0)? as i32,
            power_kp: word("gpu-pwr-proportional-gain", 0x40a90fdb)?,
            perf_filters: [word("gpu-perf-filter-time-constant", 5)?,
                           word("gpu-perf-filter-time-constant2", 200)?],
            perf_drop_threshold: word("gpu-perf-filter-drop-threshold", 0)?,
            perf_ki: [word("gpu-perf-integral-gain", 0x3f64c986)?,
                      word("gpu-perf-integral-gain2", 0x3f64c986)?],
            perf_minimum: word("gpu-perf-integral-min-clamp", 0)? as i32,
            perf_kp: [word("gpu-perf-proportional-gain", 0x403ea7f0)?,
                      word("gpu-perf-proportional-gain2", 0x403ea7f0)?],
            target_utilization: word("gpu-perf-tgt-utilization", 80)?,
            deadzone: word("gpu-perf-dz", 0)?,
            limiter_filter: word("gpu-perf-limiter-filter-time-constant", 5)?,
        };
        value.valid().then_some(value)
    }

    fn valid(&self) -> bool {
        self.period_aic_clocks != 0 && self.period_ms != 0
            && self.period_aic_clocks / PERIOD_CLOCKS_PER_MS == self.period_ms
            && self.maximum_index == 15 && self.base_index != 0
            && self.base_index <= self.maximum_index
            && self.target_utilization >= self.deadzone
            && self.power_filter != 0 && self.perf_filters[0] != 0
            && self.perf_filters[1] != 0 && self.limiter_filter != 0
            && self.minimum_duty <= self.maximum_index * 100
            && [self.power_ki, self.power_kp, self.perf_ki[0], self.perf_ki[1],
                self.perf_kp[0], self.perf_kp[1]].iter().all(
                    |bits| bits & 0x7f800000 != 0x7f800000)
    }

    /// Independent controller image: the selected fresh firmware object starts
    /// zero, and G16X writes one 1.02 SRAM scale per native main-table entry.
    /// Chip leakage begins at CPU firmware + ae0, beyond image + 160.
    pub(crate) fn controller_image(&self) -> Option<[u8; CONTROLLER_IMAGE_BYTES]> {
        if !self.valid() { return None; }
        let mut image = [0u8; CONTROLLER_IMAGE_BYTES];
        for i in 0..PERF_ROWS { put32(&mut image, 0x20 + i * 4, 0x3f828f5c); }
        Some(image)
    }

    /// Write every provider-independent generic controller field and the
    /// already source-bound ARM fixed initializer. Unknown ARM-owned bytes
    /// remain unchanged. This partial writer never clears a reused allocation.
    pub(crate) fn write_component(&self, out: &mut [u8]) -> Option<()> {
        if out.len() < LOGICAL_BYTES || !self.valid() { return None; }
        let image = self.controller_image()?;
        out[CONTROLLER_IMAGE_OFFSET..CONTROLLER_IMAGE_OFFSET + image.len()]
            .copy_from_slice(&image);
        put32(out, 4, self.period_aic_clocks);
        put32(out, 8, self.period_aic_clocks);
        for &(offset, value) in INITIAL_U32_FIELDS { put32(out, offset, value); }
        put32(out, 0x9bc, 0);
        let (alpha, inverse) = filters(self.power_filter);
        putf(out, 0x9c4, alpha); putf(out, 0x9cc, inverse);
        put32(out, 0x9d4, self.power_ki); put32(out, 0x9e4, self.power_kp);
        putf(out, 0x9dc, F32::from(self.power_minimum));
        put32(out, 0x9f0, self.minimum_duty);
        let max_scaled = self.maximum_index * 100;
        put32(out, 0x9f4, max_scaled); put32(out, 0x9f8, max_scaled);
        put32(out, 0xa00, 0); put32(out, 0xa0c, 0);
        // Fresh CPU fields f2f8/f2fc are untouched by this selected setup.
        put32(out, 0xa34, 0); put32(out, 0xa38, max_scaled); put32(out, 0xa3c, 0);
        put32(out, 0xb44, 1); put32(out, 0xb48, self.perf_drop_threshold);
        for i in 0..2 {
            let (alpha, inverse) = filters(self.perf_filters[i]);
            putf(out, 0xb4c + i * 4, alpha); putf(out, 0xb54 + i * 4, inverse);
            put32(out, 0xb5c + i * 4, self.perf_ki[i]);
            put32(out, 0xb6c + i * 4, self.perf_kp[i]);
        }
        putf(out, 0xb64, F32::from(self.perf_minimum));
        putf(out, 0xb68, F32::from(95i32));
        putf(out, 0xb74, F32::from((self.maximum_index - self.base_index) * 100)
            / F32::from(95i32));
        let base_scaled = self.base_index * 100;
        put32(out, 0xb78, base_scaled); put32(out, 0xb7c, max_scaled);
        put32(out, 0xb80, base_scaled); put32(out, 0xb88, 0);
        let target = self.target_utilization - self.deadzone;
        put32(out, 0xb8c, target); put32(out, 0xb28, target);
        put32(out, 0xb94, self.deadzone);
        // Fresh CPU fields f358/f35c remain zero in the selected setup path.
        putf(out, 0xbbc, F32::from(0u32));
        put32(out, 0xbc0, base_scaled); put32(out, 0xbc4, 0);
        put32(out, 0x2870, max_scaled); put32(out, 0x2218, 0x42c80000);
        put32(out, 0x221c, max_scaled); put32(out, 0x2220, 0);
        let (alpha, inverse) = filters(self.limiter_filter);
        putf(out, 0x2224, alpha); putf(out, 0x2228, inverse);
        out[0xbef..0x1bef].fill(0);
        for pair in out[0x1bef..0x1fef].chunks_exact_mut(2) {
            pair.copy_from_slice(&0x7fffu16.to_le_bytes());
        }
        out[0x1fef..0x21ef].fill(0);
        Some(())
    }

    /// The generic full clear and ARM save/restore are one lifecycle operation.
    /// This requires genuine provider outputs. Remaining ARM controller writes
    /// are not synthesized, and POWER_COMPLETE remains false after success.
    pub(crate) fn write_lifecycle_component(
        &self, out: &mut [u8], providers: &LifecycleProviders,
    ) -> Option<()> {
        let maximum = providers.calculated_maximum_power_mw;
        if out.len() < LOGICAL_BYTES || !self.valid()
            || maximum == 0 || maximum > i32::MAX as u32 { return None; }
        out[..LOGICAL_BYTES].fill(0);
        self.write_component(out)?;
        putf(out, 0x9e0, F32::from(maximum as i32));
        putf(out, 0x9ec, -F32::from(self.maximum_index * 100) / F32::from(maximum));
        put32(out, 0xa04, maximum);
        out[0x63d4..0x63dc].copy_from_slice(&providers.native_absolute_ticks.to_le_bytes());
        out[0x6530..0x6538].copy_from_slice(&providers.preserved_6530);
        out[0x2888..0x28b8].copy_from_slice(&providers.preserved_2888);
        Some(())
    }

    pub(crate) fn write_hardware_component(&self, out: &mut [u8]) -> Option<()> {
        if out.len() < HARDWARE_LOGICAL_BYTES || !self.valid() { return None; }
        put32(out, HARDWARE_PERIOD_OFFSET, self.period_ms);
        put32(out, 0xfc4, self.maximum_index);
        for i in 0..PERF_ROWS {
            put32(out, 0xfc8 + i * 4, ((self.main_hz[i] as u64 * 0x431bde83) >> 50) as u32);
        }
        Some(())
    }

    /// CPU + 19f20 is a distinct native frequency owner; this API deliberately
    /// requires its resolved values and never aliases a donor/ADT domain.
    pub(crate) fn write_secondary_hardware_component(
        &self, out: &mut [u8], native_secondary_hz: &[u32; PERF_ROWS],
    ) -> Option<()> {
        if out.len() < HARDWARE_LOGICAL_BYTES || !self.valid() { return None; }
        for i in 0..PERF_ROWS {
            put32(out, 0x1808 + i * 4,
                ((native_secondary_hz[i] as u64 * 0x431bde83) >> 50) as u32);
        }
        Some(())
    }

    /// Initial enabled interfaces use native target 65536. This is the exact
    /// reverse table search and integer interpolation, not voltage-group count.
    fn initial_interface_limit(&self) -> Option<u32> {
        let mhz = self.main_hz.map(|hz| ((hz as u64 * 0x431bde83) >> 50) as u32);
        let target = mhz[self.maximum_index as usize];
        let mut upper = self.maximum_index as usize;
        while upper != 0 && target <= mhz[upper - 1] { upper -= 1; }
        if upper == 0 { return None; }
        let lower = upper - 1;
        let delta = mhz[upper].checked_sub(mhz[lower])?;
        if delta == 0 { return None; }
        let interpolated = (lower as u32 * 100)
            + target.checked_sub(mhz[lower])?.checked_mul(100)? / delta;
        Some(interpolated.max(self.minimum_duty))
    }

    pub(crate) fn write_region_c_component(
        &self, out: &mut [u8], providers: &LifecycleProviders,
    ) -> Option<()> {
        if out.len() < REGION_C_LOGICAL_BYTES || !self.valid()
            || providers.calculated_maximum_power_mw == 0
            || providers.calculated_maximum_power_mw > i32::MAX as u32 { return None; }
        let limit = self.initial_interface_limit()?;
        put32(out, 0x84, providers.calculated_maximum_power_mw);
        put32(out, 0x88, limit); put32(out, 0x8c, limit);
        Some(())
    }
}
