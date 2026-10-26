#!/usr/bin/env python3
"""Exercise actual cold identity functions with every allocated owner page."""
import argparse,hashlib,json,re,subprocess,tempfile
from pathlib import Path
def extract(text,marker):
 a=text.index(marker);b=text.index('{',a);i=b+1;depth=1
 while depth:depth+=(text[i]=='{')-(text[i]=='}');i+=1
 return text[a:i]
def pin(p):
 p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def qualify(source,output):
 source=Path(source).resolve();runtime=(source/'gfx-cold-runtime.h').read_text();cold=(source/'gfx-cold-render.h').read_text()
 macro=re.search(r'^#define GFX_COLD_PAGES (.*)$',runtime,re.M).group(1)
 assert macro=='ARRAY_SIZE(owned)'
 assert 'static_assert(GFX_COLD_PAGES == ARRAY_SIZE(owned));'in cold
 prefix=r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
typedef uint64_t u64;
#define ARRAY_SIZE(x) (sizeof(x)/sizeof(*(x)))
#define READ_ONCE(x) (x)
struct page {u64 pa;};
static struct page storage[176],*owned[176];
/* ACTUAL_MACRO */
static struct page *gfx_cold_pages[GFX_COLD_PAGES];
static u64 gfx_cold_page_pa[GFX_COLD_PAGES];
struct power {int usage_count,runtime_error;};
struct device {struct power power;};
struct platform_device {struct device dev;};
static struct platform_device object,*consumer=&object,*gfx_cold_consumer;
static int asc_object,mbox_object;static void *asc=&asc_object,*mbox=&mbox_object,*gfx_cold_asc,*gfx_cold_mbox;
static u64 word,*target_slot=&word,*bootstrap=&word,*target_page=&word,*borrowed_l1;
static u64 *gfx_cold_bootstrap,*gfx_cold_borrowed_l1,*gfx_cold_target_page,*gfx_cold_target_slot,gfx_cold_root_word;
static bool held,asc_region,mbox_region,started,root_sent,installed,root_detached,device_context_retained,resident_session,receive_crashed;
static bool gfx_cold_identity_captured,gfx_cold_identities_preserved,gfx_coord_owner_module_pinned;
static struct {bool on_complete;}gfx_coord_owner_session;
static struct {unsigned int status;}receive_journal;
static unsigned int gfx_cold_apps_started;
static bool owner_retained,ap_known,enabled,active,suspended;
static int atomic_read(int*p){return *p;}
static bool gfx_coord_owner_retained(void){return owner_retained;}
static bool gfx_cold_ap_known(void){return ap_known;}
static bool pm_runtime_enabled(struct device*d){(void)d;return enabled;}
static bool pm_runtime_active(struct device*d){(void)d;return active;}
static bool pm_runtime_suspended(struct device*d){(void)d;return suspended;}
static u64 page_to_phys(struct page*p){return p->pa;}
static void reset(void){
 for(unsigned int i=0;i<ARRAY_SIZE(owned);i++){storage[i].pa=0x100000000ULL+i*16384;owned[i]=&storage[i];}
 consumer=&object;object.dev.power.usage_count=1;object.dev.power.runtime_error=0;
 held=asc_region=mbox_region=started=root_sent=installed=device_context_retained=resident_session=true;
 root_detached=receive_crashed=suspended=false;receive_journal.status=0;
 gfx_cold_identity_captured=gfx_cold_identities_preserved=false;
 owner_retained=ap_known=enabled=active=gfx_coord_owner_module_pinned=gfx_coord_owner_session.on_complete=true;
 gfx_cold_apps_started=3;borrowed_l1=NULL;word=storage[0].pa|3;
}
'''.replace('/* ACTUAL_MACRO */','#define GFX_COLD_PAGES '+macro)
 functions=extract(cold,'static bool gfx_cold_live(void)')+'\n'+extract(cold,'static bool gfx_cold_capture_identity(void)')
 main=r'''
int main(void){
 reset();assert(GFX_COLD_PAGES==176);assert(gfx_cold_capture_identity());assert(gfx_cold_identities_preserved);
 for(unsigned int i=0;i<176;i++){
  reset();owned[i]=NULL;assert(!gfx_cold_capture_identity());assert(!gfx_cold_identity_captured);
  reset();assert(gfx_cold_capture_identity());owned[i]=NULL;assert(!gfx_cold_live());assert(!gfx_cold_identities_preserved);
  reset();assert(gfx_cold_capture_identity());storage[i].pa+=16384;assert(!gfx_cold_live());assert(!gfx_cold_identities_preserved);
 }
 reset();borrowed_l1=&word;word=storage[1].pa|3;assert(gfx_cold_capture_identity());
 reset();word^=16384;assert(!gfx_cold_capture_identity());
 return 0;
}
'''
 with tempfile.TemporaryDirectory(prefix='full-power-cold-identity-')as td:
  p=Path(td);(p/'main.c').write_text(prefix+functions+main)
  subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror',str(p/'main.c'),'-o',str(p/'run')],check=True)
  subprocess.run([str(p/'run')],check=True)
  # Reproduce the consumed v24 failure with exactly the same176owner array.
  broken=prefix.replace('#define GFX_COLD_PAGES ARRAY_SIZE(owned)','#define GFX_COLD_PAGES 174U')+functions+'\nint main(void){reset();assert(!gfx_cold_capture_identity());return 0;}\n'
  (p/'old.c').write_text(broken);subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror',str(p/'old.c'),'-o',str(p/'old')],check=True);subprocess.run([str(p/'old')],check=True)
 j=dict(schema='m4rch.v24-cold-identity-owner-array.v1',owned_pages=176,successful_identity_cases=2,per_page_refusals=528,wrong_root_refusals=1,old174_with176_reproduced=True,pins=[pin(source/'gfx-cold-runtime.h'),pin(source/'gfx-cold-render.h'),pin(__file__)],hardware_actions=[],scope='Actual cold live/capture C functions with intercepted owner/PM providers. All176pages included, absent/swapped physical backing refused. Reproduces former unconditional174vs176 rejection; does not prove live control/draw or teardown.')
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
 with output.open('x')as f:f.write(json.dumps(j,indent=2)+'\n')
 print(json.dumps(j))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();qualify(a.source,a.output)
