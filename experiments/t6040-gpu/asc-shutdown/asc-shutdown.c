// SPDX-License-Identifier: GPL-2.0-only
/* EXPERIMENTAL: start cold GFX ASC, reply to protocol-12 HELLO, acknowledge bounded endpoint maps. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/io.h>
#include <linux/ioport.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>
#include <linux/delay.h>
#include <linux/jiffies.h>
#define ASC_BASE 0x28a600000ULL
#define MBOX_BASE (ASC_BASE + 0x8000)
#define START BIT(4)
#define EMPTY BIT(17)
static unsigned int run_gate;
module_param(run_gate,uint,0400);
static struct platform_device *consumer;
static void __iomem *asc, *mbox;
static bool held, asc_region, mbox_region, started;
static void cleanup(void)
{
 if (mbox) iounmap(mbox);
 if (asc) iounmap(asc);
 if (mbox_region) release_mem_region(MBOX_BASE,0x1000);
 if (asc_region) release_mem_region(ASC_BASE,0x1000);
 if (consumer) {
  if (held) pm_runtime_put_sync_suspend(&consumer->dev);
  pm_runtime_disable(&consumer->dev);
  pm_genpd_remove_device(&consumer->dev);
  platform_device_unregister(consumer);
 }
}
/* Handshake-only retirement: no endpoint starts or firmware-accessible buffers. */
static bool power_ack(unsigned int request, unsigned int reply, u16 state)
{
 unsigned long deadline;
 unsigned int messages = 0;
 if (readl(mbox+0x110) & BIT(16)) return false;
 wmb();writeq(((u64)request << 52) | state,mbox+0x800);
 writeq(0,mbox+0x808);
 deadline=jiffies+msecs_to_jiffies(2000);
 do {
  if (!(readl(mbox+0x114)&EMPTY)) {
   u64 msg=readq(mbox+0x830),meta=readq(mbox+0x838);
   unsigned int type=(msg>>52)&0xff;
   pr_info("m4rch ASC shutdown: power response message=%#llx metadata=%#llx\n",msg,meta);
   if ((meta&0xff)!=0) return false;
   if (type==reply && (msg&0xffff)==state) return true;
   if (++messages>=16) return false;
  }
  usleep_range(1000,2000);
 } while(time_before(jiffies,deadline));
 return false;
}

