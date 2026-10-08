// SPDX-License-Identifier: GPL-2.0-only
/* EXPERIMENTAL: start cold GFX ASC, reply to protocol-12 HELLO, acknowledge bounded endpoint maps. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/io.h>
#include <linux/ioport.h>
#include <linux/mm.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>
#include <linux/delay.h>
#include <linux/jiffies.h>
#include <linux/kobject.h>
#include <linux/sysfs.h>
#include "boot-contract.h"
#include "graph-map.h"
#define ASC_BASE 0x28a600000ULL
#define MBOX_BASE (ASC_BASE + 0x8000)
#define START BIT(4)
#define EMPTY BIT(17)
static unsigned int run_gate;
static bool request_shutdown;
static bool warm_restart;
module_param(warm_restart,bool,0400);
static bool release_on_shutdown;
module_param(release_on_shutdown,bool,0400);
module_param(request_shutdown,bool,0400);
static unsigned int observe_ms=30000;
module_param(observe_ms,uint,0400);
module_param(run_gate,uint,0400);
static struct platform_device *consumer;
static void __iomem *asc, *mbox;
static bool held, asc_region, mbox_region, started;
static struct kobject *graph_directory;
static ssize_t graph_read(struct file *file, struct kobject *kobj,
 const struct bin_attribute *attr, char *buf, loff_t off, size_t count)
{
 size_t done=0;
 if (off<0) return -EINVAL;
 if (off>=sizeof(graph_bytes)) return 0;
 count=min_t(size_t,count,sizeof(graph_bytes)-off);
 while (done<count) {
  size_t position=off+done, index=position/PAGE_SIZE;
  size_t within=position%PAGE_SIZE, bytes=min_t(size_t,count-done,PAGE_SIZE-within);
  void *page;
  unsigned long address;
  if (!owned[2+index]) return -ENODEV;
  page=page_address(owned[2+index]);
  for (address=(unsigned long)page;address<(unsigned long)page+PAGE_SIZE;address+=16)
   asm volatile("dc ivac, %0" :: "r"(address) : "memory");
  asm volatile("dsb sy" ::: "memory");
  memcpy(buf+done,(u8 *)page+within,bytes);done+=bytes;
 }
 return count;
}
static struct bin_attribute graph_raw = {
 .attr={.name="objects",.mode=0400},.read=graph_read,.size=sizeof(graph_bytes),
};
static int graph_snapshot_create(void)
{
 int ret;
 graph_directory=kobject_create_and_add("m4rch_gpu_graph_trial",kernel_kobj);
 if (!graph_directory) return -ENOMEM;
 ret=sysfs_create_bin_file(graph_directory,&graph_raw);
 if (ret) {kobject_put(graph_directory);graph_directory=NULL;}
 return ret;
}
static void graph_snapshot_remove(void)
{
 if (graph_directory) {
  sysfs_remove_bin_file(graph_directory,&graph_raw);kobject_put(graph_directory);
  graph_directory=NULL;
 }
}
static void cleanup(void)
{
 graph_snapshot_remove();
 root_release();
 if (mbox) iounmap(mbox);
 if (asc) iounmap(asc);
 if (mbox_region) release_mem_region(MBOX_BASE,0x1000);
 if (asc_region) release_mem_region(ASC_BASE,0x1000);
 if (consumer) {
  if (held) {
   int ret=pm_runtime_put_sync_suspend(&consumer->dev);
   pr_info("m4rch graph-init: runtime suspend result=%d\n",ret);
  }
  pm_runtime_disable(&consumer->dev);
  pm_genpd_remove_device(&consumer->dev);
  platform_device_unregister(consumer);
 }
}
/* Start only endpoint 1. Echo only a firmware-owned reserved DATA offer. */
static bool crashlog_boot(void)
{
 unsigned long deadline;
 bool offered=false, iop_on=false;
 unsigned int messages=0;
 if (readl(mbox+0x110)&BIT(16)) return false;
 wmb();writeq((5ULL<<52)|(1ULL<<32)|2ULL,mbox+0x800);writeq(0,mbox+0x808);
 pr_info("m4rch ASC crashlog: started system endpoint 1 only\n");
 deadline=jiffies+msecs_to_jiffies(4000);
 do {
  if (!(readl(mbox+0x114)&EMPTY)) {
   u64 msg=readq(mbox+0x830),meta=readq(mbox+0x838);
   unsigned int ep=meta&0xff,type=(msg>>52)&0xff;
   pr_info("m4rch ASC crashlog: boot response message=%#llx metadata=%#llx\n",msg,meta);
   if (ep==1 && type==1 && !offered) {
    u64 address=msg&GENMASK_ULL(43,0),bytes=((msg>>44)&0xff)<<12;
    pr_info("m4rch ASC crashlog: offer address=%#llx bytes=%#llx\n",address,bytes);
    if (!bytes || address<FW_DATA_BASE || bytes>FW_DATA_BYTES ||
        address-FW_DATA_BASE>FW_DATA_BYTES-bytes || (address&0xfff) ||
        region_intersects(address,bytes,IORESOURCE_SYSTEM_RAM,IORES_DESC_NONE)!=REGION_DISJOINT ||
        (readl(mbox+0x110)&BIT(16))) {
     pr_err("m4rch ASC crashlog: unqualified offer; no acknowledgement\n");return false;
    }
    wmb();writeq(msg,mbox+0x800);writeq(1,mbox+0x808);offered=true;
    pr_info("m4rch ASC crashlog: reserved DATA offer echoed; no new DMA allocation\n");
   } else if (ep==0 && type==7 && (msg&0xffff)==0x20) {
    iop_on=true;
   } else {
    pr_err("m4rch ASC crashlog: unexpected boot message; stopping\n");return false;
   }
   if (offered && iop_on) return true;
   if (++messages>=16) return false;
  }
  usleep_range(1000,2000);
 } while(time_before(jiffies,deadline));
 pr_info("m4rch ASC crashlog: boot timeout offered=%d IOP_ON=%d\n",offered,iop_on);
 return false;
}
/* Bounded RTKit shutdown requests; replies alone do not authorize graph release. */
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
   pr_info("m4rch ASC crashlog: power response message=%#llx metadata=%#llx\n",msg,meta);
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
 u32 appmap = 0;
 u8 apps_started = 0;
 u8 map_seen = 0;
 if (warm_restart && (!release_on_shutdown || !request_shutdown || !GRAPH_RELEASE_EXPERIMENT)) return -EINVAL;
 if (release_on_shutdown && (!request_shutdown || !GRAPH_RELEASE_EXPERIMENT)) return -EINVAL;
 if (observe_ms<5000 || observe_ms>60000) return -EINVAL;
 if ((run_gate!=1 && run_gate!=2) || !of_machine_is_compatible("apple,j614s") ||
     !of_machine_is_compatible("apple,t6040")) return -ENODEV;
 if (run_gate==1) {
  ret=root_prepare(false);
  root_release();
  return ret;
 }
 spec.np=of_find_node_by_path("/soc/power-management@288e80000/power-controller@110");
 if (!spec.np) return -ENODEV;
 ret=of_property_read_u32_array(spec.np,"reg",reg,2);
 if (ret || reg[0]!=0x110 || reg[1]!=4 ||
     of_property_read_u32(spec.np,"#power-domain-cells",&cells) || cells ||
     of_property_read_string(spec.np,"label",&label) || strcmp(label,"gfx")) {
  of_node_put(spec.np); return -EINVAL;
 }
 consumer=platform_device_register_simple("m4rch-asc-crashlog",-1,NULL,0);
 if (IS_ERR(consumer)) {ret=PTR_ERR(consumer);consumer=NULL;of_node_put(spec.np);return ret;}
 ret=of_genpd_add_device(&spec,&consumer->dev);of_node_put(spec.np);
 if (ret) {platform_device_unregister(consumer);consumer=NULL;return ret;}
 ret=pm_runtime_set_suspended(&consumer->dev);if(ret)goto fail;
 pm_runtime_enable(&consumer->dev);
 ret=pm_runtime_resume_and_get(&consumer->dev);if(ret<0)goto fail;held=true;
 if (!request_mem_region(ASC_BASE,0x1000,"m4rch-asc-crashlog")) {ret=-EBUSY;goto fail;}asc_region=true;
 if (!request_mem_region(MBOX_BASE,0x1000,"m4rch-asc-crashlog")) {ret=-EBUSY;goto fail;}mbox_region=true;
 asc=ioremap(ASC_BASE,0x1000);mbox=ioremap(MBOX_BASE,0x1000);
 if (!asc || !mbox) {ret=-ENOMEM;goto fail;}
 control=readl(asc+0x44);status=readl(asc+0x48);
 pr_info("m4rch graph-init: entry control=%#x status=%#x warm_restart=%d\n",control,status,warm_restart);
 if ((control&START) || (status!=0x6a && !(warm_restart && status==0x6e))) {ret=-EBUSY;goto fail;}
 /* Refuse an old pending receive: this experiment needs a cold FIFO. */
 if (!(readl(mbox+0x114)&EMPTY)) {ret=-EBUSY;goto fail;}
 pr_info("m4rch ASC crashlog: cold control=%#x status=%#x; starting bounded poll\n",control,status);
 started=true;writel(control|START,asc+0x44);readl(asc+0x44);
 if (warm_restart) {
  /* Matched local apple_rtkit_wake: INIT requests negotiation after sleep. */
  if (readl(mbox+0x110)&BIT(16)) goto stop_firmware;
  wmb();writeq((6ULL<<52)|0x220ULL,mbox+0x800);writeq(0,mbox+0x808);
  pr_info("m4rch graph-init: warm IOP INIT request0x220 sent; awaiting fresh HELLO/map\n");
 }
 limit=jiffies+msecs_to_jiffies(4000);
 do {
  if (!(readl(mbox+0x114)&EMPTY)) {
   u64 message=readq(mbox+0x830),metadata=readq(mbox+0x838);
   unsigned int type = (message >> 52) & 0xff, endpoint = metadata & 0xff;
   pr_info("m4rch ASC crashlog: message=%#llx metadata=%#llx\n",message,metadata);
   got=true;messages++;
   if (!replied && endpoint == 0 && type == 1) {
    unsigned int min = message & 0xffff, max = (message >> 16) & 0xffff;
    if (min != 12 || max != 12) {
     pr_err("m4rch ASC crashlog: unexpected HELLO versions %u/%u; no reply\n",min,max);
     break;
    }
    if (readl(mbox+0x110) & BIT(16)) {
     pr_err("m4rch ASC crashlog: transmit FIFO full; no reply\n");break;
    }
    /* Standard RTKit management HELLO_REPLY, endpoint zero. No addresses. */
    wmb();writeq((2ULL << 52) | (12ULL << 16) | 12ULL,mbox+0x800);
    writeq(0,mbox+0x808);
    replied=true;
    pr_info("m4rch ASC crashlog: HELLO_REPLY version 12 sent; no application endpoints started\n");
   } else if (replied && endpoint == 0 && type == 8) {
    pr_info("m4rch ASC crashlog: endpoint-map base=%llu bitmap=%#x last=%u; map received\n",(message >> 32)&7,(u32)message,!!(message & BIT_ULL(51)));
    unsigned int base = (message >> 32) & 7;
    if (base==1) appmap=(u32)message;
    bool last = !!(message & BIT_ULL(51));
    u64 reply = (8ULL << 52) | ((u64)base << 32) |
                (last ? BIT_ULL(51) : 1ULL);
    if ((map_seen & BIT(base)) || (readl(mbox+0x110) & BIT(16))) {
     pr_err("m4rch ASC crashlog: duplicate map or full TX; stopping\n");break;
    }
    map_seen |= BIT(base);
    wmb();writeq(reply,mbox+0x800);writeq(0,mbox+0x808);
    pr_info("m4rch ASC crashlog: map ACK=%#llx; no endpoints started\n",reply);
    if (last) {epmap=true;break;}
   }
   if (messages >= 16) break;
  }
  usleep_range(1000,2000);
 } while(time_before(jiffies,limit));
 pr_info("m4rch ASC crashlog: message_received=%d hello_replied=%d endpoint_map=%d; requesting ASC core stop\n",got,replied,epmap);
 if (epmap && crashlog_boot() && power_ack(0xb,0xb,0x20)) {
  ret=root_prepare(true);if(ret)goto retire_firmware;
  ret=graph_snapshot_create();if(ret)goto retire_firmware;
  /* Start only the two advertised app endpoints. No init-root message. */
  if ((appmap&3)==3) {
   unsigned int ep;
   for (ep=32;ep<=33;ep++) {
    if (readl(mbox+0x110)&BIT(16)) break;
    wmb();writeq((5ULL<<52)|((u64)ep<<32)|2ULL,mbox+0x800);
    writeq(0,mbox+0x808);
    apps_started |= BIT(ep-32);
    pr_info("m4rch ASC crashlog: application endpoint %u start sent; no init graph\n",ep);
   }
  }
  /* Publish one complete candidate batch; published pages remain pinned. */
  if (apps_started==3 && !(readl(mbox+0x110)&BIT(16))) {
   unsigned long observe_until;
   unsigned int observed=0;
   root_sent=true; /* pin even if delivery/consumption cannot be established */
   wmb();writeq(0x00810c2000100000ULL,mbox+0x800);writeq(32,mbox+0x808);
   pr_warn("m4rch graph-init: G16S root sent to EP32; host allocations enabled; structural fixture, NOT rendering readiness\n");
   observe_until=jiffies+msecs_to_jiffies(observe_ms);
   do {
    if (!(readl(mbox+0x114)&EMPTY)) {
     u64 msg=readq(mbox+0x830),meta=readq(mbox+0x838);
     pr_info("m4rch graph-init: after-publication message=%#llx metadata=%#llx; no reply\n",msg,meta);
     if (++observed>=64) break;
    }
    usleep_range(1000,2000);
   } while(time_before(jiffies,observe_until));
   pr_info("m4rch graph-init: observation messages=%u; capture crashlog before reboot\n",observed);
  }
retire_firmware:
  pr_info("m4rch graph-init: shutdown requested=%d root_sent=%d; published backing remains pinned\n",request_shutdown,root_sent);
  if (!root_sent || request_shutdown) ap_quiesced=power_ack(0xb,0xb,0x10);
  if (ap_quiesced) iop_sleep=power_ack(6,7,1);
 }
