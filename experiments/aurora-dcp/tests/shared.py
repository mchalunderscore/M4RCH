#!/usr/bin/env python3
"""Regress the full register list, firmware replies and retention on r7's DT."""
import argparse
import json
from pathlib import Path
import subprocess
from desktop import block


def main(root,out,live):
    def get(node,prop):return subprocess.check_output(['fdtget','-t','x',str(live),node,prop],text=True).split()
    def strings(node,prop):return subprocess.check_output(['fdtget',str(live),node,prop],text=True).strip().split()
    cells=list(map(lambda v:int(v,16),get('/dcp@402e00000','reg')))
    regs=[((cells[i]<<32)|cells[i+1],(cells[i+2]<<32)|cells[i+3]) for i in range(0,len(cells),4)]
    names=strings('/dcp@402e00000','reg-names');assert len(regs)==len(names)==6
    scratch=list(map(lambda v:int(v,16),get('/dcp@402e00000','apple,bw-scratch')))
    provider='/power-management@504800000'
    assert scratch[0]==int(get(provider,'phandle')[0],16)
    cells=list(map(lambda v:int(v,16),get(provider,'reg')))
    base=(cells[0]<<32)|cells[1];size=(cells[2]<<32)|cells[3]
    assert regs[5]==(base,size) and scratch[1:]==[0,4,0x20000]
    assert {'apple,j614s','apple,t6040'}<=set(strings('/','compatible'))
    get('/dcp@402e00000','apple,j614s-inherited-mappings')
    prefix=r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint32_t u32;typedef uint64_t u64;typedef u64 dma_addr_t;
