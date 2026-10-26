/* SPDX-License-Identifier: GPL-2.0-only */
/* Cold integrated INIT trial: publish one owned context, retain until reboot.
 * No work doorbell is issued. This is not a general context allocator. */
static int joined_context_attach(void)
{
 const u64 base=0x288d08000ULL, table_pa=0x105fffb8000ULL;
 u64 entry=page_to_phys(owned[DEVICE_TABLE_FIRST])|((u64)STAGED_CONTEXT<<48)|1;
 void __iomem *mmu;u64 *table;unsigned int i;int ret=-EINVAL;
 if (region_intersects(table_pa,PAGE_SIZE,IORESOURCE_SYSTEM_RAM,IORES_DESC_NONE)!=REGION_DISJOINT) return -ENODEV;
 if (!request_mem_region(base,PAGE_SIZE,"m4rch-joined-init")) return -EBUSY;
 mmu=ioremap(base,PAGE_SIZE);if(!mmu){ret=-ENOMEM;goto region;}
 if(readl(mmu)!=1 || readl(mmu+0x2c)!=(table_pa>>14) ||
    readl(mmu+0x14)!=0x3680d8 || readl(mmu+0x18)!=0x3680d8) goto mmio;
 table=memremap(table_pa,PAGE_SIZE,MEMREMAP_WB);if(!table){ret=-ENOMEM;goto mmio;}
 for(i=0;i<PAGE_SIZE;i+=16) asm volatile("dc ivac, %0" :: "r"((unsigned long)table+i) : "memory");
 asm volatile("dsb sy" ::: "memory");
 for(i=0;i<PAGE_SIZE/sizeof(u64);i++) if(READ_ONCE(table[i])) {ret=-EBUSY;goto unmap;}
 /* Pin the entire graph before publishing any physical root reference. */
 device_context_retained=true;
 WRITE_ONCE(table[STAGED_CONTEXT*2],entry);clean_page(table);
 for(i=0;i<PAGE_SIZE;i+=16) asm volatile("dc ivac, %0" :: "r"((unsigned long)table+i) : "memory");
 asm volatile("dsb sy" ::: "memory");
 if(READ_ONCE(table[STAGED_CONTEXT*2])!=entry || READ_ONCE(table[STAGED_CONTEXT*2+1])) {ret=-EIO;goto unmap;}
 pr_info("m4rch joined-init: live context=%u ttbr0=%#llx root=%#llx table=%#llx retained_until_reboot=1 jobs_enqueued=0\n",STAGED_CONTEXT,entry,page_to_phys(owned[DEVICE_TABLE_FIRST]),table_pa);
 ret=0;
unmap: memunmap(table);
mmio: iounmap(mmu);
region: release_mem_region(base,PAGE_SIZE);return ret;
}
