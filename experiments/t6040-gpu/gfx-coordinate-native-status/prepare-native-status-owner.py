#!/usr/bin/env python3
"""Prepare a distinct native STATUS0 execution owner from the frozen bridge.

No module build/load or hardware access. Only core, passive observation logging
and distinct compile flag change; dispatcher, draw, graph and lifetime stay fixed.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = {
 'asc-graph-init.c':'5e6156de5894c93b97b7ae43f2e6cf00df698e0e14c3c380e62c4432b049a29b',
 'recovery-cycle.h':'9971b319f7bbcc265ec6a9eca5b2f9bdf00e44a7c19eabce301eb48cc0debe71',
 'gfx-coordinate-core.h':'417179e014653c2b97e55888346cbda70c79a4166fe2a1ca191d741f7201ad01',
 'gfx-coordinate-owner.h':'a9dc2ef9184464f50cb4fddc8d1710daac06d9b594054aaf569d467e2a7dda1a',
 'graph-before.bin':'287f2c53bc6ef7ed226c4a2995b9d9904e7623acae9713af105be6b04fc690a9',
 'graph-receipt.json':'92771b8036464c8dc9bdadd1dd4e1458a6c5a9f95f87fbdac34696bd2b3af219',
 'backing.bin':'35112ef3c261673bda227a3867a0d2b9dd58ac89f35f7bba9c8c05f1dee118d3',
 'execution-owner-source-receipt.json':'9c3af71b46eb0ebe956d4164125a57dcf280f64bbd1effca25d94abacdd2ca1d',
}
CORE_SHA='b7a7376ab2a7e1b054e0338ce37efe035b85acaa6ba5072ed7231b6dcb245a95'


def sha(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
 if source.count(old)!=1: raise ValueError('Adapter insertion point changed: '+repr(old[:80]))
 return source.replace(old,new,1)


def transform_adapter(source):
 if hashlib.sha256(source.encode()).hexdigest()!=EXPECTED['gfx-coordinate-owner.h']:
  raise ValueError('Frozen adapter changed')
 source=replace_once(source,'#include <linux/of_address.h>',
  '#ifndef GFX_NATIVE_STATUS_ZERO_TRIAL\n#error Native STATUS success requires its distinct owner profile\n#endif\n\n#include <linux/of_address.h>')
 source=replace_once(source,'status_wait_events=%u ack_wait_events=%u\\n",',
  'status_wait_events=%u ack_wait_events=%u ack_bypassed=%u status_payload=%#llx status_raw=%#llx\\n",')
 source=replace_once(source,'  gfx_coord_owner_status_wait_events,gfx_coord_owner_ack_wait_events);',
  '  gfx_coord_owner_status_wait_events,gfx_coord_owner_ack_wait_events,\n'
  '  observation->ack_bypassed,(unsigned long long)observation->status_payload,\n'
  '  (unsigned long long)observation->status_raw);')
 return source


def prepare(source,destination):
 source,destination=source.resolve(),destination.resolve()
 if destination.exists() or source==destination or source in destination.parents:
  raise ValueError('Destination must be new and outside the frozen bridge')
 for name,expected in EXPECTED.items():
  if sha(source/name)!=expected: raise ValueError('Frozen execution input changed: '+name)
 frozen_receipt=json.loads((source/'execution-owner-source-receipt.json').read_text())
 for row in frozen_receipt['output_source_pins']:
  if sha(source/row['name'])!=row['sha256']: raise ValueError('Frozen source pin changed: '+row['name'])
 if sha(HERE/'gfx-coordinate-core.h')!=CORE_SHA:raise ValueError('Qualified native core changed')
 adapter=transform_adapter((source/'gfx-coordinate-owner.h').read_text())
 if (HERE/'gfx-coordinate-owner.h').read_text()!=adapter:raise ValueError('Kit adapter differs from exact transformation')
 make=(source/'Makefile').read_text()
 if '-DGFX_COORDINATED_EXECUTION_TRIAL' not in make or 'GFX_NATIVE_STATUS_ZERO_TRIAL' in make:
  raise ValueError('Input is not the qualified execution profile')
 make+='\nccflags-y += -DGFX_NATIVE_STATUS_ZERO_TRIAL\n'
 inputs=sorted(p for p in source.iterdir() if p.is_file() and
  (p.suffix in ('.c','.h','.bin','.json') or p.name=='Makefile') and not p.name.endswith('.mod.c'))
 before={p.name:sha(p) for p in inputs}
 destination.mkdir(parents=True)
 for p in inputs:(destination/p.name).write_bytes(p.read_bytes())
 (destination/'gfx-coordinate-core.h').write_bytes((HERE/'gfx-coordinate-core.h').read_bytes())
 (destination/'gfx-coordinate-owner.h').write_text(adapter)
 (destination/'Makefile').write_text(make)
 after={p.name:sha(destination/p.name) for p in inputs}
 changed=sorted(n for n in before if before[n]!=after[n])
 if changed!=['Makefile','gfx-coordinate-core.h','gfx-coordinate-owner.h']:
  raise ValueError('Unexpected native STATUS source delta')
 if before!={p.name:sha(p) for p in inputs}:raise ValueError('Frozen source changed during preparation')
 receipt={'schema':'m4rch.gfx-native-status-owner-source.v1','source':str(source),
  'destination':str(destination),'source_preparer':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__))},
  'input_source_pins':[{'name':n,'sha256':v} for n,v in before.items()],
  'output_source_pins':[{'name':n,'sha256':v} for n,v in after.items()],
  'changed_files':changed,'hardware_actions':[],'build_actions':[],
  'native_predicate':'Full REQ write then STATUS.payload==0 OR ACK.rawstatus.bit1 and matching REQ.bit13, before strict deadline',
  'status_zero_is_ack_or_inactivity':False,'graph_draw_dispatcher_lifetime_unchanged':True,
  'once_only_on_off_work_intents_unchanged':True,
  'qualification':'Source-only preparation. No hardware recovery, reset, teardown, DMA retirement, rendering or release is established.'}
 with (destination/'native-status-owner-source-receipt.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 return receipt


def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--destination',type=Path,required=True)
 args=ap.parse_args();r=prepare(args.source,args.destination)
 print(json.dumps({'receipt':str(args.destination/'native-status-owner-source-receipt.json'),'changed_files':r['changed_files'],'hardware_actions':[]}))


if __name__=='__main__':main()