stop_firmware:
 pr_info("m4rch ASC crashlog: AP_QUIESCED_ACK=%d IOP_SLEEP_ACK=%d\n",ap_quiesced,iop_sleep);
 writel(control&~START,asc+0x44);readl(asc+0x44);
 limit=jiffies+msecs_to_jiffies(100);
 do {
  u32 c=readl(asc+0x44),s=readl(asc+0x48);
  if (!(c&START) && (s&3)==2) {stopped=true;break;}
  usleep_range(1000,2000);
 } while(time_before(jiffies,limit));
 pr_info("m4rch ASC crashlog: final control=%#x status=%#x stop_readback=%d\n",readl(asc+0x44),readl(asc+0x48),stopped);
 /* Only the explicitly compiled structural/no-job experiment may detach
  * published backing after both ACKs, core stop and an empty FIFO.
  * The ordinary non-publication path retains its previous checks.
  * Only this reserved-buffer, crashlog-only probe may release after both power
  * ACKs, core stop and an empty receive FIFO. Any incomplete step stays pinned.
  * This does not authorize teardown of an initialized or rendering GPU. */
 retired=!root_sent && ap_quiesced && iop_sleep && stopped && (readl(mbox+0x114)&EMPTY);
 if (root_sent && release_on_shutdown && ap_quiesced && iop_sleep && stopped &&
     (readl(mbox+0x114)&EMPTY)) {
  retired=root_detach_after_shutdown();
  if (retired) pr_info("m4rch graph-init: graph retirement verified; normal unload allowed\n");
 }
 if (retired) {
  if (!root_sent) pr_info("m4rch ASC crashlog: application-start-only retirement verified; normal unload allowed\n");
 } else {
  __module_get(THIS_MODULE);
  pr_warn("m4rch ASC crashlog: retirement incomplete; resources pinned; reboot required\n");
 }

 return 0;
fail:
 if (started) {__module_get(THIS_MODULE);pr_err("m4rch ASC crashlog: started-state failure retained; reboot required\n");return 0;}
 cleanup();return ret;
}
static void __exit hello_exit(void) {cleanup();}
module_init(hello_init);module_exit(hello_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Experimental J614s structural init batch; published graph pins until reboot");
