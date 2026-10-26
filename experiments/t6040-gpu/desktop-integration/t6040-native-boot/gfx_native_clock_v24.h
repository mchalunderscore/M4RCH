/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef GFX_NATIVE_CLOCK_V24_H
#define GFX_NATIVE_CLOCK_V24_H
#include <linux/errno.h>
#include <linux/math64.h>
#include <linux/overflow.h>
#include <linux/types.h>

/* Explicit Linux physical-counter origin; Apple per-CPU offset is not emulated.
 * The matched native timebase provider takes running CPU ADT frequency 24 MHz.
 * Saved Linux startup takes the standard physical counter at 1 GHz instead.
 * This header performs no reads until its future fresh-trial caller invokes it.
 */
struct gfx_full_power_clock_snapshot {
    u64 raw_counter;
    u64 frequency_hz;
    u64 native_absolute_ticks;
    u64 architectural_ns;
};

static inline int gfx_full_power_clock_scale(u64 counter, u64 frequency,
                                             u64 rate, u64 *result)
{
    u64 whole, remainder, coarse, fine;
    /* Bound the remainder product for both 24 MHz and nanosecond conversion. */
    if (frequency < 1000000ULL || frequency > 10000000000ULL ||
        !rate || rate > 1000000000ULL)
        return -EINVAL;
    whole = div64_u64_rem(counter, frequency, &remainder);
    if (check_mul_overflow(whole, rate, &coarse) ||
        check_mul_overflow(remainder, rate, &fine))
        return -EOVERFLOW;
    fine = div64_u64(fine, frequency);
    if (check_add_overflow(coarse, fine, result))
        return -EOVERFLOW;
    return 0;
}

static inline int gfx_full_power_ticks_snapshot(struct gfx_full_power_clock_snapshot *out)
{
    struct gfx_full_power_clock_snapshot sample;
    int error;
    if (!out)
        return -EINVAL;
    /* Read only standard architectural CPU registers. Do not read Apple's
     * custom S3_4_C15_C10_6 or assume a Linux-safe custom-register access. */
    asm volatile("mrs %0, cntfrq_el0\n\tisb\n\tmrs %1, cntpct_el0"
                 : "=r" (sample.frequency_hz), "=r" (sample.raw_counter)
                 : : "memory");
    error = gfx_full_power_clock_scale(sample.raw_counter, sample.frequency_hz,
                                      24000000ULL, &sample.native_absolute_ticks);
    if (error)
        return error;
    error = gfx_full_power_clock_scale(sample.raw_counter, sample.frequency_hz,
                                      1000000000ULL, &sample.architectural_ns);
    if (error)
        return error;
    *out = sample;
    return 0;
}
#endif
