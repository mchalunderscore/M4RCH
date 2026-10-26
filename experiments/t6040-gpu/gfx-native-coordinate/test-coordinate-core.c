/* SPDX-License-Identifier: GPL-2.0-only */
/* RAM-only qualification of the actual protocol header. No device access. */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint64_t u64;
typedef uint32_t u32;
#include "gfx-coordinate-core.h"

#define TRACE_MAX 40000U
struct operation { char kind; unsigned int index; u64 value; };
enum ack_mode { MATCH, INVALID, ZERO_ACK, WRONG_BIT, DECODED_BIT54 };
struct rig {
 struct gfx_coord_session session;
 struct gfx_coord_ops ops;
 struct operation trace[TRACE_MAX];
 unsigned int io_count, events, clocks, delays, request_writes, vote_writes;
 unsigned int vote_reads[GFX_COORD_RAILS], ack_waits;
 unsigned int fail_at, all_ones_at, clock_jump_at;
 bool ones_status, delivered_error, wrote_request, status_zero_before;
 bool status_zero_wait, changed_request, mutate_snapshot, snapshot_mutated, mutate_at_write;
 int fail_result, bad_vote_rail, current_vote_rail;
 enum ack_mode ack_mode;
 u64 request, request_initial, initial_votes[GFX_COORD_RAILS];
 u32 votes[GFX_COORD_RAILS];
 u64 now, delay_ns, ack_latency_ns;
};
static const char *case_name;
static unsigned int cases, assertions;
static unsigned long long total_io;
#define CHECK(x) do { ++assertions; if (!(x)) { \
 fprintf(stderr, "%s: line %d: %s\n", case_name, __LINE__, #x); exit(1); \
} } while (0)

