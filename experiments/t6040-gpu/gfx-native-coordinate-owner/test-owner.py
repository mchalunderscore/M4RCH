#!/usr/bin/env python3
"""RAM/stub qualification of the actual adapter and guarded transformations."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

PREFIX=r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
typedef uint64_t u64;
typedef uint32_t u32;
#define __iomem
#define GFX_NATIVE_COORDINATED_SCOPE_TRIAL 1
#define GFX_POWER_OFF_SCOPE_TRIAL 1
#define GFX_RESET_SCOPE_TRIAL 1
#define IORESOURCE_MEM 1
#define THIS_MODULE ((void *)1)
#define READ_ONCE(x) (x)
#define BIT(n) (1U<<(n))
#define APPLE_PMGR_GFX_VALID_BEFORE 1
struct device { struct {int usage_count,runtime_error;} power; };
struct platform_device {struct device dev;};
struct apple_pmgr_gfx_reset_observation {u32 valid,before,domain_on;int operation_error,cleanup_error;};
struct resource {u64 start,end;unsigned int flags;};
struct device_node {int available;};
static struct device_node alias_node;
static struct resource alias_resource;
static struct resource later_alias_resource;
static unsigned int alias_count=1;
static bool alias_enabled;
static unsigned int node_gets,node_puts,node_references;
static struct platform_device consumer_value;
static struct platform_device *consumer=&consumer_value;
static bool held=true,started;
static bool root_sent,asc_region,mbox_region;
static void *asc,*mbox;
static int graph_io_lock;
static unsigned int pins,request_calls,map_calls,log_calls,qwrites,lwrites;
static unsigned int cleanup_events,pm_puts;
static unsigned int fail_request,fail_map;
static int snapshot_error;
static int snapshot_operation_error,snapshot_cleanup_error;
static u32 snapshot_word=0x1f0003ff;
static u32 snapshot_valid=1,snapshot_domain_on=1;
static bool compatible=true,pm_enabled=true,pm_active=true;
static bool seed_on_map;
static u64 clock_ns;
static void *pmp_memory,*pmc_memory;
static u64 last_qwrite_offset;
static u32 vote_offsets[16];
static u64 requested_bases[2],requested_sizes[2];
static bool of_device_is_available(struct device_node *n){return n->available;}
static int of_address_to_resource(struct device_node *n,unsigned int i,struct resource *r){(void)n;if(i>=alias_count)return -EINVAL;*r=i?later_alias_resource:alias_resource;return 0;}
static void of_node_put(struct device_node *n){assert(n==&alias_node&&node_references);node_references--;node_puts++;}
static struct device_node *of_find_all_nodes(struct device_node *previous){if(previous){of_node_put(previous);return NULL;}if(!alias_enabled)return NULL;node_gets++;node_references++;return &alias_node;}
static bool of_machine_is_compatible(const char *name){assert(!strcmp(name,"apple,j614s")||!strcmp(name,"apple,t6040"));return compatible;}
static void __module_get(void *m){assert(m==THIS_MODULE);pins++;}
static void mutex_lock(int *m){assert(!*m);*m=1;}
static void mutex_unlock(int *m){assert(*m==1);*m=0;}
#define lockdep_assert_held(m) assert(*(m)==1)
static int atomic_read(int *v){return *v;}
static bool pm_runtime_enabled(struct device *d){(void)d;return pm_enabled;}
static bool pm_runtime_active(struct device *d){(void)d;return pm_active;}
static int apple_pmgr_t6040_gfx_snapshot(struct apple_pmgr_gfx_reset_observation *o){for(unsigned int n=0;n<sizeof(*o);n++)assert(!((unsigned char *)o)[n]);*o=(struct apple_pmgr_gfx_reset_observation){snapshot_valid,snapshot_word,snapshot_domain_on,snapshot_operation_error,snapshot_cleanup_error};return snapshot_error;}
static void mock_log(const char *format,...){(void)format;log_calls++;}
#define pr_info(...) mock_log(__VA_ARGS__)
#define pr_err(...) mock_log(__VA_ARGS__)
#define pr_warn(...) mock_log(__VA_ARGS__)
static void *request_mem_region(u64 b,u64 s,const char *n){(void)n;request_calls++;if(request_calls<=2){requested_bases[request_calls-1]=b;requested_sizes[request_calls-1]=s;}if(request_calls==fail_request)return NULL;return (void *)1;}
static void *ioremap(u64 b,u64 s){void *p;map_calls++;if(map_calls==fail_map)return NULL;p=calloc(1,(size_t)s);assert(p);if(b==0x5003c0000ULL){pmp_memory=p;if(seed_on_map){u64 v=1;memcpy((char *)p+0x10,&v,8);v=0x1234567800000000ULL;memcpy((char *)p+0x1e00,&v,8);}}else {assert(b==0x504000000ULL);pmc_memory=p;}return p;}
static u64 readq(void *p){u64 v;memcpy(&v,p,8);return v;}
static u32 readl(void *p){u32 v;memcpy(&v,p,4);return v;}
static void writeq(u64 v,void *p){qwrites++;last_qwrite_offset=(u64)((char *)p-(char *)pmp_memory);memcpy(p,&v,8);assert(last_qwrite_offset==0x10f00);memcpy((char *)pmp_memory+0x1e00,&v,8);memcpy((char *)pmp_memory+0x1e80,&v,8);v=2;memcpy((char *)pmp_memory+0x1e88,&v,8);}
static void writel(u32 v,void *p){assert(lwrites<16);vote_offsets[lwrites++]=(u32)((char *)p-(char *)pmc_memory);memcpy(p,&v,4);}
static u64 ktime_get_ns(void){return clock_ns;}
static void usleep_range(unsigned int lo,unsigned int hi){assert(lo==1000&&hi==1100);clock_ns+=1000000;}
static void graph_snapshot_remove(void){cleanup_events++;}
static void root_release(void){cleanup_events++;}
static void iounmap(void *p){(void)p;cleanup_events++;}
static void release_mem_region(u64 b,u64 s){(void)b;(void)s;cleanup_events++;}
static int pm_runtime_put_sync_suspend(struct device *d){(void)d;cleanup_events++;pm_puts++;return 0;}
static void pm_runtime_disable(struct device *d){(void)d;cleanup_events++;}
static void pm_genpd_remove_device(struct device *d){(void)d;cleanup_events++;}
static void platform_device_unregister(struct platform_device *d){(void)d;cleanup_events++;}
#define ASC_BASE 0x28a600000ULL
#define MBOX_BASE (ASC_BASE+0x8000)
'''

SUFFIX=r'''
static unsigned int cases;
static void reset(void){
 free(pmp_memory);free(pmc_memory);pmp_memory=NULL;pmc_memory=NULL;
 consumer=&consumer_value;consumer_value.dev.power.usage_count=1;consumer_value.dev.power.runtime_error=0;
 held=true;started=root_sent=asc_region=mbox_region=false;asc=mbox=NULL;
 graph_io_lock=0;pins=request_calls=map_calls=log_calls=qwrites=lwrites=0;
 cleanup_events=pm_puts=0;
 fail_request=fail_map=0;snapshot_error=snapshot_operation_error=snapshot_cleanup_error=0;
 snapshot_word=0x1f0003ff;snapshot_valid=snapshot_domain_on=1;
 compatible=pm_enabled=pm_active=true;seed_on_map=false;clock_ns=0;alias_enabled=false;
 node_gets=node_puts=node_references=0;
 alias_node.available=1;alias_resource=(struct resource){0x5003c0000,0x5003c000f,IORESOURCE_MEM};
 alias_count=1;later_alias_resource=(struct resource){0};
 gfx_coord_owner_module_pinned=gfx_coord_owner_startup_retained=false;
 gfx_coord_owner_pmp_region=gfx_coord_owner_pmc_region=false;
 gfx_coord_owner_pmp=gfx_coord_owner_pmc=NULL;
 gfx_coord_owner_session=(struct gfx_coord_session){0};
 gfx_coord_owner_on=gfx_coord_owner_off=(struct gfx_coord_observation){0};
 gfx_coord_owner_status_wait_events=gfx_coord_owner_ack_wait_events=0;
}
static void retained_refusal(int expected){
 bool original_held=held;
 int ret=gfx_coord_owner_begin_on();assert(ret==expected);assert(gfx_coord_owner_retained());
 assert(gfx_coord_owner_module_pinned&&pins==1&&held==original_held&&!started);assert(!graph_io_lock);
 assert(!node_references&&node_gets==node_puts);
 gfx_coord_owner_pin();gfx_coord_owner_pin();assert(pins==1);cases++;
}
static void seed(u64 request){
 u64 value=1;memcpy((char *)pmp_memory+0x10,&value,8);
 memcpy((char *)pmp_memory+0x1e00,&request,8);memcpy((char *)pmp_memory+0x1e80,&request,8);
 value=2;memcpy((char *)pmp_memory+0x1e88,&value,8);
 for(unsigned int r=0;r<3;r++){u32 v=0x12340001+r*0x100;memcpy((char *)pmc_memory+0x8ac000+r*4,&v,4);}
}
int main(void){
 reset();consumer=NULL;retained_refusal(-EBUSY);assert(!request_calls);
 reset();held=false;retained_refusal(-EBUSY);assert(!request_calls);
 reset();started=true;assert(gfx_coord_owner_begin_on()==-EBUSY&&pins==1&&held);cases++;
 reset();consumer_value.dev.power.usage_count=2;retained_refusal(-EBUSY);
 reset();consumer_value.dev.power.runtime_error=-EIO;retained_refusal(-EBUSY);
 reset();pm_enabled=false;retained_refusal(-EBUSY);
 reset();pm_active=false;retained_refusal(-EBUSY);
 reset();snapshot_error=-EIO;retained_refusal(-EIO);
 reset();snapshot_error=1;retained_refusal(-EIO);
 reset();snapshot_operation_error=-EINVAL;retained_refusal(-EINVAL);
 reset();snapshot_operation_error=1;retained_refusal(-EIO);
 reset();snapshot_cleanup_error=-ETIMEDOUT;retained_refusal(-ETIMEDOUT);
 reset();snapshot_cleanup_error=1;retained_refusal(-EIO);
 reset();snapshot_valid=0;retained_refusal(-ENODATA);
 reset();snapshot_domain_on=0;retained_refusal(-EBUSY);
 reset();snapshot_word=0x0f000b00;retained_refusal(-EBUSY);
 reset();compatible=false;retained_refusal(-ENODEV);assert(!request_calls);
 reset();alias_enabled=true;retained_refusal(-EBUSY);assert(!request_calls);
 reset();alias_enabled=true;alias_resource.start=0x5048ac000;alias_resource.end=0x5048ac00f;retained_refusal(-EBUSY);
 reset();alias_enabled=true;alias_count=2;alias_resource=(struct resource){0x12340000,0x12340fff,IORESOURCE_MEM};
 later_alias_resource=(struct resource){0x5003c1e00,0x5003c1e0f,IORESOURCE_MEM};retained_refusal(-EBUSY);assert(!request_calls);
 reset();alias_enabled=true;alias_count=2;alias_resource=(struct resource){0x12340000,0x12340fff,IORESOURCE_MEM};
 later_alias_resource=(struct resource){0x5048ac000,0x5048ac00f,IORESOURCE_MEM};retained_refusal(-EBUSY);assert(!request_calls);
 reset();alias_enabled=true;alias_node.available=0;assert(gfx_coord_owner_alias_check()==0&&node_gets==1&&node_puts==1&&!node_references);cases++;
 reset();alias_enabled=true;alias_resource=(struct resource){0x12340000,0x12340fff,IORESOURCE_MEM};assert(gfx_coord_owner_alias_check()==0&&node_gets==1&&node_puts==1&&!node_references);cases++;
 reset();alias_enabled=true;assert(gfx_coord_owner_alias_check()==-EBUSY&&node_gets==1&&node_puts==1&&!node_references);cases++;
 reset();fail_request=1;retained_refusal(-EBUSY);assert(!gfx_coord_owner_pmp_region&&!gfx_coord_owner_pmc_region);
 reset();fail_request=2;retained_refusal(-EBUSY);assert(gfx_coord_owner_pmp_region&&!gfx_coord_owner_pmc_region&&!map_calls);
 reset();fail_map=1;retained_refusal(-ENOMEM);assert(gfx_coord_owner_pmp_region&&gfx_coord_owner_pmc_region&&!pmp_memory&&!pmc_memory);
 reset();fail_map=2;retained_refusal(-ENOMEM);assert(pmp_memory&&!pmc_memory&&gfx_coord_owner_pmp_region&&gfx_coord_owner_pmc_region);
 reset();retained_refusal(-ENODATA);assert(!qwrites&&!lwrites);assert(gfx_coord_owner_session.on_attempted);
 reset();assert(gfx_coord_owner_prepare()==0);assert(requested_bases[0]==0x5003c0000ULL&&requested_sizes[0]==0x30000);
 assert(requested_bases[1]==0x504000000ULL&&requested_sizes[1]==0x1000000);seed(0x1234567800000000ULL);
 gfx_coord_owner_startup_retained=true;gfx_coord_owner_pin();mutex_lock(&graph_io_lock);
 assert(gfx_coord_owner_transition(true)==0);assert(gfx_coord_owner_session.on_complete&&qwrites==1&&lwrites==3);
 assert(gfx_coord_owner_on.request_written==0x1234567800002000ULL&&gfx_coord_owner_on.ack_status==2);
 assert(last_qwrite_offset==0x10f00&&vote_offsets[0]==0x8ac000&&vote_offsets[1]==0x8ac004&&vote_offsets[2]==0x8ac008);cases++;
 assert(gfx_coord_owner_before_off()==0);assert(gfx_coord_owner_session.off_complete&&qwrites==2&&lwrites==6&&held);
 assert(gfx_coord_owner_off.request_written==0x1234567800000000ULL);cases++;
 assert(gfx_coord_owner_before_off()==-EALREADY&&qwrites==2&&lwrites==6&&held);cases++;
 mutex_unlock(&graph_io_lock);
 reset();gfx_coord_owner_event(NULL,"ack-wait",0,0,0,0);assert(log_calls==1);
 for(unsigned int n=2;n<=127;n++)gfx_coord_owner_event(NULL,"ack-wait",0,0,0,0);
 assert(log_calls==4);gfx_coord_owner_event(NULL,"ack-wait",0,0,0,0);assert(log_calls==5);
 gfx_coord_owner_event(NULL,"ack-wait",0,0,0,-EIO);assert(log_calls==6);cases++;
 reset();mutex_lock(&graph_io_lock);assert(gfx_coord_owner_before_off()==-EBUSY&&!qwrites&&!lwrites&&held);cases++;
 mutex_unlock(&graph_io_lock);
 reset();cleanup();assert(cleanup_events>0&&pm_puts==1&&!pins);cases++;
 reset();assert(run_transformed_startup_gate()==0);assert(gfx_coord_owner_retained()&&pins==1&&held&&!started&&!root_sent&&!qwrites);
 cleanup();assert(!cleanup_events&&!pm_puts);cases++;
 assert(run_transformed_fail(-EIO)==0&&pins==1&&!cleanup_events&&!pm_puts);cases++;
 assert(run_transformed_retirement()==0&&pins==1&&!cleanup_events&&!pm_puts);cases++;
 reset();seed_on_map=true;assert(run_transformed_startup_gate()==1&&started&&held&&pins==1&&gfx_coord_owner_session.on_complete);cases++;
 cleanup();assert(!cleanup_events&&!pm_puts&&pins==1);assert(run_transformed_fail(-EIO)==0&&pins==1&&!pm_puts);cases++;
 reset();printf("adapter_cases=%u\n",cases);return 0;
}
'''

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--output',required=True,type=Path)
 args=ap.parse_args()
 spec=importlib.util.spec_from_file_location('coordinate_prepare',HERE/'prepare-owner.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 base=ROOT/'out/gfx-poweroff-scope/candidate/asc-graph-init'
 before={p:module.digest(base/p) for p in ['asc-graph-init.c','gfx-reset-scope.h','recovery-cycle.h']}
 assert before=={'asc-graph-init.c':module.BASE_OWNER_SHA,'gfx-reset-scope.h':module.BASE_OFF_SHA,'recovery-cycle.h':module.BASE_CYCLE_SHA}
 transformed=module.transform_owner((base/'asc-graph-init.c').read_text())
 off=module.transform_off((base/'gfx-reset-scope.h').read_text())
 assert transformed.index('pm_runtime_resume_and_get')<transformed.index('ret=gfx_coord_owner_begin_on();')<transformed.index('started=true;writel(control|START')<transformed.index('ret=root_prepare(true)')
 assert 'if (gfx_coord_owner_retained()) retired=false;' in transformed
 assert 'if (gfx_coord_owner_retained()) {' in transformed[transformed.index('static void cleanup'):transformed.index('static bool crashlog_boot')]
 assert transformed.count('gfx_coord_owner_pin();')==4 and '__module_get(THIS_MODULE);' not in transformed
 assert off.index('gfx_poweroff_gate_consumed=true;')<off.index('ret=gfx_coord_owner_before_off();')<off.index('held=false;')<off.index('pm_runtime_put_sync_suspend')
 cleanup=transformed[transformed.index('static void cleanup(void)'):transformed.index('/* Start only endpoint 1.')]
 gate=transformed[transformed.index(' ret=gfx_coord_owner_begin_on();'):transformed.index(' pr_info("m4rch ASC crashlog: cold control=')]
 failed=transformed[transformed.index('fail:\n')+len('fail:\n'):transformed.index('static void __exit')]
 retirement=transformed[transformed.index(' if (gfx_coord_owner_retained()) retired=false;'):transformed.index('fail:\n')]
 lifetime=cleanup+'\nstatic int run_transformed_startup_gate(void) {\n int ret;\n'+gate+' started=true; return 1;\n}\n'
 lifetime+='\nstatic int run_transformed_fail(int ret) {\n'+failed
 lifetime+='\nstatic int run_transformed_retirement(void) {\n bool retired=true;\n'+retirement+'}\n'
 for old,new,func in [('if (!(readl(mbox+0x114)&EMPTY)) {ret=-EBUSY;goto fail;}','bad',module.transform_owner),('gfx_poweroff_pm_attempted=true;gfx_reset_scope_attempted=true;','bad',module.transform_off)]:
  source=(base/('asc-graph-init.c' if func is module.transform_owner else 'gfx-reset-scope.h')).read_text()
  try:func(source.replace(old,new))
  except ValueError:pass
  else:raise AssertionError('changed insertion point accepted')
 core_path=HERE.parent/'gfx-native-coordinate/gfx-coordinate-core.h'
 core=core_path.read_text()
 legacy_source=(base/'gfx-reset-scope.h').read_text()
 legacy_snapshot=legacy_source[legacy_source.index('static int gfx_poweroff_snapshot('):legacy_source.index('static int gfx_reset_scope_snapshot(')]
 adapter=(HERE/'gfx-coordinate-owner.h').read_text()
 adapter=adapter.replace('#include <linux/of_address.h>','').replace('#include <linux/timekeeping.h>','').replace('#include "gfx-coordinate-core.h"',core)
 with tempfile.TemporaryDirectory(prefix='gfx-coordinate-owner-test-') as directory:
  directory=Path(directory);source=directory/'adapter.c';binary=directory/'adapter'
  source.write_text(PREFIX+legacy_snapshot+adapter+lifetime+SUFFIX)
  command=['clang','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address,undefined','-g',str(source),'-o',str(binary)]
  compiled=subprocess.run(command,capture_output=True,text=True)
  if compiled.returncode:
   raise RuntimeError(f'actual adapter/lifetime compilation failure:\n{compiled.stderr}')
  environment=dict(os.environ)
  environment['ASAN_OPTIONS']='detect_leaks=0'
  result=subprocess.run([str(binary)],capture_output=True,text=True,env=environment)
  if result.returncode:
   raise RuntimeError(f'actual adapter RAM failure ({result.returncode}):\n{result.stdout}\n{result.stderr}')
 assert before=={p:module.digest(base/p) for p in before}
 report={'schema':'m4rch.gfx.native-coordinate.owner-ram-test.v1','adapter_sha256':module.digest(HERE/'gfx-coordinate-owner.h'),'transform_sha256':module.digest(HERE/'prepare-owner.py'),'core_sha256':module.digest(core_path),'baseline_source_pins':before,'actual_adapter_ram_result':result.stdout.strip(),'exported_OF_iterator_reference_balance_checked':True,'ASan_UBSan':True,'LeakSanitizer':'disabled: sandbox ptrace restriction','guarded_transform_order_checked':True,'hardware_actions':[],'candidate_build_actions':[],'attempted_candidate_unchanged':True}
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))

if __name__=='__main__':main()
