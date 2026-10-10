#!/usr/bin/env python3
"""Prepare a distinct native-ordered retained cycle; never build or load."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_RECEIPT_SHA = 'd5ed3909257d659816e2c23cebe43f72308aa0677efa3660b5e76758b56ee36d'
CHANGED = ['Makefile', 'asc-graph-init.c', 'recovery-cycle.h']
ADDED = ['gfx-native-ap-retained-cycle.h']
REMOVED = ['gfx-native-running-cycle.h']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Frozen insertion changed: ' + repr(old[:100]))
    return source.replace(old, new, 1)


def prepare(source, destination):
    source, destination = source.resolve(), destination.resolve()
    if destination.exists() or source == destination or source in destination.parents:
        raise ValueError('Destination must be new and outside the frozen source')
    old_path = source / 'native-running-cycle-owner-source-receipt.json'
    if sha(old_path) != BASE_RECEIPT_SHA:
        raise ValueError('Frozen native running v10 source receipt changed')
    old = json.loads(old_path.read_text())
    before = {row['name']: row['sha256'] for row in old['output_source_pins']}
    for name, pin in before.items():
        if sha(source / name) != pin:
            raise ValueError('Frozen source pin changed: ' + name)
    before[old_path.name] = sha(old_path)
    copied = {name: pin for name, pin in before.items() if name not in REMOVED}
    make = once((source / 'Makefile').read_text(), '-DGFX_NATIVE_RUNNING_CYCLE_TRIAL',
                '-DGFX_NATIVE_AP_RETAINED_CYCLE_TRIAL')
    dispatcher = once((source / 'recovery-cycle.h').read_text(),
                      '#include "gfx-native-running-cycle.h"', '#include "gfx-native-ap-retained-cycle.h"')
    owner = once((source / 'asc-graph-init.c').read_text(),
                 'm4rch gfx-native-running-cycle-session:', 'm4rch gfx-native-ap-retained-cycle-session:')
    owner = once(owner, 'native running host ON retained PWRGATE transport management no-work coordinator',
                 'native retained AP ON skip PWRGATE transport management no-work coordinator')
    declarations = """#ifdef GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL
static bool gfx_ap_cold_request_attempted, gfx_ap_cold_request_write_attempted;
static bool gfx_ap_cold_reply_observed, gfx_ap_remote_known;
static u64 gfx_ap_cold_request_message, gfx_ap_cold_request_metadata;
static u64 gfx_ap_cold_reply_message, gfx_ap_cold_reply_metadata;
static u32 gfx_ap_remote_state;
#endif
"""
    owner = once(owner, '#ifdef GRAPH_RECOVERY_EXPERIMENT\nstatic bool power_ack(unsigned int request,unsigned int reply,u16 state);',
        declarations+'#ifdef GRAPH_RECOVERY_EXPERIMENT\nstatic bool power_ack(unsigned int request,unsigned int reply,u16 state);')
    owner = once(owner, ' unsigned int messages = 0;\n if (readl(mbox+0x110) & BIT(16)) return false;', """ unsigned int messages = 0;
#ifdef GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL
 bool cold_ap_on=request==0xb && reply==0xb && state==0x20;
 u32 cold_rx,cold_tx;
 unsigned int cold_polls=0;
 if(request==0xb && !cold_ap_on) return false;
 if(cold_ap_on && (gfx_ap_cold_request_attempted || gfx_ap_cold_reply_observed || gfx_ap_remote_known)) return false;
#endif
 if (readl(mbox+0x110) & BIT(16)) return false;
#ifdef GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL
 if(cold_ap_on) {
  cold_rx=readl(mbox+0x114);
  if(cold_rx==~0U || !(cold_rx&EMPTY)) return false;
  gfx_ap_cold_request_attempted=true;
  gfx_ap_cold_request_message=GFX_RETAINED_CYCLE_HOST_ON;gfx_ap_cold_request_metadata=0;
  gfx_retained_cycle_cold_ap_log("request");
  cold_rx=readl(mbox+0x114);cold_tx=readl(mbox+0x110);
  if(cold_rx==~0U || cold_tx==~0U || !(cold_rx&EMPTY) || (cold_tx&BIT(16))) return false;
  gfx_ap_cold_request_write_attempted=true;
 }
