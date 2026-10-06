"""Compile the applied driver's budget/gate code and exercise bounded transitions."""
from pathlib import Path
import hashlib,sys,subprocess,tempfile,unittest,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lib'))
from hardware_profile import IDLE_OPTIN,IDLE_TRACE,SAVED_WFI,WFI_BATCH,WFI_ALLCORES
class WfiAllcores(unittest.TestCase):
 def source(self):
  with tempfile.TemporaryDirectory() as temp:
   source=Path(temp)/WFI_BATCH['source'];source.parent.mkdir(parents=True);source.write_bytes((ROOT/'tests/fixtures/cpuidle-apple-base.c').read_bytes())
   for d in (IDLE_OPTIN,IDLE_TRACE,SAVED_WFI,WFI_BATCH,WFI_ALLCORES):
    self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),d['base_source_sha256'])
    subprocess.run(['git','apply','--whitespace=error-all',str(ROOT/d['path'])],cwd=temp,check=True,capture_output=True)
    self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),d['result_source_sha256'])
   return source.read_text()
 def test_actual_control_functions(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler absent')
  s=self.source();control=s[s.index('static DEFINE_RAW_SPINLOCK'):s.index('static const struct kernel_param_ops saved_budget_ops')]
  control+=s[s.index('static bool saved_take_attempt'):s.index('void m4rch_idle_checkpoint(unsigned int stage, u64 value);')]
  prefix="""#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>
#include <limits.h>
#include <errno.h>
#include <assert.h>
#include <string.h>
#define PAGE_SIZE 4096
#define DEFINE_RAW_SPINLOCK(x) int x
static int nesting;
static unsigned int online_mask=4095;
#define cpu_online(c) (online_mask & (1U << (c)))
#define raw_spin_lock_irqsave(lock,flags) do{(void)(lock);(flags)=0;assert(nesting++==0);}while(0)
#define raw_spin_unlock_irqrestore(lock,flags) do{(void)(lock);(void)(flags);assert(--nesting==0);}while(0)
#define scnprintf snprintf
#define pr_emerg(...) printf(__VA_ARGS__)
struct kernel_param { int unused; };
static int kstrtouint(const char *s,int base,unsigned int *v){
 char *end;errno=0;if(*s=='-')return -EINVAL;unsigned long n=strtoul(s,&end,base);
 if(errno||*end||end==s||n>UINT_MAX)return -EINVAL;*v=n;return 0;
}
"""
  main="""int main(void){
 char buf[4096];
 assert(saved_budget==0&&saved_target==4);assert(!saved_take_attempt(4));
 assert(saved_target_set("12",NULL)==-EINVAL);
 online_mask &= ~(1U<<8);assert(saved_target_set("8",NULL)==-EINVAL);online_mask=4095;
 assert(saved_budget_set("65",NULL)==-ERANGE);assert(saved_budget_set("-1",NULL)==-EINVAL);
 for(unsigned int cpu=0;cpu<12;cpu++) {
  assert(!saved_target_set(cpu==0?"0":cpu==1?"1":cpu==2?"2":cpu==3?"3":cpu==4?"4":cpu==5?"5":cpu==6?"6":cpu==7?"7":cpu==8?"8":cpu==9?"9":cpu==10?"10":"11",NULL));
  assert(!saved_budget_set("4",NULL));assert(saved_target_set("0",NULL)==-EBUSY);
  assert(!saved_take_attempt(12));assert(!saved_take_attempt((cpu+1)%12));
  for(int n=0;n<4;n++) {assert(saved_take_attempt(cpu));
   assert(!saved_budget_set("0",NULL));assert(saved_target_set("0",NULL)==-EBUSY);
   saved_finish_attempt(cpu);assert(!saved_budget_set("4",NULL));}
  assert(!saved_take_attempt(cpu));assert(!saved_budget_set("0",NULL));
 }
 for(int c=0;c<12;c++)assert(saved_attempts[c]==4&&saved_completed[c]==4);
 assert(!saved_budget_set("2",NULL));assert(!saved_take_attempt(11));
 assert(!saved_budget_set("64",NULL));
 for(int n=4;n<64;n++){assert(saved_take_attempt(11));saved_finish_attempt(11);}
 assert(!saved_take_attempt(11));assert(saved_progress_get(buf,NULL)>0);
 assert(strstr(buf,"cpu11 attempts=64 completed=64"));assert(nesting==0);
 return 0;}
"""
  with tempfile.TemporaryDirectory() as temp:
   f=Path(temp);(f/'gate.c').write_text(prefix+control+main)
   subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-misleading-indentation',str(f/'gate.c'),'-o',str(f/'gate')],check=True,capture_output=True)
   subprocess.run([str(f/'gate')],check=True,capture_output=True)
 def test_original_saved_assembly_unchanged(self):
  s=self.source();a=s.index('".type m4rch_cpu_saved_wfi_trace');b=s.index('void m4rch_cpu_saved_wfi_trace',a);asm=s[a:b]
  self.assertNotIn('mrs',asm);self.assertNotIn('msr',asm);self.assertEqual(asm.count('"wfi'),1)
  self.assertIn('if (saved)\n\t\tsaved_finish_attempt(cpu);',s)
