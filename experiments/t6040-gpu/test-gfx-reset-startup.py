#!/usr/bin/env python3
"""Replay actual C startup admission and its guarded invocation, without hardware."""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / 'experiments/t6040-gpu/asc-graph-init'


def conditional_block(source, start):
    lines = source[start:].splitlines(keepends=True)
    depth = 0
    block = []
    for line in lines:
        directive = line.lstrip()
        if re.match(r'#\s*(if|ifdef|ifndef)\b', directive):
            depth += 1
        elif re.match(r'#\s*endif\b', directive):
            depth -= 1
        block.append(line)
        if depth == 0:
            return ''.join(block)
    raise AssertionError('Unbalanced source conditional')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=KIT / 'asc-graph-init.c')
    parser.add_argument('--header', type=Path, default=KIT / 'gfx-reset-startup.h')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('Preserve existing report: output must be new')
    source = args.source.read_text()
    feature_start = source.index('#ifdef GFX_RESET_SCOPE_TRIAL\n')
    feature = conditional_block(source, feature_start)
    assert feature.count('#include "gfx-reset-startup.h"') == 1
    assert source.count('#include "gfx-reset-startup.h"') == 1
    init_start = source.index('static int __init hello_init(void)\n{')
    admission_start = source.index('#ifdef GFX_RESET_SCOPE_TRIAL\n', init_start)
    admission = conditional_block(source, admission_start)
    assert admission.count('gfx_reset_scope_startup_admission(') == 1
    assert source.count('gfx_reset_scope_startup_admission(') == 1
    assert re.fullmatch(
        r'#ifdef GFX_RESET_SCOPE_TRIAL\s+'
        r'ret=gfx_reset_scope_startup_admission\(run_gate,resident_session,\s*'
        r'request_shutdown,warm_restart,release_on_shutdown\);\s*'
        r'if\(ret\) return ret;\s*#endif\s*', admission)
    # Nothing can acquire or publish ownership before admission: this actual
    # hello_init prefix contains declarations only and no function call.
    prefix = source[source.index('{', init_start) + 1:admission_start]
    without_comments = re.sub(r'/\*.*?\*/|//[^\n]*', '', prefix, flags=re.S)
    assert not re.search(r'\b\w+\s*\(', without_comments)
    first_allocation = source.index('ret=root_prepare(false);', init_start)
    assert admission_start + len(admission) < first_allocation
    for name in ('of_find_node_by_path(', 'platform_device_register_simple(',
                 'pm_runtime_resume_and_get(', 'request_mem_region(', 'ioremap(',
                 'readl(', 'writel('):
        assert source.index(name, init_start) > admission_start + len(admission), name
    harness = KIT / 'test-gfx-reset-startup.c'
    outputs = []
    matrix = []
    with tempfile.TemporaryDirectory(prefix='m4rch-gfx-startup-replay-') as tmp:
        temp = Path(tmp)
        (temp / 'gfx-reset-startup.h').write_bytes(args.header.read_bytes())
        (temp / 'actual-feature-guard.inc').write_text(feature)
        (temp / 'actual-startup-admission.inc').write_text(admission)
        (temp / 'replay.c').write_bytes(harness.read_bytes())
        for enabled in (False, True):
            defines = (['-DGFX_RESET_SCOPE_TRIAL', '-DGRAPH_RECOVERY_EXPERIMENT',
                        '-DGRAPH_JOINED_INIT_EXPERIMENT'] if enabled else [])
            exe = temp / ('feature-on' if enabled else 'feature-off')
            command = ['cc', '-std=gnu11', '-O1', '-Wall', '-Wextra', '-Werror',
                       '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                       '-I', str(temp), *defines, str(temp / 'replay.c'), '-o', str(exe)]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True,
                                    env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'))
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            outputs.extend(result.stdout.splitlines())
        # Compile the actual top-level feature guard for every required fixture
        # combination, ensuring this change retains its feature-on restrictions.
        probe = temp / 'feature-probe.c'
        probe.write_text('#include <stdbool.h>\n#include <errno.h>\n' + feature)
        for enabled, recovery, joined, work in itertools.product((False, True), repeat=4):
            names = ['GFX_RESET_SCOPE_TRIAL', 'GRAPH_RECOVERY_EXPERIMENT',
                     'GRAPH_JOINED_INIT_EXPERIMENT', 'GRAPH_JOINED_WORK_EXPERIMENT']
            defines = ['-D' + name for name, present in zip(names, (enabled, recovery, joined, work)) if present]
            result = subprocess.run(['cc', '-E', '-I', str(temp), *defines, str(probe)],
                                    capture_output=True, text=True)
            accepted = result.returncode == 0
            expected = not enabled or (recovery and joined and not work)
            assert accepted == expected, (defines, result.stderr)
            assert ('gfx_reset_scope_startup_admission' in result.stdout) == enabled
            matrix.append(dict(feature=enabled, recovery=recovery, joined=joined,
                               startup_work=work, accepted=accepted))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = dict(schema='m4rch.gfx-reset-startup-admission-replay.v1',
                  hardware_access=False,
                  inputs=[dict(path=str(p), sha256=sha(p)) for p in
                          (args.source, args.header, harness, Path(__file__))],
                  actual_C_feature_on_cases=80, actual_C_feature_off_prefix_cases=80,
                  sanitizer='ASan/UBSan; LSan disabled under managed ptrace sandbox',
                  placement_verified='Actual hello_init prefix has no calls before admission; admission precedes root allocation, provider acquisition, PM and MMIO.',
                  source_replacement='None in the helper, feature guard, or admission invocation; the subsequent allocation is a recorder in the replay.',
                  feature_configuration_cases=matrix,
                  output=outputs,
                  limits='Startup admission only; later startup, kernel/module lifecycle, scheduling, PM/MMIO and hardware coverage are not exercised.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('\n'.join(outputs))
    print('actual_feature_configuration_cases=' + str(len(matrix)))
    print('report=' + str(args.output))


if __name__ == '__main__':
    main()
