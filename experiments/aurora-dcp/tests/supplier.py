#!/usr/bin/env python3
"""Exercise actual admission topology and supplier-readiness C against native DT."""
import argparse
from pathlib import Path
import subprocess
from desktop import block


def main(root,m1n1,out,live):
    work=out/'supplier-tests';work.mkdir(parents=True,exist_ok=True)
    topology=block((root/'drivers/soc/apple/j614s-display-boot.c').read_text(),'static int j614s_display_power_topology(')
    current=(root/'drivers/pmdomain/apple/pmp-report.c').read_text()
    original=(out/'pmp-report.c.before').read_text()
    prefix=r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libfdt.h>
#define EPROBE_DEFER 517
#define GFP_KERNEL 0
#define PMP_REPORT_READY 1
#define cpu_to_be32 cpu_to_fdt32
typedef uint8_t u8;typedef uint32_t __be32;typedef uint64_t u64;
struct device_node { char path[256];uint32_t phandle; };
struct property { char *name;void *value;int length; };
struct device { struct device_node *of_node;bool bound;void *data; };
struct platform_device { struct device dev; };
struct of_changeset { struct device_node *node;struct property *property; };
struct apple_pmp_report_offsets { unsigned status; };
struct apple_pmp_report { void *base;struct apple_pmp_report_offsets *offsets; };
static void *dt,*raw;static struct device_node nodes[32];static unsigned nn;
static int allocation=-1,stage_error,refs,locks,polls;static bool lockable=true;
static struct platform_device report_device;static u64 mmio[8];
static struct apple_pmp_report_offsets offsets={16};
static struct apple_pmp_report report={mmio,&offsets};
static struct property present;
static void *alloc(size_t n) { if(!allocation)return NULL;if(allocation>0)allocation--;return calloc(1,n); }
#define kzalloc(n,flags) alloc(n)
static char *kstrdup(const char *s,int flags) { char *p=alloc(strlen(s)+1);if(p)strcpy(p,s);return p; }
static void *kmemdup(const void *s,size_t n,int flags) { void *p=alloc(n);if(p)memcpy(p,s,n);return p; }
static int off(struct device_node *n) { return n?fdt_path_offset(dt,n->path):-1; }
static struct device_node *node(const char *path) {
 int x=fdt_path_offset(dt,path);if(x<0)return NULL;
 unsigned i;for(i=0;i<nn;i++)if(!strcmp(nodes[i].path,path))break;
 if(i==nn) { assert(nn<32);strcpy(nodes[nn++].path,path); }
 nodes[i].phandle=fdt_get_phandle(dt,x);return &nodes[i];
}
static struct device_node *of_find_node_by_path(const char *path) {return node(path);}
static struct device_node *of_parse_phandle(struct device_node *n,const char *name,int index) {
 int size;const fdt32_t *p=fdt_getprop(dt,off(n),name,&size);if(!p || size!=4 || index)return NULL;
 int x=fdt_node_offset_by_phandle(dt,fdt32_ld(p));if(x<0)return NULL;
 char path[256];assert(!fdt_get_path(dt,x,path,sizeof(path)));return node(path);
}
static bool of_device_is_available(struct device_node *n) {
 const char *s=fdt_getprop(dt,off(n),"status",NULL);return !s || !strcmp(s,"ok") || !strcmp(s,"okay");
}
static bool of_device_is_compatible(struct device_node *n,const char *c) { return n && !fdt_node_check_compatible(dt,off(n),c); }
static bool of_machine_is_compatible(const char *c) { return !fdt_node_check_compatible(dt,0,c); }
static void of_node_put(struct device_node *n) {}
static struct property *of_find_property(struct device_node *n,const char *name,int *length) { return fdt_getprop(dt,off(n),name,length)?&present:NULL; }
static int of_changeset_add_property(struct of_changeset *c,struct device_node *n,struct property *p) {
 if(stage_error)return stage_error;assert(!c->property);c->node=n;c->property=p;return 0;
}
static struct platform_device *of_find_device_by_node(struct device_node *n) {
 if(n!=report_device.dev.of_node)return NULL;refs++;return &report_device;
}
static bool device_trylock(struct device *d) { if(!lockable)return false;assert(!locks);locks++;return true; }
static void device_unlock(struct device *d) {assert(locks==1);locks--;}
static void put_device(struct device *d) {assert(refs>0);refs--;}
static bool device_is_bound(struct device *d) {return d->bound;}
static void *platform_get_drvdata(struct platform_device *p) {return p->dev.data;}
static u64 readq(void *p) {return *(u64 *)p;}
#define readq_poll_timeout(address,value,condition,delay,timeout) ({ polls++;value=readq(address);(condition)?0:-ETIMEDOUT; })
'''
    tests=r'''
