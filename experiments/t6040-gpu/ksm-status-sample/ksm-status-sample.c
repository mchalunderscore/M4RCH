// SPDX-License-Identifier: GPL-2.0-only
/* Bounded post-trial read-only KSM observation; caller must hold GFX power. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/io.h>
static unsigned int run_gate;
module_param(run_gate,uint,0400);
static int __init sample_init(void)
{
 void __iomem *asc,*ksm;
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
 iounmap(ksm);
 return 0;
}
static void __exit sample_exit(void){}
module_init(sample_init);
module_exit(sample_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only post-stop T6040 KSM status sample, power held externally");
