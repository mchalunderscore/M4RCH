// SPDX-License-Identifier: GPL-2.0-only
/* Bounded post-trial KSM observation, optional restored bank selector; caller must hold GFX power. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/io.h>
static bool bank_read;
module_param(bank_read,bool,0400);
static unsigned int run_gate;
module_param(run_gate,uint,0400);
static int __init sample_init(void)
{
 void __iomem *asc,*ksm,*fault,*selector;
 u64 saved;
 unsigned int q;
 u32 ctl,status;
 if(run_gate!=1 || !of_machine_is_compatible("apple,j614s") || !of_machine_is_compatible("apple,t6040"))return -ENODEV;
 asc=ioremap(0x28a600000ULL,0x1000);
 if(!asc)return -ENOMEM;
 ctl=readl(asc+0x44);status=readl(asc+0x48);
 iounmap(asc);
 if(ctl!=0 || status!=0x6e)return -EBUSY;
 ksm=ioremap(0x288020000ULL,0x4000);
 if(!ksm)return -ENOMEM;
 /* Reads appear in exact matched firmware at19858/19900 and19644. */
 pr_info("m4rch ksm-status: post-stop offset21038=%#llx offset21040=%#llx offset211c8=%#llx\n",readq(ksm+0x1038),readq(ksm+0x1040),readq(ksm+0x11c8));
 pr_info("m4rch ksm-pause: request=%#llx ack=%#llx\n",readq(ksm+0x11c8),readq(ksm+0x11d0));
 if(bank_read){
  selector=ioremap(0x288010000ULL,0x4000);
  if(!selector){iounmap(ksm);return -ENOMEM;}
  saved=readq(selector+0x3a8);
  if(saved>127){iounmap(selector);iounmap(ksm);return -EINVAL;}
  for(q=0;q<2;q++){
   writeq(q,selector+0x3a8);readq(selector+0x3a8);
   /* Matched firmware snapshot16514..1652c reads these banked words. */
   pr_info("m4rch ksm-bank: queue=%u ring_config=%#llx raw21010=%#llx raw21020=%#llx raw211e0=%#llx\n",q,readq(ksm+0x1008),readq(ksm+0x1010),readq(ksm+0x1020),readq(ksm+0x11e0));
  }
  writeq(saved,selector+0x3a8);
  pr_info("m4rch ksm-bank: restored_selector=%#llx expected=%#llx\n",readq(selector+0x3a8),saved);
  if(readq(selector+0x3a8)!=saved){iounmap(selector);iounmap(ksm);return -EIO;}
  iounmap(selector);
 }
 /* Matched firmware16544..16568 snapshots four global words. */
 pr_info("m4rch ksm-global: raw210e8=%#llx raw210f0=%#llx raw210f8=%#llx raw21100=%#llx\n",readq(ksm+0x10e8),readq(ksm+0x10f0),readq(ksm+0x10f8),readq(ksm+0x1100));
 iounmap(ksm);
 fault=ioremap(0x28800c000ULL,0x4000);
 if(!fault)return -ENOMEM;
 /* Matched firmware5eb0 reads fault-info; maintained regs.rs reads paired address. */
 pr_info("m4rch ksm-fault: post-stop info=%#llx addr=%#llx\n",readq(fault+0x18c0),readq(fault+0x18c8));
 iounmap(fault);
 return 0;
}
static void __exit sample_exit(void){}
module_init(sample_init);
module_exit(sample_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Post-stop T6040 KSM/fault sample; optional bank selector; power held externally");
