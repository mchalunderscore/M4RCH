#!/usr/bin/env python3
"""Sequential bounded wake trials on twelve cores; disable saved WFI on exit."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import selectors
import shutil
import subprocess
import time

PARAM = Path('/sys/module/cpuidle_apple/parameters')
BUDGET = PARAM / 'experimental_t6040_idle_wfi_budget'
TARGET = PARAM / 'experimental_t6040_idle_wfi_cpu'
PROGRESS = PARAM / 'experimental_t6040_idle_wfi_progress'


def parse_progress(text):
    tokens = re.findall(r'cpu(\d+) attempts=(\d+) completed=(\d+) ', text)
    tail = re.search(r'budget=(\d+) target=(\d+)\s*$', text)
    if len(tokens) != 12 or [int(x[0]) for x in tokens] != list(range(12)) or tail is None:
        raise ValueError('Malformed all-core progress snapshot')
    expected = ''.join('cpu%s attempts=%s completed=%s ' % x for x in tokens)
    if not text.startswith(expected) or text[len(expected):] != tail.group(0):
        raise ValueError('Unexpected progress data')
    attempts = {int(c):int(a) for c,a,b in tokens}
    completed = {int(c):int(b) for c,a,b in tokens}
    budget,target = map(int,tail.groups())
    if any(not 0 <= completed[c] <= attempts[c] <= 64 for c in range(12)) or not 0 <= budget <= 64 or not 0 <= target < 12:
        raise ValueError('Out-of-range progress snapshot')
    return {'attempts':attempts,'completed':completed,'budget':budget,'target':target}


def progress():
    return parse_progress(PROGRESS.read_text())


def write(path, value):
    with path.open('w') as stream:
        stream.write(str(value) + '\n')


def settled(cpu=None, count=None, timeout=10):
    end = time.monotonic() + timeout
    while True:
        p = progress()
        if p['attempts'] == p['completed'] and (cpu is None or p['completed'][cpu] == count):
            return p
        if time.monotonic() >= end:
            raise ValueError(f'Wake budget did not complete: {p}')
        time.sleep(0.05)


def verify_files(kit):
    for line in (kit / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = kit / name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Kit checksum failed: {name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    output = parser.parse_args().output
    kit = Path(__file__).resolve().parent
    verify_files(kit)
    spec = importlib.util.spec_from_file_location('capture', kit / 'collect-saved.py')
    capture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(capture)
    receipt = json.loads((kit / 'build.json').read_text())
    if receipt.get('allcore_candidate') is not True:
        raise ValueError('Builder must provide allcore_candidate receipt for exact new build')
    if os.geteuid() != 0 or platform.machine() != 'aarch64' or capture.kernel_build_id() != receipt['build_id']:
        raise ValueError('Root on the exact batch kernel is required')
    compatible = Path('/proc/device-tree/compatible').read_bytes().split(b'\0')
    if not {b'apple,t6040', b'apple,j614s'} <= set(compatible):
        raise ValueError('Wrong board')
    if Path('/sys/module/m4rch_pmu_fixed').exists():
        raise ValueError('Keep the fixed-counter helper unloaded')
    for name in ('experimental_t6040_idle', 'experimental_t6040_idle_trace', 'experimental_t6040_idle_wfi_only'):
        if (PARAM / name).read_text().strip() not in ('Y', '1'):
            raise ValueError(f'Opt-in absent: {name}')
    online = (Path('/sys/devices/system/cpu/online').read_text().strip())
    if online != '0-11':
        raise ValueError('Expected all twelve cores online; do not hotplug')
    initial = settled()
    if initial != {'attempts':dict.fromkeys(range(12),0),'completed':dict.fromkeys(range(12),0),'budget':0,'target':4}:
        raise ValueError(f'Not an untouched first batch boot: {initial}')
    output.mkdir(parents=True, exist_ok=False)
    worker = output / 'state-worker'
    shutil.copyfile(kit / 'state-worker', worker)
    worker.chmod(0o700)  # /boot may disallow execution.
    def save(name, data):
        with (output / name).open('w') as stream:
            json.dump(data, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
    def journal(name):
        result = subprocess.run(['journalctl', '-b', '-k', '--no-pager'], capture_output=True, text=True, timeout=30)
        (output / name).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise ValueError('Kernel journal capture failed')
        return result.stdout
    save('identity.json', {'build_id': capture.kernel_build_id(), 'cmdline': capture.read('/proc/cmdline'), 'initial': initial})
    try:
        write(BUDGET, 0)
        settled()
        journal('journal-before.txt')
        for number, (cpu, absolute_budget) in enumerate(((cpu,b) for cpu in (1,2,3,4,0,5,6,7,8,9,10,11) for b in (1,4)), 1):
            write(BUDGET, 0)
            before = settled()
            write(TARGET, cpu)
            save(f'phase-{number}-before.json', {'cpu': cpu, 'absolute_budget': absolute_budget, 'progress': before, 'states': capture.states()})
            with subprocess.Popen([str(worker), str(cpu), '32'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
                try:
                    with selectors.DefaultSelector() as selector:
                        selector.register(process.stdout, selectors.EVENT_READ)
                        if not selector.select(5) or process.stdout.readline().strip() != 'READY':
                            raise ValueError('Integrity worker failed its first sleep or readiness check')
                    write(BUDGET, absolute_budget)
                    stdout, stderr = process.communicate(timeout=20)
                    save(f'phase-{number}-worker.json', {'returncode': process.returncode, 'stdout': stdout, 'stderr': stderr})
                    if process.returncode:
                        raise ValueError(f'State worker failed in phase {number}; stopping')
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
            after = settled(cpu, absolute_budget)
            write(BUDGET, 0)
            settled()
            save(f'phase-{number}-after.json', {'progress': after, 'states': capture.states()})
            text = journal(f'phase-{number}-journal.txt')
            if re.search(r'M4RCH_FAULT|CPU_PM_ENTER rejected|BUG:|Oops:|Internal error:', text):
                raise ValueError('Kernel fault/rejection marker; stopping')
        save('result.json', {'completed': True, 'progress': progress(), 'limitation': 'Bounded wake and user GPR/SIMD/FP control checks; not all architectural/debug state or continuous idle qualification.'})
    except BaseException as error:
        save('error.json', {'error': str(error)})
        raise
    finally:
        write(BUDGET, 0)
        journal('journal-final.txt')
        os.sync()
    print(output)


if __name__ == '__main__':
    main()
