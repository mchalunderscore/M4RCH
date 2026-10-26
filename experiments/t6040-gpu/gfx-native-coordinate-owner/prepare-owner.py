#!/usr/bin/env python3
"""Prepare separate source files only; never build, load or alter the input."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE_OWNER_SHA='664127ec86429b479ded378f4cdcd7501c1895ec3cebf1679bc116c225363620'
BASE_OFF_SHA='9ac963d90d9b54f209fb47f934ced4387e51f44cdd4a45626a6c4b9f9f05a05f'
BASE_CYCLE_SHA='e465ccbc1365e2a745a9a6f7c6eaf91d64a785f62925dc2ad4243048fd5e9500'

def digest(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def replace_once(text,old,new):
 if text.count(old)!=1:
  raise ValueError(f'expected one unchanged insertion point: {old[:90]!r}')
 return text.replace(old,new,1)

def transform_owner(text):
 if text.count('__module_get(THIS_MODULE);')!=4:
  raise ValueError('expected exactly four old lifetime-pin sites')
 text=text.replace('__module_get(THIS_MODULE);','gfx_coord_owner_pin();')
 text=replace_once(text,'static DEFINE_MUTEX(graph_io_lock);',
  'static DEFINE_MUTEX(graph_io_lock);\n'
  'static void gfx_coord_owner_pin(void);\n'
  'static bool gfx_coord_owner_retained(void);\n'
  'static void gfx_coord_owner_log(const char *phase,int result);\n'
  'static int gfx_coord_owner_before_off(void);')
 text=replace_once(text,'#include "recovery-cycle.h"\n#endif',
  '#include "recovery-cycle.h"\n#endif\n'
  '#include "gfx-coordinate-owner.h"')
 text=replace_once(text,'static void cleanup(void)\n{\n',
  'static void cleanup(void)\n{\n'
  ' if (gfx_coord_owner_retained()) {\n'
  '  gfx_coord_owner_log("cleanup-refused-retained",-EPERM);\n'
  '  return;\n'
  ' }\n')
 text=replace_once(text,
  ' if (!(readl(mbox+0x114)&EMPTY)) {ret=-EBUSY;goto fail;}\n'
  ' pr_info("m4rch ASC crashlog: cold control=',
  ' if (!(readl(mbox+0x114)&EMPTY)) {ret=-EBUSY;goto fail;}\n'
  ' ret=gfx_coord_owner_begin_on();\n'
  ' if (ret) {\n'
  '  gfx_coord_owner_log("startup-refused-before-start",ret);\n'
  '  pr_err("m4rch gfx-native-coordinate: startup-retained result=%d consumer=%u held=%u module_pinned=%u started=%u root_published=%u cleanup_attempted=0\\n",\n'
  '   ret,!!consumer,held,gfx_coord_owner_module_pinned,started,root_sent);\n'
  '  return 0; /* Retained module/consumer/PM/resources; no graph published. */\n'
  ' }\n'
  ' pr_info("m4rch ASC crashlog: cold control=')
 text=replace_once(text,' if (retired) {\n',
  ' if (gfx_coord_owner_retained()) retired=false;\n'
  ' if (retired) {\n')
 text=replace_once(text,'fail:\n if (started)',
  'fail:\n'
  ' if (gfx_coord_owner_retained()) {\n'
  '  gfx_coord_owner_log("later-startup-failure-retained",ret);\n'
  '  return 0;\n'
  ' }\n'
  ' if (started)')
 text=replace_once(text,
  'MODULE_DESCRIPTION("Experimental J614s structural init batch; published graph pins until reboot");',
  'MODULE_DESCRIPTION("Experimental J614s paired PMP/PMC retained no-work coordinator");')
 return text

def transform_off(text):
 return replace_once(text,
  ' gfx_poweroff_pm_attempted=true;gfx_reset_scope_attempted=true;\n',
  ' ret=gfx_coord_owner_before_off();\n'
  ' if (ret) {\n'
  '  gfx_poweroff_snapshot_result=ret;\n'
  '  gfx_reset_scope_protocol("coordination-off-refused");\n'
  '  return gfx_reset_scope_result("gfx-poweroff",ret);\n'
  ' }\n'
  ' gfx_poweroff_pm_attempted=true;gfx_reset_scope_attempted=true;\n')

def prepare(source,destination,core):
 expected={'asc-graph-init.c':BASE_OWNER_SHA,'gfx-reset-scope.h':BASE_OFF_SHA,
           'recovery-cycle.h':BASE_CYCLE_SHA}
 for name,sha in expected.items():
  if digest(source/name)!=sha:raise ValueError(f'unchanged base source mismatch: {name}')
 if destination.exists():raise ValueError('destination already exists; refuse overwrite')
 if not core.is_file():raise ValueError('root protocol core is not saved yet')
 owner=transform_owner((source/'asc-graph-init.c').read_text())
 off=transform_off((source/'gfx-reset-scope.h').read_text())
 make=(source/'Makefile').read_text()
 if make.count('-DGFX_POWER_OFF_SCOPE_TRIAL')!=1:raise ValueError('missing distinct base profile')
 make+='\nccflags-y += -DGFX_NATIVE_COORDINATED_SCOPE_TRIAL\n'
 # Copy source/build-input files only; no .ko, build result, runtime capture or log.
 inputs=[p for p in source.iterdir() if p.is_file() and
  (p.suffix in {'.c','.h','.bin'} or p.name=='Makefile')]
 if any(p.name.endswith('.mod.c') for p in inputs):
  inputs=[p for p in inputs if not p.name.endswith('.mod.c')]
 destination.mkdir(parents=True)
 for path in inputs:(destination/path.name).write_bytes(path.read_bytes())
 (destination/'asc-graph-init.c').write_text(owner)
 (destination/'gfx-reset-scope.h').write_text(off)
 (destination/'Makefile').write_text(make)
 (destination/'gfx-coordinate-owner.h').write_bytes((HERE/'gfx-coordinate-owner.h').read_bytes())
 (destination/'gfx-coordinate-core.h').write_bytes(core.read_bytes())
 receipt={'schema':'m4rch.gfx.native-coordinate.owner-source.v1',
  'source':str(source.resolve()),'destination':str(destination.resolve()),
  'input_source_pins':[{'path':str(p.resolve()),'sha256':digest(p)} for p in sorted(inputs)],
  'root_core':{'path':str(core.resolve()),'sha256':digest(core)},
  'adapter':{'path':str((HERE/'gfx-coordinate-owner.h').resolve()),
             'sha256':digest(HERE/'gfx-coordinate-owner.h')},
  'output_source_pins':[{'name':p.name,'sha256':digest(p)} for p in sorted(destination.iterdir())],
  'on_after_physical_get_cold_checks_before_start':True,
  'off_before_sole_pm_put':True,'startup_intent_failure_retained':True,
  'lifetime_pin_idempotent':True,'cleanup_refused_after_on_invocation':True,
  'hardware_actions':[],'build_actions':[],'candidate_created':False}
 (destination/'coordinate-owner-source-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 return receipt

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--source',required=True,type=Path)
 ap.add_argument('--destination',required=True,type=Path)
 ap.add_argument('--core',type=Path,default=HERE.parent/'gfx-native-coordinate/gfx-coordinate-core.h')
 args=ap.parse_args()
 receipt=prepare(args.source,args.destination,args.core)
 print(json.dumps({'receipt':str(args.destination/'coordinate-owner-source-receipt.json'),
  'sources':len(receipt['output_source_pins']),'hardware_actions':[],'build_actions':[]}))

if __name__=='__main__':main()
