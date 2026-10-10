/* SPDX-License-Identifier: GPL-2.0-only */
/* Read-only runtime admission after the exact native Fender enable has been
 * verified. Gravity's PMGR provider considers TARGETf plus AUTO active even
 * when ACTUAL gates. This experiment admits only its named states0/4/f;
 * unknown intermediate states remain refused. It does not change PMGR policy,
 * synthesize physical OFF, or establish GPU execution or DMA retirement.
 */
#ifndef GFX_NATIVE_FENDER_RUNTIME_CYCLE_TRIAL
#error Distinct native Fender runtime cycle profile required
#endif
#define GFX_RUNTIME_BLOCKED_MASK 0x80001c00U
#define GFX_RUNTIME_STRICT_MASK 0x80001cffU

static bool gfx_runtime_active_word(u32 word,bool fender_complete)
{
 u32 actual=(word>>4)&15U;
 if(word==~0U) return false;
 if(!fender_complete) return (word&GFX_RUNTIME_STRICT_MASK)==0xffU;
 if((word&GFX_RUNTIME_BLOCKED_MASK) || (word&15U)!=15U) return false;
 if(actual==15U) return true;
 return (word&0x10000000U) && (actual==0U || actual==4U);
}

/* Include after gfx-native-fender-enable.h. The caller must first normalize
 * its fresh provider snapshot and refuse every snapshot error. BEFORE validity
 * is checked again. PM reference, consumer/174-page identity, coordinate ON
 * and all application guards remain caller requirements. No hardware access.
 */
static bool gfx_native_runtime_active(const char *phase,u32 valid,bool domain_on,u32 word)
{
 bool fender_complete=gfx_native_fender_enable_complete && !gfx_native_fender_enable_unknown;
 bool policy_known=!gfx_native_fender_enable_unknown &&
  (!gfx_native_fender_enable_attempted || fender_complete);
 bool accepted=policy_known && (valid&APPLE_PMGR_GFX_VALID_BEFORE) && domain_on &&
  gfx_runtime_active_word(word,fender_complete);
 pr_info("m4rch gfx-runtime-active: phase=%s valid=%#x domain_on=%u word=%#x fender_complete=%u policy_known=%u policy=%s accepted=%u actual=%u target=%u auto=%u auto_state=%u min_state=%u blocked=%#x operand_samples_atomic=0\n",
  phase,valid,domain_on,word,fender_complete,policy_known,
  fender_complete?"dynamic-auto":"strict-ff",accepted,(word>>4)&15U,
  word&15U,!!(word&0x10000000U),(word>>24)&15U,
  (word>>16)&15U,word&GFX_RUNTIME_BLOCKED_MASK);
 return accepted;
}

/* Caller samples application operands only after physical/owner admission.
 * This preserves the existing zero-state/control/trace/idle predicates while
 * reporting the precise failed operand instead of only draw-admission EBUSY.
 */
static bool gfx_runtime_application_guard(unsigned int count,unsigned int expected_trace,
 bool idle_required,bool idle_observed,bool live,u64 counter,u32 phase,u32 host_stop,
 u32 request_state,u32 request_flag,const u32 control[3],u32 trace)
{
 const char *condition="none";
 if(counter) condition="counter";
 else if(phase) condition="phase";
 else if(host_stop) condition="host-stop";
 else if(request_state) condition="request-state";
 else if(request_flag) condition="request-flag";
 else if(control[0]!=count || control[1]!=count || control[2]!=count) condition="control";
 else if(trace!=expected_trace) condition="trace";
 else if(idle_required && !idle_observed) condition="work-not-idle";
 else if(!live) condition="identity-or-pm";
 if(condition[0]=='n') return true;
 pr_info("m4rch gfx-runtime-guard-refused: condition=%s expected_count=%u expected_trace=%u counter=%llu phase=%u host_stop=%u request_state=%u request_flag=%u control=%u/%u/%u trace=%u idle_required=%u idle=%u live=%u operand_samples_atomic=0\n",
  condition,count,expected_trace,(unsigned long long)counter,phase,host_stop,
  request_state,request_flag,control[0],control[1],control[2],trace,
  idle_required,idle_observed,live);
 return false;
}
