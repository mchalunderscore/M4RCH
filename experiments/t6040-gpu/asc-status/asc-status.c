// SPDX-License-Identifier: GPL-2.0-only
/* J614s bounded ASC control/status snapshot; never touches FIFOs or writes ASC. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/io.h>
#include <linux/ioport.h>
static unsigned int read_gate;
module_param(read_gate, uint, 0400);
static int __init snapshot(void)
{
 void __iomem *regs;
 u32 control, status;
 const resource_size_t base = 0x28a600000ULL;
 if (read_gate != 1 || !of_machine_is_compatible("apple,t6040") ||
     !of_machine_is_compatible("apple,j614s")) return -ENODEV;
 if (!request_mem_region(base, 0x1000, "m4rch-asc-status")) return -EBUSY;
 regs = ioremap(base, 0x1000);
 if (!regs) { release_mem_region(base,0x1000); return -ENOMEM; }
 control = readl(regs + 0x44);
 status = readl(regs + 0x48);
 iounmap(regs);
 release_mem_region(base,0x1000);
 pr_info("m4rch ASC snapshot: base=%#llx control=%#x status=%#x; two reads, no ASC writes\n",(unsigned long long)base,control,status);
 return 0;
}
static void __exit done(void) {}
module_init(snapshot);module_exit(done);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("GFX ASC control/status-only snapshot; external qualified power hold required");
