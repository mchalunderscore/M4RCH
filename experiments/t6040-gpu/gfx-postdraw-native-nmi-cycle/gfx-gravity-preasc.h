/* SPDX-License-Identifier: GPL-2.0-only */
/* Initial cold START only. Gravity g16.rs:300..303 writes these operands
 * before its first ASC START. That tree's normal T6040 startup is closed:
 * this is a source-derived experimental prefix, not a G16S boot claim.
 * Fender literal 6 deliberately overrides the whole register; the first
 * two writes preserve every bit other than setting bit0. No coverage/ACK
 * register is written. Resources and any partial writes remain retained.
 */
#ifndef GFX_POSTDRAW_NATIVE_NMI_CYCLE_TRIAL
#error Distinct postdraw native NMI cycle profile required
#endif
#include <linux/of_address.h>
#define GFX_GRAVITY_PREASC_CONTROL_BASE 0x289000000ULL
#define GFX_GRAVITY_PREASC_FENDER_BASE 0x288d04000ULL
#define GFX_GRAVITY_PREASC_MAP_BYTES 0x4000U
static bool gfx_gravity_preasc_intent,gfx_gravity_preasc_attempted;
static bool gfx_gravity_preasc_complete,gfx_gravity_preasc_unknown;
static bool gfx_gravity_preasc_region[2];
static void __iomem *gfx_gravity_preasc_io[2];
static struct platform_device *gfx_gravity_preasc_consumer;
static void __iomem *gfx_gravity_preasc_asc,*gfx_gravity_preasc_mbox;
static u32 gfx_gravity_preasc_control,gfx_gravity_preasc_status;
static u32 gfx_gravity_preasc_rx,gfx_gravity_preasc_gpu_id;
static u32 gfx_gravity_preasc_baseline[3];
static const u32 gfx_gravity_preasc_offsets[3]={0x1000104U,0x1000108U,0xd06030U};

static bool gfx_gravity_preasc_pm(void)
{
 return consumer && held && !started && asc && mbox && asc_region && mbox_region &&
  consumer==gfx_gravity_preasc_consumer && asc==gfx_gravity_preasc_asc &&
  mbox==gfx_gravity_preasc_mbox && gfx_coord_owner_retained() &&
  gfx_coord_owner_module_pinned && gfx_coord_owner_session.on_complete &&
  atomic_read(&consumer->dev.power.usage_count)==1 &&
  !READ_ONCE(consumer->dev.power.runtime_error) &&
  pm_runtime_enabled(&consumer->dev) && pm_runtime_active(&consumer->dev) &&
  !pm_runtime_suspended(&consumer->dev);
}

static void gfx_gravity_preasc_log(const char *phase,const char *condition,int result)
{
 pr_info("m4rch gfx-gravity-preasc: phase=%s result=%d refused_condition=%s complete=%u attempted=%u held=%u usage=%d active=%u start_clear=%u status=%#x rx_empty=%u gpu_id=%#x resources_owned=%u unknown=%u retained=1 restart_replay=0 operand_samples_atomic=0\n",
  phase,result,condition,gfx_gravity_preasc_complete,gfx_gravity_preasc_attempted,
  held,consumer?atomic_read(&consumer->dev.power.usage_count):-1,
  consumer?pm_runtime_active(&consumer->dev):false,
  !(gfx_gravity_preasc_control&START),gfx_gravity_preasc_status,
  !!(gfx_gravity_preasc_rx&EMPTY),gfx_gravity_preasc_gpu_id,
  gfx_gravity_preasc_region[0] && gfx_gravity_preasc_region[1] &&
   gfx_gravity_preasc_io[0] && gfx_gravity_preasc_io[1],gfx_gravity_preasc_unknown);
}

static int gfx_gravity_preasc_alias_check(void)
{
 struct device_node *node;
 struct resource resource;
 unsigned int index;
 for(node=of_find_all_nodes(NULL);node;node=of_find_all_nodes(node)) {
  if(!of_device_is_available(node)) continue;
  for(index=0;!of_address_to_resource(node,index,&resource);index++) {
   if(!(resource.flags&IORESOURCE_MEM)) continue;
   if((resource.start<GFX_GRAVITY_PREASC_CONTROL_BASE+GFX_GRAVITY_PREASC_MAP_BYTES &&
       resource.end>=GFX_GRAVITY_PREASC_CONTROL_BASE) ||
      (resource.start<GFX_GRAVITY_PREASC_FENDER_BASE+GFX_GRAVITY_PREASC_MAP_BYTES &&
       resource.end>=GFX_GRAVITY_PREASC_FENDER_BASE)) {
    pr_err("m4rch gfx-gravity-preasc-resource: alias=%pOF resource=%u start=%#llx end=%#llx result=%d retained=1\n",
     node,index,(unsigned long long)resource.start,(unsigned long long)resource.end,-EBUSY);
    of_node_put(node);
    return -EBUSY;
   }
  }
 }
 return 0;
}

/* All readl/writel operands below are in exclusively claimed, disjoint 16K
 * pages. In particular ID_VERSION at d04000 shares the Fender-owned page;
 * d04018 is a different chip-count word and is not used as GPU ID here.
 */
