/* SPDX-License-Identifier: GPL-2.0-only */
#define GFX_COLD_AP_ON 0x00b0000000000020ULL
static bool gfx_ap_cold_request_attempted,gfx_ap_cold_request_write_attempted;
static bool gfx_ap_cold_reply_observed,gfx_ap_remote_known;
static u64 gfx_ap_cold_request_message,gfx_ap_cold_request_metadata;
static u64 gfx_ap_cold_reply_message,gfx_ap_cold_reply_metadata;
static u32 gfx_ap_remote_state;
static u8 gfx_cold_apps_started;
static void gfx_cold_ap_log(const char *phase)
{
 pr_info("m4rch gfx-cold-render-ap: phase=%s request_attempted=%u write_attempted=%u request_message=%#llx request_metadata=%#llx reply_observed=%u reply_message=%#llx reply_metadata=%#llx remote_known=%u remote_state=%#x\n",
  phase,gfx_ap_cold_request_attempted,gfx_ap_cold_request_write_attempted,
  (unsigned long long)gfx_ap_cold_request_message,(unsigned long long)gfx_ap_cold_request_metadata,
  gfx_ap_cold_reply_observed,(unsigned long long)gfx_ap_cold_reply_message,
  (unsigned long long)gfx_ap_cold_reply_metadata,gfx_ap_remote_known,gfx_ap_remote_state);
}
static bool gfx_cold_ap_known(void)
{
 return gfx_ap_cold_request_attempted && gfx_ap_cold_request_write_attempted &&
  gfx_ap_cold_reply_observed && gfx_ap_remote_known && gfx_ap_remote_state==0x20 &&
  gfx_ap_cold_request_message==GFX_COLD_AP_ON && !gfx_ap_cold_request_metadata &&
  gfx_ap_cold_reply_message==GFX_COLD_AP_ON && gfx_ap_cold_reply_metadata!=~0ULL &&
  !(gfx_ap_cold_reply_metadata&0xff);
}