static struct device *supplier(void) {static struct device d;d.of_node=node("/pmp@500700000");return &d;}
static void reset(void) {
 assert(!fdt_open_into(raw,dt,2<<20));nn=0;allocation=-1;stage_error=0;refs=locks=polls=0;lockable=true;
 report_device.dev=(struct device){node("/pmp-report@5003c0000"),true,&report};mmio[2]=1;
}
static int topology(bool apply) {
 struct of_changeset c={0};struct property *p=NULL;
 int ret=j614s_display_power_topology(node("/dcp@402e00000"),&c,&p);
 if(!ret && c.property) {
  assert(!of_parse_phandle(supplier()->of_node,"apple,pmp-report",0));
  if(apply)assert(!fdt_setprop(dt,off(c.node),p->name,p->value,p->length));
 }
 if(p){free(p->name);free(p->value);free(p);}return ret;
}
static int ready(unsigned timeout) {
 int ret=apple_pmp_report_wait_supplier_ready(supplier(),timeout);assert(!refs&&!locks);return ret;
}
static void set_string(const char *path,const char *name,const char *s) { assert(!fdt_setprop_string(dt,fdt_path_offset(dt,path),name,s)); }
int main(int argc,char **argv) {
 assert(argc==2);raw=malloc(2<<20);dt=malloc(2<<20);assert(raw&&dt);
 FILE *f=fopen(argv[1],"rb");assert(f);assert(fread(raw,1,2<<20,f)>40);fclose(f);reset();
 assert(ready(5000)==-ENODEV); /* The original native tree has no supplier/report link. */
 assert(!topology(true));assert(!ready(5000));assert(!topology(true));
 mmio[2]=2;assert(!ready(5000)); /* T6041's driver treats any nonzero status as running. */
 mmio[2]=0;assert(ready(5000)==-ETIMEDOUT);
 polls=0;assert(ready(0)==-EAGAIN && !polls);mmio[2]=1;assert(!ready(0)&&!polls);
 report_device.dev.bound=false;assert(ready(5000)==-EPROBE_DEFER);report_device.dev.bound=true;
 lockable=false;assert(ready(5000)==-EPROBE_DEFER);lockable=true;
 set_string("/pmp-report@5003c0000","compatible","apple,j613-25g83-pmp-report");assert(ready(5000)==-ENODEV);
 reset();set_string("/pmp-report@5003c0000","status","disabled");assert(topology(true)==-ENODEV);
 reset();set_string("/pmp-report@5003c0000","compatible","apple,t8132-pmp-v2-report");assert(topology(true)==-ENODEV);
 reset();set_string("/pmp@500700000","compatible","apple,t8132-pmp-v2");assert(topology(true)==-ENODEV);
 reset();__be32 wrong=cpu_to_fdt32(supplier()->of_node->phandle);
 assert(!fdt_setprop(dt,off(supplier()->of_node),"apple,pmp-report",&wrong,4));assert(topology(true)==-ENODEV);
 for(int i=0;i<3;i++) {reset();allocation=i;assert(topology(true)==-ENOMEM);assert(!of_parse_phandle(supplier()->of_node,"apple,pmp-report",0));}
 reset();stage_error=-ENOMEM;assert(topology(true)==-ENOMEM);assert(!of_parse_phandle(supplier()->of_node,"apple,pmp-report",0));
 reset();assert(!topology(false));assert(!of_parse_phandle(supplier()->of_node,"apple,pmp-report",0));
 /* Legacy boards keep their prior status rules. */
 reset();assert(!topology(true));set_string("/","compatible","apple,j713");
 set_string("/pmp@500700000","compatible","apple,t8132-pmp-v2");
 set_string("/pmp-report@5003c0000","compatible","apple,t8132-pmp-v2-report");
 mmio[2]=3;assert(!ready(5000));mmio[2]=2;assert(ready(5000)==-ETIMEDOUT);
 set_string("/","compatible","apple,j613");set_string("/pmp-report@5003c0000","compatible","apple,j613-25g83-pmp-report");
 mmio[2]=3;assert(ready(5000)==-ETIMEDOUT);mmio[2]=1;assert(!ready(5000));
 free(raw);free(dt);puts("Supplier production tests PASS: native DT topology/readiness, staged link, mismatch/allocation/timeout/removal guards, legacy status semantics");
}
'''
    lib=m1n1/'src/libfdt'
    for name,text in [('current',current),('original',original)]:
        source=work/(name+'.c');exe=work/name
        source.write_text(prefix+topology+'\n'+block(text,'int apple_pmp_report_wait_supplier_ready(')+'\n'+tests)
        subprocess.run(['clang','-g','-O1','-include','stdlib.h','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(lib),str(source),*map(str,sorted(lib.glob('*.c'))),'-o',str(exe)],check=True)
        if name=='current':subprocess.run([str(exe),str(live)],check=True)
        else:
            r=subprocess.run([str(exe),str(live)],capture_output=True)
            assert r.returncode!=0 and b'Assertion' in r.stderr
            print('Supplier negative control PASS: original readiness API rejects the correctly linked native report')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['root','m1n1','out','live']:p.add_argument(name,type=Path)
    a=p.parse_args();main(a.root,a.m1n1,a.out,a.live)
