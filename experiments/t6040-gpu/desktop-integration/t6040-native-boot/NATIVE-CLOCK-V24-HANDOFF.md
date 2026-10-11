# Future v24 clock provider

Apple mach_absolute_time reads its custom CPU timer and adds a stable per-CPU offset. Its native rate is independently sourced: the matched kernel selects /cpus children with state `running`, reads timebase-frequency, and passes the frequency to its timebase callback. The saved actual board ADT has running cpu4 and frequency 24,000,000 Hz. The callback reduces its nanosecond conversion ratio to 125/3.

The same saved Linux boot reports its architectural physical timer at 1,000,000,000 Hz. V8 scaled Linux ktime_get_raw nanoseconds to 24 MHz, but Linux initializes its raw time from a counter delta and zero base, so that conversion discards the architectural counter origin.

`gfx_native_clock_v24.h` supplies a future cold-trial provider using standard CPU CNTFRQ_EL0 and CNTPCT_EL0. The caller invokes `gfx_full_power_ticks_snapshot(&snapshot)` once and records all fields: raw_counter, frequency_hz, native_absolute_ticks, architectural_ns. It passes native_absolute_ticks directly to the Rust power wrapper and uses the same source for later QoS timestamps. The conversion preserves physical-counter origin while changing rate; at the saved 1 GHz rate it is floor(counter*3/125). It uses checked quotient/remainder arithmetic rather than overflowing a 64-bit product or depending on compiler 128-bit division support in kernel C.

This is explicit Linux clock policy. Equivalence of the standard physical counter origin to Apple's custom timer plus per-CPU offset remains unproven. Native firmware's need for that exact Apple offset is also unproven. The future bounded trial should retain the raw snapshot for interpretation. Do not read the custom register without a separate Linux-safe access source proof.

No CPU or GPU register was read during this investigation. All native evidence comes from saved kernelcache, disassembly and ADT; Linux frequency comes from the saved consumed-boot log. Frozen v8 source and module remain unchanged. The standalone Rust v9 proposal is unintegrated; the typed C header is the intended v24 interface.
