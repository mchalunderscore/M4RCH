#!/usr/bin/env python3
"""Offline ASan/UBSan replay of the actual GFX reset resident-owner C.

No kernel module, device, sysfs, MMIO or GPU operation. Driver APIs, cache
maintenance and transport are bounded recording stubs; owner C is extracted
unchanged except its ARM cache-clean assembly in the unreachable submit branch.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / 'experiments/t6040-gpu/asc-graph-init'


def extract(source, name, result_type):
    start = source.index(f'static {result_type} {name}(')
    end = source.index('\n}\n', start) + 3
    return source[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=KIT / 'recovery-cycle.h')
    parser.add_argument('--owner', type=Path, default=KIT / 'gfx-reset-scope.h')
    parser.add_argument('--contract', type=Path, default=ROOT / 'out/recovery-dispatch/prepared/recovery-contract.h')
    parser.add_argument('--api-header', type=Path, default=ROOT / 'out/gfx-reset-capability/driver-api-v1/include/linux/soc/apple/pmgr-gfx-reset.h')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--native', action='store_true', help='Replay the distinct native command API path')
    args = parser.parse_args()
    source = args.source.read_text()
    functions = [extract(source, n, t) for n, t in
                 [('recovery_idle', 'bool'), ('recovery_sample', 'void'),
                  ('recovery_receive_worker', 'void')]]
    # The source declares the worker first; extract the definition, not its prototype.
    worker_start = source.index('static void recovery_receive_worker(struct work_struct *work)\n{')
    functions[2] = source[worker_start:source.index('\n}\n', worker_start) + 3]
    handler = extract(source, 'recovery_command_store', 'ssize_t')
    clean = 'asm volatile("dc cvac, %0\\n\\tdc cvac, %1\\n\\tdsb sy" :: "r"(p),"r"(p+16) : "memory");'
    assert handler.count(clean) == 1
    handler = handler.replace(clean, 'replay_cache_clean(p,p+16);')
    owner = args.owner.read_text()
    for forbidden in ('root_release(', 'iounmap(', 'pm_runtime_put', '__free_pages(',
                      'power_ack(', 'recovery_send(', 'recovery_messages(', 'recovery_write32('):
        assert forbidden not in owner, forbidden
    actual = '\n'.join(functions) + '\n' + owner + '\n' + handler
    harness = (KIT / 'test-gfx-reset-owner.c').read_text()
    with tempfile.TemporaryDirectory(prefix='m4rch-gfx-owner-replay-') as tmp:
        temp = Path(tmp)
        header = temp / 'include/linux/soc/apple/pmgr-gfx-reset.h'
        header.parent.mkdir(parents=True)
        header.write_bytes(args.api_header.read_bytes())
        (temp / 'include/linux/bits.h').write_text('#define BIT(n) (1U<<(n))\n')
        (temp / 'include/linux/types.h').write_text('/* u32 supplied by replay preamble. */\n')
        (temp / 'recovery-contract.h').write_bytes(args.contract.read_bytes())
        (temp / 'actual-owner.inc').write_text(actual)
        (temp / 'replay.c').write_text(harness)
        executable = temp / 'replay'
        command = ['cc', '-std=gnu11', '-O1', '-Wall', '-Wextra',
                   '-Wno-unused-variable', '-Wno-unused-function', '-Wno-unused-parameter',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                   '-I', str(temp / 'include'), str(temp / 'replay.c'), '-o', str(executable)]
        if args.native:
            command.insert(1, '-DGFX_RESET_NATIVE_SEQUENCE_TRIAL')
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        result = subprocess.run([str(executable)], capture_output=True, text=True,
                                env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'))
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
    print(result.stdout, end='')
    if args.output:
        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        report = dict(schema='m4rch-gfx-reset-owner-c-replay-v1', hardware_access=False,
                      native_command_profile=args.native,
                      inputs=[dict(path=str(p), sha256=sha(p)) for p in
                              (args.source, args.owner, args.contract, args.api_header,
                               KIT / 'test-gfx-reset-owner.c', Path(__file__))],
                      functions=['recovery_idle', 'recovery_sample', 'recovery_receive_worker',
                                 'gfx-reset-scope.h (complete)', 'recovery_command_store'],
                      sanitizer='ASan/UBSan; LSan disabled under managed ptrace sandbox',
                      output=result.stdout.splitlines(),
                      replacement='Only submit cache-clean ARM assembly replaced by recorder. API/MMIO/PM/transport are recording stubs.',
                      qualification='Owner guards and retained lifetime only; no real kernel concurrency, API provider lifetime, hardware reset coverage, firmware restart, cache coherence or DMA retirement proof.')
        args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
