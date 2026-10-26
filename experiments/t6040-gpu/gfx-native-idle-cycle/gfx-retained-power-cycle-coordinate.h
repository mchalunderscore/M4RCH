/* SPDX-License-Identifier: GPL-2.0-only */
/* Separate second coordinator session. Never reset first session/observations. */
static bool gfx_retained_cycle_first_coord_complete(void)
{
 return gfx_coord_owner_session.on_attempted && gfx_coord_owner_session.on_complete &&
  gfx_coord_owner_session.off_attempted && gfx_coord_owner_session.off_complete &&
  gfx_coord_owner_module_pinned && gfx_coord_owner_startup_retained;
}
static int gfx_retained_cycle_coordinate_on(void)
{
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if(!gfx_retained_cycle_first_coord_complete() || !gfx_coord_owner_pmp ||
    !gfx_coord_owner_pmc || !gfx_coord_owner_pmp_region || !gfx_coord_owner_pmc_region)
  return -EBUSY;
 ret=gfx_coord_owner_alias_check();
 if(!ret) ret=gfx_coord_transition(&gfx_retained_cycle_coord_session,
  &gfx_coord_owner_ops,true,&gfx_retained_cycle_coord_on);
 pr_info("m4rch gfx-retained-cycle-coordinate: epoch=2 enabled=1 result=%d on_attempted=%u on_complete=%u request_attempted=%u request_acked=%u ack_bypassed=%u request_before=%#llx request_written=%#llx status_payload=%#llx status_raw=%#llx votes_attempted=%u votes_verified=%u first_on_complete=%u first_off_complete=%u first_session_reset=0\n",
  ret,gfx_retained_cycle_coord_session.on_attempted,gfx_retained_cycle_coord_session.on_complete,
  gfx_retained_cycle_coord_on.request_attempted,gfx_retained_cycle_coord_on.request_acked,
  gfx_retained_cycle_coord_on.ack_bypassed,
  (unsigned long long)gfx_retained_cycle_coord_on.request_before,
  (unsigned long long)gfx_retained_cycle_coord_on.request_written,
  (unsigned long long)gfx_retained_cycle_coord_on.status_payload,
  (unsigned long long)gfx_retained_cycle_coord_on.status_raw,
  gfx_retained_cycle_coord_on.votes_attempted,gfx_retained_cycle_coord_on.votes_verified,
  gfx_coord_owner_session.on_complete,gfx_coord_owner_session.off_complete);
 return ret;
}
static int gfx_retained_cycle_coordinate_off(void)
{
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if(!gfx_retained_cycle_first_coord_complete() || !gfx_retained_cycle_coord_session.on_complete ||
    !gfx_coord_owner_pmp || !gfx_coord_owner_pmc || !gfx_coord_owner_pmp_region || !gfx_coord_owner_pmc_region)
  return -EBUSY;
 ret=gfx_coord_owner_alias_check();
 if(!ret) ret=gfx_coord_transition(&gfx_retained_cycle_coord_session,
  &gfx_coord_owner_ops,false,&gfx_retained_cycle_coord_off);
 pr_info("m4rch gfx-retained-cycle-coordinate: epoch=2 enabled=0 result=%d off_attempted=%u off_complete=%u request_attempted=%u request_acked=%u ack_bypassed=%u request_before=%#llx request_written=%#llx status_payload=%#llx status_raw=%#llx votes_attempted=%u votes_verified=%u first_on_complete=%u first_off_complete=%u first_session_reset=0\n",
  ret,gfx_retained_cycle_coord_session.off_attempted,gfx_retained_cycle_coord_session.off_complete,
  gfx_retained_cycle_coord_off.request_attempted,gfx_retained_cycle_coord_off.request_acked,
  gfx_retained_cycle_coord_off.ack_bypassed,
  (unsigned long long)gfx_retained_cycle_coord_off.request_before,
  (unsigned long long)gfx_retained_cycle_coord_off.request_written,
  (unsigned long long)gfx_retained_cycle_coord_off.status_payload,
  (unsigned long long)gfx_retained_cycle_coord_off.status_raw,
  gfx_retained_cycle_coord_off.votes_attempted,gfx_retained_cycle_coord_off.votes_verified,
  gfx_coord_owner_session.on_complete,gfx_coord_owner_session.off_complete);
 return ret;
}
