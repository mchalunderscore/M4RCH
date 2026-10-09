#!/usr/bin/env python3
"""Compile the distinct staged native actual C core with the existing fault-harness method."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
KIT = Path(__file__).resolve().parent
DRIVER_PIN = '93df185e68c3e69d428460db7fc725b85ed191f75d24753a0563536a0dd1da61'
HEADER_PIN = '22392cd82cfdabcc1796166612bbb1d7b935cc34111bc1bf930e72d8e328c71e'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('staged_driver', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    base_driver = ROOT / 'out/gfx-reset-kernel/linux/drivers/pmdomain/apple/pmgr-pwrstate.c'
    base_header = ROOT / 'out/gfx-reset-kernel/linux/include/linux/soc/apple/pmgr-gfx-reset.h'
    assert digest(base_driver) == DRIVER_PIN and digest(base_header) == HEADER_PIN
    source = args.staged_driver.read_text()
    start = source.index('/* BEGIN T6040 GFX NATIVE CORE:')
    end = source.index('/* END T6040 GFX NATIVE CORE. */', start)
    core = source[start:end]
    # Removing exactly the two additive blocks recovers every byte of the v1 driver.
    wrap_start = source.index('int apple_pmgr_t6040_gfx_native_probe(')
    wrap_end = source.index('MODULE_AUTHOR(', wrap_start)
    without_new = source[:wrap_start] + source[wrap_end:]
    native_end = without_new.index('static int apple_pmgr_ps_set(', start)
    without_new = without_new[:start] + without_new[native_end:]
    assert without_new == base_driver.read_text()
    public = args.staged_driver.parent / 'include/linux/soc/apple/pmgr-gfx-reset.h'
    header = public.read_text()
    header_start = header.index('/* Attempt bits are set before the call,')
    assert header[:header_start] + '#endif\n' == base_header.read_text()
    args.output.mkdir()
    (args.output / 'linux').mkdir()
    (args.output / 'linux/types.h').write_text('/* CPU-only harness provides u32. */\n')
    (args.output / 'linux/bits.h').write_text('/* CPU-only harness provides BIT. */\n')
    (args.output / 'pmgr-gfx-reset.h').write_bytes(public.read_bytes())
    (args.output / 'native-gfx-reset-core.inc').write_text(core)
    binary = args.output / 'test-gfx-native-reset-api'
    command = ['clang', '-std=c11', '-g', '-O1', '-Wall', '-Wextra', '-Werror',
               '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
               '-I' + str(args.output.resolve()), str(KIT / 'test-gfx-native-reset-api.c'),
               '-o', str(binary)]
    subprocess.run(command, check=True)
    environment = os.environ.copy()
    environment['ASAN_OPTIONS'] = 'detect_leaks=0'
    result = subprocess.run([str(binary)], check=True, capture_output=True, text=True,
                            env=environment)
    report = json.loads(result.stdout)
    report.update(schema='m4rch.gfx-native-reset-api-c-faults.v1', compiler_command=command,
                  actual_core_sha256=hashlib.sha256(core.encode()).hexdigest(),
                  staged_driver_sha256=digest(args.staged_driver), public_header_sha256=digest(public),
                  test_source_sha256=digest(KIT / 'test-gfx-native-reset-api.c'),
                  test_runner_sha256=digest(Path(__file__)), legacy_driver_recovered_exactly=True,
                  legacy_header_recovered_exactly=True, asan_ubsan=True, leak_sanitizer=False,
                  hardware_access=False, physical_acknowledgement_claimed=False,
                  qualification='Actual extracted native C core; independent fault/order/state model. '
                                'Provider/DT guards, real concurrency, MMIO/hardware are excluded.')
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
