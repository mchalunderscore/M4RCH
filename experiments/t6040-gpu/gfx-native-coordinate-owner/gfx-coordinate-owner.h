/* SPDX-License-Identifier: GPL-2.0-only */
/* Separate retained owner adapter for the qualified paired PMP/PMC protocol.
 * This is included only in a distinct future owner, never the attempted owner.
 */
#if !defined(GFX_NATIVE_COORDINATED_SCOPE_TRIAL) || \
    !defined(GFX_POWER_OFF_SCOPE_TRIAL) || !defined(GFX_RESET_SCOPE_TRIAL)
#error Paired coordination requires the separate retained no-work owner profile
#endif
#ifdef GFX_RESET_NATIVE_SEQUENCE_TRIAL
#error Paired coordination cannot include the native reset command profile
#endif

#include <linux/of_address.h>
#include <linux/timekeeping.h>
#include "gfx-coordinate-core.h"

#define GFX_COORD_OWNER_PMP_BASE 0x5003c0000ULL
#define GFX_COORD_OWNER_PMP_SIZE 0x30000ULL
#define GFX_COORD_OWNER_PMC_BASE 0x504000000ULL
#define GFX_COORD_OWNER_PMC_SIZE 0x1000000ULL
#define GFX_COORD_OWNER_VOTE_BASE 0x8ac000U

static bool gfx_coord_owner_module_pinned, gfx_coord_owner_startup_retained;
static bool gfx_coord_owner_pmp_region, gfx_coord_owner_pmc_region;
static void __iomem *gfx_coord_owner_pmp, *gfx_coord_owner_pmc;
static struct gfx_coord_session gfx_coord_owner_session;
static struct gfx_coord_observation gfx_coord_owner_on, gfx_coord_owner_off;
static unsigned int gfx_coord_owner_status_wait_events, gfx_coord_owner_ack_wait_events;

static void gfx_coord_owner_pin(void)
{
 if (!gfx_coord_owner_module_pinned) {
  __module_get(THIS_MODULE);
  gfx_coord_owner_module_pinned=true;
 }
}

static bool gfx_coord_owner_retained(void)
{
 return gfx_coord_owner_startup_retained;
}

/* of_iomap/syscon mappings need not have a busy resource reservation. Reject
 * every available OF MMIO alias as well as request_mem_region conflicts.
 * The experiment does not permit dynamic DT or competing raw MMIO helpers.
 */
static int gfx_coord_owner_alias_check(void)
{
 struct device_node *node;
 struct resource resource;
 unsigned int index;
 /* The exported iterator gets the next node and puts its predecessor.
  * An early return must put the current referenced node explicitly.
  */
 for (node=of_find_all_nodes(NULL); node; node=of_find_all_nodes(node)) {
  if (!of_device_is_available(node)) continue;
  for (index=0; !of_address_to_resource(node,index,&resource); index++) {
   if (!(resource.flags&IORESOURCE_MEM)) continue;
   if ((resource.start<GFX_COORD_OWNER_PMP_BASE+GFX_COORD_OWNER_PMP_SIZE &&
        resource.end>=GFX_COORD_OWNER_PMP_BASE) ||
       (resource.start<GFX_COORD_OWNER_PMC_BASE+GFX_COORD_OWNER_PMC_SIZE &&
        resource.end>=GFX_COORD_OWNER_PMC_BASE)) {
    pr_err("m4rch gfx-coordinate-resource: alias=%pOF resource=%u start=%#llx end=%#llx result=%d\n",
     node,index,(unsigned long long)resource.start,
     (unsigned long long)resource.end,-EBUSY);
    of_node_put(node);
    return -EBUSY;
   }
  }
 }
 return 0;
}

