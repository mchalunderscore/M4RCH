/* SPDX-License-Identifier: GPL-2.0-only */
/* Experimental structural graph mapping: firmware may write qualified device pages.
 * Gate 1 allocates and walks owned shadow tables only. Gate 2 may publish one
 * previously empty bootstrap root entry after the cold firmware boot handshake.
 */
#include <linux/unaligned.h>
#include "graph-contract.h"
#define ROOT_VA 0xfffffc2000100000ULL
#define TABLE_BASE 0x105fff78000ULL
#define TABLE_BYTES 0x40000
#define PA_MASK (GENMASK_ULL(41,14))
#define FW_MMIO_RO (BIT_ULL(55) | BIT_ULL(10) | BIT_ULL(6) | 4ULL | 3ULL)
#define FW_MMIO_RW (FW_MMIO_RO | BIT_ULL(54))
#define FW_GRAPH_RW (BIT_ULL(55) | BIT_ULL(54) | BIT_ULL(10) | BIT_ULL(6) | 8ULL | 3ULL)
#ifdef GRAPH_COMMAND_POOL_EXPERIMENT
#include "job-data.h"
#ifdef GRAPH_RENDER_BACKING_EXPERIMENT
#include "render-data.h"
#define EXTRA_OWNED_PAGES (POOL_PAGES + 6 + RENDER_EXTRA_PAGES)
#else
#define EXTRA_OWNED_PAGES (POOL_PAGES + 6)
#endif
#define EFFECTIVE_MAPPED_PAGES (GRAPH_MAPPED_PAGES + POOL_PAGES + 2)
#else
#define EXTRA_OWNED_PAGES 0
#define EFFECTIVE_MAPPED_PAGES GRAPH_MAPPED_PAGES
#endif
static struct page *owned[ARENA_OBJECT_PAGES + 2 + EXTRA_OWNED_PAGES]; /* Generated candidate backing plus two tables. */
static u64 *bootstrap, *borrowed_l1, *target_page, *target_slot;
static bool installed, root_sent, root_detached;
static bool device_context_retained;
#ifdef GRAPH_COMMAND_POOL_EXPERIMENT
#include "command-pool-map.h"
#endif

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
 unsigned int i;
 for (i=0;i<ARENA_OBJECT_PAGES+ARRAY_SIZE(mmio_leaves);i++) {
  u64 va=i<ARENA_OBJECT_PAGES?owned_page_vas[i]:mmio_leaves[i-ARENA_OBJECT_PAGES].gpu_va;
  u64 operand=(va>>12)&0x00000ffffffffffcULL;
  asm volatile(".arch armv8.4-a\n\ttlbi vaae1os, %0" :: "r"(operand) : "memory");
 }
#ifdef GRAPH_COMMAND_POOL_EXPERIMENT
 for (i=0;i<POOL_PAGES+2;i++) {
  u64 va=FW_BASE+(u64)i*PAGE_SIZE;
  u64 operand=(va>>12)&0x00000ffffffffffcULL;
  asm volatile(".arch armv8.4-a\n\ttlbi vaae1os, %0" :: "r"(operand) : "memory");
 }
#endif
 asm volatile("dsb sy" ::: "memory");
}
/* Only called after RTKit quiesce/sleep ACKs, core stop and an empty FIFO.
 * Keep physical backing for the post-stop snapshot; free on ordinary unload.
 */
