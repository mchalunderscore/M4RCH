#!/usr/bin/env python3
"""Run the actual m1n1 DT address decoder against real candidate/live DTBs."""
import argparse
from pathlib import Path
import subprocess


def main(m1n1, uboot, output, trees):
    work = output / 'flat-root-tests'; work.mkdir(parents=True, exist_ok=True)
    header = (m1n1 / 'src/devicetree.h').read_text().replace('#include "types.h"',
        '#include <stdint.h>\ntypedef uint64_t u64;')
    (work / 'devicetree.h').write_text(header)
    lib = m1n1 / 'src/libfdt'
    link = work / 'libfdt'
    if link.is_symlink():
        link.unlink()
    link.symlink_to(lib, target_is_directory=True)
    source = (m1n1 / 'src/devicetree.c').read_text()
    (work / 'decoder.c').write_text(source)
    test = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "devicetree.h"
int main(int argc,char **argv) {
 void *dt=malloc(2<<20),*raw=malloc(2<<20);assert(dt&&raw);
 for(int n=1;n<argc;n++) {
  FILE *f=fopen(argv[n],"rb");assert(f);size_t len=fread(raw,1,2<<20,f);fclose(f);
  assert(len>40 && !fdt_open_into(raw,dt,2<<20));
  int dcp=fdt_path_offset(dt,"/iommu@402340000");assert(dcp>0);
  assert(dt_get_address(dt,dcp)==0x402340000ULL);
  int disp=fdt_path_offset(dt,"/iommu@402300000");assert(disp>0);
  assert(dt_get_address(dt,disp)==0x402300000ULL);
  int node=fdt_add_subnode(dt,0,"nested-test-bus");assert(node>0);
  int child=fdt_add_subnode(dt,node,"child");assert(child>0);
  u64 reg[]={cpu_to_fdt64(0x402340000ULL),cpu_to_fdt64(0x20000)};
  assert(!fdt_setprop(dt,child,"reg",reg,sizeof(reg)));
  child=fdt_path_offset(dt,"/nested-test-bus/child");assert(dt_get_address(dt,child)==0);
  node=fdt_path_offset(dt,"/nested-test-bus");assert(!fdt_setprop_empty(dt,node,"ranges"));
  child=fdt_path_offset(dt,"/nested-test-bus/child");assert(dt_get_address(dt,child)==0x402340000ULL);
  dcp=fdt_path_offset(dt,"/iommu@402340000");assert(!fdt_setprop(dt,dcp,"reg",reg,8));
  assert(dt_get_address(dt,dcp)==0);
  assert(!fdt_setprop_u32(dt,0,"#address-cells",1));
  disp=fdt_path_offset(dt,"/iommu@402300000");assert(dt_get_address(dt,disp)==0);
 }
 free(dt);free(raw);
 puts("Flat-root decoder PASS: actual control, template and r4 live DT; nested-bus behavior and malformed-cell refusals");
}
'''
    (work / 'test.c').write_text(test)
    flags = ['clang', '-g', '-O1', '-include', 'stdlib.h', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
             '-I' + str(work), '-I' + str(lib)]
    def build(source, exe):
        subprocess.run(flags + [str(source), str(work / 'test.c'), *map(str, sorted(lib.glob('*.c'))), '-o', str(exe)], check=True)
    exe = work / 'flat-root-test'; build(work / 'decoder.c', exe)
    subprocess.run([str(exe), *map(str, trees)], check=True)
    (work / 'decoder-before.c').write_bytes((output / 'devicetree.before.c').read_bytes())
    exe = work / 'flat-root-before'; build(work / 'decoder-before.c', exe)
    r = subprocess.run([str(exe), *map(str, trees)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert r.returncode != 0 and b'Assertion' in r.stderr
    print('Native-failure negative control PASS: the original decoder rejects the actual SID23 root address')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('m1n1', type=Path); p.add_argument('uboot', type=Path)
    p.add_argument('output', type=Path); p.add_argument('trees', type=Path, nargs='+')
    a = p.parse_args(); main(a.m1n1, a.uboot, a.output, a.trees)
