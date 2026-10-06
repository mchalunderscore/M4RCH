#!/usr/bin/env python3
"""Exercise the actual patched kernel formatter with synthetic MMIO, never hardware."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
args = parser.parse_args()
text = args.source.read_text()
body = text[text.index('static unsigned int apple_cpufreq_snapshot_khz'):text.index('DEFINE_SHOW_ATTRIBUTE(apple_cpufreq_snapshot);')]
shim = r'''
#include <stdio.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
typedef unsigned long long u64;
typedef unsigned int u32;
struct cpufreq_frequency_table { unsigned int driver_data, frequency, flags; };
struct cpufreq_policy { unsigned int cpu, cur; struct cpufreq_frequency_table *freq_table; };
struct apple_soc_cpufreq_info { bool has_ps2; u64 max_pstate, cur_pstate_mask, cur_pstate_shift, ps1_mask, ps1_shift; };
struct mask { char list[16]; };
struct apple_cpu_priv { struct cpufreq_policy *policy; struct apple_soc_cpufreq_info *info; char *reg_base; struct mask init_cpus; const char *compatible; };
struct seq_file { void *private; };
#define cpufreq_for_each_valid_entry(p,t) for(p=(t);p->frequency;p++)
#define cpumask_pr_args(m) (int)strlen((m)->list), (m)->list
#define READ_ONCE(x) (x)
#define FIELD_GET(m,x) ((x)&(m))
#define APPLE_DVFS_CMD 0x20
#define APPLE_DVFS_STATUS 0x50
#define APPLE_DVFS_CMD_PS1 31
#define APPLE_DVFS_CMD_BUSY (1ULL<<31)
#define APPLE_DVFS_CMD_SET (1ULL<<25)
static u64 clock_ns;
static char regs[128];
static unsigned reads;
static u64 ktime_get_boottime_ns(void) { return ++clock_ns*10; }
static u64 readq(const void *p) { u64 v; if(p!=regs+32) abort(); reads++; memcpy(&v,p,8); return v; }
static u32 readl(const void *p) { u32 v; if(p!=regs+80) abort(); reads++; memcpy(&v,p,4); return v; }
static void seq_printf(struct seq_file *s,const char *fmt,...) {
 char copy[4096]; const char *special=strstr(fmt,"%*pbl");
 if(special) {size_t n=special-fmt; memcpy(copy,fmt,n); strcpy(copy+n,"%.*s"); strcat(copy,special+5); fmt=copy;}
 va_list ap; va_start(ap,fmt); vprintf(fmt,ap); va_end(ap); (void)s;
}
static void seq_puts(struct seq_file *s,const char *text) { fputs(text,stdout); (void)s; }
'''
main = r'''
int main(int argc,char **argv) {
 int kind=argc>1?atoi(argv[1]):0;
 struct cpufreq_frequency_table table[]={{14,3924000,0},{19,4512000,0},{0,0,0}};
 struct cpufreq_policy policy={0,4512000,table};
 struct apple_soc_cpufreq_info info={false,31,0x3e0,5,31,0};
 struct apple_cpu_priv priv={&policy,&info,regs,{"0,5-7"},"apple,t8112-cluster-cpufreq"};
 struct seq_file seq={&priv};
 u64 cmd=(1ULL<<25)|19; u32 status=14<<5;
 if(kind==1)status=19<<5;
 if(kind==2)status=31<<5;
 if(kind==3){info.cur_pstate_mask=0;info.cur_pstate_shift=0;priv.compatible="apple,cluster-cpufreq";}
 if(kind==4)cmd|=1ULL<<31;
 if(kind==5)cmd&=~(1ULL<<25);
 memcpy(regs+32,&cmd,8);memcpy(regs+80,&status,4);
 char original[128];memcpy(original,regs,sizeof(regs));
 apple_cpufreq_snapshot_show(&seq,NULL);
 return memcmp(original,regs,sizeof(regs)) || reads!=(kind==3?1U:2U);
}
'''
spec = importlib.util.spec_from_file_location('capture', Path(__file__).with_name('collect.py'))
capture = importlib.util.module_from_spec(spec); spec.loader.exec_module(capture)
with tempfile.TemporaryDirectory(prefix='m4rch-cpufreq-format-') as work:
    c, binary = Path(work)/'check.c', Path(work)/'check'
    c.write_text(shim+body+main)
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(c),'-o',str(binary)],check=True)
    for kind in range(6):
        raw = subprocess.check_output([str(binary), str(kind)],text=True)
        analysis = capture.analyze(raw)
        if kind == 0: assert (analysis['command_khz'],analysis['get_rate_khz']) == (4512000,3924000)
        if kind == 1: assert analysis['get_rate_khz'] == 4512000
        if kind == 2: assert analysis['mapping_missing']
        if kind == 3: assert not json.loads(raw)['status']['available']
        if kind == 4: assert analysis['busy']
print('Six actual-formatter cases passed; only existing apertures read, synthetic MMIO unchanged.')
