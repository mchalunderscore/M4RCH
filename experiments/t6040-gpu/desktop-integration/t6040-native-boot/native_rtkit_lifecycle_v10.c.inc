/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
/* Native G16 only: preserves stock RTKit behavior until explicitly selected.
 * Caller owns runtime PM and ASC mapping, excludes submissions, and retains
 * every old application/DMA allocation. No successful return grants release.
 */
struct apple_rtkit_g16_retained {
 struct apple_rtkit_g16_retained *next;
 struct apple_rtkit_shmem buffers[5];
 char *syslog_msg_buffer;
 void *cookie;
};

int apple_rtkit_g16_own_retained(struct apple_rtkit *rtk)
{
 mutex_lock(&rtk->g16_lock);
 rtk->g16_owner=true;
 mutex_unlock(&rtk->g16_lock);
 return 0;
}
EXPORT_SYMBOL_GPL(apple_rtkit_g16_own_retained);

int apple_rtkit_g16_powergate(struct apple_rtkit *rtk, void __iomem *asc,
                             size_t asc_bytes)
{
 unsigned long until;
 u32 control, status, rx;
 int ret;
 if (!asc || asc_bytes < 0x1018 || !rtk->early_crashlog)
  return -EINVAL;
 mutex_lock(&rtk->g16_lock);
 if (!rtk->g16_owner || rtk->g16_intent || !apple_rtkit_is_running(rtk)) { ret=-EBUSY; goto out; }
 /* Intent precedes sends. An errored send may already have reached hardware. */
 rtk->g16_intent=true;
 flush_workqueue(rtk->wq);
 if (rtk->crashed) {ret=-EIO;goto out;}
 reinit_completion(&rtk->g16_ack_completion);
 WRITE_ONCE(rtk->g16_waiting,true);
 ret=apple_rtkit_management_send(rtk,APPLE_RTKIT_MGMT_SET_IOP_PWR_STATE,0x202);
 if (ret) {WRITE_ONCE(rtk->g16_waiting,false);goto out;}
 ret=wait_for_completion_interruptible_timeout(&rtk->g16_ack_completion,
                                              msecs_to_jiffies(2000));
 WRITE_ONCE(rtk->g16_waiting,false);
 if (ret<0) goto out;
 if (READ_ONCE(rtk->g16_rx_error)) {ret=READ_ONCE(rtk->g16_rx_error);goto out;}
 if (!ret) {
  if (rtk->crashed) {ret=-EIO;goto out;}
  rtk->g16_nmi_attempted=true;
  ret=apple_rtkit_management_send(rtk,0xf,0);
  if (ret) goto out;
  writel(0x10,asc+0x1004);
  writel(1,asc+0x1014);
 }
 until=jiffies+msecs_to_jiffies(250);
 for (;;) {
  apple_mbox_poll(rtk->mbox);
  status=readl(asc+0x48);
  rx=readl(rtk->mbox->regs+0x114);
  if (status==U32_MAX || rx==U32_MAX) {ret=-EIO;goto out;}
  if ((status&3) && (rx&BIT(17))) break;
  if (time_after_eq(jiffies,until)) {ret=-ETIMEDOUT;goto out;}
  usleep_range(1000,1100);
 }
 flush_workqueue(rtk->wq);
 control=readl(asc+0x44);
 status=readl(asc+0x48);
 rx=readl(rtk->mbox->regs+0x114);
 if (control==U32_MAX || !(control&0x10) || status==U32_MAX || !(status&3)
     || rx==U32_MAX || !(rx&BIT(17))) {ret=-EBUSY;goto out;}
 rtk->g16_clear10_attempted=true;
 writel(control&~0x10,asc+0x44);
 control=readl(asc+0x44);
 if (control==U32_MAX || (control&0x10)) {ret=-EIO;goto out;}
 /* Distinct fresh RMW, never replay the pre-stop image. */
 rtk->g16_clear20_attempted=true;
 writel(control&~0x20,asc+0x44);
 control=readl(asc+0x44);status=readl(asc+0x48);
 if (control==U32_MAX || (control&0x30) || status==U32_MAX || !(status&3)) {
  ret=-EIO;goto out;
 }
 rtk->g16_cpu_stopped=true;
 apple_mbox_stop(rtk->mbox);
 flush_workqueue(rtk->wq);
 ret=0;
out:
 pr_info("RTKit G16 stop: result=%d intent=%u ack=%u nmi=%u clear10=%u clear20=%u cpu_stopped=%u rx_error=%d retained=1\n",
         ret,rtk->g16_intent,READ_ONCE(rtk->g16_ack),rtk->g16_nmi_attempted,
         rtk->g16_clear10_attempted,rtk->g16_clear20_attempted,
         rtk->g16_cpu_stopped,READ_ONCE(rtk->g16_rx_error));
 mutex_unlock(&rtk->g16_lock);
 return ret;
}
EXPORT_SYMBOL_GPL(apple_rtkit_g16_powergate);

