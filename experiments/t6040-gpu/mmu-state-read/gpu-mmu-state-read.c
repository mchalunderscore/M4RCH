// SPDX-License-Identifier: GPL-2.0-only
/* Exact offsets from executed matching25G83 MMU setup/invalidation, not an aperture scan.
 * Harness holds GFX genpd. No firmware start or register writes. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/io.h>
#include <linux/ioport.h>
static unsigned int run_gate;
module_param(run_gate,uint,0400);
static int sample(u64 base,const u32 *offsets,unsigned int count)
{
 void __iomem *map;
 unsigned int i;
 if (!request_mem_region(base,0x4000,"m4rch-gpu-mmu-state-read")) return -EBUSY;
 map=ioremap(base,0x4000);
 if (!map) {release_mem_region(base,0x4000);return -ENOMEM;}
 for (i=0;i<count;i++) {
  u32 value;
  pr_info("m4rch mmu-read: begin physical=%#llx\n",base+offsets[i]);
  value=readl(map+offsets[i]);
  pr_info("m4rch mmu-read: physical=%#llx value=%#x\n",base+offsets[i],value);
 }
 iounmap(map);release_mem_region(base,0x4000);
 return 0;
}
static int __init exact_init(void)
{
 const u32 offsets[]={0,4,8,0xc,0x10,0x14,0x18,0x1c,0x20,0x24,0x28,0x2c,0x30};
 if (run_gate!=1 || !of_machine_is_compatible("apple,j614s") ||
     !of_machine_is_compatible("apple,t6040")) return -ENODEV;
 return sample(0x288d08000ULL,offsets,ARRAY_SIZE(offsets));
}
static void __exit exact_exit(void) {}
module_init(exact_init);module_exit(exact_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("J614s exact MMU control and GPTBAT reads, no writes");