static bool root_detach_after_shutdown(void)
{
 u64 expected;
 if (!root_sent || !installed || !target_slot || !target_page) return false;
 expected=page_to_phys(owned[borrowed_l1?1:0])|3;
 if (READ_ONCE(*target_slot)!=expected) return false;
 WRITE_ONCE(*target_slot,0);
 clean_page(target_page);invalidate_root_va();
 if (READ_ONCE(*target_slot)) return false;
 installed=false;root_detached=true;
 pr_info("m4rch graph-init: acknowledged shutdown; owned root detached; %u VAs invalidated; backing retained for snapshot\n",EFFECTIVE_MAPPED_PAGES);
 return true;
}
static void root_release(void)
{
 unsigned int i;
 /* Published backing is releasable only after the acknowledged detach path. */
 if (device_context_retained || (root_sent && !root_detached)) return;
 if (installed) {
  WRITE_ONCE(*target_slot,0);
  clean_page(target_page);
  invalidate_root_va();
  installed=false;
  pr_info("m4rch graph-init: child slot restored; all %u VAs invalidated\n",EFFECTIVE_MAPPED_PAGES);
 }
 if (borrowed_l1) {memunmap(borrowed_l1);borrowed_l1=NULL;}
 target_page=NULL;target_slot=NULL;
 if (bootstrap) {memunmap(bootstrap);bootstrap=NULL;}
 for (i=0;i<ARRAY_SIZE(owned);i++)
  if (owned[i]) {__free_pages(owned[i],0);owned[i]=NULL;}
 pr_info("m4rch graph-init: owned backing released; published=%d detached=%d\n",root_sent,root_detached);
}
static int root_prepare(bool install)
{
 u64 *l1,*l2;
 unsigned int i;
 int ret=-EINVAL;
 if (PAGE_SIZE!=0x4000 || ARENA_OBJECT_PAGES==0 ||
     ARRAY_SIZE(owned_page_vas)!=ARENA_OBJECT_PAGES || owned_page_vas[0]!=ROOT_VA || GRAPH_MAPPED_PAGES!=ARENA_OBJECT_PAGES+ARRAY_SIZE(mmio_leaves)) return -EINVAL;
 for (i=0;i<ARRAY_SIZE(owned);i++) {
  u64 pa;
  owned[i]=alloc_pages(GFP_KERNEL|__GFP_ZERO,0);
  if (!owned[i]) {ret=-ENOMEM;goto fail_root;}
  pa=page_to_phys(owned[i]);
  if (pa&~PA_MASK) goto fail_root;
  pr_info("m4rch graph-init: owned page %u physical=%#llx\n",i,pa);
 }
 l1=page_address(owned[0]);l2=page_address(owned[1]);
 l1[(ROOT_VA>>25)&2047]=page_to_phys(owned[1])|3;
 for (i=0;i<ARENA_OBJECT_PAGES;i++) {
  u64 va=owned_page_vas[i];
  if ((va&(PAGE_SIZE-1)) || (va>>25)!=(ROOT_VA>>25) || l2[(va>>14)&2047]) goto fail_root;
  l2[(va>>14)&2047]=page_to_phys(owned[2+i])|FW_GRAPH_RW;
  memcpy(page_address(owned[2+i]),graph_bytes+i*PAGE_SIZE,PAGE_SIZE);
 }
 for (i=0;i<ARRAY_SIZE(mmio_leaves);i++) {
  u64 pa=mmio_leaves[i].physical,va=mmio_leaves[i].gpu_va;
  bool platform=(pa==0x502414000ULL && va==0xfffffc2001a00000ULL) ||
                (pa==0x5003d8000ULL && va==0xfffffc2001b18000ULL);
  bool afr=pa>=0x28b000000ULL && pa<0x28b640000ULL &&
           ((pa-0x28b000000ULL)%0x200000ULL)<0x40000ULL &&
           va==0xfffffc2001c00000ULL+((pa-0x28b000000ULL)/0x200000ULL)*0x40000ULL+((pa-0x28b000000ULL)%0x200000ULL);
  bool sgx=pa>=0x288000000ULL && pa+PAGE_SIZE<=0x28b758000ULL &&
           va==GRAPH_MMIO_BASE+(pa-0x288000000ULL);
  if ((pa&~PA_MASK) || (va&(PAGE_SIZE-1)) || (!sgx && !platform && !afr) || (platform && !mmio_leaves[i].writable) ||
      (va>>25)!=(ROOT_VA>>25) || l2[(va>>14)&2047] ||
      ((i>0) && va<=mmio_leaves[i-1].gpu_va) ||
      region_intersects(pa,PAGE_SIZE,IORESOURCE_SYSTEM_RAM,IORES_DESC_NONE)!=REGION_DISJOINT)
   goto fail_root;
  if (afr && mmio_leaves[i].writable && ((pa-0x28b000000ULL)%0x10000ULL)) goto fail_root;
  if (mmio_leaves[i].writable && pa!=0x288000000ULL && pa!=0x288004000ULL && pa!=0x288008000ULL && pa!=0x28800c000ULL && pa!=0x288010000ULL && pa!=0x288014000ULL && pa!=0x288018000ULL && pa!=0x28801c000ULL && pa!=0x288020000ULL && pa!=0x288d04000ULL && pa!=0x288d10000ULL &&
      pa!=0x288d40000ULL && pa!=0x288d44000ULL && pa!=0x288d4c000ULL &&
      pa!=0x288e00000ULL && pa!=0x288e1c000ULL && pa!=0x288e40000ULL && pa!=0x289004000ULL && !platform && !afr) goto fail_root;
  l2[((va>>14)&2047)]=pa|(mmio_leaves[i].writable?FW_MMIO_RW:FW_MMIO_RO);
 }
 /* Explicit structural fixture, including allocations-enabled root and all
  * known pointer edges. Opaque contents are zero; this is not a render graph. */
 if (get_unaligned_le64(page_address(owned[2]))!=0x0c8aa322039604c0ULL ||
     get_unaligned_le32((u8 *)page_address(owned[2])+0x2c)!=1)
  goto fail_root;
#ifdef GRAPH_COMMAND_POOL_EXPERIMENT
 if (!command_pool_prepare(l2)) goto fail_root;
#endif
 for (i=0;i<ARRAY_SIZE(owned);i++) clean_page(page_address(owned[i]));
 if ((l1[(ROOT_VA>>25)&2047]&PA_MASK)!=page_to_phys(owned[1])) goto fail_root;
 for (i=0;i<ARENA_OBJECT_PAGES;i++)
  if ((l2[(owned_page_vas[i]>>14)&2047]&PA_MASK)!=page_to_phys(owned[2+i])) goto fail_root;
 for (i=0;i<ARRAY_SIZE(mmio_leaves);i++)
  if (l2[(mmio_leaves[i].gpu_va>>14)&2047]!=(mmio_leaves[i].physical|(mmio_leaves[i].writable?FW_MMIO_RW:FW_MMIO_RO)))
   goto fail_root;
 pr_info("m4rch graph-init: %zu device leaves prepared; total mapped pages=%u\n",ARRAY_SIZE(mmio_leaves),EFFECTIVE_MAPPED_PAGES);
 pr_info("m4rch graph-init: shadow walk passed, root=%#llx interface=%#llx host_allocations=1\n",
         ROOT_VA,get_unaligned_le64(page_address(owned[2])));
 if (!install) return 0;
 /* Exact reservation, disjoint from allocatable RAM. Fresh ADT must be checked
  * by the harness; module additionally requires the existing TEXT table path. */
 if (region_intersects(TABLE_BASE,TABLE_BYTES,IORESOURCE_SYSTEM_RAM,IORES_DESC_NONE)!=REGION_DISJOINT)
  goto fail_root;
 bootstrap=memremap(TABLE_BASE,TABLE_BYTES,MEMREMAP_WB);
 if (!bootstrap) {ret=-ENOMEM;goto fail_root;}
 /* Validate the full boot TEXT/DATA path, not just the first pointer. */
 if (((READ_ONCE(bootstrap[PAGE_SIZE/8])^((TABLE_BASE+2*PAGE_SIZE)|3ULL))&~BIT_ULL(10)) ||
     (READ_ONCE(bootstrap[2*PAGE_SIZE/8])&3)!=3 ||
     (READ_ONCE(bootstrap[2*PAGE_SIZE/8+24])&3)!=3 ||
     (READ_ONCE(bootstrap[2*PAGE_SIZE/8])&PA_MASK)!=0x10000be4000ULL ||
     (READ_ONCE(bootstrap[2*PAGE_SIZE/8+24])&PA_MASK)!=FW_DATA_BASE) {
  pr_err("m4rch graph-init: firmware TEXT/DATA table path refused\n");
  ret=-EINVAL;goto fail_root;
 }
 if (((READ_ONCE(bootstrap[0])^((TABLE_BASE+PAGE_SIZE)|3ULL))&~BIT_ULL(10))) {
  ret=-EBUSY;goto fail_root;
 }
 if (!READ_ONCE(bootstrap[(ROOT_VA>>36)&63])) {
  target_page=bootstrap;target_slot=&bootstrap[(ROOT_VA>>36)&63];
  WRITE_ONCE(*target_slot,page_to_phys(owned[0])|3);
 } else {
  /* Native cold ON installs this descriptor to the separate loader L2 page.
   * Preserve it exactly and borrow only a currently empty child slot. */
  if (READ_ONCE(bootstrap[(ROOT_VA>>36)&63])!=0x200105fff744cbULL ||
      region_intersects(0x105fff74000ULL,PAGE_SIZE,IORESOURCE_SYSTEM_RAM,IORES_DESC_NONE)!=REGION_DISJOINT) {
   ret=-EBUSY;goto fail_root;
  }
  borrowed_l1=memremap(0x105fff74000ULL,PAGE_SIZE,MEMREMAP_WB);
  if (!borrowed_l1) {ret=-ENOMEM;goto fail_root;}
  for (i=0;i<PAGE_SIZE/8;i++)
   if (READ_ONCE(borrowed_l1[i])) {ret=-EBUSY;goto fail_root;}
  target_page=borrowed_l1;target_slot=&borrowed_l1[(ROOT_VA>>25)&2047];
  WRITE_ONCE(*target_slot,page_to_phys(owned[1])|3);
 }
 installed=true;clean_page(target_page);invalidate_root_va();
 if (READ_ONCE(*target_slot)!=((borrowed_l1?page_to_phys(owned[1]):page_to_phys(owned[0]))|3)) {
  ret=-EIO;goto fail_root;
 }
 pr_info("m4rch graph-init: %u object pages mapped; structural fixture ready; borrowed_L1=%d; firmware root descriptors preserved\n",ARENA_OBJECT_PAGES,!!borrowed_l1);
 return 0;
fail_root:
 root_release();return ret;
}
