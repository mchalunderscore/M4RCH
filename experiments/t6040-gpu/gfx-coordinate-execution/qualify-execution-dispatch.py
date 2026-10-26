#!/usr/bin/env python3
"""Compile/run the actual transformed dispatcher with RAM-only dependencies."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CACHE_ASM = 'asm volatile("dc cvac, %0\\n\\tdc cvac, %1\\n\\tdsb sy" :: "r"(p),"r"(p+16) : "memory");'


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def function(source, name):
    anchor = 'static ssize_t ' + name + '('
    if source.count(anchor) != 1:
        raise ValueError('Dispatcher function is missing or ambiguous')
    start = source.index(anchor)
    opening = source.index('{', start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == '{':
            depth += 1
        elif source[index] == '}':
            depth -= 1
            if not depth:
                return source[start:index + 1] + '\n'
    raise ValueError('Unclosed dispatcher function')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path,
        default=REPO / 'out/gfx-native-coordinate/candidate/asc-graph-init')
    parser.add_argument('--output', type=Path,
        default=REPO / 'out/gfx-coordinate-execution/dispatcher-qualification.json')
    args = parser.parse_args()
    preparer_path = HERE / 'prepare-execution-owner.py'
    spec = importlib.util.spec_from_file_location('execution_dispatch_preparer', preparer_path)
    preparer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preparer)
    source = args.source.resolve()
    before = {name: sha((source / name).read_bytes()) for name in preparer.EXPECTED}
    if before != preparer.EXPECTED:
        raise ValueError('Frozen coordinator source pins differ')
    transformed = preparer.transform_dispatcher((source / 'recovery-cycle.h').read_text())
    actual = function(transformed, 'recovery_command_store')
    if actual.count(CACHE_ASM) != 1:
        raise ValueError('Exact cache-maintenance exclusion changed')
    replay = actual.replace(CACHE_ASM, 'ram_cache_clean(p);', 1)
    state = 'static bool gfx_execution_submit_intent;'
    if transformed.count(state) != 1:
        raise ValueError('Actual execution-intent declaration changed')
    compiler = shutil.which('cc')
    if not compiler:
        raise ValueError('No local C compiler for RAM qualification')
    runs = []
    with tempfile.TemporaryDirectory(prefix='m4rch-execution-dispatch-') as temporary:
        work = Path(temporary)
        (work / 'actual-execution-dispatch.inc').write_text(replay)
        (work / 'actual-recovery-contract.inc').write_bytes((source / 'recovery-contract.h').read_bytes())
        (work / 'actual-execution-state.inc').write_text('#ifdef GFX_COORDINATED_EXECUTION_TRIAL\n' + state + '\n#endif\n')
        for enabled in (False, True):
            target = work / ('dispatcher-execution' if enabled else 'dispatcher-no-work')
            command = [compiler, '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-parameter',
                '-Wno-sign-compare',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                '-DGFX_RESET_SCOPE_TRIAL', '-DGFX_POWER_OFF_SCOPE_TRIAL']
            if enabled:
                command.append('-DGFX_COORDINATED_EXECUTION_TRIAL')
            command += ['-I', str(work), str(HERE / 'test-execution-dispatch.c'), '-o', str(target)]
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
                replay_environment = os.environ.copy()
                replay_environment['ASAN_OPTIONS'] = 'detect_leaks=0'
                result = subprocess.run([str(target)], check=True, capture_output=True,
                                        text=True, env=replay_environment)
            except subprocess.CalledProcessError as error:
                raise ValueError('RAM dispatcher build/replay failed: ' +
                                 (error.stderr or error.stdout)) from error
            row = json.loads(result.stdout)
            if row.get('passed') is not True or row.get('hardware_access') is not False:
                raise ValueError('Unexpected dispatcher qualification result')
            row['sanitizers'] = ['address', 'undefined']
            runs.append(row)
    after = {name: sha((source / name).read_bytes()) for name in preparer.EXPECTED}
    if after != before:
        raise ValueError('Frozen source changed during RAM replay')
    paths = [Path(__file__), HERE / 'test-execution-dispatch.c', preparer_path]
    inputs = [{'path': str(path.resolve()), 'sha256': sha(path.read_bytes())} for path in paths]
    inputs += [{'path': str(source / name), 'sha256': digest} for name, digest in before.items()]
    receipt = {
        'schema': 'm4rch.gfx-coordinate-execution-dispatch-qualification.v1',
        'passed': True, 'hardware_access': False,
        'case_count': sum(row['case_count'] for row in runs), 'inputs': inputs,
        'runs': runs, 'hardware_actions': [], 'candidate_build_actions': [],
        'actual_transformed_dispatcher_sha256': sha(actual.encode()),
        'replayed_dispatcher_sha256': sha(replay.encode()),
        'excluded_exact_cache_asm_sha256': sha(CACHE_ASM.encode()),
        'frozen_inputs_unchanged': True,
        'qualification': 'Actual transformed C dispatcher compiled with ASan/UBSan and RAM-only dependencies. Execution macro and unchanged no-work dispatcher branches both replayed; intent precedes state/hardware-facing reads, later mutations close before those reads, and immutable publication/cache-event/producer/EP33 ordering is asserted.',
        'limitations': [
            'Exact existing cache-maintenance asm is replaced once with an instrumented RAM event; actual cache instructions and coherency are not executed.',
            'LeakSanitizer is disabled because the execution sandbox uses ptrace; AddressSanitizer and UndefinedBehaviorSanitizer remain enabled.',
            'Recovery/control/trace, MMIO, packet transport, snapshots and resource ownership are mock dependencies; their implementations and asynchronous receive worker are not requalified by this replay.',
            'No kernel candidate built or loaded; no firmware recovery, work fetch, GPU completion, pixels, DMA retirement, reset, restart or backing release established.',
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'receipt': str(args.output.resolve()), 'passed': True,
                     'hardware_access': False, 'case_count': receipt['case_count']}))


if __name__ == '__main__':
    main()
