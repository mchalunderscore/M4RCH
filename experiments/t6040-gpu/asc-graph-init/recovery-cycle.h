/* SPDX-License-Identifier: GPL-2.0-only */
/* Bounded, idle-only application recovery. Never retire or free GPU backing.
 * Generated offsets bind the native shared pointers to this owned fixture.
 * The common snapshot/operation mutex protects host writes from invalidation.
 */
#include "recovery-contract.h"
static bool resident_session,recovery_resident,recovery_work_submitted;
module_param(resident_session,bool,0400);
static void *recovery_ptr(unsigned int offset)
{
 return (u8 *)page_address(owned[2+offset/PAGE_SIZE])+offset%PAGE_SIZE;
}
static void recovery_invalidate(void *ptr,size_t bytes)
{
 unsigned long p=(unsigned long)ptr,end=p+bytes;
 for(;p<end;p+=16) asm volatile("dc ivac, %0" :: "r"(p) : "memory");
 asm volatile("dsb sy" ::: "memory");
}
static u32 recovery_read32(unsigned int offset)
{
 u32 *p=recovery_ptr(offset);recovery_invalidate(p,sizeof(*p));return READ_ONCE(*p);
}
static u64 recovery_read64(unsigned int offset)
{
 u64 *p=recovery_ptr(offset);recovery_invalidate(p,sizeof(*p));return READ_ONCE(*p);
}
static void recovery_write32(unsigned int offset,u32 value)
{
 u32 *p=recovery_ptr(offset);
 /* Firmware is waiting, or the control queue is empty, at each write site. */
 recovery_invalidate(p,sizeof(*p));WRITE_ONCE(*p,value);
 asm volatile("dmb ish\n\tdc cvac, %0\n\tdsb sy" :: "r"(p) : "memory");
}
#include "receive-service.h"
static bool recovery_messages(void)
{
 unsigned int n=0;
 if(!receive_drain()) return false;
 while(!(readl(mbox+0x114)&EMPTY)) {
  u64 msg=readq(mbox+0x830),meta=readq(mbox+0x838);
  if(!receive_mailbox(msg,meta)) return false;
  /* A bounded batch is not a crash. The next wait/worker poll continues it. */
  if(++n>=64) break;
 }
 return true;
}
static bool recovery_send(u64 packet)
{
 if(readl(mbox+0x110)&BIT(16)) return false;
 wmb();writeq(packet,mbox+0x800);writeq(33,mbox+0x808);
 pr_info("m4rch recovery-send: endpoint=33 packet=%#llx\n",packet);return true;
}
static void recovery_power_sample(const char *phase)
{
 u32 state=recovery_read32(RECOVERY_STATUS+0x4900);
 u32 pstate=recovery_read32(RECOVERY_POWER+0x38);
 void __iomem *primary,*prc,*engines;
 pr_info("m4rch recovery-power: phase=%s recovery_phase=%u pstate=%u power78=%u down_active=%u up_count=%u\n",
  phase,state,pstate,recovery_read32(RECOVERY_POWER+0x78),
  recovery_read32(RECOVERY_POWER+0x63c8),recovery_read32(RECOVERY_POWER+0x652c));
 /* Exact firmware poll operands while application recovery holds ASC/GFX.
  * Firmware clears power+38 at2c02c before its second5960 and PRC polls;
  * a zero software pstate must not suppress those diagnostics. power+78
  * remains old until cdb0, not the requested down target (w19=0).
  * Also diagnose initial GPC startup when no control record was consumed.
  * No selector writes. 2becc/2c0c4:5960; 2bfec:5978; 2c11c:d4c004;
  * 322ec/2a1b4:5970; 2a21c:d4c000; 2bf44:d44070. */
 if(state!=2 && !(state==0 && recovery_read32(RECOVERY_CONTROL)==0)) return;
 primary=ioremap(0x288004000ULL,PAGE_SIZE);
 prc=ioremap(0x288d4c000ULL,PAGE_SIZE);
 if(primary) {
  pr_info("m4rch recovery-poll: phase=%s raw5960=%#llx raw5978=%#llx\n",phase,readq(primary+0x1960),readq(primary+0x1978));
  pr_info("m4rch recovery-aux-poll: phase=%s raw5970=%#llx\n",phase,readq(primary+0x1970));
  iounmap(primary);
 }
 if(prc) {
  pr_info("m4rch recovery-prc: phase=%s rawd4c004=%#x\n",phase,readl(prc+4));
  pr_info("m4rch recovery-aux-prc: phase=%s rawd4c000=%#x\n",phase,readl(prc));
  iounmap(prc);
 }
 engines=ioremap(0x288d44000ULL,PAGE_SIZE);
 if(engines) {
  pr_info("m4rch recovery-engine-poll: phase=%s rawd44070=%#x\n",phase,readl(engines+0x70));
  iounmap(engines);
 }
}
static bool recovery_idle(void)
{
 unsigned int i,active=0;
 for(i=0;i<ARRAY_SIZE(recovery_work_cursors);i++) {
  unsigned int o=recovery_work_cursors[i];
  if(recovery_read32(o) || recovery_read32(o+8) || recovery_read32(o+16)) return false;
 }
 for(i=0;i<256;i++) active+=(recovery_read32(RECOVERY_STATUS+0x40b8+i*8)&9)==9;
 pr_info("m4rch recovery-idle: active_ta_records=%u\n",active);
 return !active;
}
static void recovery_sample(unsigned int cycle,const char *phase)
{
 pr_info("m4rch recovery-state: cycle=%u phase=%s counter=%llu state=%u host_stop=%u request_state=%u request_flag=%u control=%u/%u/%u\n",
  cycle,phase,recovery_read64(RECOVERY_STATUS+0x48f0),recovery_read32(RECOVERY_STATUS+0x4900),
  recovery_read32(RECOVERY_STATUS+0x4910),recovery_read32(RECOVERY_REQUEST),recovery_read32(RECOVERY_REQUEST+4),
  recovery_read32(RECOVERY_CONTROL),recovery_read32(RECOVERY_CONTROL+8),recovery_read32(RECOVERY_CONTROL+16));
}
static bool recovery_wait(unsigned int state,u64 counter)
{
 unsigned long until=jiffies+msecs_to_jiffies(5000);
 unsigned long next_sample=jiffies+msecs_to_jiffies(100);
 do {
  if(!recovery_messages()) return false;
  if(recovery_read32(RECOVERY_STATUS+0x4900)==state &&
     recovery_read64(RECOVERY_STATUS+0x48f0)==counter &&
     recovery_read32(RECOVERY_STATUS+0x4910)==1) return true;
  if(state==3 && time_after_eq(jiffies,next_sample)) {
   recovery_power_sample("waiting-post");next_sample=jiffies+msecs_to_jiffies(1000);
  }
  usleep_range(1000,2000);
 } while(time_before(jiffies,until));
 return false;
}
static bool recovery_control(unsigned int count,bool publish)
{
 unsigned long until=jiffies+msecs_to_jiffies(5000);
 if(publish) {
  /* Every record was staged before root publication; expose one fresh record.
   * No cursor wrap, firmware-owned read/prefetch reset, or ring overwrite. */
  if(count>RECOVERY_CONTROL_LAST || recovery_read32(RECOVERY_CONTROL)!=count-1 ||
     recovery_read32(RECOVERY_CONTROL+8)!=count-1 ||
     recovery_read32(RECOVERY_CONTROL+16)!=count-1) return false;
  recovery_write32(RECOVERY_CONTROL+16,count);
  if(!recovery_send(0x0084000000000000ULL)) return false;
 }
 do {
  if(!recovery_messages()) return false;
  if(recovery_read32(RECOVERY_CONTROL)==count && recovery_read32(RECOVERY_CONTROL+8)==count &&
     recovery_read32(RECOVERY_CONTROL+16)==count) return true;
  usleep_range(1000,2000);
 } while(time_before(jiffies,until));
 return false;
}
static bool recovery_cycles(void)
{
 unsigned int cycle=0,completed=0,initial=recovery_read32(RECOVERY_CONTROL+16);u64 token;
 recovery_sample(0,"baseline");
 if(recovery_work_submitted || initial<RECOVERY_CONTROL_INITIAL || initial>RECOVERY_CONTROL_LAST-2 ||
    !recovery_idle() || !recovery_control(initial,false) ||
    recovery_read32(RECOVERY_STATUS+0x4900) || recovery_read32(RECOVERY_REQUEST) ||
    recovery_read32(RECOVERY_REQUEST+4)) goto done;
 token=recovery_read64(RECOVERY_STATUS+0x48f0);
 for(cycle=1;cycle<=2;cycle++) {
  if(token>=GENMASK_ULL(43,0) || !recovery_idle() ||
     !recovery_send(0x0086000000000000ULL|token)) goto done;
  if(!recovery_wait(1,token+1)) goto done;
  recovery_sample(cycle,"pre");
  recovery_power_sample("before-pre-ack");
  if(!recovery_idle()) goto done;
  recovery_write32(RECOVERY_STATUS+0x4900,2);
  if(!recovery_wait(3,token+1)) goto done;
  recovery_sample(cycle,"post");
  if(!recovery_idle()) goto done;
  recovery_write32(RECOVERY_STATUS+0x4900,0);
  if(!recovery_control(initial+cycle,true)) goto done;
  if(recovery_read32(RECOVERY_STATUS+0x4900) ||
     recovery_read64(RECOVERY_STATUS+0x48f0)!=token+1 || recovery_read32(RECOVERY_REQUEST) ||
     recovery_read32(RECOVERY_REQUEST+4) || !recovery_idle()) goto done;
  token++;completed++;recovery_sample(cycle,"fresh-control-consumed");
 }
done:
 recovery_sample(cycle,"final");
 recovery_power_sample("recovery-return");
 pr_info("m4rch recovery-result: completed=%u requested=2 allocations_retained=1 work_submitted=0\n",completed);
 return completed==2;
}