static int io(struct rig *r, char kind, unsigned int index, u64 value)
{
 CHECK(r->io_count < TRACE_MAX);
 r->trace[r->io_count++] = (struct operation){kind,index,value};
 ++total_io;
 return r->io_count == r->fail_at ? r->fail_result : 0;
}
static int read_ptd(void *context, unsigned int entry, u64 *payload, u64 *status)
{
 struct rig *r=context;
 int ret=io(r,'p',entry,0);
 if (ret) { *payload=0x123; *status=0x456; return ret; }
 *payload=0; *status=2;
 if (entry==GFX_COORD_STATUS_ENTRY)
  *payload=(r->status_zero_before || (r->wrote_request && r->status_zero_wait)) ? 0 : 1;
 else if (entry==GFX_COORD_REQUEST_ENTRY) {
  if (r->wrote_request && r->changed_request) r->request ^= 1ULL<<39;
  *payload=r->request;
 } else if (entry==GFX_COORD_ACK_ENTRY) {
  *payload=r->request;
  if (r->wrote_request) {
   ++r->ack_waits;
   r->now += r->ack_latency_ns;
   if (r->ack_mode==INVALID) *status=0;
   if (r->ack_mode==ZERO_ACK) { *status=0; *payload=0; }
   if (r->ack_mode==WRONG_BIT) *payload ^= GFX_COORD_REQUEST_BIT;
   if (r->ack_mode==DECODED_BIT54) *status=1ULL<<54;
  }
 } else CHECK(false);
 if (r->io_count==r->all_ones_at) {
  if (r->ones_status) *status=~0ULL; else *payload=~0ULL;
 }
 return 0;
}
static int write_ptd(void *context, unsigned int entry, u64 value)
{
 struct rig *r=context;
 int ret=io(r,'P',entry,value);
 CHECK(entry==GFX_COORD_REQUEST_ENTRY);
 ++r->request_writes;
 if (r->mutate_at_write) { r->request |= 1ULL<<39; r->snapshot_mutated=true; }
 if (!ret || r->delivered_error) { r->request=value; r->wrote_request=true; }
 return ret;
}
static int read_vote(void *context, unsigned int rail, u32 *value)
{
 struct rig *r=context;
 int ret=io(r,'v',rail,0);
 CHECK(rail<GFX_COORD_RAILS);
 if (ret) { *value=0x123; return ret; }
 ++r->vote_reads[rail];
 if (r->mutate_snapshot && !r->snapshot_mutated) {
  r->request |= 1ULL<<39; r->snapshot_mutated=true;
 }
 if ((int)rail==r->current_vote_rail && r->vote_reads[rail]==2)
  r->votes[rail] |= 1U<<30;
 *value=r->votes[rail];
 if ((int)rail==r->bad_vote_rail && r->vote_reads[rail]==3) *value ^= 1U<<29;
 if (r->io_count==r->all_ones_at) *value=~0U;
 return 0;
}
static int write_vote(void *context, unsigned int rail, u32 value)
{
 struct rig *r=context;
 int ret=io(r,'V',rail,value);
 CHECK(rail<GFX_COORD_RAILS);
 ++r->vote_writes;
 if (!ret || r->delivered_error) r->votes[rail]=value;
 return ret;
}
static u64 now_ns(void *context)
{
 struct rig *r=context;
 ++r->clocks;
 if (r->clocks==r->clock_jump_at) r->now += GFX_COORD_TIMEOUT_NS;
 return r->now;
}
static void delay(void *context)
{
 struct rig *r=context;
 ++r->delays; r->now += r->delay_ns;
}
static void event(void *context, const char *phase, unsigned int entry,
                  u64 payload, u64 status, int result)
{
 struct rig *r=context;
 (void)phase; (void)entry; (void)payload; (void)status; (void)result;
 ++r->events;
}
static struct rig *new_rig(const char *name)
{
 struct rig *r=calloc(1,sizeof(*r));
 case_name=name; ++cases; CHECK(r!=NULL);
 r->request=r->request_initial=0x8123456789010001ULL;
 r->votes[0]=0xa55a0201U; r->votes[1]=0x11223340U; r->votes[2]=0x00800008U;
 for (unsigned int i=0;i<GFX_COORD_RAILS;++i) r->initial_votes[i]=r->votes[i];
 r->fail_result=-EIO; r->bad_vote_rail=-1; r->current_vote_rail=-1;
 r->delay_ns=1000000;
 r->ops=(struct gfx_coord_ops){r,read_ptd,write_ptd,read_vote,write_vote,now_ns,delay,event};
 return r;
}
static void reset_trace(struct rig *r)
{
 r->io_count=r->events=r->clocks=r->delays=r->request_writes=r->vote_writes=0;
 r->ack_waits=0; r->wrote_request=false; r->now=0;
 memset(r->vote_reads,0,sizeof(r->vote_reads));
}
static void prime_off(struct rig *r)
{
 struct gfx_coord_observation observation;
 CHECK(gfx_coord_transition(&r->session,&r->ops,true,&observation)==0);
 CHECK(r->session.on_complete);
 reset_trace(r);
}
static int transition(struct rig *r, bool enabled, struct gfx_coord_observation *o)
{
 int result=gfx_coord_transition(&r->session,&r->ops,enabled,o);
 CHECK(o->result==result);
 return result;
}
static void expected_trace(struct rig *r)
{
 static const struct operation expected[]={
  {'p',1,0},{'p',0x1e0,0},{'p',0x1e8,0},{'v',0,0},{'v',1,0},{'v',2,0},
  {'p',0x1e0,0},{'P',0x1e0,0},{'p',1,0},{'p',0x1e8,0},{'p',0x1e0,0},
  {'v',0,0},{'V',0,0},{'v',0,0},{'v',1,0},{'V',1,0},{'v',1,0},
  {'v',2,0},{'V',2,0},{'v',2,0}};
 CHECK(r->io_count==sizeof(expected)/sizeof(expected[0]));
 for (unsigned int i=0;i<r->io_count;++i) {
  CHECK(r->trace[i].kind==expected[i].kind);
  CHECK(r->trace[i].index==expected[i].index);
 }
 CHECK(r->request_writes==1 && r->vote_writes==3);
}
static void paired(void)
{
 struct rig *r=new_rig("paired ON/OFF full-width ordered trace");
 struct gfx_coord_observation o;
 CHECK(transition(r,true,&o)==0); expected_trace(r);
 CHECK(r->request==(r->request_initial|GFX_COORD_REQUEST_BIT));
 CHECK(r->request>>32==r->request_initial>>32);
 CHECK(o.request_acked && o.ack_samples==1 && o.votes_verified==3);
 for (unsigned int i=0;i<3;++i) CHECK(r->votes[i]==(r->initial_votes[i]|GFX_COORD_VOTE_BIT));
 reset_trace(r);
 CHECK(transition(r,false,&o)==0); expected_trace(r);
 CHECK(r->request==r->request_initial);
 for (unsigned int i=0;i<3;++i) CHECK(r->votes[i]==r->initial_votes[i]);
 CHECK(r->session.on_complete && r->session.off_complete);
 unsigned int calls=r->io_count+r->events+r->clocks+r->delays;
 CHECK(transition(r,true,&o)==-EALREADY);
 CHECK(transition(r,false,&o)==-EALREADY);
 CHECK(calls==r->io_count+r->events+r->clocks+r->delays);
 free(r);
}
static void admission(void)
{
 struct gfx_coord_observation o;
 struct rig *r=new_rig("OFF without ON consumes admission without callbacks");
 CHECK(transition(r,false,&o)==-EPERM);
 CHECK(transition(r,false,&o)==-EALREADY);
 CHECK(transition(r,true,&o)==-EALREADY);
 CHECK(r->io_count==0 && r->events==0 && r->clocks==0 && r->delays==0); free(r);
 r=new_rig("repeated ON before OFF invokes no callbacks");
 CHECK(transition(r,true,&o)==0); reset_trace(r);
 CHECK(transition(r,true,&o)==-EALREADY);
 CHECK(r->io_count==0 && r->events==0 && r->clocks==0 && r->delays==0); free(r);
 r=new_rig("missing callback consumes ON admission");
 r->ops.write_vote=NULL;
 CHECK(transition(r,true,&o)==-EINVAL);
 r->ops.write_vote=write_vote;
 CHECK(transition(r,true,&o)==-EALREADY);
 CHECK(transition(r,false,&o)==-EPERM);
 CHECK(r->io_count==0 && r->events==0 && r->clocks==0 && r->delays==0); free(r);
}
static void callback_errors(void)
{
 char name[128];
 for (unsigned int direction=0;direction<2;++direction)
  for (unsigned int fail=1;fail<=20;++fail)
   for (unsigned int positive=0;positive<2;++positive) {
    snprintf(name,sizeof(name),"%s callback error at IO%u (%s)",direction?"OFF":"ON",fail,positive?"positive":"negative");
    struct rig *r=new_rig(name); struct gfx_coord_observation o;
    if (direction) prime_off(r);
    r->fail_at=fail; r->fail_result=positive?7:-EREMOTEIO;
    CHECK(transition(r,!direction,&o)==(positive?-EIO:-EREMOTEIO));
    CHECK(r->io_count==fail); /* No retry or compensating callback follows. */
    CHECK(o.request_attempted==(fail>=8));
    CHECK(!o.request_acked || fail>=11);
    CHECK(direction?!r->session.off_complete:!r->session.on_complete);
    unsigned int calls=r->io_count+r->events+r->clocks+r->delays;
    CHECK(transition(r,!direction,&o)==-EALREADY);
    if (!direction) CHECK(transition(r,false,&o)==-EPERM);
    CHECK(calls==r->io_count+r->events+r->clocks+r->delays); free(r);
   }
 for (unsigned int direction=0;direction<2;++direction)
  for (unsigned int n=0;n<4;++n) {
   unsigned int writes[]={8,13,16,19};
   snprintf(name,sizeof(name),"%s potentially delivered write error IO%u",direction?"OFF":"ON",writes[n]);
   struct rig *r=new_rig(name); struct gfx_coord_observation o;
   if (direction) prime_off(r);
   u64 before=r->request; u32 vote_before[3]; memcpy(vote_before,r->votes,sizeof(vote_before));
   r->fail_at=writes[n]; r->delivered_error=true;
   CHECK(transition(r,!direction,&o)==-EIO);
   CHECK(r->io_count==writes[n]); CHECK(r->request_writes==1);
   CHECK(r->request==(!direction?before|GFX_COORD_REQUEST_BIT:before&~GFX_COORD_REQUEST_BIT));
   if (n) CHECK(r->votes[n-1]==(!direction?vote_before[n-1]|4U:vote_before[n-1]&~4U));
   CHECK(r->vote_writes==n); free(r);
  }
}
static void guards_and_timeouts(void)
{
 char name[128]; struct gfx_coord_observation o;
 for (unsigned int direction=0;direction<2;++direction) {
  for (unsigned int after=0;after<2;++after) {
   snprintf(name,sizeof(name),"%s STATUS0 strict refusal %swrite",direction?"OFF":"ON",after?"after ":"before ");
   struct rig *r=new_rig(name); if (direction) prime_off(r);
   r->status_zero_before=!after; r->status_zero_wait=after;
   CHECK(transition(r,!direction,&o)==-ENODATA);
   CHECK(r->request_writes==after && r->vote_writes==0);
   CHECK(!o.request_acked); free(r);
  }
  for (unsigned int mode=INVALID;mode<=DECODED_BIT54;++mode)
   for (unsigned int samples=0;samples<2;++samples) {
    snprintf(name,sizeof(name),"%s ACK mode%u %s timeout",direction?"OFF":"ON",mode,samples?"sample":"time");
    struct rig *r=new_rig(name); if (direction) prime_off(r);
    r->ack_mode=(enum ack_mode)mode; r->delay_ns=samples?0:1000000000ULL;
    CHECK(transition(r,!direction,&o)==-ETIMEDOUT);
    CHECK(o.ack_samples==(samples?GFX_COORD_MAX_ACK_SAMPLES:15U));
    CHECK(!o.request_acked && r->vote_writes==0 && r->request_writes==1);
    CHECK(r->delays==o.ack_samples-(samples?1U:0U)); free(r);
   }
  for (unsigned int late=0;late<3;++late) {
   snprintf(name,sizeof(name),"%s valid ACK at deadline boundary%u",direction?"OFF":"ON",late);
   struct rig *r=new_rig(name); if (direction) prime_off(r);
   r->ack_latency_ns=GFX_COORD_TIMEOUT_NS+(u64)late-1ULL;
   CHECK(transition(r,!direction,&o)==(late?-ETIMEDOUT:0));
   CHECK(o.request_acked==!late);
   CHECK(r->vote_writes==(late?0U:3U)); free(r);
  }
  struct rig *r=new_rig(direction?"OFF deadline before first sample":"ON deadline before first sample");
  if (direction) prime_off(r); r->clock_jump_at=2;
  CHECK(transition(r,!direction,&o)==-ETIMEDOUT);
  CHECK(o.ack_samples==0 && r->io_count==8 && r->vote_writes==0); free(r);
  for (unsigned int at=1;at<=20;++at) {
   if (at==8 || at==13 || at==16 || at==19) continue;
   for (unsigned int status=0;status<2;++status) {
    if (status && (at==4 || at==5 || at==6 || at==12 || at==14 || at==15 || at==17 || at==18 || at==20)) continue;
    snprintf(name,sizeof(name),"%s all-ones %s IO%u",direction?"OFF":"ON",status?"PTD status":"payload/vote",at);
    r=new_rig(name); if (direction) prime_off(r);
    r->all_ones_at=at; r->ones_status=status;
    CHECK(transition(r,!direction,&o)==-EIO);
    CHECK(r->io_count==at); free(r);
   }
  }
 }
}
static void changing_reads(void)
{
 struct gfx_coord_observation o; char name[128];
 for (unsigned int direction=0;direction<2;++direction) {
  struct rig *r=new_rig(direction?"OFF changed request after ACK":"ON changed request after ACK");
  if (direction) prime_off(r); r->changed_request=true;
  CHECK(transition(r,!direction,&o)==-EAGAIN);
  CHECK(o.request_acked && r->vote_writes==0 && r->io_count==11); free(r);
  for (int rail=0;rail<3;++rail) {
   snprintf(name,sizeof(name),"%s changed vote readback rail%d",direction?"OFF":"ON",rail);
   r=new_rig(name); if (direction) prime_off(r); r->bad_vote_rail=rail;
   CHECK(transition(r,!direction,&o)==-EAGAIN);
   CHECK(o.votes_verified==(unsigned int)rail && o.votes_attempted==(unsigned int)rail+1);
   CHECK(r->vote_writes==(unsigned int)rail+1 && r->io_count==14U+(unsigned int)rail*3U); free(r);
   snprintf(name,sizeof(name),"%s preserve latest vote unrelated bit rail%d",direction?"OFF":"ON",rail);
   r=new_rig(name); if (direction) prime_off(r); r->current_vote_rail=rail;
   CHECK(transition(r,!direction,&o)==0);
   CHECK(r->votes[rail]&(1U<<30)); free(r);
  }
 }
 struct rig *r=new_rig("refresh preserves concurrent preflight request update");
 r->mutate_snapshot=true;
 CHECK(transition(r,true,&o)==0);
 CHECK(r->snapshot_mutated);
 CHECK(r->request&(1ULL<<39)); free(r);
 r=new_rig("document external request change at write snapshot limitation");
 r->mutate_at_write=true;
 CHECK(transition(r,true,&o)==0);
 CHECK(r->snapshot_mutated);
 /* The whole-word native-style RMW cannot preserve an external update
  * after its final snapshot. This is an ownership bound, not a safety claim. */
 CHECK(!(r->request&(1ULL<<39))); free(r);
}
int main(void)
{
 paired(); admission(); callback_errors(); guards_and_timeouts(); changing_reads();
 printf("{\"cases\":%u,\"assertions\":%u,\"io_callbacks\":%llu,"
        "\"hardware_access\":false,\"concurrent_snapshot_atomicity_proved\":false}\n",
        cases,assertions,total_io);
 return 0;
}