static int gfx_gravity_preasc(void)
{
 struct apple_pmgr_gfx_reset_observation physical;
 unsigned int index;
 int ret;
 const char *condition="none";
 void __iomem *operands[3];
 u32 before,requested,after;
 mutex_lock(&graph_io_lock);
 if(gfx_gravity_preasc_intent) {ret=-EALREADY;condition="one-shot";goto refused;}
 gfx_gravity_preasc_intent=true;
 gfx_gravity_preasc_consumer=consumer;
 gfx_gravity_preasc_asc=asc;
 gfx_gravity_preasc_mbox=mbox;
 gfx_gravity_preasc_log("intent","none",0);
 if(!of_machine_is_compatible("apple,j614s") ||
    !of_machine_is_compatible("apple,t6040")) {ret=-ENODEV;condition="board";goto refused;}
 if(!gfx_gravity_preasc_pm()) {ret=-EBUSY;condition="pm-identity";goto refused;}
 ret=gfx_cold_snapshot("gravity-preasc",0,&physical);
 if(ret) {condition="physical-observation";goto refused;}
 if(!(physical.valid&APPLE_PMGR_GFX_VALID_BEFORE) || !physical.domain_on ||
    (physical.before&0x80001cffU)!=0xffU) {ret=-EBUSY;condition="physical-on";goto refused;}
 gfx_gravity_preasc_control=readl(asc+0x44);
 gfx_gravity_preasc_status=readl(asc+0x48);
 gfx_gravity_preasc_rx=readl(mbox+0x114);
 if((gfx_gravity_preasc_control&START) || gfx_gravity_preasc_status!=0x6a ||
    !(gfx_gravity_preasc_rx&EMPTY)) {ret=-EBUSY;condition="cold-asc-fifo";goto refused;}
 ret=gfx_gravity_preasc_alias_check();
 if(ret) {condition="available-alias";goto refused;}
 if(!request_mem_region(GFX_GRAVITY_PREASC_CONTROL_BASE,GFX_GRAVITY_PREASC_MAP_BYTES,
                        "m4rch-gravity-preasc-control")) {ret=-EBUSY;condition="control-resource";goto refused;}
 gfx_gravity_preasc_region[0]=true;
 if(!request_mem_region(GFX_GRAVITY_PREASC_FENDER_BASE,GFX_GRAVITY_PREASC_MAP_BYTES,
                        "m4rch-gravity-preasc-fender")) {ret=-EBUSY;condition="fender-resource";goto refused;}
 gfx_gravity_preasc_region[1]=true;
 gfx_gravity_preasc_io[0]=ioremap(GFX_GRAVITY_PREASC_CONTROL_BASE,GFX_GRAVITY_PREASC_MAP_BYTES);
 gfx_gravity_preasc_io[1]=ioremap(GFX_GRAVITY_PREASC_FENDER_BASE,GFX_GRAVITY_PREASC_MAP_BYTES);
 if(!gfx_gravity_preasc_io[0] || !gfx_gravity_preasc_io[1]) {ret=-ENOMEM;condition="mapping";goto refused;}
 pr_info("m4rch gfx-gravity-preasc-resource: control_base=%#llx fender_base=%#llx bytes=%#x exclusive=1 retained=1 source_t6040_normal_startup=0\n",
  GFX_GRAVITY_PREASC_CONTROL_BASE,GFX_GRAVITY_PREASC_FENDER_BASE,GFX_GRAVITY_PREASC_MAP_BYTES);
 gfx_gravity_preasc_gpu_id=readl(gfx_gravity_preasc_io[1]);
 if(!gfx_gravity_preasc_gpu_id || gfx_gravity_preasc_gpu_id==~0U) {ret=-ENODEV;condition="gpu-id";goto refused;}
 operands[0]=gfx_gravity_preasc_io[0]+0x104;
 operands[1]=gfx_gravity_preasc_io[0]+0x108;
 operands[2]=gfx_gravity_preasc_io[1]+0x2030;
 for(index=0;index<3;index++) {
  gfx_gravity_preasc_baseline[index]=readl(operands[index]);
  pr_info("m4rch gfx-gravity-preasc-baseline: index=%u offset=%#x value=%#x valid=%u operand_samples_atomic=0\n",
   index,gfx_gravity_preasc_offsets[index],gfx_gravity_preasc_baseline[index],
   gfx_gravity_preasc_baseline[index]!=~0U);
 }
 for(index=0;index<3;index++)
  if(gfx_gravity_preasc_baseline[index]==~0U) {ret=-ENODATA;condition="baseline-invalid";goto refused;}
 for(index=0;index<3;index++) {
  if(!gfx_gravity_preasc_pm()) {ret=-EBUSY;condition="prewrite-pm-identity";goto refused;}
  before=readl(operands[index]);
  if(before==~0U) {ret=-ENODATA;condition="prewrite-invalid";goto refused;}
  requested=index<2?(before|1U):6U;
  gfx_gravity_preasc_attempted=true;
  writel(requested,operands[index]);
  after=readl(operands[index]);
  pr_info("m4rch gfx-gravity-preasc-op: index=%u offset=%#x baseline=%#x before=%#x requested=%#x after=%#x write_attempted=1 verified=%u policy=%s operand_samples_atomic=0\n",
   index,gfx_gravity_preasc_offsets[index],gfx_gravity_preasc_baseline[index],before,requested,after,
   after!=~0U && after==requested,index<2?"preserve-set-bit0":"literal-six");
  if(after==~0U || after!=requested) {ret=-EIO;condition="readback";goto refused;}
 }
 /* Ordered MMIO write/readback for every operand, then an ARM64 full system
  * barrier before the caller's first START, matching Gravity's mem::sync.
  */
 asm volatile("dsb sy" ::: "memory");
 gfx_gravity_preasc_complete=true;
 gfx_gravity_preasc_log("complete","none",0);
 mutex_unlock(&graph_io_lock);
 return 0;
refused:
 gfx_gravity_preasc_unknown=gfx_gravity_preasc_attempted && !gfx_gravity_preasc_complete;
 gfx_gravity_preasc_log("refused",condition,ret);
 mutex_unlock(&graph_io_lock);
 return ret;
}
