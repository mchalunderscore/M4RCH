// SPDX-License-Identifier: GPL-2.0-only OR MIT
#define AURORA_HOST_TEST
#include "board_handoff.c"
#include <assert.h>
#include <stdlib.h>

static void *load(const char *name) {
    FILE *f=fopen(name,"rb"); assert(f);
    void *buffer=calloc(1,2<<20); assert(buffer);
    assert(fread(buffer,1,2<<20,f)>0); assert(!ferror(f)); fclose(f);
    assert(!fdt_open_into(buffer,buffer,2<<20)); return buffer;
}
static const char *aliases[]={"dcp","disp0","disp0_piodma"};
static void setup(void *live) {
    for(int i=0;i<3;i++) {
        int n=fdt_path_offset(live,fdt_get_alias(live,aliases[i])); assert(n>=0);
        assert(!fdt_setprop_u32(live,n,"phandle",0x800+i));
        n=fdt_path_offset(live,fdt_get_alias(live,aliases[i]));
        assert(!fdt_setprop_empty(live,n,"apple,j614s-inherited-mappings"));
    }
    fdt32_t refs[8];
    for(int i=0;i<8;i++) {
        char path[100],name[60]; snprintf(name,sizeof(name),"dcp-test-%d",i);
        int root=fdt_path_offset(live,"/reserved-memory"); assert(root>=0);
        int n=fdt_add_subnode(live,root,name); assert(n>=0);
        snprintf(path,sizeof(path),"/reserved-memory/%s",name);
        assert(!fdt_setprop_string(live,n,"compatible","apple,asc-mem"));
        n=fdt_path_offset(live,path); assert(!fdt_setprop_empty(live,n,"no-map"));
        n=fdt_path_offset(live,path); assert(!fdt_setprop_u32(live,n,"phandle",0x900+i));
        fdt64_t reg[]={cpu_to_fdt64(0x10000000000ULL+i*0x4000),cpu_to_fdt64(0x4000)};
        n=fdt_path_offset(live,path); assert(!fdt_setprop(live,n,"reg",reg,sizeof(reg)));
        fdt32_t maps[15]; int count=0;
        for(int owner=0;owner<3;owner++) {
            if(i==2 || (owner==1 && i!=3 && i!=6) || (owner==2 && i!=5)) continue;
            maps[count++]=cpu_to_fdt32(0x800+owner);
            maps[count++]=cpu_to_fdt32(0x100); maps[count++]=cpu_to_fdt32(0x100000+i*0x4000);
            maps[count++]=0; maps[count++]=cpu_to_fdt32(0x4000);
        }
        n=fdt_path_offset(live,path);
        if(count) assert(!fdt_setprop(live,n,"iommu-addresses",maps,count*4));
        else assert(!fdt_setprop_empty(live,n,"apple,dcp-os-log"));
        refs[i]=cpu_to_fdt32(0x900+i);
    }
    for(int i=0;i<3;i++) {
        int n=fdt_path_offset(live,fdt_get_alias(live,aliases[i]));
        fdt32_t display[]={refs[3],refs[6]},pio[]={refs[5]};
        assert(!fdt_setprop(live,n,"memory-region",i==0?refs:i==1?display:pio,i==0?32:i==1?8:4));
    }
    int n=fdt_path_offset(live,fdt_get_alias(live,"dcp"));
    assert(!fdt_setprop_string(live,n,"apple,firmware-uuid","6CC9349E-D30B-33FB-B12B-8D6D38F9F1B3"));
    n=fdt_path_offset(live,fdt_get_alias(live,"dcp"));
    assert(!fdt_setprop_string(live,n,"apple,firmware-version","26.6.2"));
    n=fdt_path_offset(live,fdt_get_alias(live,"dcp"));
    assert(!fdt_setprop_string(live,n,"apple,firmware-compat","26.6.2"));
    n=fdt_path_offset(live,"/chosen"); assert(!fdt_setprop_string(live,n,"m4rch,dcp-handoff","DCP001-v1"));
    n=fdt_path_offset(live,"/chosen"); assert(!fdt_setprop_string(live,n,"m4rch,dcp-summary","stage=complete result=0"));
}
static void copy_metadata(void *out,void *live) {
    int n=fdt_path_offset(live,"/chosen"); assert(!copy_tree(out,0,live,n,0));
    n=fdt_path_offset(live,"/reserved-memory");
    assert(!copy_tree(out,0,live,n,0));
}
int main(int argc,char **argv) {
    assert(argc==3); void *live=load(argv[1]),*out=load(argv[2]); setup(live); copy_metadata(out,live);
    assert(!dcp_handoff(out,live));
    int chosen=fdt_path_offset(out,"/chosen");
    assert(!strcmp(fdt_getprop(out,chosen,"m4rch,dcp-summary",NULL),"stage=complete result=0"));
    assert(strstr(fdt_getprop(out,chosen,"m4rch,dcp-bridge-summary",NULL),"result=0 line=0"));
    for(int a=0;a<3;a++) {
        int n=fdt_path_offset(out,fdt_get_alias(out,aliases[a])),len;
        const fdt32_t *refs=fdt_getprop(out,n,"memory-region",&len); assert(refs&&len==(a==0?32:a==1?8:4));
        for(int i=0;i<len/4;i++) {
            u32 ph=fdt32_ld(refs+i); assert(ph<0x800); n=fdt_node_offset_by_phandle(out,ph); assert(n>=0);
            int bytes; const fdt32_t *maps=fdt_getprop(out,n,"iommu-addresses",&bytes);
            if(!maps) { assert(fdt_getprop(out,n,"apple,dcp-os-log",NULL)); continue; }
            for(int j=0;j<bytes/4;j+=5) {
                int owner=fdt_node_offset_by_phandle(out,fdt32_ld(maps+j)); assert(owner>=0);
                assert(fdt32_ld(maps+j)<0x800); int matched=0;
                for(int k=0;k<3;k++) matched|=owner==fdt_path_offset(out,fdt_get_alias(out,aliases[k]));
                assert(matched);
            }
        }
    }
    const char *devices[]={"/iommu@402300000","/iommu@402340000","/mailbox@402e08000","/dcp@402e00000","/display-subsystem"};
    for(int i=0;i<5;i++) assert(!strcmp(fdt_getprop(out,fdt_path_offset(out,devices[i]),"status",NULL),"disabled"));
    int n=fdt_path_offset(live,"/reserved-memory/dcp-test-0");
    fdt32_t bad[]={cpu_to_fdt32(0xdead),0,0,0,cpu_to_fdt32(0x4000)};
    assert(!fdt_setprop(live,n,"iommu-addresses",bad,sizeof(bad)));
    assert(dcp_handoff(out,live)<0);
    chosen=fdt_path_offset(out,"/chosen");
    assert(dcp_bridge_line>0);
    assert(strstr(fdt_getprop(out,chosen,"m4rch,dcp-bridge-summary",NULL),"result=-1"));
    assert(!strcmp(fdt_getprop(out,chosen,"m4rch,dcp-summary",NULL),"stage=complete result=0"));
    puts("DCP handoff: disjoint-tree memory/IOVA references, OS-log and disabled hardware PASS; foreign owner rejected");
    free(out); free(live); return 0;
}
