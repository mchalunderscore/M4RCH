// SPDX-License-Identifier: GPL-2.0-only
/* Owned host pages and unpublished UAT-shaped tables. No device/MMIO/TTBR access. */
#include <linux/module.h>
#include <linux/mm.h>
#include <linux/slab.h>
#include <linux/unaligned.h>
#include "job-data.h"
static struct page *pages[POOL_PAGES];
#define PA_MASK GENMASK_ULL(41,14) /* Linux CPU physical addresses, not native generic UAT inputs. */
/* Candidate protections cross-checked against native UAT encoding and pgtable.rs.
 * Resource API options -> encoder input and actual pool dispatch remain unknown. */
static const u64 leaf_flags[2]={0x00e0000000000c0bULL,0x00c000000000044bULL};
static struct page *tables[2][3];
static u8 mapping_records[POOL_PAGES][24];
static unsigned int notification_count;
static void command_pages_release(void)
{
 unsigned int i,r,l;
 for (r=0;r<2;r++) for (l=0;l<3;l++) if (tables[r][l]) {
  __free_pages(tables[r][l],0);tables[r][l]=NULL;
 }
 for (i=0;i<POOL_PAGES;i++) if (pages[i]) {
  __free_pages(pages[i],0);pages[i]=NULL;
 }
}
static void *walk(unsigned int role,u64 va)
{
 unsigned int index;
 u64 base,entry,*root,*l1,*l2;
 if (role>1) return NULL;
 base=role?FW_BASE:DEVICE_BASE;
 if (va<base || va-base>=POOL_BYTES) return NULL;
 root=page_address(tables[role][0]);l1=page_address(tables[role][1]);
 l2=page_address(tables[role][2]);
 /* Never dereference a physical pointer taken from a table. Verify ownership. */
 if (root[(va>>36)&63]!=(page_to_phys(tables[role][1])|3) ||
     l1[(va>>25)&2047]!=(page_to_phys(tables[role][2])|3)) return NULL;
 index=(va-base)>>PAGE_SHIFT;entry=l2[(va>>14)&2047];
 if (entry!=(page_to_phys(pages[index])|leaf_flags[role])) return NULL;
 return (u8 *)page_address(pages[index])+((va-base)&(PAGE_SIZE-1));
}
static int tables_prepare(void)
{
 unsigned int r,l,i;
 for (r=0;r<2;r++) {
  u64 base=r?FW_BASE:DEVICE_BASE,*root,*l1,*l2;
  if (base+POOL_BYTES<base || ((base>>42)!=0 && (base>>42)!=((1ULL<<22)-1)) || (base&(PAGE_SIZE-1)) || ((base+POOL_BYTES-1)>>25)!=(base>>25)) return -EINVAL;
  for (l=0;l<3;l++) {
   tables[r][l]=alloc_pages(GFP_KERNEL|__GFP_ZERO,0);
   if (!tables[r][l]) return -ENOMEM;
   if (page_to_phys(tables[r][l])&~PA_MASK) return -EINVAL;
  }
  root=page_address(tables[r][0]);l1=page_address(tables[r][1]);l2=page_address(tables[r][2]);
  root[(base>>36)&63]=page_to_phys(tables[r][1])|3;
  l1[(base>>25)&2047]=page_to_phys(tables[r][2])|3;
  for (i=0;i<POOL_PAGES;i++) l2[((base+(u64)i*PAGE_SIZE)>>14)&2047]=page_to_phys(pages[i])|leaf_flags[r];
 }
 return 0;
}
static bool rejection_checks(void)
{
 unsigned int r,l;
 for (r=0;r<2;r++) {
  u64 base=r?FW_BASE:DEVICE_BASE;
  if (walk(r,base-1) || walk(r,base+POOL_BYTES)) return false;
  for (l=0;l<3;l++) {
   unsigned int index=l==0?(base>>36)&63:l==1?(base>>25)&2047:(base>>14)&2047;
   u64 *table=page_address(tables[r][l]),saved=table[index];
   table[index]=0;
   if (walk(r,base)) {table[index]=saved;return false;}
   table[index]=saved^BIT_ULL(14); /* Wrong physical ownership must also fail. */
   if (walk(r,base)) {table[index]=saved;return false;}
   table[index]=saved;
   if (!walk(r,base)) return false;
  }
 }
 return !walk(2,DEVICE_BASE);
}
static bool notifications_prepare(void)
{
 unsigned int i;
 bool eligible=(FW_BASE>=0xfffffc2000000000ULL && FW_BASE+POOL_BYTES<=0xfffffc2180000000ULL) ||
               (FW_BASE>=0xfffffc2181400000ULL && FW_BASE+POOL_BYTES<=0xfffffc2185400000ULL);
 if (!eligible) return true; /* Legacy low fixture profile has no callback. */
 for (i=0;i<POOL_PAGES;i++) {
  u64 va=FW_BASE+(u64)i*PAGE_SIZE,pa=page_to_phys(pages[i]);
  u16 flags=(va>=0xfffffc20c0000000ULL && va<0xfffffc2180000000ULL)?7:5;
  u8 *record=mapping_records[i];
  if ((pa>>12)>U32_MAX) return false;
  put_unaligned_le64(va,record);put_unaligned_le32(pa>>12,record+8);
  put_unaligned_le16(1,record+16);put_unaligned_le16(flags,record+18);
  /* Static zeroed record padding; no firmware publication or cache claim. */
  pr_info("m4rch command-memory: mapping %u va=%#llx pa=%#llx descriptor=%*phN\n",i,va,pa,24,record);
 }
 notification_count=POOL_PAGES;return true;
}
static int __init command_memory_init(void)
{
 unsigned int i,j,part,boundaries=0;
 if (PAGE_SIZE!=0x4000 || POOL_PAGES*PAGE_SIZE!=POOL_BYTES ||
     JOB_COUNT*COMMAND_BYTES>POOL_BYTES) return -EINVAL;
 for (i=0;i<POOL_PAGES;i++) {
  pages[i]=alloc_pages(GFP_KERNEL|__GFP_ZERO,0);
  if (!pages[i]) goto failure;
  if (page_to_phys(pages[i])&~PA_MASK) goto failure;
 }
 if (tables_prepare() || !rejection_checks() || !notifications_prepare()) goto failure;
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
 pr_info("m4rch command-memory: PASS jobs=%u pages=%u bytes=%u crossings=%u two_aliases=1 trailing_zero=1 table_pages=6 rejected_invalid=17 notifications=%u fw_base=%#llx published=0\n",
         JOB_COUNT,POOL_PAGES,POOL_BYTES,boundaries,notification_count,(u64)FW_BASE);
 pr_info("m4rch command-memory: CPU copies through owned three-level shadow tables; candidate protections only; no installed GPU mappings/cache/acceptance/completion proof\n");
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
MODULE_DESCRIPTION("Host-only ordinary3D owned backing and unpublished UAT table validation");