/* Typed resident operations share the snapshot lock. No arbitrary memory/MMIO
 * commands and no reusing or freeing a submitted job. A failed operation seals
 * the session; stop-and-pin remains available. Sysfs calls are bounded. */
static bool recovery_session_failed;
static unsigned int recovery_operation;
static void recovery_receive_worker(struct work_struct *work);
static DECLARE_DELAYED_WORK(recovery_receive_work,recovery_receive_worker);
static void recovery_receive_worker(struct work_struct *work)
{
 mutex_lock(&graph_io_lock);
 if(recovery_resident && !recovery_session_failed) {
  if(!recovery_messages()) recovery_session_failed=true;
  if(!recovery_session_failed) schedule_delayed_work(&recovery_receive_work,msecs_to_jiffies(10));
 }
 mutex_unlock(&graph_io_lock);
}
static ssize_t recovery_command_store(struct kobject *kobj,struct kobj_attribute *attr,
 const char *buf,size_t count)
{
 int ret=0;unsigned int i;bool ok=true;
 mutex_lock(&graph_io_lock);
 if(!recovery_resident) {ret=-ENODEV;goto out;}
 if(sysfs_streq(buf,"stop")) {
  bool ap=power_ack(0xb,0xb,0x10),sleep=false;
  if(ap) sleep=power_ack(6,7,1);
  writel(readl(asc+0x44)&~START,asc+0x44);readl(asc+0x44);
  recovery_resident=false;
  cancel_delayed_work(&recovery_receive_work);
  pr_info("m4rch recovery-session: stop_requested_and_pinned=1 ap_ack=%d sleep_ack=%d control=%#x status=%#x\n",ap,sleep,readl(asc+0x44),readl(asc+0x48));
 } else if(sysfs_streq(buf,"sample")) {
  if(!recovery_session_failed && !recovery_messages()) {recovery_session_failed=true;ret=-EIO;}
  recovery_sample(0,"resident");recovery_power_sample("resident");
  if(!recovery_session_failed) {ksm_status_sample("resident");joined_output_sample("resident");}
 } else if(recovery_session_failed) {ret=-EIO;goto out;}
 else if(sysfs_streq(buf,"control")) {
  if(recovery_work_submitted) {ret=-EBUSY;goto out;}
  ok=recovery_control(recovery_read32(RECOVERY_CONTROL+16)+1,true);
 } else if(sysfs_streq(buf,"recover")) {
  if(recovery_work_submitted) {ret=-EBUSY;goto out;}
  ok=recovery_cycles();
 } else if(sysfs_streq(buf,"submit")) {
  if(recovery_work_submitted) {ret=-EALREADY;goto out;}
  if(!recovery_idle() || recovery_read32(RECOVERY_STATUS+0x4900) ||
     recovery_read32(RECOVERY_REQUEST) || recovery_read32(RECOVERY_REQUEST+4)) {ret=-EBUSY;goto out;}
  if(!recovery_control(recovery_read32(RECOVERY_CONTROL+16),false)) {ok=false;goto failed;}
  /* Quarantine this immutable batch even if a later publication step fails. */
  recovery_work_submitted=true;
  for(i=0;i<2;i++) {
   u8 *p=recovery_ptr(recovery_work_rings[i]);
   recovery_invalidate(p,24);memcpy(p,recovery_work_records[i],24);
   asm volatile("dc cvac, %0\n\tdc cvac, %1\n\tdsb sy" :: "r"(p),"r"(p+16) : "memory");
   recovery_write32(recovery_work_cursors[i]+16,1);
  }
  ok=recovery_send(0x0083000000000000ULL);
  pr_info("m4rch recovery-session: prepared_triangle_published=1 notification_sent=%d reuse_allowed=0\n",ok);
 } else {ret=-EINVAL;goto out;}
failed:
 recovery_operation++;
 if(!ok) {recovery_session_failed=true;ret=-EIO;}
 pr_info("m4rch recovery-operation: id=%u result=%d resident=%d sealed=%d work_submitted=%d allocations_retained=1\n",recovery_operation,ret,recovery_resident,recovery_session_failed,recovery_work_submitted);
 pr_info("m4rch receive-status: records=%u status=%#x doorbells=%u\n",receive_journal.used,receive_journal.status,receive_journal.doorbells);
out:
 mutex_unlock(&graph_io_lock);return ret?ret:count;
}
static struct kobj_attribute recovery_command=__ATTR(command,0200,NULL,recovery_command_store);