static int gfx_coord_owner_prepare(void)
{
 int ret;
 if (!of_machine_is_compatible("apple,j614s") ||
     !of_machine_is_compatible("apple,t6040")) return -ENODEV;
 ret=gfx_coord_owner_alias_check();
 if (ret) return ret;
 if (!request_mem_region(GFX_COORD_OWNER_PMP_BASE,GFX_COORD_OWNER_PMP_SIZE,
                         "m4rch-gfx-coordinate-pmp")) return -EBUSY;
 gfx_coord_owner_pmp_region=true;
 if (!request_mem_region(GFX_COORD_OWNER_PMC_BASE,GFX_COORD_OWNER_PMC_SIZE,
                         "m4rch-gfx-coordinate-pmc")) return -EBUSY;
 gfx_coord_owner_pmc_region=true;
 gfx_coord_owner_pmp=ioremap(GFX_COORD_OWNER_PMP_BASE,GFX_COORD_OWNER_PMP_SIZE);
 if (!gfx_coord_owner_pmp) return -ENOMEM;
 gfx_coord_owner_pmc=ioremap(GFX_COORD_OWNER_PMC_BASE,GFX_COORD_OWNER_PMC_SIZE);
 if (!gfx_coord_owner_pmc) return -ENOMEM;
 pr_info("m4rch gfx-coordinate-resource: pmp=%#llx pmp_size=%#llx pmc=%#llx pmc_size=%#llx exclusive=1 retained=1 runtime_mode_register_qualified=0\n",
  GFX_COORD_OWNER_PMP_BASE,GFX_COORD_OWNER_PMP_SIZE,
  GFX_COORD_OWNER_PMC_BASE,GFX_COORD_OWNER_PMC_SIZE);
 return 0;
}

static int gfx_coord_owner_read_ptd(void *context,unsigned int entry,
                                  u64 *payload,u64 *raw_status)
{
 unsigned int offset;
 (void)context;
 if (!gfx_coord_owner_pmp || !gfx_coord_owner_pmp_region) return -ENODEV;
 if (entry!=1 && entry!=0x1e0 && entry!=0x1e8) return -EINVAL;
 offset=entry*16;
 /* Separate reads preserve both words; this is not an atomic LDP snapshot. */
 *payload=readq(gfx_coord_owner_pmp+offset);
 *raw_status=readq(gfx_coord_owner_pmp+offset+8);
 return 0;
}

static int gfx_coord_owner_write_ptd(void *context,unsigned int entry,u64 payload)
{
 (void)context;
 if (!gfx_coord_owner_pmp || !gfx_coord_owner_pmp_region) return -ENODEV;
 if (entry!=0x1e0) return -EINVAL;
 writeq(payload,gfx_coord_owner_pmp+0x10000+entry*8);
 return 0;
}

static int gfx_coord_owner_read_vote(void *context,unsigned int rail,u32 *value)
{
 (void)context;
 if (!gfx_coord_owner_pmc || !gfx_coord_owner_pmc_region) return -ENODEV;
 if (rail>=3) return -EINVAL;
 *value=readl(gfx_coord_owner_pmc+GFX_COORD_OWNER_VOTE_BASE+rail*4);
 return 0;
}

static int gfx_coord_owner_write_vote(void *context,unsigned int rail,u32 value)
{
 (void)context;
 if (!gfx_coord_owner_pmc || !gfx_coord_owner_pmc_region) return -ENODEV;
 if (rail>=3) return -EINVAL;
 writel(value,gfx_coord_owner_pmc+GFX_COORD_OWNER_VOTE_BASE+rail*4);
 return 0;
}

static u64 gfx_coord_owner_now_ns(void *context)
{
 (void)context;
 return ktime_get_ns();
}

static void gfx_coord_owner_delay(void *context)
{
 (void)context;
 usleep_range(1000,1100);
}

static void gfx_coord_owner_event(void *context,const char *phase,
                                 unsigned int index,u64 value,u64 status,int result)
{
 unsigned int count=0;
 (void)context;
 if (!strcmp(phase,"status-wait")) count=++gfx_coord_owner_status_wait_events;
 else if (!strcmp(phase,"ack-wait")) count=++gfx_coord_owner_ack_wait_events;
 if (count>4 && count%128 && !result) return;
 pr_info("m4rch gfx-coordinate-event: phase=%s index=%u value=%#llx status=%#llx result=%d\n",
  phase,index,(unsigned long long)value,(unsigned long long)status,result);
}

static const struct gfx_coord_ops gfx_coord_owner_ops={
 .context=NULL,
 .read_ptd=gfx_coord_owner_read_ptd,.write_ptd=gfx_coord_owner_write_ptd,
 .read_vote=gfx_coord_owner_read_vote,.write_vote=gfx_coord_owner_write_vote,
 .now_ns=gfx_coord_owner_now_ns,.delay=gfx_coord_owner_delay,
 .event=gfx_coord_owner_event,
};

