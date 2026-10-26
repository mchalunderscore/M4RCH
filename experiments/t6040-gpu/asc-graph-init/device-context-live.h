/* SPDX-License-Identifier: GPL-2.0-only */
/* One reserved-table context trial; harness holds existing GFX genpd. */
static void context_cpu_invalidate(void *page)
{
 unsigned long pos;
 for (pos=(unsigned long)page;pos<(unsigned long)page+PAGE_SIZE;pos+=16)
  asm volatile("dc ivac, %0" :: "r"(pos) : "memory");
 asm volatile("dsb sy" ::: "memory");
}
static int device_context_trial(void)
{
 const u64 mmu_base=0x288d08000ULL,table_base=0x105fffb8000ULL;
 void __iomem *mmu=NULL,*core=NULL;
 u64 *table=NULL,entry=page_to_phys(owned[DEVICE_TABLE_FIRST])|((u64)STAGED_CONTEXT<<48)|1;
 u32 config14,config18,control,status,readback;
 unsigned int i;
 int ret=-EINVAL;
 bool mmu_region=false,core_region=false,inserted=false,restored=false;
 if (region_intersects(table_base,PAGE_SIZE,IORESOURCE_SYSTEM_RAM,IORES_DESC_NONE)!=REGION_DISJOINT) return -ENODEV;
 if (!request_mem_region(mmu_base,PAGE_SIZE,"m4rch-context-trial")) return -EBUSY;
 mmu_region=true;mmu=ioremap(mmu_base,PAGE_SIZE);if (!mmu) {ret=-ENOMEM;goto done;}
 if (!request_mem_region(ASC_BASE,0x1000,"m4rch-context-trial")) {ret=-EBUSY;goto done;}
 core_region=true;core=ioremap(ASC_BASE,0x1000);if (!core) {ret=-ENOMEM;goto done;}
 control=readl(core+0x44);status=readl(core+0x48);
 pr_info("m4rch live-context: ASC control=%#x status=%#x\n",control,status);
 if ((control&START) || (status!=0x6a && status!=0x6e) || readl(mmu)!=1 ||
     readl(mmu+0x2c)!=(table_base>>14)) {ret=-EBUSY;goto done;}
 config14=readl(mmu+0x14);config18=readl(mmu+0x18);
 if (config14!=0x3680d8 || config18!=0x3680d8) {ret=-EINVAL;goto done;}
 table=memremap(table_base,PAGE_SIZE,MEMREMAP_WB);if (!table) {ret=-ENOMEM;goto done;}
 context_cpu_invalidate(table);
 for (i=0;i<PAGE_SIZE/sizeof(u64);i++) if (READ_ONCE(table[i])) {ret=-EBUSY;goto done;}
 WRITE_ONCE(table[STAGED_CONTEXT*2],entry);WRITE_ONCE(table[STAGED_CONTEXT*2+1],0);
 clean_page(table);inserted=true;context_cpu_invalidate(table);
 if (READ_ONCE(table[STAGED_CONTEXT*2])!=entry || READ_ONCE(table[STAGED_CONTEXT*2+1])) {ret=-EIO;goto remove;}
 pr_info("m4rch live-context: inserted context=%u ttbr0=%#llx root_pa=%#llx table_pa=%#llx firmware_start=0\n",
         STAGED_CONTEXT,entry,page_to_phys(owned[DEVICE_TABLE_FIRST]),table_base);
 ret=0;
remove:
 /* Never overwrite a context that no longer contains our exact pair. */
 if (READ_ONCE(table[STAGED_CONTEXT*2])!=entry || READ_ONCE(table[STAGED_CONTEXT*2+1])) {
  device_context_retained=true;ret=-EIO;goto done;
 }
 WRITE_ONCE(table[STAGED_CONTEXT*2],entry&~1ULL);clean_page(table);
 asm volatile("dmb ish" ::: "memory");
 writel(STAGED_CONTEXT<<8,mmu+0x30);readback=readl(mmu+0x30);
 WRITE_ONCE(table[STAGED_CONTEXT*2],0);WRITE_ONCE(table[STAGED_CONTEXT*2+1],0);
 clean_page(table);context_cpu_invalidate(table);
 restored=true;
 for (i=0;i<PAGE_SIZE/sizeof(u64);i++) if (READ_ONCE(table[i])) restored=false;
 if (!restored) {device_context_retained=true;ret=-EIO;goto done;}
 if (readl(mmu)!=1 || readl(mmu+0x2c)!=(table_base>>14) ||
     readl(mmu+0x14)!=config14 || readl(mmu+0x18)!=config18) ret=-EIO;
 pr_info("m4rch live-context: removed context=%u invalidate=%#x readback=%#x table_zero=1 configuration_preserved=%u firmware_start=0\n",
         STAGED_CONTEXT,STAGED_CONTEXT<<8,readback,ret==0);
done:
 if (inserted && !restored) device_context_retained=true;
 if (table) memunmap(table);
 if (core) iounmap(core);
 if (core_region) release_mem_region(ASC_BASE,0x1000);
 if (mmu) iounmap(mmu);
 if (mmu_region) release_mem_region(mmu_base,PAGE_SIZE);
 return ret;
}
