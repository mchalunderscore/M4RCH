/* SPDX-License-Identifier: GPL-2.0-only */
/* Fresh one-shot native performance-map capture and qualified RAM writer.
 * No boot replay. All map/scratch resources are retained once PM owner is pinned. */
#include <linux/slab.h>
#include <linux/ktime.h>
#include <linux/bug.h>
#define GFX_FULL_POWER_MAP_BASE 0x288e00000ULL
#define GFX_FULL_POWER_MAP_SIZE 0x4000U
#define GFX_FULL_POWER_BYTES 0x6578U
#define GFX_FULL_HW_BYTES 0x2718U
#define GFX_FULL_REGION_BYTES 0xe58U
#define GFX_FULL_AON_BYTES 0xe4U
static bool gfx_full_power_snapshot_attempted,gfx_full_power_snapshot_valid;
static bool gfx_full_power_written;
static void __iomem *gfx_full_power_map;
static bool gfx_full_power_region;
static u32 gfx_full_power_maps[2][8];
static u64 gfx_full_power_ticks;
static u8 *gfx_full_power_scratch;
extern int m4rch_native_power_validate(const u32 *,const u32 *);
extern int m4rch_native_power_write(const u32 *,const u32 *,u64,u8 *,u8 *,u8 *,u8 *,u64,u64,u64);
void __noreturn m4rch_full_power_panic(void);
void __noreturn m4rch_full_power_panic(void) { BUG(); for (;;) cpu_relax(); }
/* Clock domain reader is joined by the clock-provider helper. */
static struct gfx_full_power_clock_snapshot gfx_full_power_clock;
static int gfx_full_power_snapshot(void)
{
 unsigned int table,i;int ret;
 if(gfx_full_power_snapshot_attempted || started || !held || !consumer || !asc || !mbox ||
    !gfx_coord_owner_session.on_complete || root_sent) return -EINVAL;
 gfx_full_power_snapshot_attempted=true;
 if(!request_mem_region(GFX_FULL_POWER_MAP_BASE,GFX_FULL_POWER_MAP_SIZE,"m4rch-native-perf-map")) return -EBUSY;
 gfx_full_power_region=true;
 gfx_full_power_map=ioremap(GFX_FULL_POWER_MAP_BASE,GFX_FULL_POWER_MAP_SIZE);
 if(!gfx_full_power_map) return -ENOMEM;
 gfx_full_power_scratch=kmalloc(GFX_FULL_POWER_BYTES+GFX_FULL_HW_BYTES+GFX_FULL_REGION_BYTES+GFX_FULL_AON_BYTES,GFP_KERNEL);
 if(!gfx_full_power_scratch) return -ENOMEM;
 for(table=0;table<2;table++) for(i=0;i<8;i++) {
  u32 value=readl(gfx_full_power_map+(table?0x1480:0x1400)+i*4);
  gfx_full_power_maps[table][i]=value;
  pr_info("m4rch full-power-map: table=%u index=%u value=%#x primary=%u secondary=%u before_ASC_START=1\n",table,i,value,value&15,(value>>16)&15);
 }
 ret=m4rch_native_power_validate(gfx_full_power_maps[0],gfx_full_power_maps[1]);
 if(ret) {pr_err("m4rch full-power-map: unsupported=1 before_ASC_START=1 result=%d\n",ret);return ret;}
 ret=gfx_full_power_ticks_snapshot(&gfx_full_power_clock);if(ret)return ret;
 gfx_full_power_ticks=gfx_full_power_clock.native_absolute_ticks;
 pr_info("m4rch full-power-clock: counter=%#llx frequency=%llu native_ticks=%#llx ns=%llu linux_epoch_policy=1\n",gfx_full_power_clock.raw_counter,gfx_full_power_clock.frequency_hz,gfx_full_power_ticks,gfx_full_power_clock.architectural_ns);
 gfx_full_power_snapshot_valid=true;
 return 0;
}
static void gfx_full_power_arena_copy(void *buffer,unsigned int offset,size_t bytes,bool to_arena)
{
 u8 *b=buffer;
 while(bytes) {
  size_t n=min_t(size_t,bytes,PAGE_SIZE-offset%PAGE_SIZE);
  void *p=(u8 *)page_address(owned[2+offset/PAGE_SIZE])+offset%PAGE_SIZE;
  if(to_arena)memcpy(p,b,n);else memcpy(b,p,n);
  b+=n;offset+=n;bytes-=n;
 }
}
static int gfx_full_power_graph_prepare(void)
{
 u8 *p=gfx_full_power_scratch,*h,*r,*a;int ret;
 if(!gfx_full_power_snapshot_valid || gfx_full_power_written || !p || root_sent) return -EINVAL;
 h=p+GFX_FULL_POWER_BYTES;r=h+GFX_FULL_HW_BYTES;a=r+GFX_FULL_REGION_BYTES;
 gfx_full_power_arena_copy(p,0x30000,GFX_FULL_POWER_BYTES,false);
 gfx_full_power_arena_copy(h,0x8000,GFX_FULL_HW_BYTES,false);
 gfx_full_power_arena_copy(r,0xc000,GFX_FULL_REGION_BYTES,false);
 memset(a,0,GFX_FULL_AON_BYTES);
 ret=m4rch_native_power_write(gfx_full_power_maps[0],gfx_full_power_maps[1],gfx_full_power_ticks,p,h,r,a,
   0xfffffc200014f000ULL,0xfffffc200012c000ULL,0xfffffc200014f100ULL);
 if(ret)return ret;
 gfx_full_power_arena_copy(p,0x30000,GFX_FULL_POWER_BYTES,true);
 gfx_full_power_arena_copy(h,0x8000,GFX_FULL_HW_BYTES,true);
 gfx_full_power_arena_copy(r,0xc000,GFX_FULL_REGION_BYTES,true);
 gfx_full_power_arena_copy(a,0x4f100,GFX_FULL_AON_BYTES,true);
 gfx_full_power_written=true;
 pr_info("m4rch full-power-init: completed=1 power_bytes=%#x hardware_bytes=%#x region_bytes=%#x aon_bytes=%#x tick=%#llx before_root_publication=1\n",
   GFX_FULL_POWER_BYTES,GFX_FULL_HW_BYTES,GFX_FULL_REGION_BYTES,GFX_FULL_AON_BYTES,gfx_full_power_ticks);
 return 0;
}

