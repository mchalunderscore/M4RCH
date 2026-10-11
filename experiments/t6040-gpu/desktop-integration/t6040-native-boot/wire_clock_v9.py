#!/usr/bin/env python3
"""Apply one absolute architectural clock origin to native power and QoS.

The caller owns the new stage. This helper only edits its source dictionary;
no frozen source directory, module, device or register is touched here.
"""
from pathlib import Path
from stage_v7 import change
KIT=Path(__file__).resolve().parent


def wiring(files):
    files['g16_native_clock.rs']=(KIT/'g16_native_clock_v9.rs').read_text()
    change(files,'asahi_m4.rs','mod g16_t6040_power;\n','mod g16_t6040_power;\nmod g16_native_clock;\n')
    change(files,'g16.rs','let enabled_cores = native.masks.iter().map(|mask| mask.count_ones()).sum();',
           'let enabled_cores: u32 = native.masks.iter().map(|mask| mask.count_ones()).sum();')
    change(files,'g16.rs','''            // Same raw monotonic origin as persistent QoS publication.
            // SAFETY: The kernel raw monotonic service has no pointer inputs.
            let ns = u64::try_from(unsafe { kernel::bindings::ktime_get_raw() }).map_err(|_| EINVAL)?;
            let policy = crate::g16_t6040_power::LinuxBootPolicy::t6040_20w_24mhz(
                ns, enabled_cores, clusters).ok_or(EINVAL)?;''','''            // Power and persistent QoS share the physical architectural
            // counter origin; 24 MHz is the matched native timebase rate.
            if enabled_cores != 16 || clusters != 2 { return Err(EINVAL); }
            let clock = crate::g16_native_clock::Snapshot::capture().ok_or(EINVAL)?;
            dev_info!(dev, "G16: native clock physical={:#x} frequency={} ticks={:#x} ns={} Linux_epoch_policy=1\\n",
                clock.raw_counter, clock.frequency_hz, clock.native_absolute_ticks, clock.architectural_ns);
            let policy = crate::g16_t6040_power::LinuxBootPolicy {
                maximum_power_mw: 20000, native_absolute_ticks: clock.native_absolute_ticks,
            };''')
    change(files,'g16_runtime.rs','''        // SAFETY: The kernel raw monotonic time service has no pointer inputs.
        let raw_ns = u64::try_from(unsafe { kernel::bindings::ktime_get_raw() }).map_err(|_| EINVAL)?;
        let native_ticks = u64::try_from(u128::from(raw_ns) * 24_000_000 / 1_000_000_000).map_err(|_| EINVAL)?;''','''        // Each publication samples the same physical counter origin used by
        // the native power initializer. Neither path uses boot-relative time.
        let native_ticks = crate::g16_native_clock::Snapshot::capture()
            .ok_or(EINVAL)?.native_absolute_ticks;''')
