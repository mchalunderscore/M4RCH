// SPDX-License-Identifier: GPL-2.0-only
/* Owned host pages and software alias walk only. No device/MMIO/TTBR access. */
#include <linux/module.h>
#include <linux/mm.h>
#include <linux/slab.h>
#include "job-data.h"
static struct page *pages[POOL_PAGES];
struct alias_leaf { u64 va; phys_addr_t pa; };
static struct alias_leaf aliases[2][POOL_PAGES];
static void command_pages_release(void)
{
 unsigned int i;
 for (i=0;i<POOL_PAGES;i++) if (pages[i]) {
  __free_pages(pages[i],0);pages[i]=NULL;
 }
}
static void *walk(unsigned int role,u64 va)
{
 unsigned int index;
 u64 base=role?FW_BASE:DEVICE_BASE;
 if (role>1 || va<base || va-base>=POOL_BYTES) return NULL;
 index=(va-base)>>PAGE_SHIFT;
 if (aliases[role][index].va!=base+(u64)index*PAGE_SIZE ||
     aliases[role][index].pa!=page_to_phys(pages[index])) return NULL;
 return (u8 *)page_address(pages[index])+((va-base)&(PAGE_SIZE-1));
}
static int __init command_memory_init(void)
{
 unsigned int i,j,part,boundaries=0;
 if (PAGE_SIZE!=0x4000 || POOL_PAGES*PAGE_SIZE!=POOL_BYTES ||
     JOB_COUNT*COMMAND_BYTES>POOL_BYTES) return -EINVAL;
 for (i=0;i<POOL_PAGES;i++) {
  pages[i]=alloc_pages(GFP_KERNEL|__GFP_ZERO,0);
  if (!pages[i]) goto failure;
  aliases[0][i]=(struct alias_leaf){DEVICE_BASE+(u64)i*PAGE_SIZE,page_to_phys(pages[i])};
  aliases[1][i]=(struct alias_leaf){FW_BASE+(u64)i*PAGE_SIZE,page_to_phys(pages[i])};
 }
 for (i=0;i<JOB_COUNT;i++) {
  unsigned int offset=i*COMMAND_BYTES;
  for (j=0;j<COMMAND_BYTES;j+=part) {
   unsigned int pos=offset+j;
   part=min_t(unsigned int,COMMAND_BYTES-j,PAGE_SIZE-(pos&(PAGE_SIZE-1)));
   memcpy(walk(0,DEVICE_BASE+pos),job_bytes[i]+j,part);
   if (j) boundaries++;
  }
 }
 for (i=0;i<JOB_COUNT;i++) {
  for (j=0;j<COMMAND_BYTES;j+=part) {
   unsigned int pos=i*COMMAND_BYTES+j;
   void *device=walk(0,DEVICE_BASE+pos),*firmware=walk(1,FW_BASE+pos);
   part=min_t(unsigned int,COMMAND_BYTES-j,PAGE_SIZE-(pos&(PAGE_SIZE-1)));
   if (!device || device!=firmware || memcmp(device,job_bytes[i]+j,part)) goto failure;
  }
 }
 /* Native-rounded trailing capacity is uninitialized command space, kept zero. */
 for (j=JOB_COUNT*COMMAND_BYTES;j<POOL_BYTES;j++)
  if (*(u8 *)walk(1,FW_BASE+j)) goto failure;
 pr_info("m4rch command-memory: PASS jobs=%u pages=%u bytes=%u crossings=%u two_aliases=1 trailing_zero=1 published=0\n",
         JOB_COUNT,POOL_PAGES,POOL_BYTES,boundaries);
 pr_info("m4rch command-memory: CPU copies and software walks only; no GPU mappings/cache/acceptance/completion proof\n");
 return 0;
failure:
 command_pages_release();return -EINVAL;
}
static void __exit command_memory_exit(void)
{
 command_pages_release();pr_info("m4rch command-memory: all owned pages released; published=0\n");
}
module_init(command_memory_init);
module_exit(command_memory_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Host-only ordinary3D owned backing and software alias validation");
