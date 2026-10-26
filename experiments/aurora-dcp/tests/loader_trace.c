/* Host regression: production loader header, actual serialized FDT, mocked ADT/MMIO. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libfdt.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;
#define SZ_16K 0x4000ULL
#define BIT(x) (1ULL << (x))
#define GENMASK(h,l) (((1ULL << ((h)+1))-1)&~((1ULL<<(l))-1))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define ALIGN_UP(v,a) (((v)+(a)-1)&~((a)-1))
#define T6040 0x6040
#define V26_6_2 2662
static void *dt; static int dt_bufsize=2<<20; static void *adt;
static u32 chip_id,board_id;
static struct {int version;const char *string;} os_firmware;
static struct {u64 phys_base,mem_size;} cur_boot_args;
struct adt_segment_ranges {u64 phys,iova,remap;u32 size,unk;};
static struct adt_segment_ranges segments[8];
static u64 dram_base,dram_size,regions[3][2];
static u32 tcr[3],ttbr[3],enabled[3];
static int bad_uuid,bad_count,protect=1,wrong_translation,fail_firmware,fail_reserve,fail_maps;
static int adt_path_offset(void *a,const char *p) {return strstr(p,"iop-dcp")?1:2;}
static int adt_path_offset_trace(void *a,const char *p,int *t) {t[0]=strstr(p,"dart-dcp")?1:0;return t[0]+3;}
static int adt_is_compatible(void *a,int n,const char *c) {return !strcmp(c,"dart,t8110");}
static int adt_get_reg(void *a,int *trace,const char *p,int index,u64 *base,u64 *size) {*base=trace[0]?0x402340000:0x402300000;*size=0xc000;return 0;}
static const void *adt_getprop(void *a,int n,const char *p,u32 *len) {
 if(!strcmp(p,"uuid")) {if(bad_uuid==2)return NULL;*len=37;return bad_uuid?"00000000-0000-0000-0000-000000000000":"6CC9349E-D30B-33FB-B12B-8D6D38F9F1B3";}
 assert(!strcmp(p,"segment-ranges"));if(bad_count==2)return NULL;*len=sizeof(segments)-(bad_count?32:0);return segments;
}
static int adt_getprop_copy(void *a,int n,const char *p,void *out,size_t len) {
 const void *v;
 if(!strcmp(p,"dram-base")) v=&dram_base;
 else if(!strcmp(p,"dram-size")) v=&dram_size;
 else v=regions[!strcmp(p,"pt-region-0")?0:!strcmp(p,"pt-region-16")?1:2];
 memcpy(out,v,len);return len;
}
#define ADT_GETPROP(a,n,p,v) adt_getprop_copy(a,n,p,v,sizeof(*(v)))
#define ADT_GETPROP_ARRAY(a,n,p,v) adt_getprop_copy(a,n,p,v,sizeof(v))
static u32 read32(u64 addr) {
 if(addr==0x402300200 || addr==0x402340200)return protect;
 for(int i=0;i<3;i++) {
  u64 base=i==2?0x402340000:0x402300000;int sid=i==0?0:i==1?16:23;
  if(addr==base+0x1000+4*sid)return tcr[i];
  if(addr==base+0x1400+4*sid)return ttbr[i];
  if(addr==base+0xc00)return enabled[i==2?2:0];
 }
 assert(!"unexpected register read");return 0;
}
static void dart_lock_adt(const char *p,int n) {}
typedef int dart_dev_t;
static dart_dev_t dart;
static dart_dev_t *dt_init_dart_by_node(int node,int sid) {return &dart;}
static void *dart_translate_silent(dart_dev_t *d,u64 iova) {
 for(int i=0;i<8;i++) if(iova>=segments[i].remap && iova<segments[i].remap+segments[i].size)
  return (void *)(uintptr_t)(segments[i].phys+iova-segments[i].remap+(wrong_translation?0x4000:0));
 assert(!"unrecognized IOVA");return 0;
}
static void dart_shutdown(dart_dev_t *d) {}
static int dt_set_dcp_firmware(const char *p) {
 int node=fdt_path_offset(dt,"dcp");assert(node>=0);
 assert(!fdt_setprop_string(dt,node,"test-firmware","written"));return fail_firmware?-1:0;
}
static int dt_reserve_asc_firmware(const char *p,const char *x,const char *alias,bool remap,int v) {
 int node=fdt_path_offset(dt,"dcp");assert(!fdt_setprop_string(dt,node,"test-reservation","written"));return fail_reserve?-1:0;
}
static int dt_set_m4_display_maps(const struct adt_segment_ranges *s,unsigned count,u64 base,u64 size) {
 assert(count==8);return fail_maps?-1:0;
}
#include "j614s-dcp.h"
static const char *prop(const char *name) {return fdt_getprop(dt,fdt_path_offset(dt,"/chosen"),name,0);}
static void setup(void) {
 assert(!fdt_create_empty_tree(dt,dt_bufsize));
 assert(fdt_add_subnode(dt,0,"chosen")>=0);assert(fdt_add_subnode(dt,0,"aliases")>=0);
 assert(fdt_add_subnode(dt,0,"dcp")>=0);
 assert(!fdt_setprop_string(dt,fdt_path_offset(dt,"/aliases"),"dcp","/dcp"));
 assert(!fdt_setprop_string(dt,0,"compatible","apple,j614s"));
 assert(!fdt_setprop_string(dt,fdt_path_offset(dt,"dcp"),"compatible","apple,t6041-dcp"));
 chip_id=T6040;board_id=4;os_firmware.version=V26_6_2;os_firmware.string="26.6.2";
 dram_base=0x10000000000;dram_size=0x600000000;cur_boot_args.phys_base=dram_base+0x100000;
 cur_boot_args.mem_size=0x100000;bad_uuid=bad_count=wrong_translation=fail_firmware=fail_reserve=fail_maps=0;protect=1;
 for(int i=0;i<8;i++)segments[i]=(struct adt_segment_ranges){.phys=dram_base+0x300000+i*0x4000,.remap=dram_base+0x400000+i*0x4000,.size=0x4000,.unk=i==0?1:i==1?0:i==2?10:2};
 for(int i=0;i<3;i++) {
  regions[i][0]=dram_base+0x500000+i*0x8000;regions[i][1]=regions[i][0]+0x8000;
  tcr[i]=5;ttbr[i]=(regions[i][0]>>14)<<2|1;enabled[i]=BIT(0)|BIT(16)|BIT(23);
 }
 j614s_dcp_line=j614s_dcp_segment_bytes=j614s_dcp_segments_saved=j614s_dcp_uuid_bytes=0;
 memset(j614s_dcp_uuid,0,sizeof(j614s_dcp_uuid));memset(j614s_dcp_dart_state,0,sizeof(j614s_dcp_dart_state));
}
static void refused(const char *stage,bool rollback) {
 int ret=dt_set_j614s_dcp_handoff();assert(ret<0 && j614s_dcp_line && !strcmp(j614s_dcp_stage,stage));
 assert(!fdt_getprop(dt,fdt_path_offset(dt,"/chosen"),"m4rch,dcp-handoff",0));
 if(rollback) assert(!fdt_getprop(dt,fdt_path_offset(dt,"dcp"),"test-firmware",0));
 assert(!j614s_dcp_publish_trace(ret));assert(!strcmp(prop("m4rch,dcp-stage"),stage));
 assert(strstr(prop("m4rch,dcp-summary"),"result=-1"));
 assert(fdt32_to_cpu(*(fdt32_t *)prop("m4rch,dcp-refusal-line"))==j614s_dcp_line);
}
int main(void) {
 dt=malloc(dt_bufsize);assert(dt);
 setup();assert(!dt_set_j614s_dcp_handoff());assert(!j614s_dcp_publish_trace(0));assert(!strcmp(prop("m4rch,dcp-stage"),"complete"));
 assert(!strcmp(prop("m4rch,dcp-handoff"),"DCP001-v1"));
 setup();board_id=9;refused("board-firmware-identity",false);
 setup();bad_uuid=1;refused("firmware-uuid",false);assert(strstr(prop("m4rch,dcp-observed-uuid"),"00000000"));
 setup();bad_uuid=2;refused("firmware-uuid",false);assert(j614s_dcp_uuid_bytes==0);
 setup();bad_count=1;refused("segment-count",false);
 setup();bad_count=2;refused("segment-count",false);assert(j614s_dcp_segment_bytes==0);
 setup();dram_size=0;refused("dram-range",false);
 setup();segments[3].unk=7;refused("segment-layout",false);
 setup();regions[0][1]=regions[0][0];refused("dart-sid0-region",false);
 setup();tcr[1]=2;refused("dart-sid16-registers",false);assert(strstr(prop("m4rch,dcp-dart-1"),"tcr=2"));
 setup();ttbr[2]=0;refused("dart-sid23-registers",false);
 setup();enabled[0]=0;refused("dart-sid0-registers",false);
 setup();protect=0;refused("dart-protection",false);
 setup();wrong_translation=1;refused("sid23-firmware-mappings",false);
 setup();fail_firmware=1;refused("dt-firmware-version",true);
 setup();fail_reserve=1;refused("dt-firmware-reservations",true);
 setup();fail_maps=1;refused("dt-display-mappings",true);
 setup();for(int i=0;i<3;i++)ttbr[i]|=0xc0000000;assert(!dt_set_j614s_dcp_handoff());
 free(dt);puts("Loader trace PASS: complete handoff, 16 refusal paths, DT rollback preserves evidence, exact T8110 TTBR address mask");return 0;
}
