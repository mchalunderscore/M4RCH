#define AURORA_HOST_TEST
#include "../aurora-direct/board_handoff.c"
#include "aop_standard_handoff.c"
#include <assert.h>
#include <stdlib.h>
static void *load(const char *name) {
    FILE *f = fopen(name,"rb"); assert(f); void *p=calloc(1,2<<20); assert(p);
    assert(fread(p,1,2<<20,f)>0); fclose(f); assert(!fdt_open_into(p,p,2<<20)); return p;
}
int main(int argc,char **argv) {
    assert(argc==2);
    for (int scenario=0;scenario<4;scenario++) {
        void *live=load(argv[1]),*out=load(argv[1]);
        int aop=find_compatible(live,"apple,t6041-aop");u32 dev=fdt_get_phandle(live,aop),h;
        fdt32_t refs[3];
        assert(!asc_region(live,"fixture-code",dev,0x100009f0000ULL,0x10000000000ULL,0x18000,&h));refs[0]=cpu_to_fdt32(h);
        assert(!asc_region(live,"fixture-log",dev,0x1000cb6c000ULL,0x1000cb6c000ULL,0x30000,&h));refs[1]=cpu_to_fdt32(h);
        int count=2;
        if (scenario==1) { assert(!asc_region(live,"fixture-cal",dev,0x10001b9c000ULL,0x10000020000ULL,0x4000,&h));refs[count++]=cpu_to_fdt32(h); }
        aop=find_compatible(live,"apple,t6041-aop");
        assert(!fdt_setprop(live,aop,"memory-region",refs,count*4));
        int parent=fdt_path_offset(live,"/reserved-memory"),n;
        fdt_for_each_subnode(n,live,parent) {
            const char *name=fdt_get_name(live,n,NULL);
            if (!strncmp(name,"fixture-",8)) assert(!copy_tree(out,fdt_path_offset(out,"/reserved-memory"),live,n,0));
        }
        assert(!fdt_setprop_u32(out,find_compatible(out,"apple,t6041-aop"),"phandle",0x123456));
        if(scenario==3) { int node=fdt_node_offset_by_phandle(live,fdt32_ld(refs));assert(!fdt_setprop_u32(live,node,"iommu-addresses",0)); }
        int result=aop_standard_handoff(out,live,scenario==2?0:3);
        if(scenario>=2) assert(result<0);
        else {
            assert(!result);int len;const fdt32_t *r=fdt_getprop(out,find_compatible(out,"apple,t6041-aop"),"memory-region",&len);assert(r && len==8);
            for(int i=0;i<2;i++) { int node=fdt_node_offset_by_phandle(out,fdt32_ld(r+i));const fdt32_t *map=fdt_getprop(out,node,"iommu-addresses",&len);assert(map && len==20 && fdt32_ld(map)==0x123456); }
            int spkr=find_compatible(out,"apple,j616-macaudio");assert(!strcmp(fdt_getprop(out,spkr,"status",NULL),"disabled"));
            if(scenario==1) { int node=fdt_path_offset(out,"/reserved-memory/fixture-cal");assert(node>=0 && !fdt_getprop(out,node,"iommu-addresses",NULL)); }
        }
        free(live);free(out);
    }
    puts("PASS: same-boot code/log transfer, phandle rebasing, SRAM and DRAM calibration, speaker exclusion, malformed mapping and DAPF refusal");
}