static int __init hello_init(void)
{
 struct of_phandle_args spec = {};
 u32 reg[2],cells,control,status;
 const char *label;
 unsigned long limit;
 int ret;
 bool got = false, stopped = false, replied = false, epmap = false;
 bool ap_quiesced = false, iop_sleep = false, retired = false;
 unsigned int messages = 0;
 u8 map_seen = 0;
 if (run_gate!=1 || !of_machine_is_compatible("apple,j614s") ||
     !of_machine_is_compatible("apple,t6040")) return -ENODEV;
 spec.np=of_find_node_by_path("/soc/power-management@288e80000/power-controller@110");
 if (!spec.np) return -ENODEV;
 ret=of_property_read_u32_array(spec.np,"reg",reg,2);
 if (ret || reg[0]!=0x110 || reg[1]!=4 ||
     of_property_read_u32(spec.np,"#power-domain-cells",&cells) || cells ||
     of_property_read_string(spec.np,"label",&label) || strcmp(label,"gfx")) {
  of_node_put(spec.np); return -EINVAL;
 }
 consumer=platform_device_register_simple("m4rch-asc-shutdown",-1,NULL,0);
 if (IS_ERR(consumer)) {ret=PTR_ERR(consumer);consumer=NULL;of_node_put(spec.np);return ret;}
 ret=of_genpd_add_device(&spec,&consumer->dev);of_node_put(spec.np);
 if (ret) {platform_device_unregister(consumer);consumer=NULL;return ret;}
 ret=pm_runtime_set_suspended(&consumer->dev);if(ret)goto fail;
 pm_runtime_enable(&consumer->dev);
 ret=pm_runtime_resume_and_get(&consumer->dev);if(ret<0)goto fail;held=true;
 if (!request_mem_region(ASC_BASE,0x1000,"m4rch-asc-shutdown")) {ret=-EBUSY;goto fail;}asc_region=true;
 if (!request_mem_region(MBOX_BASE,0x1000,"m4rch-asc-shutdown")) {ret=-EBUSY;goto fail;}mbox_region=true;
 asc=ioremap(ASC_BASE,0x1000);mbox=ioremap(MBOX_BASE,0x1000);
 if (!asc || !mbox) {ret=-ENOMEM;goto fail;}
 control=readl(asc+0x44);status=readl(asc+0x48);
 if ((control&START) || (status&3)!=2) {ret=-EBUSY;goto fail;}
 /* Refuse an old pending receive: this experiment needs a cold FIFO. */
 if (!(readl(mbox+0x114)&EMPTY)) {ret=-EBUSY;goto fail;}
 pr_info("m4rch ASC shutdown: cold control=%#x status=%#x; starting bounded poll\n",control,status);
 started=true;writel(control|START,asc+0x44);readl(asc+0x44);
 limit=jiffies+msecs_to_jiffies(4000);
 do {
  if (!(readl(mbox+0x114)&EMPTY)) {
   u64 message=readq(mbox+0x830),metadata=readq(mbox+0x838);
   unsigned int type = (message >> 52) & 0xff, endpoint = metadata & 0xff;
   pr_info("m4rch ASC shutdown: message=%#llx metadata=%#llx\n",message,metadata);
   got=true;messages++;
   if (!replied && endpoint == 0 && type == 1) {
    unsigned int min = message & 0xffff, max = (message >> 16) & 0xffff;
    if (min != 12 || max != 12) {
     pr_err("m4rch ASC shutdown: unexpected HELLO versions %u/%u; no reply\n",min,max);
     break;
    }
    if (readl(mbox+0x110) & BIT(16)) {
     pr_err("m4rch ASC shutdown: transmit FIFO full; no reply\n");break;
    }
    /* Standard RTKit management HELLO_REPLY, endpoint zero. No addresses. */
    wmb();writeq((2ULL << 52) | (12ULL << 16) | 12ULL,mbox+0x800);
    writeq(0,mbox+0x808);
    replied=true;
    pr_info("m4rch ASC shutdown: HELLO_REPLY version 12 sent; no application endpoints started\n");
   } else if (replied && endpoint == 0 && type == 8) {
    pr_info("m4rch ASC shutdown: endpoint-map base=%llu bitmap=%#x last=%u; map received\n",(message >> 32)&7,(u32)message,!!(message & BIT_ULL(51)));
    unsigned int base = (message >> 32) & 7;
    bool last = !!(message & BIT_ULL(51));
    u64 reply = (8ULL << 52) | ((u64)base << 32) |
                (last ? BIT_ULL(51) : 1ULL);
    if ((map_seen & BIT(base)) || (readl(mbox+0x110) & BIT(16))) {
     pr_err("m4rch ASC shutdown: duplicate map or full TX; stopping\n");break;
    }
    map_seen |= BIT(base);
    wmb();writeq(reply,mbox+0x800);writeq(0,mbox+0x808);
    pr_info("m4rch ASC shutdown: map ACK=%#llx; no endpoints started\n",reply);
    if (last) {epmap=true;break;}
   }
   if (messages >= 16) break;
  }
  usleep_range(1000,2000);
 } while(time_before(jiffies,limit));
 pr_info("m4rch ASC shutdown: message_received=%d hello_replied=%d endpoint_map=%d; requesting ASC core stop\n",got,replied,epmap);
 if (epmap) {
  ap_quiesced=power_ack(0xb,0xb,0x10);
  if (ap_quiesced) iop_sleep=power_ack(6,7,1);
 }
 pr_info("m4rch ASC shutdown: AP_QUIESCED_ACK=%d IOP_SLEEP_ACK=%d\n",ap_quiesced,iop_sleep);
 writel(control&~START,asc+0x44);readl(asc+0x44);
 limit=jiffies+msecs_to_jiffies(100);
 do {
  u32 c=readl(asc+0x44),s=readl(asc+0x48);
  if (!(c&START) && (s&3)==2) {stopped=true;break;}
  usleep_range(1000,2000);
 } while(time_before(jiffies,limit));
 pr_info("m4rch ASC shutdown: final control=%#x status=%#x stop_readback=%d\n",readl(asc+0x44),readl(asc+0x48),stopped);
 /* Only this buffer-free, endpoint-free probe may release after both power
  * ACKs, core stop and an empty receive FIFO. Any incomplete step stays pinned.
  * This does not authorize teardown of an initialized or rendering GPU. */
 retired=ap_quiesced && iop_sleep && stopped && (readl(mbox+0x114)&EMPTY);
 if (retired) {
  pr_info("m4rch ASC shutdown: handshake-only retirement verified; normal unload allowed\n");
 } else {
  __module_get(THIS_MODULE);
  pr_warn("m4rch ASC shutdown: retirement incomplete; resources pinned; reboot required\n");
 }

 return 0;
fail:
 if (started) {__module_get(THIS_MODULE);pr_err("m4rch ASC shutdown: started-state failure retained; reboot required\n");return 0;}
 cleanup();return ret;
}
static void __exit hello_exit(void) {cleanup();}
module_init(hello_init);module_exit(hello_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Experimental J614s RTKit HELLO-reply/endpoint-enumeration probe; pins resources until reboot");