/* Retained immutable CPU snapshot; this read never touches GPU mappings. */
static bool gfx_full_power_initial_captured;
static void gfx_full_power_capture_initialized(void)
{
 if(!gfx_full_power_written || !gfx_full_power_scratch || gfx_full_power_initial_captured) return;
 /* Timestamp owner binds HW+28 after the native writer. */
 gfx_full_power_arena_copy(gfx_full_power_scratch+GFX_FULL_POWER_BYTES,0x8000,GFX_FULL_HW_BYTES,false);
 gfx_full_power_initial_captured=true;
}
static ssize_t gfx_full_power_initial_read(struct file *file,struct kobject *kobj,
 const struct bin_attribute *attr,char *buf,loff_t off,size_t count)
{
 size_t total=GFX_FULL_POWER_BYTES+GFX_FULL_HW_BYTES+GFX_FULL_REGION_BYTES+GFX_FULL_AON_BYTES;
 if(off<0)return -EINVAL;
 if(!gfx_full_power_initial_captured || !gfx_full_power_scratch)return -ENODATA;
 if(off>=total)return 0;
 count=min_t(size_t,count,total-off);memcpy(buf,gfx_full_power_scratch+off,count);return count;
}
static struct bin_attribute gfx_full_power_initial_raw={.attr={.name="full-power-initialized",.mode=0400},.read=gfx_full_power_initial_read,.size=GFX_FULL_POWER_BYTES+GFX_FULL_HW_BYTES+GFX_FULL_REGION_BYTES+GFX_FULL_AON_BYTES};
