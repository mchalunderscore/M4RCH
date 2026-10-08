/* SPDX-License-Identifier: GPL-2.0-only */
#define RENDER_FIRST_PAGE (GPTBAT_PAGE + 1)
#define RENDER_TABLE_FIRST (RENDER_FIRST_PAGE + RENDER_BACKING_PAGES)
static bool pool_prepare_render(void)
{
 u64 *root=page_address(owned[DEVICE_TABLE_FIRST]);
 unsigned int i,region;
 const unsigned int starts[]={0,20,21},counts[]={20,1,1};
 const u64 flags=0x00e0000000000c0bULL; /* Candidate; GPU visibility unproved. */
 if (ARRAY_SIZE(render_vas)!=RENDER_BACKING_PAGES || RENDER_EXTRA_PAGES!=RENDER_BACKING_PAGES+6) return false;
 for (region=0;region<3;region++) {
  u64 va=render_vas[starts[region]];
  u64 *l1=page_address(owned[RENDER_TABLE_FIRST+region*2]);
  u64 *l2=page_address(owned[RENDER_TABLE_FIRST+region*2+1]);
  if (root[(va>>36)&63]) return false;
  root[(va>>36)&63]=page_to_phys(owned[RENDER_TABLE_FIRST+region*2])|3;
  l1[(va>>25)&2047]=page_to_phys(owned[RENDER_TABLE_FIRST+region*2+1])|3;
  for (i=starts[region];i<starts[region]+counts[region];i++) {
   u64 addr=render_vas[i],pa=page_to_phys(owned[RENDER_FIRST_PAGE+i]);
   void *cpu=page_address(owned[RENDER_FIRST_PAGE+i]);
   if ((addr&(PAGE_SIZE-1)) || (addr>>36)!=(va>>36) || (addr>>25)!=(va>>25) || l2[(addr>>14)&2047]) return false;
   l2[(addr>>14)&2047]=pa|flags;
   memcpy(cpu,render_bytes+i*PAGE_SIZE,PAGE_SIZE);
   if (root[(addr>>36)&63]!=(page_to_phys(owned[RENDER_TABLE_FIRST+region*2])|3) ||
       l1[(addr>>25)&2047]!=(page_to_phys(owned[RENDER_TABLE_FIRST+region*2+1])|3) ||
       l2[(addr>>14)&2047]!=(pa|flags) || memcmp(cpu,render_bytes+i*PAGE_SIZE,PAGE_SIZE)) return false;
   pr_info("m4rch render-backing: page=%u va=%#llx physical=%#llx bytes=%lu root_index=%llu publication=0\n",
           i,addr,pa,PAGE_SIZE,(addr>>36)&63);
  }
 }
 pr_info("m4rch render-backing: PASS data_pages=%u table_pages=6 regions=3 byte_comparisons=%zu context=%u publication=0\n",
         RENDER_BACKING_PAGES,sizeof(render_bytes),STAGED_CONTEXT);
 return true;
}
