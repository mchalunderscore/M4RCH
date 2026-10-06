"""Compile the applied entry callback to check continuous/disabled/rejected paths."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from test_wfi_allcores import WfiAllcores, ROOT
from hardware_profile import WFI_CONTINUOUS

class Continuous(unittest.TestCase):
 def source(self):
  base=WfiAllcores().source()
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/WFI_CONTINUOUS['source'];p.parent.mkdir(parents=True);p.write_text(base)
   subprocess.run(['git','apply','--whitespace=error-all',str(ROOT/WFI_CONTINUOUS['path'])],cwd=temp,check=True,capture_output=True)
   self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),WFI_CONTINUOUS['result_source_sha256'])
   return base,p.read_text()
 def test_entry_paths(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('no C compiler')
  base,s=self.source();a=s.index('static __cpuidle int apple_enter_idle');b=s.index('static struct cpuidle_driver',a)
  entry=s[a:b]
  prefix='''#include <stdbool.h>
#include <assert.h>
#define __cpuidle
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define this_cpu_inc(x) ((x)[cpu_current]++)
#define pr_warn_ratelimited(...) ((void)0)
#define pr_emerg(...) ((void)0)
#define WARN_ON(x) assert(!(x))
#define STATE_WFI 0
#define STATE_PWRDOWN 1
struct cpuidle_device{};struct cpuidle_driver{};
static bool t6040_trial=true, experimental_t6040_idle_trace=true;
static bool experimental_t6040_idle_wfi_only=true,experimental_t6040_idle_continuous;
static bool trace_attempted,bounded_allowed,pm_reject;
static unsigned int cpu_current,nop,entered,exited,wakes,deep,bounded_finishes,context;
static unsigned long long continuous_attempts[12],continuous_completed[12];
static unsigned int smp_processor_id(void){return cpu_current;}
static void cpu_do_idle(void){nop++;}
static bool saved_take_attempt(unsigned int c){(void)c;return bounded_allowed;}
static void saved_finish_attempt(unsigned int c){(void)c;bounded_finishes++;}
static void m4rch_idle_checkpoint(unsigned int s,unsigned long long v){(void)s;(void)v;}
static int cpu_pm_enter(void){if(pm_reject)return -1;entered++;return 0;}
static void cpu_pm_exit(void){exited++;}
static void ct_cpuidle_enter(void){assert(context++==0);}
static void ct_cpuidle_exit(void){assert(--context==0);}
static void m4rch_cpu_saved_wfi_trace(void){assert(context==1);wakes++;}
static void m4rch_cpu_deep_wfi_trace(void){deep++;}
static void apple_cpu_deep_wfi(void){deep++;}
'''
  main='''int main(void){
 assert(apple_enter_idle(0,0,1)==0&&nop==1&&wakes==0);
 experimental_t6040_idle_continuous=true;
 for(cpu_current=0;cpu_current<12;cpu_current++)for(int n=0;n<128;n++)assert(apple_enter_idle(0,0,1)==1);
 assert(wakes==1536&&entered==wakes&&exited==wakes&&bounded_finishes==0&&deep==0);
 for(int c=0;c<12;c++)assert(continuous_attempts[c]==128&&continuous_completed[c]==128);
 cpu_current=4;pm_reject=true;assert(apple_enter_idle(0,0,1)==-1);assert(continuous_attempts[4]==128);
 pm_reject=false;experimental_t6040_idle_continuous=false;
 assert(apple_enter_idle(0,0,1)==0&&nop==2);
 bounded_allowed=true;assert(apple_enter_idle(0,0,1)==1&&bounded_finishes==1);
 t6040_trial=false;assert(apple_enter_idle(0,0,1)==1&&deep==1);
 return 0;}
'''
  if getattr(self, 'shallow', False):
   main=main.replace('apple_enter_idle(0,0,1)', 'apple_enter_idle(0,0,0)').replace('apple_enter_idle(0,0,0)==1', 'apple_enter_idle(0,0,0)==0')
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);(p/'entry.c').write_text(prefix+entry+main)
   subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(p/'entry.c'),'-o',str(p/'test')],check=True,capture_output=True)
   subprocess.run([str(p/'test')],check=True)
 def test_saved_assembly_unchanged_and_optin(self):
  a,b=self.source()
  for s in (a,b):
   start=s.index('".type m4rch_cpu_saved_wfi_trace');end=s.index('void m4rch_cpu_saved_wfi_trace',start)
   if s==a:old=s[start:end]
   else:self.assertEqual(old,s[start:end])
  self.assertIn('static bool experimental_t6040_idle_continuous;',b)
  self.assertIn('!experimental_t6040_idle_wfi_only)',b)
