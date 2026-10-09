/* SPDX-License-Identifier: GPL-2.0-only */
/* Experimental paired PMP/PMC notification, independent of MMIO bindings.
 * Success describes native STATUS0 skip or a valid ACK, then three vote words.
 * It never authorizes reset, restart, retirement or backing release.
 */
#ifndef M4RCH_GFX_COORDINATE_CORE_H
#define M4RCH_GFX_COORDINATE_CORE_H

#define GFX_COORD_STATUS_ENTRY 1U
#define GFX_COORD_REQUEST_ENTRY 0x1e0U
#define GFX_COORD_ACK_ENTRY 0x1e8U
#define GFX_COORD_REQUEST_BIT (1ULL << 13)
#define GFX_COORD_ACK_VALID_BIT (1ULL << 1)
#define GFX_COORD_VOTE_BIT (1U << 2)
#define GFX_COORD_RAILS 3U
#define GFX_COORD_TIMEOUT_NS 15000000000ULL
#define GFX_COORD_MAX_ACK_SAMPLES 15001U

struct gfx_coord_ops {
 void *context;
 int (*read_ptd)(void *, unsigned int, u64 *, u64 *);
 int (*write_ptd)(void *, unsigned int, u64);
 int (*read_vote)(void *, unsigned int, u32 *);
 int (*write_vote)(void *, unsigned int, u32);
 u64 (*now_ns)(void *);
 void (*delay)(void *);
 void (*event)(void *, const char *, unsigned int, u64, u64, int);
};

struct gfx_coord_session {
 bool on_attempted, on_complete, off_attempted, off_complete;
};

struct gfx_coord_observation {
 bool enabled, request_attempted, request_acked, ack_bypassed;
 unsigned int ack_samples, votes_attempted, votes_verified;
 u64 request_before, request_written, ack_payload, ack_status;
 u64 status_payload, status_raw;
 int result;
};

static int gfx_coord_result(struct gfx_coord_observation *observation, int ret)
{
 observation->result = ret > 0 ? -EIO : ret;
 return observation->result;
}

static int gfx_coord_read_ptd(const struct gfx_coord_ops *ops, const char *phase,
 unsigned int entry, u64 *payload, u64 *status)
{
 int ret;
 *payload = 0; *status = 0;
 ret = ops->read_ptd(ops->context, entry, payload, status);
 if (ret > 0) ret = -EIO;
 if (!ret && (*payload == ~0ULL || *status == ~0ULL)) ret = -EIO;
 ops->event(ops->context, phase, entry, *payload, *status, ret);
 return ret;
}

static int gfx_coord_read_vote(const struct gfx_coord_ops *ops, const char *phase,
 unsigned int rail, u32 *value)
{
 int ret;
 *value = 0;
 ret = ops->read_vote(ops->context, rail, value);
 if (ret > 0) ret = -EIO;
 if (!ret && *value == ~0U) ret = -EIO;
 ops->event(ops->context, phase, rail, *value, 0, ret);
 return ret;
}

static int gfx_coord_transition(struct gfx_coord_session *session,
 const struct gfx_coord_ops *ops, bool enabled,
 struct gfx_coord_observation *observation)
{
 u64 status_payload, status_raw, request, ack, ack_status, started;
 unsigned int rail;
 u32 vote, expected, observed;
 int ret;

 if (!session || !observation) return -EINVAL;
 *observation = (struct gfx_coord_observation){ .enabled = enabled };
 /* Consume each admission before invoking any external callback. */
 if (enabled) {
  if (session->on_attempted || session->off_attempted)
   return gfx_coord_result(observation, -EALREADY);
  session->on_attempted = true;
 } else {
  if (session->off_attempted)
   return gfx_coord_result(observation, -EALREADY);
  session->off_attempted = true;
  if (!session->on_complete)
   return gfx_coord_result(observation, -EPERM);
 }
 if (!ops || !ops->read_ptd || !ops->write_ptd || !ops->read_vote ||
     !ops->write_vote || !ops->now_ns || !ops->delay || !ops->event)
  return gfx_coord_result(observation, -EINVAL);

