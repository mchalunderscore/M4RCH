/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
#include <assert.h>
#include "policy.h"
int main(void)
{
    unsigned int bit;
    unsigned long long controls[] = {0, ~0ULL, 0x123456789abcdef0ULL};
    for (bit = 0; bit < 64; bit++) {
        unsigned long long value = 1ULL << bit;
        assert(fixed_owned(value) == !!(value & OWNER_MASK));
        assert((fixed_filter(value) & ~FIXED_FILTER) == (value & ~FIXED_FILTER));
        assert((fixed_filter(value) & FIXED_FILTER) == FIXED_KERNEL);
    }
    for (bit = 0; bit < sizeof(controls)/sizeof(controls[0]); bit++) {
        unsigned long long initial = controls[bit];
        assert((fixed_filter(initial) & ~FIXED_FILTER) == (initial & ~FIXED_FILTER));
        assert((fixed_filter(initial) & FIXED_FILTER) == FIXED_KERNEL);
    }
    return 0;
}
