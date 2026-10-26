// SPDX-License-Identifier: GPL-2.0-only
/* Fixed read-only native power polls. Caller verifies retained ASC/GFX owner. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/io.h>
static unsigned int run_gate;
module_param(run_gate,uint,0400);
static int __init sample_init(void)
{
 void __iomem *asc,*primary,*prc,*engines;
 u32 control,status;
 if(run_gate!=1 || !of_machine_is_compatible("apple,j614s") ||
    !of_machine_is_compatible("apple,t6040")) return -ENODEV;
 asc=ioremap(0x28a600000ULL,0x1000);
 if(!asc) return -ENOMEM;
 control=readl(asc+0x44);status=readl(asc+0x48);iounmap(asc);
 if(!(control&BIT(4))) return -EBUSY;
 primary=ioremap(0x288004000ULL,0x4000);
 if(!primary) return -ENOMEM;
 prc=ioremap(0x288d4c000ULL,0x4000);
 if(!prc) {iounmap(primary);return -ENOMEM;}
 engines=ioremap(0x288d44000ULL,0x4000);
 if(!engines) {iounmap(prc);iounmap(primary);return -ENOMEM;}
 /* Matched FW322ec/2a1b4 polls5970, 2becc polls5960, 2bfec polls5978.
  * PRC+0 is32248/2a21c's transition; PRC+4 is2bdac/2c11c's transition.
  * Only read operands of native polling loops; no command/selector writes. */
 pr_info("m4rch power-poll-sample: asc_control=%#x asc_status=%#x raw5960=%#llx raw5970=%#llx raw5978=%#llx\n",
  control,status,readq(primary+0x1960),readq(primary+0x1970),readq(primary+0x1978));
 pr_info("m4rch power-poll-sample: rawd4c000=%#x rawd4c004=%#x\n",readl(prc),readl(prc+4));
 /* Subsequent main power-up polls low16 against its engine mask. */
 pr_info("m4rch power-poll-sample: rawd44070=%#x\n",readl(engines+0x70));
 iounmap(engines);iounmap(prc);iounmap(primary);return 0;
}
static void __exit sample_exit(void){}
module_init(sample_init);
module_exit(sample_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Fixed T6040 power poll operands; read only; GFX held externally");
