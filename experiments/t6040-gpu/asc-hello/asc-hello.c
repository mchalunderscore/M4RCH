// SPDX-License-Identifier: GPL-2.0-only
/* EXPERIMENTAL: start cold GFX ASC, poll one message, stop; no GPU work or replies. */
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
static int __init hello_init(void)
{
 struct of_phandle_args spec = {};
 u32 reg[2],cells,control,status;
 const char *label;
 unsigned long limit;
 int ret;
 bool got = false, stopped = false;
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
 consumer=platform_device_register_simple("m4rch-asc-hello",-1,NULL,0);
 if (IS_ERR(consumer)) {ret=PTR_ERR(consumer);consumer=NULL;of_node_put(spec.np);return ret;}
 ret=of_genpd_add_device(&spec,&consumer->dev);of_node_put(spec.np);
 if (ret) {platform_device_unregister(consumer);consumer=NULL;return ret;}
 ret=pm_runtime_set_suspended(&consumer->dev);if(ret)goto fail;
 pm_runtime_enable(&consumer->dev);
 ret=pm_runtime_resume_and_get(&consumer->dev);if(ret<0)goto fail;held=true;
 if (!request_mem_region(ASC_BASE,0x1000,"m4rch-asc-hello")) {ret=-EBUSY;goto fail;}asc_region=true;
 if (!request_mem_region(MBOX_BASE,0x1000,"m4rch-asc-hello")) {ret=-EBUSY;goto fail;}mbox_region=true;
 asc=ioremap(ASC_BASE,0x1000);mbox=ioremap(MBOX_BASE,0x1000);
 if (!asc || !mbox) {ret=-ENOMEM;goto fail;}
 control=readl(asc+0x44);status=readl(asc+0x48);
 if ((control&START) || (status&3)!=2) {ret=-EBUSY;goto fail;}
 /* Refuse an old pending receive: this experiment needs a cold FIFO. */
 if (!(readl(mbox+0x114)&EMPTY)) {ret=-EBUSY;goto fail;}
 pr_info("m4rch ASC hello: cold control=%#x status=%#x; starting bounded poll\n",control,status);
 started=true;writel(control|START,asc+0x44);readl(asc+0x44);
 limit=jiffies+msecs_to_jiffies(4000);
 do {
  if (!(readl(mbox+0x114)&EMPTY)) {
   u64 message=readq(mbox+0x830),metadata=readq(mbox+0x838);
   pr_info("m4rch ASC hello: message=%#llx metadata=%#llx; no reply sent\n",message,metadata);
   got=true;break;
  }
  usleep_range(1000,2000);
 } while(time_before(jiffies,limit));
 pr_info("m4rch ASC hello: message_received=%d; requesting ASC core stop\n",got);
 writel(control&~START,asc+0x44);readl(asc+0x44);
 limit=jiffies+msecs_to_jiffies(100);
 do {
  u32 c=readl(asc+0x44),s=readl(asc+0x48);
  if (!(c&START) && (s&3)==2) {stopped=true;break;}
  usleep_range(1000,2000);
 } while(time_before(jiffies,limit));
 pr_info("m4rch ASC hello: final control=%#x status=%#x stop_readback=%d\n",readl(asc+0x44),readl(asc+0x48),stopped);
 /* Register readback is not a DMA-quiescence proof. After every start, keep
  * power/mappings and module text pinned until a normal reboot, even on stop. */
 __module_get(THIS_MODULE);
 pr_warn("m4rch ASC hello: trial complete; resources pinned, reboot required; do not force module removal\n");
 return 0;
fail:
 if (started) {__module_get(THIS_MODULE);pr_err("m4rch ASC hello: started-state failure retained; reboot required\n");return 0;}
 cleanup();return ret;
}
static void __exit hello_exit(void) {cleanup();}
module_init(hello_init);module_exit(hello_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Experimental J614s cold ASC initial-message probe; pins resources until reboot");
