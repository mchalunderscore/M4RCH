#!/usr/bin/env python3
"""Run actual DRM framebuffer selection against the failed native boot's DT."""
import argparse
from pathlib import Path
import subprocess
from desktop import block


def main(root, m1n1, output, live):
    work = output / 'bootfb-tests'; work.mkdir(parents=True, exist_ok=True)
    source = (root / 'drivers/gpu/drm/apple/apple_drv.c').read_text()
    original = (output / 'apple_drv.before.c').read_text()
    prefix = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <libfdt.h>
typedef uint64_t u64;
struct device_node { int off; };
struct device { struct device_node *of_node; };
struct resource { u64 start,end; };
static void *dt;
static struct device_node iter;
#define dev_err(...) ((void)0)
static bool of_device_is_compatible(struct device_node *n,const char *c) { return !fdt_node_check_compatible(dt,n->off,c); }
static int of_property_match_string(struct device_node *n,const char *p,const char *s) { return fdt_stringlist_search(dt,n->off,p,s); }
static void of_node_put(struct device_node *n) {}
static struct device_node *next_compatible(int off,const char *c) {
 int x=fdt_node_offset_by_compatible(dt,off,c);if(x<0)return NULL;
 iter.off=x;return &iter;
}
#define for_each_compatible_node(n,type,compat) for(n=next_compatible(-1,compat);n;n=next_compatible(n->off,compat))
static bool of_device_is_available(struct device_node *n) {
 const char *s=fdt_getprop(dt,n->off,"status",NULL);return !s || !strcmp(s,"okay") || !strcmp(s,"ok");
}
static int of_address_to_resource(struct device_node *n,int index,struct resource *r) {
 int len;const fdt64_t *p=fdt_getprop(dt,n->off,"reg",&len);
 if(!p || len!=16)return -EINVAL;
 r->start=fdt64_ld(p);r->end=r->start+fdt64_ld(p+1)-1;return 0;
}
'''
    tests = r'''
int main(int argc,char **argv) {
 assert(argc==2);void *raw=malloc(2<<20);dt=malloc(2<<20);assert(raw&&dt);
 FILE *f=fopen(argv[1],"rb");assert(f);size_t len=fread(raw,1,2<<20,f);fclose(f);
 assert(len>40 && !fdt_open_into(raw,dt,2<<20));
 struct device_node display={fdt_path_offset(dt,"/display-subsystem")};assert(display.off>0);
 struct device dev={&display};struct resource r;
 assert(apple_boot_fb_only(&dev));assert(!apple_get_boot_fb_resource(&dev,&r));
 int fb=fdt_path_offset(dt,"/chosen/framebuffer");assert(fb>0);
 int reg_len;const fdt64_t *reg=fdt_getprop(dt,fb,"reg",&reg_len);assert(reg_len==16);
 assert(r.start==fdt64_ld(reg) && r.end-r.start+1==fdt64_ld(reg+1));
 assert(r.start && r.end>r.start);
 assert(!fdt_setprop_string(dt,fb,"status","disabled"));
 assert(apple_get_boot_fb_resource(&dev,&r)==-ENODEV);
 fb=fdt_path_offset(dt,"/chosen/framebuffer");assert(!fdt_setprop_string(dt,fb,"status","okay"));
 int chosen=fdt_path_offset(dt,"/chosen");int extra=fdt_add_subnode(dt,chosen,"duplicate-fb");assert(extra>0);
 assert(!fdt_setprop_string(dt,extra,"compatible","simple-framebuffer"));
 extra=fdt_path_offset(dt,"/chosen/duplicate-fb");u64 fake[]={cpu_to_fdt64(0x10000100000ULL),cpu_to_fdt64(0x10000)};
 assert(!fdt_setprop(dt,extra,"reg",fake,sizeof(fake)));
 assert(apple_get_boot_fb_resource(&dev,&r)==-EINVAL);
 extra=fdt_path_offset(dt,"/chosen/duplicate-fb");assert(!fdt_setprop_string(dt,extra,"status","disabled"));
 assert(!apple_get_boot_fb_resource(&dev,&r));
 display.off=fdt_path_offset(dt,"/display-subsystem");
 assert(!fdt_setprop_string(dt,display.off,"memory-region-names","framebuffer"));
 assert(!apple_boot_fb_only(&dev));
 display.off=fdt_path_offset(dt,"/display-subsystem");assert(!fdt_delprop(dt,display.off,"memory-region-names"));
 for(int i=0;i<2;i++) {
  display.off=fdt_path_offset(dt,"/display-subsystem");
  assert(!fdt_setprop_string(dt,display.off,"compatible",i?"apple,t6030-display-subsystem":"apple,t8132-display-subsystem"));
  assert(apple_boot_fb_only(&dev)==!i);
 }
 free(raw);free(dt);
 puts("Boot framebuffer PASS: real r5 aperture, disabled/duplicate refusal, reserved-memory preference and J713/legacy selection");
}
'''
    lib = m1n1 / 'src/libfdt'
    flags = ['clang', '-g', '-O1', '-include', 'stdlib.h', '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I'+str(lib)]
    for name, code in [('current', source), ('original', original)]:
        unit = work / (name + '.c')
        unit.write_text(prefix + block(code, 'static bool apple_boot_fb_only(') + '\n' +
                        block(code, 'static int apple_get_boot_fb_resource(') + '\n' + tests)
        exe = work / name
        subprocess.run(flags+[str(unit),*map(str,sorted(lib.glob('*.c'))),'-o',str(exe)],check=True)
        if name == 'current':
            subprocess.run([str(exe), str(live)], check=True)
        else:
            r = subprocess.run([str(exe),str(live)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            assert r.returncode != 0 and b'Assertion' in r.stderr
            print('Boot framebuffer negative control PASS: original selector rejects the actual T6041 live tree')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path);p.add_argument('m1n1',type=Path);p.add_argument('output',type=Path);p.add_argument('live',type=Path)
    a=p.parse_args();main(a.root,a.m1n1,a.output,a.live)