bool apple_rtkit_g16_ack_observed(struct apple_rtkit *rtk)
{
 return READ_ONCE(rtk->g16_ack);
}
EXPORT_SYMBOL_GPL(apple_rtkit_g16_ack_observed);

/* Call after owned CPU stop + provider OFF/ON sequence, before START. Unlike
 * ordinary reinit this preserves ALL prior system endpoint buffers. On a
 * timeout no code runs ordinary reinit/free against the old generation.
 */
int apple_rtkit_g16_rearm_retained(struct apple_rtkit *rtk, void *fresh_cookie)
{
 struct apple_rtkit_g16_retained *old;
 int ret;
 mutex_lock(&rtk->g16_lock);
 if (!fresh_cookie || !rtk->g16_cpu_stopped || rtk->g16_rearm_attempted) {ret=-EBUSY;goto out;}
 old=kzalloc(sizeof(*old),GFP_KERNEL);
 if (!old) {ret=-ENOMEM;goto out;}
 rtk->g16_rearm_attempted=true;
 apple_mbox_stop(rtk->mbox);
 flush_workqueue(rtk->wq);
 old->buffers[0]=rtk->ioreport_buffer;old->buffers[1]=rtk->system7_buffer;
 old->buffers[2]=rtk->crashlog_buffer;old->buffers[3]=rtk->oslog_buffer;
 old->buffers[4]=rtk->syslog_buffer;old->syslog_msg_buffer=rtk->syslog_msg_buffer;
 old->cookie=rtk->cookie;
 old->next=rtk->g16_retained;rtk->g16_retained=old;
 rtk->cookie=fresh_cookie;
 memset(&rtk->ioreport_buffer,0,sizeof(rtk->ioreport_buffer));
 memset(&rtk->system7_buffer,0,sizeof(rtk->system7_buffer));
 memset(&rtk->crashlog_buffer,0,sizeof(rtk->crashlog_buffer));
 memset(&rtk->oslog_buffer,0,sizeof(rtk->oslog_buffer));
 memset(&rtk->syslog_buffer,0,sizeof(rtk->syslog_buffer));
 rtk->syslog_msg_buffer=NULL;rtk->syslog_n_entries=0;rtk->syslog_msg_size=0;
 bitmap_zero(rtk->endpoints,APPLE_RTKIT_MAX_ENDPOINTS);
 set_bit(APPLE_RTKIT_EP_MGMT,rtk->endpoints);
 reinit_completion(&rtk->epmap_completion);
 reinit_completion(&rtk->crashlog_completion);
 reinit_completion(&rtk->iop_pwr_ack_completion);
 reinit_completion(&rtk->ap_pwr_ack_completion);
 rtk->boot_result=0;rtk->version=0;rtk->crashed=false;
 rtk->iop_power_state=APPLE_RTKIT_PWR_STATE_OFF;
 rtk->ap_power_state=APPLE_RTKIT_PWR_STATE_OFF;
 /* Permit the ordinary autonomous HELLO/map/7-20/B20 boot parser, without
  * stock wake's INIT220 or freeing old buffers. The next native intent is a
  * distinct generation and may be consumed only after boot completes. */
 rtk->g16_intent=false;rtk->g16_cpu_stopped=false;rtk->g16_rearm_attempted=false;
 WRITE_ONCE(rtk->g16_ack,false);WRITE_ONCE(rtk->g16_rx_error,0);
 rtk->g16_nmi_attempted=false;rtk->g16_clear10_attempted=false;rtk->g16_clear20_attempted=false;
 ret=apple_mbox_start(rtk->mbox);
out:
 mutex_unlock(&rtk->g16_lock);return ret;
}
EXPORT_SYMBOL_GPL(apple_rtkit_g16_rearm_retained);

/* Failure after cookie replacement still transfers ownership. The Rust
 * adapter must not free callback data when mailbox-start itself fails. */
bool apple_rtkit_g16_cookie_owned(struct apple_rtkit *rtk, void *cookie)
{
 return READ_ONCE(rtk->cookie)==cookie;
}
EXPORT_SYMBOL_GPL(apple_rtkit_g16_cookie_owned);
