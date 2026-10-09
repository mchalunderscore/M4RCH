#!/usr/bin/env python3
"""Replay the actual bounded GFX power-off owner C in RAM with ASan/UBSan.

No kernel module, device, sysfs, MMIO or GPU operation. Provider, runtime PM,
cache maintenance and transport effects are recording stubs. The idle/sample,
receive worker, full owner header and typed command handler are actual C.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[2]


def extract(source, name, result_type):
    signature = f'static {result_type} {name}('
    start = source.index(signature)
    while source.index('\n', start) < source.index('{', start):
        # The worker has an earlier prototype; locate its actual definition.
        line_end = source.index('\n', start)
        if source[start:line_end].rstrip().endswith(';'):
            start = source.index(signature, line_end)
            continue
        break
    return source[start:source.index('\n}\n', start) + 3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=KIT / 'recovery-cycle.h')
    parser.add_argument('--owner', type=Path, default=KIT / 'gfx-poweroff-scope.h')
    parser.add_argument('--contract', type=Path, default=ROOT / 'out/gfx-native-reset-owner/candidate/asc-graph-init/recovery-contract.h')
    parser.add_argument('--api-header', type=Path, default=ROOT / 'out/gfx-native-reset-kernel/linux/include/linux/soc/apple/pmgr-gfx-reset.h')
    parser.add_argument('--output', type=Path, default=ROOT / 'out/gfx-poweroff-scope/owner-validation.json')
    args = parser.parse_args()
    source = args.source.read_text()
    functions = [extract(source, n, t) for n, t in
                 [('recovery_idle', 'bool'), ('recovery_sample', 'void'),
                  ('recovery_receive_worker', 'void')]]
    handler = extract(source, 'recovery_command_store', 'ssize_t')
    clean = 'asm volatile("dc cvac, %0\\n\\tdc cvac, %1\\n\\tdsb sy" :: "r"(p),"r"(p+16) : "memory");'
    assert handler.count(clean) <= 1
    if clean in handler:
        handler = handler.replace(clean, 'replay_cache_clean(p,p+16);')
    owner = args.owner.read_text()
    for forbidden in ('root_release(', 'iounmap(', '__free_pages(',
                      'power_ack(', 'recovery_send(', 'recovery_messages(',
                      'recovery_write32(', 'pm_runtime_get',
                      'apple_pmgr_t6040_gfx_checked_pulse(',
                      'apple_pmgr_t6040_gfx_native_probe('):
        assert forbidden not in owner, forbidden
    assert owner.count('pm_runtime_put_sync_suspend(') == 1
    actual = '\n'.join(functions) + '\n' + owner + '\n' + handler
    harness_path = KIT / 'test-gfx-poweroff-owner.c'
    with tempfile.TemporaryDirectory(prefix='m4rch-gfx-poweroff-owner-') as tmp:
        temp = Path(tmp)
        header = temp / 'include/linux/soc/apple/pmgr-gfx-reset.h'
        header.parent.mkdir(parents=True)
        header.write_bytes(args.api_header.read_bytes())
        (temp / 'include/linux/bits.h').write_text('#define BIT(n) (1U<<(n))\n')
        (temp / 'include/linux/types.h').write_text('/* u32 supplied by replay preamble. */\n')
        (temp / 'recovery-contract.h').write_bytes(args.contract.read_bytes())
        (temp / 'actual-owner.inc').write_text(actual)
        (temp / 'replay.c').write_bytes(harness_path.read_bytes())
        executable = temp / 'replay'
        command = ['cc', '-std=gnu11', '-O1', '-Wall', '-Wextra',
                   '-Wno-unused-variable', '-Wno-unused-function', '-Wno-unused-parameter',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                   '-DGFX_RESET_SCOPE_TRIAL', '-DGFX_POWER_OFF_SCOPE_TRIAL',
                   '-I', str(temp / 'include'), str(temp / 'replay.c'), '-o', str(executable)]
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
        report = dict(schema='m4rch.gfx-poweroff-owner-c-replay.v1', hardware_access=False,
                      inputs=[dict(path=str(p), sha256=sha(p)) for p in
                              (args.source, args.owner, args.contract, args.api_header,
                               harness_path, Path(__file__))],
                      functions=['recovery_idle', 'recovery_sample', 'recovery_receive_worker',
                                 'gfx-poweroff-scope.h (complete)', 'recovery_command_store'],
                      sanitizer='ASan/UBSan; LSan disabled under managed ptrace sandbox',
                      output=result.stdout.splitlines(),
                      replacement='Only optional unreachable submit cache-clean ARM assembly replaced by recorder. Provider/PM/MMIO/cache/transport are recording stubs.',
                      qualification='Owner admission, one PM put, accounting and bounded provider observations only; no real runtime PM/genpd concurrency, hardware shutdown, cache coherence, power-off coverage or DMA retirement proof.')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
