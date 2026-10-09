#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Qualify the actual STATUS0 adapter and retained startup/OFF source gates."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN_HARNESS = HERE.parent / 'gfx-native-coordinate-owner/test-owner.py'
HARNESS_SHA = 'ad4c1d180ba77fb89511b7fac0acab1e7df2012cfa46e34394249686519437b1'
CORE_SHA = 'b7a7376ab2a7e1b054e0338ce37efe035b85acaa6ba5072ed7231b6dcb245a95'
ADAPTER_SHA = '9798b26320e2b0f9b270da9b598f21e909cf037e58070154a6818ac6156601b4'
FROZEN_ADAPTER_SHA = 'a9dc2ef9184464f50cb4fddc8d1710daac06d9b594054aaf569d467e2a7dda1a'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Harness insertion changed: ' + repr(old[:80]))
    return source.replace(old, new, 1)


EXTRA_CASES = r'''
 reset();assert(gfx_coord_owner_begin_on()==0&&pins==1&&held&&!started);
 assert(gfx_coord_owner_on.request_attempted&&gfx_coord_owner_on.ack_bypassed&&!gfx_coord_owner_on.request_acked);
 assert(!gfx_coord_owner_on.ack_samples&&gfx_coord_owner_on.votes_verified==3&&qwrites==1&&lwrites==3);
 assert(has_log("ack_bypassed=1 status_payload=0 status_raw=0"));cases++;
 mutex_lock(&graph_io_lock);assert(gfx_coord_owner_before_off()==0&&held&&qwrites==2&&lwrites==6);
 assert(gfx_coord_owner_off.ack_bypassed&&!gfx_coord_owner_off.request_acked&&!gfx_coord_owner_off.ack_samples);
 assert(gfx_coord_owner_off.request_written==0&&!strcmp(write_trace,"QLLLQLLL"));cases++;
 assert(gfx_coord_owner_before_off()==-EALREADY&&qwrites==2&&lwrites==6&&held);cases++;
 mutex_unlock(&graph_io_lock);cleanup();assert(!cleanup_events&&!pm_puts&&pins==1);cases++;
 reset();status_raw_on_map=0x1234;assert(gfx_coord_owner_begin_on()==0);
 assert(gfx_coord_owner_on.status_payload==0&&gfx_coord_owner_on.status_raw==0x1234);
 assert(has_log("ack_bypassed=1 status_payload=0 status_raw=0x1234"));cases++;
 reset();drop_request_write=true;retained_refusal(-EAGAIN);
 assert(qwrites==1&&!lwrites&&gfx_coord_owner_on.request_attempted&&gfx_coord_owner_on.ack_bypassed&&!started);
 cleanup();assert(!cleanup_events&&!pm_puts);cases++;
 reset();drop_vote_number=2;retained_refusal(-EAGAIN);
 assert(qwrites==1&&lwrites==2&&gfx_coord_owner_on.votes_verified==1&&!started);
 cleanup();assert(!cleanup_events&&!pm_puts);cases++;
 reset();assert(gfx_coord_owner_begin_on()==0);mutex_lock(&graph_io_lock);
 assert(run_transformed_off_gate()==0&&!held&&pm_puts==1&&qwrites==2&&lwrites==6);
 assert(gfx_poweroff_pm_attempted&&gfx_reset_scope_attempted);
 assert(gfx_coord_owner_session.off_complete&&!strcmp(write_trace,"QLLLQLLL"));cases++;
 mutex_unlock(&graph_io_lock);unsigned int saved_cleanup=cleanup_events;
 cleanup();assert(cleanup_events==saved_cleanup&&pm_puts==1&&pins==1);cases++;
 reset();assert(gfx_coord_owner_begin_on()==0);drop_vote_number=5;mutex_lock(&graph_io_lock);
 assert(run_transformed_off_gate()==-EAGAIN&&held&&!pm_puts&&qwrites==2&&lwrites==5);
 assert(!gfx_poweroff_pm_attempted&&!gfx_reset_scope_attempted);
 assert(!gfx_coord_owner_session.off_complete&&gfx_coord_owner_off.votes_verified==1);cases++;
 mutex_unlock(&graph_io_lock);cleanup();assert(!cleanup_events&&!pm_puts&&pins==1);cases++;
 reset();assert(gfx_coord_owner_begin_on()==0);u64 invalid=~0ULL;
 memcpy((char *)pmp_memory+0x10,&invalid,8);mutex_lock(&graph_io_lock);
 assert(run_transformed_off_gate()==-EIO&&held&&!pm_puts&&qwrites==1&&lwrites==3);cases++;
 mutex_unlock(&graph_io_lock);cleanup();assert(!cleanup_events&&!pm_puts&&pins==1);cases++;
 reset();assert(run_transformed_startup_gate()==1&&started&&held&&pins==1);
 assert(gfx_coord_owner_on.ack_bypassed&&!root_sent);cleanup();assert(!cleanup_events&&!pm_puts);cases++;
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert sha(FROZEN_HARNESS) == HARNESS_SHA
    old = runpy.run_path(str(FROZEN_HARNESS))
    frozen = ROOT / 'out/gfx-coordinate-execution/candidate/asc-graph-init'
    prepared = ROOT / 'out/gfx-coordinate-native-status/prepared-owner'
    baseline = {name: sha(frozen / name) for name in
                ['asc-graph-init.c', 'gfx-reset-scope.h', 'recovery-cycle.h', 'gfx-coordinate-owner.h']}
    assert baseline == {
        'asc-graph-init.c': '5e6156de5894c93b97b7ae43f2e6cf00df698e0e14c3c380e62c4432b049a29b',
        'gfx-reset-scope.h': '4ad396fa170b694f7b7e00e37d7f88bbcd07b55ba44d767ee825a4cff8de7fff',
        'recovery-cycle.h': '9971b319f7bbcc265ec6a9eca5b2f9bdf00e44a7c19eabce301eb48cc0debe71',
        'gfx-coordinate-owner.h': FROZEN_ADAPTER_SHA}
    assert sha(HERE / 'gfx-coordinate-core.h') == CORE_SHA
    assert sha(HERE / 'gfx-coordinate-owner.h') == ADAPTER_SHA
    for name in ('asc-graph-init.c', 'gfx-reset-scope.h', 'recovery-cycle.h'):
        assert (prepared / name).read_bytes() == (frozen / name).read_bytes()
    for name in ('gfx-coordinate-core.h', 'gfx-coordinate-owner.h'):
        assert (prepared / name).read_bytes() == (HERE / name).read_bytes()
    adapter = (HERE / 'gfx-coordinate-owner.h').read_text()
    reversed_adapter = replace_once(adapter,
        '#ifndef GFX_NATIVE_STATUS_ZERO_TRIAL\n#error Native STATUS success requires its distinct owner profile\n#endif\n\n', '')
    reversed_adapter = replace_once(reversed_adapter,
        ' ack_bypassed=%u status_payload=%#llx status_raw=%#llx', '')
    reversed_adapter = replace_once(reversed_adapter,
        '  gfx_coord_owner_status_wait_events,gfx_coord_owner_ack_wait_events,\n'
        '  observation->ack_bypassed,(unsigned long long)observation->status_payload,\n'
        '  (unsigned long long)observation->status_raw);',
        '  gfx_coord_owner_status_wait_events,gfx_coord_owner_ack_wait_events);')
    assert reversed_adapter == (frozen / 'gfx-coordinate-owner.h').read_text()
    spec = importlib.util.spec_from_file_location('native_status_prepare', HERE / 'prepare-native-status-owner.py')
    preparer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preparer)
    assert preparer.transform_adapter((frozen / 'gfx-coordinate-owner.h').read_text()) == adapter
    try:
        preparer.transform_adapter((frozen / 'gfx-coordinate-owner.h').read_text() + '\n')
    except ValueError:
        pass
    else:
        raise AssertionError('Changed frozen adapter accepted')

    transformed = (prepared / 'asc-graph-init.c').read_text()
    off = (prepared / 'gfx-reset-scope.h').read_text()
    assert transformed.index('pm_runtime_resume_and_get') < transformed.index('ret=gfx_coord_owner_begin_on();') < transformed.index('started=true;writel(control|START') < transformed.index('ret=root_prepare(true)')
    assert off.index('gfx_poweroff_gate_consumed=true;') < off.index('ret=gfx_coord_owner_before_off();') < off.index('held=false;') < off.index('pm_runtime_put_sync_suspend')
    assert transformed.count('gfx_coord_owner_pin();') == 4
    assert '__module_get(THIS_MODULE);' not in transformed
    cleanup = transformed[transformed.index('static void cleanup(void)'):transformed.index('/* Start only endpoint 1.')]
    gate = transformed[transformed.index(' ret=gfx_coord_owner_begin_on();'):transformed.index(' pr_info("m4rch ASC crashlog: cold control=')]
    failed = transformed[transformed.index('fail:\n') + len('fail:\n'):transformed.index('static void __exit')]
    retirement = transformed[transformed.index(' if (gfx_coord_owner_retained()) retired=false;'):transformed.index('fail:\n')]
    lifetime = cleanup + '\nstatic int run_transformed_startup_gate(void) {\n int ret;\n' + gate + ' started=true; return 1;\n}\n'
    lifetime += '\nstatic int run_transformed_fail(int ret) {\n' + failed
    lifetime += '\nstatic int run_transformed_retirement(void) {\n bool retired=true;\n' + retirement + '}\n'
    off_gate = off[off.index(' ret=gfx_coord_owner_before_off();'):off.index(' gfx_poweroff_accounting_ok=gfx_poweroff_accounting("after-put");')]
    lifetime += '\nstatic int gfx_poweroff_snapshot_result,gfx_poweroff_pm_result;\nstatic bool gfx_poweroff_pm_attempted,gfx_reset_scope_attempted;\n'
    lifetime += 'static void gfx_reset_scope_protocol(const char *phase) {(void)phase;}\nstatic int gfx_reset_scope_result(const char *command,int ret) {(void)command;assert(gfx_poweroff_snapshot_result==ret);return ret;}\n'
    lifetime += 'static int run_transformed_off_gate(void) {int ret;\n' + off_gate + 'return gfx_poweroff_pm_result;}\n'
    legacy_snapshot = off[off.index('static int gfx_poweroff_snapshot('):off.index('static int gfx_reset_scope_snapshot(')]

    prefix = old['PREFIX']
    prefix = replace_once(prefix, '#include <assert.h>', '#include <assert.h>\n#include <stdarg.h>')
    prefix = replace_once(prefix, '#define GFX_NATIVE_COORDINATED_SCOPE_TRIAL 1', '#define GFX_NATIVE_COORDINATED_SCOPE_TRIAL 1\n#define GFX_NATIVE_STATUS_ZERO_TRIAL 1')
    prefix = replace_once(prefix, 'static bool seed_on_map;', 'static bool seed_on_map,bad_status_on_map,drop_request_write;\nstatic unsigned int drop_vote_number;\nstatic u64 status_raw_on_map;\nstatic char write_trace[32];\nstatic unsigned int write_trace_count;\nstatic char log_records[1024][2048];')
    prefix = replace_once(prefix, 'static void mock_log(const char *format,...){(void)format;log_calls++;}',
        'static void mock_log(const char *format,...) __attribute__((format(printf,1,2)));\n'
        'static void mock_log(const char *format,...){va_list ap;assert(log_calls<1024);va_start(ap,format);vsnprintf(log_records[log_calls],sizeof(log_records[0]),format,ap);va_end(ap);log_calls++;}\n'
        'static bool has_log(const char *text){for(unsigned int n=0;n<log_calls;n++)if(strstr(log_records[n],text))return true;return false;}')
    prefix = replace_once(prefix, 'pmp_memory=p;if(seed_on_map)', 'pmp_memory=p;memcpy((char *)p+0x18,&status_raw_on_map,8);if(bad_status_on_map){u64 bad=~0ULL;memcpy((char *)p+0x10,&bad,8);}if(seed_on_map)')
    prefix = replace_once(prefix, 'qwrites++;last_qwrite_offset=', 'qwrites++;write_trace[write_trace_count++]=\'Q\';last_qwrite_offset=')
    prefix = replace_once(prefix, 'memcpy((char *)pmp_memory+0x1e00,&v,8);memcpy((char *)pmp_memory+0x1e80,&v,8);', 'if(!drop_request_write)memcpy((char *)pmp_memory+0x1e00,&v,8);memcpy((char *)pmp_memory+0x1e80,&v,8);')
    prefix = replace_once(prefix, 'memcpy(p,&v,4);}', 'write_trace[write_trace_count++]=\'L\';if(lwrites!=drop_vote_number)memcpy(p,&v,4);}')
    suffix = old['SUFFIX']
    suffix = replace_once(suffix, 'cleanup_events=pm_puts=0;', 'cleanup_events=pm_puts=0;gfx_poweroff_pm_attempted=gfx_reset_scope_attempted=false;gfx_poweroff_snapshot_result=gfx_poweroff_pm_result=0;')
    suffix = replace_once(suffix, 'compatible=pm_enabled=pm_active=true;seed_on_map=false;', 'compatible=pm_enabled=pm_active=true;seed_on_map=bad_status_on_map=drop_request_write=false;drop_vote_number=0;status_raw_on_map=0;write_trace_count=0;memset(write_trace,0,sizeof(write_trace));memset(log_records,0,sizeof(log_records));')
    suffix = replace_once(suffix, 'reset();retained_refusal(-ENODATA);assert(!qwrites&&!lwrites);assert(gfx_coord_owner_session.on_attempted);', 'reset();bad_status_on_map=true;retained_refusal(-EIO);assert(!qwrites&&!lwrites);assert(gfx_coord_owner_session.on_attempted);')
    suffix = replace_once(suffix, 'reset();assert(run_transformed_startup_gate()==0);', 'reset();bad_status_on_map=true;assert(run_transformed_startup_gate()==0);')
    suffix = replace_once(suffix, 'reset();printf("adapter_cases=%u\\n",cases);return 0;', EXTRA_CASES + '\n reset();printf("adapter_cases=%u\\n",cases);return 0;')
    core = (HERE / 'gfx-coordinate-core.h').read_text()
    actual = adapter.replace('#include <linux/of_address.h>', '').replace('#include <linux/timekeeping.h>', '').replace('#include "gfx-coordinate-core.h"', core)
    source_text = prefix + legacy_snapshot + actual + lifetime + suffix
    with tempfile.TemporaryDirectory(prefix='gfx-native-status-owner-test-') as directory:
        directory = Path(directory)
        source, binary = directory / 'adapter.c', directory / 'adapter'
        source.write_text(source_text)
        command = ['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', '-fsanitize=address,undefined', '-g', str(source), '-o', str(binary)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError('Actual adapter/lifetime compilation failed:\n' + result.stderr)
        environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
        result = subprocess.run([str(binary)], capture_output=True, text=True, env=environment)
        if result.returncode:
            raise RuntimeError('Actual adapter RAM failed:\n' + result.stdout + '\n' + result.stderr)
        rejected = directory / 'wrong-profile.c'
        rejected.write_text(source_text.replace('#define GFX_NATIVE_STATUS_ZERO_TRIAL 1', ''))
        refusal = subprocess.run(command[:-3] + [str(rejected), '-o', str(directory / 'wrong-profile')], capture_output=True, text=True)
        assert refusal.returncode and 'Native STATUS success requires its distinct owner profile' in refusal.stderr
    assert baseline == {name: sha(frozen / name) for name in baseline}
    assert sha(FROZEN_HARNESS) == HARNESS_SHA
    input_paths = [Path(__file__), FROZEN_HARNESS,
        HERE / 'gfx-coordinate-owner.h', HERE / 'gfx-coordinate-core.h',
        HERE / 'prepare-native-status-owner.py']
    input_paths += [frozen / name for name in baseline]
    input_paths += [prepared / name for name in
        ['asc-graph-init.c', 'gfx-reset-scope.h', 'recovery-cycle.h',
         'gfx-coordinate-owner.h', 'gfx-coordinate-core.h', 'Makefile',
         'native-status-owner-source-receipt.json']]
    report = {
        'schema': 'm4rch.gfx-native-status.owner-ram-test.v1',
        'actual_adapter_ram_result': result.stdout.strip(),
        'adapter_sha256': ADAPTER_SHA, 'core_sha256': CORE_SHA,
        'harness_sha256': sha(Path(__file__)), 'frozen_harness_sha256': HARNESS_SHA,
        'preparer_sha256': sha(HERE / 'prepare-native-status-owner.py'),
        'baseline_source_pins': baseline,
        'actual_prepared_source_pins': {name: sha(prepared / name) for name in
            ['asc-graph-init.c', 'gfx-reset-scope.h', 'recovery-cycle.h', 'gfx-coordinate-owner.h', 'gfx-coordinate-core.h', 'Makefile']},
        'adapter_only_profile_and_passive_log_delta': True,
        'actual_transformed_startup_cleanup_failure_retirement_off_gate_replayed': True,
        'status_zero_request_before_votes_verified': True,
        'status_zero_is_ack_or_inactivity': False,
        'request_vote_readback_failure_retains_before_pm_put': True,
        'exactly_one_pm_put_after_off_completion': True,
        'native_profile_missing_compile_refused': True,
        'exported_OF_iterator_reference_balance_checked': True,
        'ASan_UBSan': True, 'LeakSanitizer': 'disabled: sandbox ptrace restriction',
        'hardware_actions': [], 'candidate_build_actions': [],
        'frozen_sources_unchanged': True,
        'inputs': [{'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}
                   for path in input_paths],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