 ret = gfx_coord_read_ptd(ops, "status-before", GFX_COORD_STATUS_ENTRY,
                         &status_payload, &status_raw);
 observation->status_payload=status_payload;
 observation->status_raw=status_raw;
 if (ret) return gfx_coord_result(observation, ret);
 /* Native STATUS0 succeeds only after the full request write. This
  * observation does not establish PMP inactivity or an ACK. */
 ret = gfx_coord_read_ptd(ops, "request-before", GFX_COORD_REQUEST_ENTRY,
                         &request, &status_raw);
 if (ret) return gfx_coord_result(observation, ret);
 observation->request_before = request;
 ret = gfx_coord_read_ptd(ops, "ack-before", GFX_COORD_ACK_ENTRY,
                         &ack, &ack_status);
 if (ret) return gfx_coord_result(observation, ret);
 for (rail = 0; rail < GFX_COORD_RAILS; ++rail) {
  ret = gfx_coord_read_vote(ops, "vote-before", rail, &vote);
  if (ret) return gfx_coord_result(observation, ret);
 }
 /* Refresh after preflight so those extra reads do not widen the native
  * request RMW window. This remains non-atomic against an external writer.
  */
 ret = gfx_coord_read_ptd(ops, "request-current", GFX_COORD_REQUEST_ENTRY,
                         &request, &status_raw);
 if (ret) return gfx_coord_result(observation, ret);
 observation->request_before = request;
 observation->request_written = enabled ? request | GFX_COORD_REQUEST_BIT :
                                         request & ~GFX_COORD_REQUEST_BIT;
 /* A reported write error may still have reached hardware. No compensation
  * or second write follows any failure; all ownership stays retained.
  */
 observation->request_attempted = true;
 ops->event(ops->context, "request-intent", GFX_COORD_REQUEST_ENTRY,
            observation->request_written, 0, 0);
 ret = ops->write_ptd(ops->context, GFX_COORD_REQUEST_ENTRY,
                      observation->request_written);
 ops->event(ops->context, "request-return", GFX_COORD_REQUEST_ENTRY,
            observation->request_written, 0, ret);
 if (ret) return gfx_coord_result(observation, ret);
 started = ops->now_ns(ops->context);
 for (;;) {
  if (ops->now_ns(ops->context) - started >= GFX_COORD_TIMEOUT_NS)
   return gfx_coord_result(observation, -ETIMEDOUT);
  ret = gfx_coord_read_ptd(ops, "status-wait", GFX_COORD_STATUS_ENTRY,
                          &status_payload, &status_raw);
  observation->status_payload=status_payload;
  observation->status_raw=status_raw;
  if (ret) return gfx_coord_result(observation, ret);
  if (ops->now_ns(ops->context) - started >= GFX_COORD_TIMEOUT_NS)
   return gfx_coord_result(observation, -ETIMEDOUT);
  if (!status_payload) {observation->ack_bypassed=true;break;}
  ++observation->ack_samples;
  ret = gfx_coord_read_ptd(ops, "ack-wait", GFX_COORD_ACK_ENTRY,
                          &observation->ack_payload, &observation->ack_status);
  if (ret) return gfx_coord_result(observation, ret);
  /* A late ACK is not a within-deadline acknowledgement. */
  if (ops->now_ns(ops->context) - started >= GFX_COORD_TIMEOUT_NS)
   return gfx_coord_result(observation, -ETIMEDOUT);
  if ((observation->ack_status & GFX_COORD_ACK_VALID_BIT) &&
      !!(observation->ack_payload & GFX_COORD_REQUEST_BIT) == enabled) {
   observation->request_acked = true;
   break;
  }
  if (observation->ack_samples >= GFX_COORD_MAX_ACK_SAMPLES)
   return gfx_coord_result(observation, -ETIMEDOUT);
  ops->delay(ops->context);
 }
 /* Hardware status and MMIO reads are observations, not atomic snapshots.
  * Preserve the whole request payload and all other voter bits in our writes.
  */
 ret = gfx_coord_read_ptd(ops, "request-after-ack", GFX_COORD_REQUEST_ENTRY,
                         &request, &status_raw);
 if (ret) return gfx_coord_result(observation, ret);
 if (request != observation->request_written)
  return gfx_coord_result(observation, -EAGAIN);
 for (rail = 0; rail < GFX_COORD_RAILS; ++rail) {
  ret = gfx_coord_read_vote(ops, "vote-current", rail, &vote);
  if (ret) return gfx_coord_result(observation, ret);
  expected = enabled ? vote | GFX_COORD_VOTE_BIT : vote & ~GFX_COORD_VOTE_BIT;
  ++observation->votes_attempted;
  ops->event(ops->context, "vote-intent", rail, expected, vote, 0);
  ret = ops->write_vote(ops->context, rail, expected);
  ops->event(ops->context, "vote-return", rail, expected, vote, ret);
  if (ret) return gfx_coord_result(observation, ret);
  ret = gfx_coord_read_vote(ops, "vote-readback", rail, &observed);
  if (ret) return gfx_coord_result(observation, ret);
  if (observed != expected) return gfx_coord_result(observation, -EAGAIN);
  ++observation->votes_verified;
 }
 if (enabled) session->on_complete = true;
 else session->off_complete = true;
 return gfx_coord_result(observation, 0);
}
#endif