static int gfx_coord_owner_transition(bool enabled)
{
 struct gfx_coord_observation *observation=enabled?&gfx_coord_owner_on:&gfx_coord_owner_off;
 int ret;
 gfx_coord_owner_status_wait_events=0;
 gfx_coord_owner_ack_wait_events=0;
 ret=gfx_coord_transition(&gfx_coord_owner_session,&gfx_coord_owner_ops,enabled,observation);
 pr_info("m4rch gfx-coordinate-observation: enabled=%u result=%d request_attempted=%u request_acked=%u ack_samples=%u votes_attempted=%u votes_verified=%u request_before=%#llx request_written=%#llx ack_payload=%#llx ack_status=%#llx status_wait_events=%u ack_wait_events=%u\n",
  observation->enabled,observation->result,observation->request_attempted,
  observation->request_acked,observation->ack_samples,
  observation->votes_attempted,observation->votes_verified,
  (unsigned long long)observation->request_before,
  (unsigned long long)observation->request_written,
  (unsigned long long)observation->ack_payload,
  (unsigned long long)observation->ack_status,
  gfx_coord_owner_status_wait_events,gfx_coord_owner_ack_wait_events);
 return ret;
}

static void gfx_coord_owner_log(const char *phase,int result)
{
 pr_info("m4rch gfx-coordinate-owner: phase=%s result=%d startup_retained=%u module_pinned=%u pmp_region=%u pmc_region=%u pmp_mapped=%u pmc_mapped=%u on_attempted=%u on_complete=%u off_attempted=%u off_complete=%u held=%u started=%u retirement_verified=0\n",
  phase,result,gfx_coord_owner_startup_retained,gfx_coord_owner_module_pinned,
  gfx_coord_owner_pmp_region,gfx_coord_owner_pmc_region,
  !!gfx_coord_owner_pmp,!!gfx_coord_owner_pmc,
  gfx_coord_owner_session.on_attempted,gfx_coord_owner_session.on_complete,
  gfx_coord_owner_session.off_attempted,gfx_coord_owner_session.off_complete,
  held,started);
}

/* Called only after the physical PM get and the old cold ASC/FIFO checks,
 * before START and before any joined graph allocation or publication.
 * Even an eligibility refusal pins the consumer/PM and acquired resources.
 */
static int gfx_coord_owner_begin_on(void)
{
 struct apple_pmgr_gfx_reset_observation observation;
 int ret;
 gfx_coord_owner_startup_retained=true;
 gfx_coord_owner_pin();
 mutex_lock(&graph_io_lock);
 if (!consumer || !held || started ||
     atomic_read(&consumer->dev.power.usage_count)!=1 ||
     READ_ONCE(consumer->dev.power.runtime_error) ||
     !pm_runtime_enabled(&consumer->dev) || !pm_runtime_active(&consumer->dev)) {
  ret=-EBUSY;
  goto out;
 }
 /* Reuse the exact retained owner's zeroing/error/validity normalization. */
 ret=gfx_poweroff_snapshot("coordinate-before-on",0,&observation);
 if (ret) goto out;
 if (!(observation.valid&APPLE_PMGR_GFX_VALID_BEFORE) ||
     !observation.domain_on || (observation.before&0x80001cffU)!=0xffU) {
  ret=-EBUSY;
  goto out;
 }
 ret=gfx_coord_owner_prepare();
 if (!ret) ret=gfx_coord_owner_transition(true);
out:
 gfx_coord_owner_log("post-active-on",ret);
 mutex_unlock(&graph_io_lock);
 return ret;
}

/* This is called with the existing OFF terminal gate already consumed and
 * its retained/no-work/STOP/ACTIVE checks passed, before held=false/PM put.
 */
static int gfx_coord_owner_before_off(void)
{
 int ret;
 lockdep_assert_held(&graph_io_lock);
 if (!gfx_coord_owner_retained() || !gfx_coord_owner_module_pinned ||
     !gfx_coord_owner_session.on_complete || !gfx_coord_owner_pmp ||
     !gfx_coord_owner_pmc || !gfx_coord_owner_pmp_region ||
     !gfx_coord_owner_pmc_region) ret=-EBUSY;
 else {
  ret=gfx_coord_owner_alias_check();
  if (!ret) ret=gfx_coord_owner_transition(false);
 }
 gfx_coord_owner_log("before-target-zero-off",ret);
 return ret;
}