#define MAX_DISP_REGISTERS 8
#define IORESOURCE_MEM 0
#define DCP_FIRMWARE_V_26_6_DESKTOP 1
#define DCP_FIRMWARE_H17P 2
#define DCP_FIRMWARE_M4 3
#define DCP_IOMFB_METHODS_H17P_EXTERNAL 4
#define DCP_IOMFB_METHODS_H17G 5
#define THIS_MODULE NULL
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define dev_warn(...) ((void)0)
#define dev_err_probe(dev,error,...) (error)
#define WRITE_ONCE(x,v) ((x)=(v))
#define kzalloc_obj(x) (allocation_fail?NULL:calloc(1,sizeof(x)))
struct device_node {int unused;};
struct device {struct device_node *of_node;};
struct resource {u64 start,end;};
struct platform_device {struct device dev;int num_resources;struct resource r[8];};
struct of_phandle_args {struct device_node *np;int args_count;u32 args[3];};
struct apple_dcp_hw_data {bool adopt_live_session;unsigned iomfb_method_profile,firmware_display_windows,firmware_scratch,firmware_request;struct resource *firmware_clock;};
struct apple_dcp {struct device *dev;struct apple_dcp_hw_data hw;unsigned fw_compat,nr_disp_registers,disp_bw_scratch_index,disp_bw_scratch_offset,disp_bw_doorbell_index;struct resource *disp_registers[8],disp_bw_scratch_res,disp_bw_doorbell_res;bool retain_dma;};
struct dcp_session_ref {int link;struct device *dev;void *group;};
static int dcp_retained_sessions_lock,dcp_retained_sessions,refcount,groupcount,modulecount;
static struct dcp_session_ref *session;
static bool j614s=true,inherited=true,doorbell=false,allocation_fail=false;
static unsigned offset,args_count=3;
static struct device_node dcp_node,provider_node;
static struct platform_device pdev;
static struct resource provider;
static u32 scratch_index;
static const char *reg_names[]={"coproc","disp-0","disp-1","disp-2","disp-3","disp-4","disp-5","disp-6"};
static bool j614s_display_board(void) {return j614s;}
static bool of_property_read_bool(struct device_node *n,const char *p) {return inherited;}
static bool iomfb_is_m4(const struct apple_dcp *d) {return d->fw_compat==DCP_FIRMWARE_M4;}
static void mutex_lock(int *m) {}static void mutex_unlock(int *m) {}
static struct device *get_device(struct device *d) {refcount++;return d;}
static void *iommu_group_get(struct device *d) {groupcount++;return &groupcount;}
static void __module_get(void *m) {modulecount++;}
static void list_add_tail(int *p,int *h) {assert(!session);session=(struct dcp_session_ref *)p;}
static u64 resource_size(const struct resource *r) {return r->end-r->start+1;}
static bool of_property_present(struct device_node *n,const char *p) {return !strcmp(p,"reg-names") || (!strcmp(p,"apple,bw-doorbell")&&doorbell);}
static int of_property_count_strings(struct device_node *n,const char *p) {return pdev.num_resources;}
static int of_property_read_string_index(struct device_node *n,const char *p,int i,const char **s) {*s=reg_names[i];return 0;}
static struct platform_device *to_platform_device(struct device *d) {return &pdev;}
static struct resource *platform_get_resource(struct platform_device *p,int type,unsigned i) {return i<(unsigned)p->num_resources?&p->r[i]:NULL;}
static struct resource *platform_get_resource_byname(struct platform_device *p,int type,const char *name) {for(int i=0;i<p->num_resources;i++)if(!strcmp(name,reg_names[i]))return &p->r[i];return NULL;}
static int of_parse_phandle_with_args(struct device_node *n,const char *p,const char *cells,int index,struct of_phandle_args *a) {*a=(struct of_phandle_args){&provider_node,args_count,{0,scratch_index,offset}};return 0;}
static int of_address_to_resource(struct device_node *n,unsigned index,struct resource *r) {if(n!=&provider_node||index)return -EINVAL;*r=provider;return 0;}
static void of_node_put(struct device_node *n) {}
static bool apple_dcp_external_clock_window(u64 a,u64 b,u64 c,u64 d) {return a==c&&b==d;}
static int dcp_get_bw_doorbell_reg(struct apple_dcp *d,u32 expected) {return -EINVAL;}
#define DCP_FW_VERSION(a,b,c) ((a)*10000+(b)*100+(c))
#define DCP_FW_VER DCP_FW_VERSION(26,6,2)
#define DCP_FW_H17(x) 0
#define DCP_FW_DESKTOP_26(x) 1
#define DCP_FW_NAME(x) x
struct dcp_map_reg_req {u32 index;};
struct dcp_map_reg_resp {u64 addr,length,dva;u32 ret;};
'''
    fixture='static struct resource initial[]={'+','.join(f'{{0x{start:x}ULL,0x{start+length-1:x}ULL}}' for start,length in regs)+'};\n'
    fixture+=f'static const struct resource initial_provider={{0x{base:x}ULL,0x{base+size-1:x}ULL}};\n'
    tests=r'''
