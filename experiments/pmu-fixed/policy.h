/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
#ifndef M4RCH_FIXED_POLICY_H
#define M4RCH_FIXED_POLICY_H
/* Fixed PMC0/1 and their execution-mode filters; no event selectors. */
#define FIXED_ENABLE 3ULL
#define FIXED_FILTER (3ULL | (3ULL << 8) | (3ULL << 16) | (3ULL << 24))
#define FIXED_KERNEL (3ULL << 16)
/* Include all ten counters and pending/enable interrupt state from Linux. */
#define OWNER_MASK (0xffULL | (3ULL << 32) | (0xffULL << 12) | \
                    (3ULL << 44) | (1ULL << 11))
static inline int fixed_owned(unsigned long long control)
{
    return !!(control & OWNER_MASK);
}
static inline unsigned long long fixed_filter(unsigned long long original)
{
    return (original & ~FIXED_FILTER) | FIXED_KERNEL;
}
#endif
