/* SPDX-License-Identifier: GPL-2.0-only */
/* Cache/RX primitives only. No class86 recovery, phase writes or work command. */
#ifndef GFX_COLD_RENDER_TRIAL
#error Distinct cold-render feature profile required
#endif
#include "recovery-contract.h"
#include "gfx-cold-runtime.h"
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
static void recovery_clean(void *ptr,size_t bytes)
{
 unsigned long p=(unsigned long)ptr,end=p+bytes;
 asm volatile("dmb ish" ::: "memory");
 for(;p<end;p+=16) asm volatile("dc cvac, %0" :: "r"(p) : "memory");
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
 u32 *p=recovery_ptr(offset);recovery_invalidate(p,sizeof(*p));WRITE_ONCE(*p,value);
 recovery_clean(p,sizeof(*p));
}
#include "receive-service.h"
static bool recovery_messages(void)
{
 unsigned int n=0;
 if(!receive_drain()) return false;
 while(!(readl(mbox+0x114)&EMPTY)) {
  u64 msg=readq(mbox+0x830),meta=readq(mbox+0x838);
  if(!receive_mailbox(msg,meta)) return false;
  if(++n>=64) break;
 }
 return true;
}
static bool recovery_idle(void)
{
 unsigned int i;
 for(i=0;i<ARRAY_SIZE(recovery_work_cursors);i++) {
  unsigned int o=recovery_work_cursors[i];
  if(recovery_read32(o) || recovery_read32(o+8) || recovery_read32(o+16)) return false;
 }
 for(i=0;i<256;i++)
  if((recovery_read32(RECOVERY_STATUS+0x40b8+i*8)&9)==9) return false;
 return true;
}
static int gfx_cold_diagnostic(const char *command);
static ssize_t recovery_command_store(struct kobject *kobj,struct kobj_attribute *attr,
 const char *buf,size_t count)
{
 int ret;
 mutex_lock(&graph_io_lock);ret=gfx_cold_diagnostic(buf);mutex_unlock(&graph_io_lock);
 return ret?ret:count;
}
static struct kobj_attribute recovery_command=__ATTR(command,0200,NULL,recovery_command_store);
