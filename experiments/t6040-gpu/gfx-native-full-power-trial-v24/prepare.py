#!/usr/bin/env python3
"""Stage distinct v24 source and standalone qualified Rust power ABI object.

Never loads modules or accesses GPU. Existing render payload bytes remain exact.
"""
import argparse,hashlib,importlib.util,json,re,shutil,subprocess
from pathlib import Path
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[2]
OLD='GFX_NATIVE_POWER_ASSERTION_FENDER_CYCLE_TRIAL';NEW='GFX_NATIVE_FULL_POWER_TRIAL_V24'
def pin(path):
 path=Path(path).resolve();b=path.read_bytes();return dict(path=str(path),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def prepare(source,destination,adt):
 source=Path(source);destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
 original={p.name:p.read_bytes() for p in source.iterdir() if p.is_file() and (p.suffix in ['.c','.h','.bin','.json'] or p.name=='Makefile') and not p.name.endswith('.mod.c')}
 for name,data in original.items():
  if name.endswith(('.c','.h')):data=data.replace(OLD.encode(),NEW.encode())
  (destination/name).write_bytes(data)
 cycle_path=destination/'gfx-postdraw-native-nmi-cycle.h';cycle=cycle_path.read_text()
 marker='ret=gfx_postdraw_off();if(!ret) ret=gfx_postdraw_on();';assert cycle.count(marker)==1
 cycle=cycle.replace(marker,'ret=gfx_postdraw_off(); /* v24: stop after bounded OFF; no wake or management rejoin. */')
 cycle=cycle.replace('static int gfx_postdraw_on(void)','static int __maybe_unused gfx_postdraw_on(void)')
 marker='gfx_postdraw_unknown,gfx_postdraw_capture_token,gfx_cold_retained_pages(),gfx_postdraw_complete);'
 assert cycle.count(marker)==1
 cycle=cycle.replace(marker,'gfx_postdraw_unknown,gfx_postdraw_capture_token,gfx_cold_retained_pages(),0U); /* v24 never rejoins */')
 cycle_path.write_text(cycle)
 c=(destination/'asc-graph-init.c').read_text()
 c=c.replace('#include "gfx-gravity-preasc.h"','#include "gfx-gravity-preasc.h"\n#include "gfx-full-power-clock.h"\n#include "gfx-full-power.h"')
 marker=' pr_info("m4rch ASC crashlog: cold control=%#x status=%#x; starting bounded poll\\n",control,status);'
 assert c.count(marker)==1
 c=c.replace(marker,' ret=gfx_full_power_snapshot();\n if(ret) { pr_err("m4rch full-power: pre-START snapshot refused=%d; resources retained\\n",ret); return 0; }\n'+marker)
 c=c.replace(' if (!ret) ret=sysfs_create_bin_file(graph_directory,&joined_raw);',' if (!ret) ret=sysfs_create_bin_file(graph_directory,&joined_raw);\n if (!ret) ret=sysfs_create_bin_file(graph_directory,&gfx_full_power_initial_raw);')
 c=c.replace('  sysfs_remove_bin_file(graph_directory,&graph_raw);','  sysfs_remove_bin_file(graph_directory,&gfx_full_power_initial_raw);\n  sysfs_remove_bin_file(graph_directory,&graph_raw);')
 (destination/'asc-graph-main.c').write_text(c);(destination/'asc-graph-init.c').unlink()
 g=(destination/'graph-map.h').read_text();g=g.replace('static int root_prepare(bool install)','static int gfx_full_power_graph_prepare(void);\nstatic void gfx_full_power_capture_initialized(void);\nstatic int root_prepare(bool install)')
 marker=' for (i=0;i<ARRAY_SIZE(owned);i++) clean_page(page_address(owned[i]));'
 assert g.count(marker)==1;g=g.replace(marker,' if(install) {ret=gfx_full_power_graph_prepare();if(ret)goto fail_root;}\n'+marker)
 g=g.replace('#include "graph-contract.h"','#include "graph-contract.h"\n#include "full-power-timestamp-contract.h"')
 g=re.sub(r'^#define EXTRA_OWNED_PAGES (.*)$',lambda m:'#define EXTRA_OWNED_PAGES ('+m[1]+' + FULL_POWER_TIMESTAMP_EXTRA_PAGES)',g,flags=re.M)
 g=re.sub(r'^#define EFFECTIVE_MAPPED_PAGES (.*)$',lambda m:'#define EFFECTIVE_MAPPED_PAGES ('+m[1]+' + 1U)',g,flags=re.M)
 g=g.replace('static void invalidate_root_va(void)','#include "full-power-timestamp-map.h"\nstatic void invalidate_root_va(void)')
 g=g.replace(' asm volatile("dsb sy" ::: "memory");\n}\n/* Only called',' gfx_full_power_timestamp_invalidate();\n asm volatile("dsb sy" ::: "memory");\n}\n/* Only called')
 g=g.replace(' if (READ_ONCE(*target_slot)!=expected) return false;',' if (READ_ONCE(*target_slot)!=expected || !gfx_full_power_timestamp_can_detach()) return false;\n if (!gfx_full_power_timestamp_remove_borrowed()) return false;')
 g=g.replace(' if (device_context_retained || (root_sent && !root_detached)) return;',' if (device_context_retained || (root_sent && !root_detached) || !gfx_full_power_timestamp_can_detach()) return;')
 g=g.replace(' if (installed) {\n  WRITE_ONCE(*target_slot,0);',' if (installed) {\n  if (!target_slot || !target_page || READ_ONCE(*target_slot)!=(page_to_phys(owned[borrowed_l1?1:0])|3)) return;\n  if (!gfx_full_power_timestamp_remove_borrowed()) return;\n  WRITE_ONCE(*target_slot,0);')
 g=g.replace(' if(install) {ret=gfx_full_power_graph_prepare();if(ret)goto fail_root;}',' if(install) {ret=gfx_full_power_graph_prepare();if(ret)goto fail_root;}\n if(!gfx_full_power_timestamp_prepare(l1,l2)) {ret=-EINVAL;goto fail_root;}\n if(install)gfx_full_power_capture_initialized();')
 g=g.replace('  WRITE_ONCE(*target_slot,page_to_phys(owned[1])|3);','  if(!gfx_full_power_timestamp_borrowed_available(borrowed_l1)) {ret=-EBUSY;goto fail_root;}\n  WRITE_ONCE(*target_slot,page_to_phys(owned[1])|3);')
 g=g.replace(' installed=true;clean_page(target_page);invalidate_root_va();',' installed=true;\n if(borrowed_l1 && !gfx_full_power_timestamp_publish_borrowed(borrowed_l1)) {ret=-EIO;goto fail_root;}\n clean_page(target_page);invalidate_root_va();')
 (destination/'graph-map.h').write_text(g)
 # Snapshot/retention guards must cover the same owner array as the allocator,
 # including timestamp table/data pages added above. A stale174 constant made
 # the full-power176 owner refuse before control/draw on its first real boot.
 runtime_path=destination/'gfx-cold-runtime.h';runtime=runtime_path.read_text()
 marker='#define GFX_COLD_PAGES 174U';assert runtime.count(marker)==1
 runtime=runtime.replace(marker,'#define GFX_COLD_PAGES ARRAY_SIZE(owned)')
 runtime_path.write_text(runtime)
 cold_path=destination/'gfx-cold-render.h';cold=cold_path.read_text()
 marker='static struct page *gfx_cold_pages[GFX_COLD_PAGES];';assert cold.count(marker)==1
 cold=cold.replace(marker,'static_assert(GFX_COLD_PAGES == ARRAY_SIZE(owned));\n'+marker)
 cold_path.write_text(cold)
 for name in ['gfx-full-power.h','power_bridge.rs','full-power-timestamp-contract.h','full-power-timestamp-map.h']:shutil.copyfile(KIT/name,destination/name)
 # Root/clock owner supplies this typed experimental time-domain helper.
 shutil.copyfile(ROOT/'experiments/t6040-gpu/desktop-integration/t6040-native-boot/gfx_native_clock_v24.h',destination/'gfx-full-power-clock.h')
 component=KIT/'g16_t6040_power_trial_v24.rs';shutil.copyfile(component,destination/'power.rs')
 f=(ROOT/'out/gpu-gravity-normal-boot-v6/source/linux/drivers/gpu/drm/asahi/float.rs').read_text()
 f=f[:f.index("impl<'a> TryFrom<of::Property")];f=re.sub(r'use kernel::\{.*?\};','',f,flags=re.S).replace('unsafe impl Zeroable for F32 {}','')
 (destination/'float.rs').write_text(f)
 spec=importlib.util.spec_from_file_location('v24_adt',ROOT/'experiments/t6040-gpu/adt.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p);node=p.parse(Path(adt).read_bytes())['/device-tree/arm-io/sgx']
 properties=[]
 for i,(key,value) in enumerate(node.items()):
  if isinstance(value,bytes):
   name=f'adt-property-{i}.bin';(destination/name).write_bytes(value);properties.append(f'({json.dumps(key)},include_bytes!({json.dumps(name)}).as_slice())')
 (destination/'properties.rs').write_text('pub static ROWS: &[(&str,&[u8])] = &[\n'+',\n'.join(properties)+'\n];\n')
 cmd=['rustc','--edition=2021','--crate-type=lib','--emit=obj','-C','panic=abort','-C','opt-level=2','-C','force-frame-pointers=yes','-C','target-feature=-neon,-fp-armv8',str(destination/'power_bridge.rs'),'-o',str(destination/'native-power-rust.o')]
 compile=subprocess.run(cmd,capture_output=True,text=True);(destination/'rust-compile.log').write_text(compile.stdout+compile.stderr)
 assert compile.returncode==0,compile.stderr
 undefined=subprocess.check_output(['llvm-nm','-u',str(destination/'native-power-rust.o')],text=True)
 shims=[line.split()[-1] for line in undefined.splitlines() if 'core' in line and 'panic' in line or 'slice_index_fail' in line]
 (destination/'rust-panic-shims.S').write_text('.section .text,\"ax\"\n'+''.join(f'.global {symbol}\n.type {symbol},%function\n{symbol}:\n b m4rch_full_power_panic\n' for symbol in shims))
 make=original['Makefile'].decode().replace(OLD,NEW)
 make=make.replace('obj-m += asc-graph-init.o','obj-m += asc-graph-init.o\nasc-graph-init-y := asc-graph-main.o native-power-rust.o rust-panic-shims.o\n$(obj)/native-power-rust.o: $(src)/power_bridge.rs $(src)/power.rs $(src)/float.rs $(src)/properties.rs\n\trustc --edition=2021 --crate-type=lib --emit=obj -C panic=abort -C opt-level=2 -C force-frame-pointers=yes -C target-feature=-neon,-fp-armv8 $< -o $@')
 (destination/'Makefile').write_text(make)
 report=dict(schema='m4rch.native-full-power-trial-source.v24',inputs=[pin(Path(__file__)),pin(adt),pin(component)],source=str(source.resolve()),destination=str(destination.resolve()),
  rust_object=pin(destination/'native-power-rust.o'),rust_command=cmd,rust_compile_returncode=compile.returncode,
  old_macro=OLD,new_macro=NEW,hardware_actions=[],hardware_ready=False,
  unchanged_payloads=[dict(name=n,sha256=hashlib.sha256(b).hexdigest()) for n,b in original.items() if n.endswith('.bin')],
  joined_clock_and_timestamp=True,pre_START_map_validation=True,postdraw_OFF_only=True,management_rejoin_logged=False,remaining=['Actual module build and C ABI qualification receipt','Launcher/fresh-preflight bundle and root READY review'])
 (destination/'v24-source-receipt.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path);p.add_argument('--destination',required=True,type=Path);p.add_argument('--adt',required=True,type=Path);a=p.parse_args();print(json.dumps(prepare(a.source,a.destination,a.adt)['rust_object']))
