// SPDX-License-Identifier: GPL-2.0-only
/* Exact offsets from matching25G83 static mapping, not an aperture scan.
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
 if (!request_mem_region(base,0x4000,"m4rch-exact-register-read")) return -EBUSY;
 map=ioremap(base,0x4000);
 if (!map) {release_mem_region(base,0x4000);return -ENOMEM;}
 for (i=0;i<count;i++) {
  u32 value;
  pr_info("m4rch exact-read: begin physical=%#llx\n",base+offsets[i]);
  value=readl(map+offsets[i]);
  pr_info("m4rch exact-read: physical=%#llx value=%#x\n",base+offsets[i],value);
 }
 iounmap(map);release_mem_region(base,0x4000);
 return 0;
}
static int __init exact_init(void)
{
 const u32 bumper[]={0xa0,0xa4,0xa8},dfender[]={0x1704,0x1780},counter[]={0x3860};
 const u32 gfender[]={0x2020,0x2040},gcpms[]={0,0x80},mcw[]={0,4},prc[]={0,4},cs[]={0x1010,0x1014};
 int ret;
 if (run_gate!=1 || !of_machine_is_compatible("apple,j614s") ||
     !of_machine_is_compatible("apple,t6040")) return -ENODEV;
 ret=sample(0x288d44000ULL,bumper,ARRAY_SIZE(bumper));
 if (ret) return ret;
 ret=sample(0x288e00000ULL,dfender,ARRAY_SIZE(dfender));
 if (ret) return ret;
 ret=sample(0x288e1c000ULL,counter,ARRAY_SIZE(counter)); if (ret) return ret;
 ret=sample(0x288d04000ULL,gfender,ARRAY_SIZE(gfender)); if (ret) return ret;
 ret=sample(0x288d10000ULL,gcpms,ARRAY_SIZE(gcpms)); if (ret) return ret;
 ret=sample(0x288d40000ULL,mcw,ARRAY_SIZE(mcw)); if (ret) return ret;
 ret=sample(0x288d4c000ULL,prc,ARRAY_SIZE(prc)); if (ret) return ret;
 return sample(0x288e40000ULL,cs,ARRAY_SIZE(cs));
}
static void __exit exact_exit(void) {}
module_init(exact_init);module_exit(exact_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("J614s exact Bumper/DFender candidate reads, no writes");
