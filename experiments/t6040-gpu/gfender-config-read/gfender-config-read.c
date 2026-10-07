// SPDX-License-Identifier: GPL-2.0-only
/* One read from the candidate GFenderCfg word; no register writes or firmware wake.
 * Harness must validate fresh ADT ranges and the retained graph power reference. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/io.h>
#include <linux/ioport.h>
#define CANDIDATE_BASE 0x288d04000ULL
static unsigned int run_gate;
module_param(run_gate,uint,0400);
static int __init cfg_init(void)
{
 void __iomem *map;
 u32 value;
 if (run_gate!=1 || !of_machine_is_compatible("apple,j614s") ||
     !of_machine_is_compatible("apple,t6040")) return -ENODEV;
 if (!request_mem_region(CANDIDATE_BASE,0x1000,"m4rch-gfender-config-read")) return -EBUSY;
 map=ioremap(CANDIDATE_BASE,0x1000);
 if (!map) {release_mem_region(CANDIDATE_BASE,0x1000);return -ENOMEM;}
 value=readl(map+0x10);
 pr_info("m4rch GFender candidate: physical=%#llx word=%#x; config read only, identity not established\n",CANDIDATE_BASE+0x10,value);
 iounmap(map);release_mem_region(CANDIDATE_BASE,0x1000);
 return 0;
}
static void __exit cfg_exit(void) {}
module_init(cfg_init);module_exit(cfg_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("J614s one-word candidate GFenderCfg read; no writes");
