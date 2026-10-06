#!/usr/bin/env python3
from pathlib import Path
import sys, tempfile, subprocess, struct, json, argparse
p=argparse.ArgumentParser();p.add_argument('--loader',type=Path,required=True);p.add_argument('--adt',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args()
r=Path(__file__).resolve().parents[2];sys.path.insert(0,str(r/'experiments/t6040-gpu'));import adt,contract
src=(a.loader/'src/kboot_gpu.c').read_text()
func=src[src.index('static int dt_set_gpu_t6040_clusters'):src.index('/* Metadata only:')]
node=adt.parse(a.adt.read_bytes())['/device-tree/arm-io/sgx']
count=int.from_bytes(node['perf-state-count'],'little');tables=int.from_bytes(node['perf-state-table-count'],'little')
arrays=''
for name,prop in [('cores','perf-states'),('srams','perf-states-sram')]:
 arrays+='static const struct perf_state '+name+'[] = {'+','.join('{%d,%d}'%x for x in struct.iter_unpack('<II',node[prop]))+'};\n'
head='''#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32; typedef uint32_t fdt32_t;
#define MAX_PSTATES 16
#define bail(...) do { fprintf(stderr,__VA_ARGS__); return -1; } while(0)
#define cpu_to_fdt32(v) __builtin_bswap32(v)
struct perf_state {u32 freq,volt;};
'''
head+=arrays
head+='''static int getprop(const char *name,u32 *v) { *v = !strcmp(name,"perf-state-count") ? 16 : 2; return 0; }
#define ADT_GETPROP(a,b,c,d) getprop(c,d)
static void *adt;
static const void *adt_getprop(void *a,int b,const char *p,u32 *len) { (void)a;(void)b;*len=sizeof(cores);return !strcmp(p,"perf-states")?cores:srams; }
static int fdt_path_offset(void *dt,const char *s) {(void)dt;(void)s;return 1;}
static int fdt_setprop_u32(void *dt,int n,const char *s,u32 v) {(void)dt;(void)n;printf("%s %u\\n",s,v);return 0;}
static int fdt_setprop(void *dt,int n,const char *s,const void *p,int len) {(void)dt;(void)n;printf("%s",s);for(int i=0;i<len/4;i++)printf(" %u",__builtin_bswap32(((const u32 *)p)[i]));puts("");return 0;}
'''
assert count==16 and tables==2
with tempfile.TemporaryDirectory() as tmp:
 c=Path(tmp)/'check.c';exe=Path(tmp)/'check';c.write_text(head+func+'int main(void) {return dt_set_gpu_t6040_clusters(0,0);}\n')
 subprocess.run(['cc','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
 output=subprocess.check_output([str(exe)],text=True)
rows={line.split()[0]:list(map(int,line.split()[1:])) for line in output.splitlines()}
core=contract.tables(node['perf-states'],count,tables);sram=contract.tables(node['perf-states-sram'],count,tables)
expected=[];counts=[]
for c,s in zip(core,sram):
 ladder=contract.ladder(c,s);counts.append(len(ladder))
 for step in ladder:expected.extend([step[k] for k in ['frequency_low_mhz','frequency_high_mhz','index_low','index_high','core_voltage_raw','sram_voltage_raw']])
assert rows['m4rch,cluster-group-counts']==counts
assert rows['m4rch,cluster-steps']==expected
assert rows['m4rch,cluster-metadata-version']==[1]
receipt={'method':'Execute the exact C loader metadata function with captured ADT rows and host FDT property sink; compare all output cells to independent Python ladder decoder','groups':counts,'cells_compared':len(expected),'passed':True,'loader_installed':False,'gpu_started':False}
if a.output:a.output.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
