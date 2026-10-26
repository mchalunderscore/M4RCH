#!/usr/bin/env python3
"""Compile the staged actual checked-driver core in a CPU-only fault harness."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

BASE_PIN = 'c0484db37d902b17a5a8132dddb19fdd15a153eaec6caab14b69ad941b8b72ab'
ROOT = Path(__file__).resolve().parents[3]
KIT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('staged_driver', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    base = ROOT / 'out/gpu-gravity-contract/linux/drivers/pmdomain/apple/pmgr-pwrstate.c'
    assert hashlib.sha256(base.read_bytes()).hexdigest() == BASE_PIN
    source = args.staged_driver.read_text()
    start = source.index('/* BEGIN T6040 GFX CHECKED CORE:')
    end = source.index('/* END T6040 GFX CHECKED CORE. */', start)
    core = source[start:end]
    public = args.staged_driver.parent / 'include/linux/soc/apple/pmgr-gfx-reset.h'
    args.output.mkdir()
    (args.output / 'linux').mkdir()
    (args.output / 'linux/types.h').write_text('/* CPU-only harness uses its own u32 typedef. */\n')
    (args.output / 'linux/bits.h').write_text('/* CPU-only harness uses its own BIT macro. */\n')
    (args.output / 'pmgr-gfx-reset.h').write_bytes(public.read_bytes())
    (args.output / 'checked-gfx-reset-core.inc').write_text(core)
    binary = args.output / 'test-gfx-reset-api'
    command = ['clang', '-std=c11', '-g', '-O1', '-Wall', '-Wextra', '-Werror',
               '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
               '-I' + str(args.output.resolve()), str(KIT / 'test-gfx-reset-api.c'),
               '-o', str(binary)]
    subprocess.run(command, check=True)
    environment = os.environ.copy()
    # The managed sandbox uses ptrace; LSan cannot inspect threads there.
    environment['ASAN_OPTIONS'] = 'detect_leaks=0'
    result = subprocess.run([str(binary)], check=True, capture_output=True, text=True,
                            env=environment)
    report = json.loads(result.stdout)
    report.update(schema='m4rch.gfx-reset-api-c-faults.v1', compiler_command=command,
                  actual_core_sha256=hashlib.sha256(core.encode()).hexdigest(),
                  staged_driver_sha256=hashlib.sha256(args.staged_driver.read_bytes()).hexdigest(),
                  public_header_sha256=hashlib.sha256(public.read_bytes()).hexdigest(),
                  test_source_sha256=hashlib.sha256((KIT / 'test-gfx-reset-api.c').read_bytes()).hexdigest(),
                  test_runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  asan_ubsan=True, leak_sanitizer=False, hardware_access=False,
                  qualification='Actual extracted C core; independent fault/order/state model. '
                                'Kernel device/DT provider guards and real concurrency/hardware are excluded.')
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
