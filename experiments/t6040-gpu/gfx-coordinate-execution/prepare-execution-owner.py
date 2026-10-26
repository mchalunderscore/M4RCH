#!/usr/bin/env python3
"""Prepare a separate deferred-execution source profile; never build or load.

The frozen paired no-work candidate is an input only. Its core, adapter, draw,
graph and firmware recovery implementation remain byte-identical. Only the
typed dispatcher and distinct compile flag change.
"""
import argparse
import hashlib
import json
from pathlib import Path

EXPECTED = {
    'asc-graph-init.c': '5e6156de5894c93b97b7ae43f2e6cf00df698e0e14c3c380e62c4432b049a29b',
    'recovery-cycle.h': 'e465ccbc1365e2a745a9a6f7c6eaf91d64a785f62925dc2ad4243048fd5e9500',
    'Makefile': 'b27a9fa1dc6274af903ab3c73762df7b17ee6fa6913ae8c3ef0b18ab2bbe2dd4',
    'gfx-coordinate-core.h': '417179e014653c2b97e55888346cbda70c79a4166fe2a1ca191d741f7201ad01',
    'gfx-coordinate-owner.h': 'a9dc2ef9184464f50cb4fddc8d1710daac06d9b594054aaf569d467e2a7dda1a',
    'gfx-reset-scope.h': '4ad396fa170b694f7b7e00e37d7f88bbcd07b55ba44d767ee825a4cff8de7fff',
    'recovery-contract.h': '9bce940061421a78fde0e509fdeba59a8c66c3d5ab32c4faf59dd613c14d4b23',
    'graph-before.bin': '287f2c53bc6ef7ed226c4a2995b9d9904e7623acae9713af105be6b04fc690a9',
    'graph-receipt.json': '92771b8036464c8dc9bdadd1dd4e1458a6c5a9f95f87fbdac34696bd2b3af219',
    'backing.bin': '35112ef3c261673bda227a3867a0d2b9dd58ac89f35f7bba9c8c05f1dee118d3',
    'job-data.h': 'c18ede083b691fbd3044237aaf30eb1e34c775e9391d3c6f1bea8e61561e0913',
    'render-data.h': '3bdbf04b9a3219c8e818beb464b5f55626e8a9b3d184680e3fd05a6361c47cbd',
}
PROFILE = {
    'compile_macro': 'GFX_COORDINATED_EXECUTION_TRIAL',
    'startup_work_published': False,
    'maximum_submit_intents': 1,
    'minimum_completed_idle_recovery_cycles': 4,
    'confirmed_trace_off_required': True,
    'immutable_draw_preserved': True,
    'before_work_commands': ['sample', 'gfx-snapshot', 'control', 'recover',
                             'trace-off', 'submit', 'stop', 'gfx-poweroff'],
    'after_submit_intent_commands': ['sample', 'gfx-snapshot'],
    'after_submit_typed_sample_drains_mailbox': False,
    'healthy_async_receive_service_preserved': True,
    'stop_off_reset_restart_after_submit_intent': False,
    'paired_off_contingency_before_work_preserved': True,
    'all_backing_and_pm_retained_after_submit_intent': True,
    'work_execution_verified': False,
    'dma_retirement_verified': False,
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Execution insertion point changed: ' + repr(old[:100]))
    return source.replace(old, new, 1)


def transform_dispatcher(source):
    if hashlib.sha256(source.encode()).hexdigest() != EXPECTED['recovery-cycle.h']:
        raise ValueError('Frozen paired dispatcher changed')
    source = replace_once(source,
        'static unsigned int recovery_operation;\n',
        'static unsigned int recovery_operation;\n'
        '#ifdef GFX_COORDINATED_EXECUTION_TRIAL\n'
        '#ifndef RECOVERY_TRACE_MASK\n'
        '#error Deferred execution requires the existing four-cycle trace-off proof\n'
        '#endif\n'
        'static bool gfx_execution_submit_intent;\n'
        '#endif\n')
    source = replace_once(source,
        '#ifndef GFX_POWER_OFF_SCOPE_TRIAL\n unsigned int i;bool ok=true;\n#endif\n',
        '#if !defined(GFX_POWER_OFF_SCOPE_TRIAL) || defined(GFX_COORDINATED_EXECUTION_TRIAL)\n'
        ' unsigned int i;bool ok=true;\n#endif\n'
        '#ifdef GFX_COORDINATED_EXECUTION_TRIAL\n'
        ' bool gfx_execution_first_submit=false;\n'
        '#endif\n')
    source = replace_once(source,
        ' mutex_lock(&graph_io_lock);\n#ifdef GFX_POWER_OFF_SCOPE_TRIAL\n',
        ' mutex_lock(&graph_io_lock);\n'
        '#ifdef GFX_COORDINATED_EXECUTION_TRIAL\n'
        ' /* Consume every submit intent before any hardware-facing read, even\n'
        '  * when a later prerequisite refuses the batch. Never retry it. */\n'
        ' if(sysfs_streq(buf,"submit")) {\n'
        '  if(gfx_execution_submit_intent) {ret=-EALREADY;goto out;}\n'
        '  gfx_execution_submit_intent=true;gfx_execution_first_submit=true;\n'
        '  pr_info("m4rch gfx-coordinate-execution: submit_intent=1 publication_attempted=0 all_backing_retained=1\\n");\n'
        ' }\n'
        ' if(gfx_execution_submit_intent && !gfx_execution_first_submit &&\n'
        '    !sysfs_streq(buf,"sample") && !sysfs_streq(buf,"gfx-snapshot")) {\n'
        '  ret=-EPERM;goto out;\n'
        ' }\n'
        '#endif\n'
        '#ifdef GFX_POWER_OFF_SCOPE_TRIAL\n')
    source = replace_once(source,
        '#ifdef GFX_POWER_OFF_SCOPE_TRIAL\n if(sysfs_streq(buf,"stop"))',
        '#if defined(GFX_POWER_OFF_SCOPE_TRIAL) && !defined(GFX_COORDINATED_EXECUTION_TRIAL)\n'
        ' if(sysfs_streq(buf,"stop"))')
    source = replace_once(source,
        ' } else if(sysfs_streq(buf,"sample")) {\n#ifdef GFX_RESET_SCOPE_TRIAL\n',
        ' } else if(sysfs_streq(buf,"sample")) {\n'
        '#ifdef GFX_COORDINATED_EXECUTION_TRIAL\n'
        '  /* Typed diagnostics never drain the mailbox. The existing healthy\n'
        '   * asynchronous receive worker remains available for the batch. */\n'
        '  ret=gfx_poweroff_sample();goto out;\n'
        '#endif\n'
        '#ifdef GFX_RESET_SCOPE_TRIAL\n')
    source = replace_once(source,
        ' } else if(sysfs_streq(buf,"gfx-reset")) {\n'
        '  ret=gfx_reset_scope_reset();goto out;\n',
        '#ifndef GFX_COORDINATED_EXECUTION_TRIAL\n'
        ' } else if(sysfs_streq(buf,"gfx-reset")) {\n'
        '  ret=gfx_reset_scope_reset();goto out;\n'
        '#endif\n')
    source = replace_once(source,
        ' } else if(recovery_session_failed) {ret=-EIO;goto out;}\n',
        ' } else if(recovery_session_failed\n'
        '#ifdef GFX_COORDINATED_EXECUTION_TRIAL\n'
        '           || gfx_poweroff_gate_consumed || gfx_reset_scope_sealed ||\n'
        '              gfx_reset_scope_host_stopped || !held\n'
        '#endif\n'
        '          ) {ret=-EIO;goto out;}\n')
    source = replace_once(source,
        '#ifdef RECOVERY_TRACE_MASK\n  if(!recovery_trace_disabled) {ret=-EBUSY;goto out;}\n#endif\n',
        '#ifdef RECOVERY_TRACE_MASK\n'
        '  if(!recovery_trace_disabled) {ret=-EBUSY;goto out;}\n'
        '#ifdef GFX_COORDINATED_EXECUTION_TRIAL\n'
        '  if(recovery_completed_total<4) {ret=-EBUSY;goto out;}\n'
        '#endif\n'
        '#endif\n')
    return source


def prepare(source, destination):
    source, destination = source.resolve(), destination.resolve()
    if destination.exists() or source == destination or source in destination.parents:
        raise ValueError('Destination must be new and outside the frozen source')
    for name, expected in EXPECTED.items():
        if digest(source / name) != expected:
            raise ValueError('Frozen execution input changed: ' + name)
    transformed = transform_dispatcher((source / 'recovery-cycle.h').read_text())
    layout = json.loads((source / 'graph-receipt.json').read_text())
    if layout['recovery_trial']['work_submitted'] is not False or \
       layout['recovery_trial']['resident_session'] is not True or \
       layout['recovery_trial']['deferred_triangle_available'] is not True:
        raise ValueError('Expected retained idle fixture with deferred draw')
    makefile = (source / 'Makefile').read_text()
    if 'GFX_COORDINATED_EXECUTION_TRIAL' in makefile or 'GRAPH_JOINED_WORK_EXPERIMENT' in makefile:
        raise ValueError('Execution input profile is not the frozen idle coordinator')
    makefile += '\nccflags-y += -DGFX_COORDINATED_EXECUTION_TRIAL\n'
    inputs = sorted(p for p in source.iterdir() if p.is_file() and
                    (p.suffix in ('.c', '.h', '.bin', '.json') or p.name == 'Makefile') and
                    not p.name.endswith('.mod.c'))
    before = {p.name: digest(p) for p in inputs}
    destination.mkdir(parents=True)
    for path in inputs:
        (destination / path.name).write_bytes(path.read_bytes())
    (destination / 'recovery-cycle.h').write_text(transformed)
    (destination / 'Makefile').write_text(makefile)
    after = {p.name: digest(destination / p.name) for p in inputs}
    changed = sorted(name for name in before if before[name] != after[name])
    if changed != ['Makefile', 'recovery-cycle.h']:
        raise ValueError('Unexpected execution source delta: ' + repr(changed))
    if {p.name: digest(p) for p in inputs} != before:
        raise ValueError('Frozen input changed during preparation')
    receipt = {
        'schema': 'm4rch.gfx-coordinate-execution-source.v1',
        'source': str(source), 'destination': str(destination),
        'source_preparer': {'path': str(Path(__file__).resolve()), 'sha256': digest(Path(__file__))},
        'profile': PROFILE, 'changed_files': changed,
        'input_source_pins': [{'name': name, 'sha256': value} for name, value in before.items()],
        'output_source_pins': [{'name': name, 'sha256': value} for name, value in after.items()],
        'hardware_actions': [], 'build_actions': [], 'candidate_created': False,
        'qualification': 'Source-only bridge to the preserved once-only draw. No firmware recovery, submission, GPU completion, pixels or submitted-work teardown established.',
    }
    (destination / 'execution-owner-source-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    receipt = prepare(args.source, args.destination)
    print(json.dumps({'receipt': str(args.destination / 'execution-owner-source-receipt.json'),
                      'changed_files': receipt['changed_files'], 'hardware_actions': [], 'build_actions': []}))


if __name__ == '__main__':
    main()
