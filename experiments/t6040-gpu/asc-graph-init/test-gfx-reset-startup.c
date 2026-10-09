/* SPDX-License-Identifier: GPL-2.0-only */
/* Includes the unchanged actual feature guard and hello_init admission block.
 * The first subsequent allocation is a recorder; no kernel or device access.
 */
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include "actual-feature-guard.inc"

static unsigned int run_gate,allocation_calls;
static bool resident_session,request_shutdown,warm_restart,release_on_shutdown;

static int startup_prefix(void)
{
 int ret=0;
 (void)ret;
#include "actual-startup-admission.inc"
 allocation_calls++;
 return 0;
}

int main(void)
{
 const struct {unsigned int gate;int clean[2];} cases[]={
  {0,{-EINVAL,-EINVAL}},
  {1,{0,-EINVAL}},
  {2,{-EINVAL,0}},
  {3,{-EINVAL,-EINVAL}},
  {UINT_MAX,{-EINVAL,-EINVAL}},
 };
 unsigned int tested=0;
 for(unsigned int i=0;i<sizeof(cases)/sizeof(cases[0]);i++)
  for(unsigned int resident=0;resident<2;resident++)
   for(unsigned int flags=0;flags<8;flags++) {
    unsigned int before=allocation_calls;
    int expected;
    run_gate=cases[i].gate;
    resident_session=resident;
    request_shutdown=!!(flags&1);
    warm_restart=!!(flags&2);
    release_on_shutdown=!!(flags&4);
#ifdef GFX_RESET_SCOPE_TRIAL
    expected=flags?-EINVAL:cases[i].clean[resident];
    assert(gfx_reset_scope_startup_admission(run_gate,resident_session,
     request_shutdown,warm_restart,release_on_shutdown)==expected);
#else
    /* The additional GFX guard must impose no change when compiled out.
     * This replay covers this prefix, not later preexisting startup checks.
     */
    expected=0;
#endif
    assert(startup_prefix()==expected);
    assert(allocation_calls==before+(expected==0));
    tested++;
   }
#ifdef GFX_RESET_SCOPE_TRIAL
 printf("feature_on_actual_C_admission_cases=%u accepted=%u rejected_before_allocation=%u\n",
  tested,allocation_calls,tested-allocation_calls);
#else
 printf("feature_off_actual_C_prefix_cases=%u new_guard_restrictions=0\n",tested);
#endif
 return 0;
}