static struct apple_dcp fresh(void) {assert(!session);pdev.num_resources=6;memcpy(pdev.r,initial,sizeof(initial));pdev.dev.of_node=&dcp_node;provider=initial_provider;j614s=inherited=true;doorbell=allocation_fail=false;args_count=3;offset=0x20000;scratch_index=4;return (struct apple_dcp){.dev=&pdev.dev,.fw_compat=DCP_FIRMWARE_V_26_6_DESKTOP};}
int main(void) {
 struct apple_dcp d=fresh();assert(!dcp_get_disp_regs(&d));assert(d.nr_disp_registers==5 && d.disp_bw_scratch_index==4);
 assert(d.disp_bw_scratch_offset==0x20000 && !d.disp_registers[5]);
 for(int i=0;i<5;i++) {struct dcp_map_reg_req req={i};struct dcp_map_reg_resp r=dcpep_cb_map_reg(&d,&req);assert(!r.ret && r.addr==initial[i+1].start && r.dva==r.addr && r.length==resource_size(&initial[i+1]));assert(is_disp_register(&d,r.addr,r.addr+r.length-1));}
 struct dcp_map_reg_req bad={5};assert(dcpep_cb_map_reg(&d,&bad).ret);assert(!is_disp_register(&d,0xf000,0xffff));
 d=fresh();provider.start++;assert(dcp_get_disp_regs(&d)==-EINVAL);
 d=fresh();provider.end--;assert(dcp_get_disp_regs(&d)==-EINVAL);
 d=fresh();provider.end=provider.start+1;assert(dcp_get_disp_regs(&d)==-EINVAL);
 d=fresh();offset=resource_size(&provider);assert(dcp_get_disp_regs(&d)==-EINVAL);
 d=fresh();scratch_index=5;assert(dcp_get_disp_regs(&d)==-EINVAL);
 d=fresh();args_count=2;assert(dcp_get_disp_regs(&d)==-EINVAL);
 d=fresh();doorbell=true;assert(dcp_get_disp_regs(&d)==-EINVAL);
 d=fresh();pdev.num_resources=7;assert(dcp_get_disp_regs(&d)==-EINVAL);
 d=fresh();j614s=false;pdev.num_resources=5;assert(!dcp_get_disp_regs(&d)&&d.nr_disp_registers==5); /* J616s' original append path */
 d=fresh();dcp_j614s_adopt_hw(&d);assert(d.hw.adopt_live_session);assert(!dcp_pin_live_session(&d));assert(d.retain_dma&&refcount==1&&groupcount==1&&modulecount==1);assert(!dcp_pin_live_session(&d)&&modulecount==1);free(session);session=NULL;
 d=fresh();inherited=false;dcp_j614s_adopt_hw(&d);assert(!d.hw.adopt_live_session);assert(!dcp_pin_live_session(&d)&&!d.retain_dma);
 d=fresh();j614s=false;dcp_j614s_adopt_hw(&d);assert(!d.hw.adopt_live_session);assert(!dcp_pin_live_session(&d)&&!d.retain_dma);
 d=fresh();allocation_fail=true;assert(dcp_pin_live_session(&d)==-ENOMEM&&!d.retain_dma);
 d=fresh();d.fw_compat=DCP_FIRMWARE_H17P;d.hw.adopt_live_session=true;assert(!dcp_pin_live_session(&d)&&d.retain_dma);free(session);session=NULL;
 puts("Shared-window production tests PASS: native DT -> five exact firmware replies, alias/range/index guards, J616s append path, native adoption and retained-session guards");
}
'''
    current=(root/'drivers/gpu/drm/apple/dcp.c').read_text();old=(out/'dcp.before.c').read_text()
    internal=(root/'drivers/gpu/drm/apple/dcp-internal.h').read_text();template=(root/'drivers/gpu/drm/apple/iomfb_template.c').read_text()
    work=out/'shared-tests';work.mkdir(parents=True,exist_ok=True)
    for name,text in [('current',current),('original',old)]:
        body=prefix+fixture
        for marker in ['static bool dcp_j614s_desktop_live(','static void dcp_j614s_adopt_hw(']:body+=block(current,marker)+'\n'
        body+=block(internal,'static inline bool dcp_fail_stop(')+'\n'
        for marker in ['static int dcp_pin_live_session(','static int dcp_get_bw_scratch_reg(','static int dcp_get_disp_regs(']:body+=block(text,marker)+'\n'
        body+=block(template,'static bool is_disp_register(')+'\n'
        body+=block(template,'static struct DCP_FW_NAME(dcp_map_reg_resp) dcpep_cb_map_reg(')+'\n'+tests
        path=work/(name+'.c');path.write_text(body);exe=work/name
        subprocess.run(['clang','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(path),'-o',str(exe)],check=True)
        r=subprocess.run([str(exe)],capture_output=True)
        if name=='current':
            if r.returncode:raise RuntimeError(r.stderr.decode())
            print(r.stdout.decode(),end='')
        else:
            assert r.returncode and b'Assertion' in r.stderr
            print('Shared-window negative control PASS: original builder rejects the actual r7 register list')
    (out/'resource-audit.json').write_text(json.dumps({'native_dt':str(live),'physical_resources':list(zip(names,regs)),
        'bandwidth_provider':[base,size],'bandwidth_args':scratch[1:],'firmware_register_count':5,'duplicate_alias':'index4; exact range match'},indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['root','out','live']:p.add_argument(n,type=Path)
    a=p.parse_args();main(a.root,a.out,a.live)