#endif""")
    owner = once(owner, ' deadline=jiffies+msecs_to_jiffies(2000);\n do {\n  if (!(readl(mbox+0x114)&EMPTY)) {', """ deadline=jiffies+msecs_to_jiffies(2000);
 do {
#ifdef GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL
  if(cold_ap_on && (cold_polls++>=2001U || !time_before(jiffies,deadline))) return false;
#endif
  if (!(readl(mbox+0x114)&EMPTY)) {""")
    owner = once(owner, '   if (type==reply && (msg&0xffff)==state) return true;', """   if (type==reply && (msg&0xffff)==state) {
#ifdef GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL
    if(cold_ap_on) {
     cold_rx=readl(mbox+0x114);
     if(msg!=GFX_RETAINED_CYCLE_HOST_ON || meta==~0ULL || (meta&0xff) ||
        !time_before(jiffies,deadline) || cold_rx==~0U || !(cold_rx&EMPTY)) return false;
     gfx_ap_cold_reply_message=msg;gfx_ap_cold_reply_metadata=meta;
     gfx_ap_cold_reply_observed=true;gfx_ap_remote_state=0x20;gfx_ap_remote_known=true;
     gfx_retained_cycle_cold_ap_log("reply");
    }
#endif
    return true;
   }""")
    owner = once(owner, ' if (epmap && crashlog_boot() && power_ack(0xb,0xb,0x20)) {', """ if (epmap && crashlog_boot() && power_ack(0xb,0xb,0x20)
#ifdef GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL
     && gfx_retained_cycle_ap_on_known()
#endif
     ) {""")
    destination.mkdir(parents=True)
    for name in copied:
        (destination / name).write_bytes((source / name).read_bytes())
    for name, data in [('Makefile', make), ('recovery-cycle.h', dispatcher), ('asc-graph-init.c', owner)]:
        (destination / name).write_text(data)
    for name in ADDED:
        (destination / name).write_bytes((HERE / name).read_bytes())
    after = {name: sha(destination / name) for name in copied}
    changed = sorted(name for name in copied if after[name] != copied[name])
    if changed != CHANGED:
        raise ValueError('Unexpected delta from frozen retained source')
    for name in ADDED:
        after[name] = sha(destination / name)
    for name, pin in before.items():
        if sha(source / name) != pin:
            raise ValueError('Frozen input changed during preparation: ' + name)
    profile = dict(old['profile'])
    for key in list(profile):
        if 'host_on' in key or key == 'fresh_pm_identity_cpu_fifo_required_after_host_reply_before_second_202':
            profile.pop(key)
    profile.update({
        'compile_macro':'GFX_NATIVE_AP_RETAINED_CYCLE_TRIAL','version':11,
        'typed_commands':['sample','gfx-snapshot','gfx-powergate','gfx-native-ap-retained-cycle'],
        'cold_owned_ap_on_request':'0x00b0000000000020',
        'cold_exact_ap_on_reply':'0x00b0000000000020',
        'cold_ap_state_wire':'0x20',
        'maximum_cold_ap_polls':2001,
        'nominal_cold_ap_timeout_ms':2000,
        'cold_ap_on_exact_request_reply_required_before_root_publication':True,
        'cold_ap_on_fresh_rx_empty_tx_available_before_and_after_intent':True,
        'cold_ap_on_late_or_pending_reply_refused':True,
        'cold_ap_mirror_required_before_second_pm_get':True,
        'retained_ap_unknown_state_refused':True,
        'no_ap_b201_or_b0':True,
        'cold_ap_mirror_preserved_through_management_only_202':True,
        'second_host_on_requests_maximum':0,
        'second_host_on_fallback_forbidden':True,
        'retained_host_on_skip_intent_required':True,
        'retained_host_on_skip_requires_cold_exact_ap20_and_fresh_running':True,
        'retained_host_on_skip_fresh_gates_after_intent_log':True,
        'retained_host_on_skip_does_not_fabricate_fresh_reply':True,
        'second202_fresh_gates_after_intent_log':True,
        'retained_ap_skip_is_experimental_management_hypothesis':True,
        'second_log_row_count':6,
        'second_log_row_prefixes':['m4rch gfx-native-ap-retained-cycle:',
          'm4rch gfx-native-ap-retained-cycle-state:','m4rch gfx-native-ap-retained-cycle-transport:',
          'm4rch gfx-native-ap-retained-cycle-management:','m4rch gfx-native-ap-retained-cycle-off:',
          'm4rch gfx-native-ap-retained-cycle-on:'],
        'cold_ap_log_prefix':'m4rch gfx-native-ap-retained-cold:',
        'cold_ap_log_phases':['request','reply'],
        'maximum_log_row_bytes':511,
        'second_powergate_admission':'exact owned cold B20/reply establishes AP20, unchanged management-only first202/OFF, fresh second HELLO12/two maps/Running7-20, retained AP20 skip intent and fresh identities/PM/CPU/FIFO before one202; no secondB20',
        'power20_never_shutdown_ack':True,
        'second_ack_reserved_journal_slots':1,
    })
    receipt = {
        'schema': 'm4rch.gfx-native-ap-retained-cycle-owner-source.v1',
        'source': str(source), 'destination': str(destination), 'source_path': str(source),
        'baseline_source_receipt': {'path': str(old_path), 'sha256': BASE_RECEIPT_SHA},
        'frozen_retained_receipt': {'path': str(old_path), 'sha256': BASE_RECEIPT_SHA},
        'source_preparer': {'path': str(Path(__file__).resolve()), 'sha256': sha(Path(__file__))},
        'input_source_pins': [{'name': n, 'sha256': v} for n, v in before.items()],
        'output_source_pins': [{'name': n, 'sha256': v} for n, v in after.items()],
        'changed_files': CHANGED, 'changed_frozen_retained_files': changed,
        'added_files': ADDED, 'removed_files': REMOVED,
        'profile': profile, 'hardware_actions': [], 'build_actions': [],
        'qualification': 'Source preparation only. Owned exact cold B20/reply establishes retained AP20; preserved through management-only202/OFF. Fresh Running and a guarded retained AP20 skip precede one own202/low1or2 ACK. No secondB20/fallback or invented freshreply. Experimental management hypothesis; no apprejoin, recovery, rendering or DMA retirement.',
    }
    output = destination / 'native-ap-retained-cycle-owner-source-receipt.json'
    with output.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.destination)
    print(json.dumps({'receipt': str(args.destination / 'native-ap-retained-cycle-owner-source-receipt.json'),
                      'changed_files': result['changed_files'], 'added_files': result['added_files'],
                      'hardware_actions': []}))


if __name__ == '__main__':
    main()
