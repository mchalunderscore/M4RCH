/* SPDX-License-Identifier: GPL-2.0-only */
/* Minimal isolated root mapping: no donor main/hardware graph and no SGX writes.
 * Gate 1 allocates and walks owned shadow tables only. Gate 2 may publish one
 * previously empty bootstrap root entry while ASC is still cold/stopped.
 */
#include <linux/unaligned.h>
#define ROOT_VA 0xfffffc2000100000ULL
#define TABLE_BASE 0x105fff78000ULL
#define TABLE_BYTES 0x40000
#define PA_MASK (GENMASK_ULL(41,14))
#define FW_ROOT_RO (BIT_ULL(55) | BIT_ULL(10) | BIT_ULL(6) | 8ULL | 3ULL)
static struct page *owned[3]; /* L1, L2, envelope; exactly 16 KiB each */
static u64 *bootstrap;
static bool installed, root_sent;

static void clean_page(void *ptr)
{
 unsigned long pos;
 /* A 16-byte stride covers all cache lines without assuming a cache geometry. */
 for (pos=(unsigned long)ptr;pos<(unsigned long)ptr+PAGE_SIZE;pos+=16)
  asm volatile("dc cvac, %0" :: "r"(pos) : "memory");
 asm volatile("dsb sy" ::: "memory");
}
static void invalidate_root_va(void)
{
 u64 operand=(ROOT_VA>>12)&0x00000ffffffffffcULL;
 asm volatile(".arch armv8.4-a\n\ttlbi vaae1os, %0\n\tdsb sy" :: "r"(operand) : "memory");
}
static void root_release(void)
{
 unsigned int i;
 /* No unmapping/freeing once a root publication was sent to firmware. */
 if (root_sent) return;
 if (installed) {
  WRITE_ONCE(bootstrap[(ROOT_VA>>36)&63],0);
  clean_page(bootstrap);
  invalidate_root_va();
  installed=false;
 }
 if (bootstrap) {memunmap(bootstrap);bootstrap=NULL;}
 for (i=0;i<ARRAY_SIZE(owned);i++)
  if (owned[i]) {__free_pages(owned[i],0);owned[i]=NULL;}
}
static int root_prepare(bool install)
{
 u64 *l1,*l2;
 unsigned int i;
 int ret=-EINVAL;
 if (PAGE_SIZE!=0x4000) return -EINVAL;
 for (i=0;i<ARRAY_SIZE(owned);i++) {
  u64 pa;
  owned[i]=alloc_pages(GFP_KERNEL|__GFP_ZERO,0);
  if (!owned[i]) {ret=-ENOMEM;goto fail_root;}
  pa=page_to_phys(owned[i]);
  if (pa&~PA_MASK) goto fail_root;
  pr_info("m4rch root-envelope: owned page %u physical=%#llx\n",i,pa);
 }
 l1=page_address(owned[0]);l2=page_address(owned[1]);
 l1[(ROOT_VA>>25)&2047]=page_to_phys(owned[1])|3;
 l2[(ROOT_VA>>14)&2047]=page_to_phys(owned[2])|FW_ROOT_RO;
 /* Correct interface, disabled host allocations at root+2c. Firmware's
  * confirmed check rejects before dereferencing main+18 or Region C+20. */
 put_unaligned_le64(0x0c8aa322039604c0ULL,page_address(owned[2]));
 for (i=0;i<ARRAY_SIZE(owned);i++) clean_page(page_address(owned[i]));
 if ((l1[(ROOT_VA>>25)&2047]&PA_MASK)!=page_to_phys(owned[1]) ||
     (l2[(ROOT_VA>>14)&2047]&PA_MASK)!=page_to_phys(owned[2])) goto fail_root;
 pr_info("m4rch root-envelope: shadow walk passed, root=%#llx interface=%#llx host_allocations=0\n",
         ROOT_VA,get_unaligned_le64(page_address(owned[2])));
 if (!install) return 0;
 /* Exact reservation, disjoint from allocatable RAM. Fresh ADT must be checked
  * by the harness; module additionally requires the existing TEXT table path. */
 if (region_intersects(TABLE_BASE,TABLE_BYTES,IORESOURCE_SYSTEM_RAM,IORES_DESC_NONE)!=REGION_DISJOINT)
  goto fail_root;
 bootstrap=memremap(TABLE_BASE,PAGE_SIZE,MEMREMAP_WB);
 if (!bootstrap) {ret=-ENOMEM;goto fail_root;}
 if (READ_ONCE(bootstrap[0])!=((TABLE_BASE+PAGE_SIZE)|3ULL) ||
     READ_ONCE(bootstrap[(ROOT_VA>>36)&63])) {ret=-EBUSY;goto fail_root;}
 WRITE_ONCE(bootstrap[(ROOT_VA>>36)&63],page_to_phys(owned[0])|3);
 clean_page(bootstrap);invalidate_root_va();installed=true;
 if (READ_ONCE(bootstrap[(ROOT_VA>>36)&63])!=(page_to_phys(owned[0])|3)) {
  ret=-EIO;goto fail_root;
 }
 pr_info("m4rch root-envelope: installed previously-empty bootstrap slot %llu; existing slot0 unchanged\n",(ROOT_VA>>36)&63);
 return 0;
fail_root:
 root_release();return ret;
}
