#!/usr/bin/env python3
"""Build only a fresh staged Gravity module; persist make status before postchecks."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def write_new(path, value):
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def build(staging, qualification, kernel):
    staging.relative_to(ROOT / 'out')
    kernel.relative_to(ROOT / 'out')
    q = json.loads(qualification.read_text())
    if not q['complete'] or q['hardware_actions'] or q['normal_startup_enabled']:
        raise ValueError('Completed offline qualification of the gated native source required')
    for row in q['inputs']:
        if pin(row['path']) != row:
            raise ValueError('Qualified input changed: ' + row['path'])
    stage_receipt = staging / 'stage-receipt.json'
    stage = json.loads(stage_receipt.read_text())
    if stage['schema'] != 'm4rch.gravity-native-t6040-components.stage.v3':
        raise ValueError('Native v3 source stage required')
    source = staging / 'source/linux/drivers/gpu/drm/asahi'
    owner = staging / 'build-owner'
    inputs = []
    for row in stage['source_files']:
        path = Path(row['path'])
        if path.name.endswith(('.mod', '.mod.c', '.o', '.ko', '.cmd')) or path.name in {
                'Module.symvers', 'modules.order'}:
            raise ValueError('Generated kbuild state was incorrectly staged as immutable input')
        if pin(path) != row:
            raise ValueError('Staged source changed: ' + str(path))
        other = owner / path.relative_to(source)
        mapped = pin(other)
        if (mapped['sha256'], mapped['bytes']) != (row['sha256'], row['bytes']):
            raise ValueError('Build source differs: ' + str(other))
        inputs.append(mapped)
    kernel_inputs = [pin(kernel / name) for name in
                     ['.config', 'Module.symvers', 'include/config/kernel.release']]
    command = ['make', '-C', str(kernel), 'M=' + str(owner), 'LLVM=1', 'W=1', 'modules']
    log = staging / 'module-build.log'
    result = staging / 'module-make-result.json'
    closure = staging / 'module-build-closure.json'
    if any(path.exists() for path in [log, result, closure]):
        raise ValueError('This stage already has a build attempt; observe its handle/result instead of restarting')
    write_new(staging / 'module-build-intent.json', {'command': command,
        'qualification': pin(qualification), 'stage_receipt': pin(stage_receipt),
        'source_input_pins': inputs, 'kernel_input_pins': kernel_inputs,
        'builder': pin(__file__), 'hardware_actions': [], 'kernel_rebuilt': False})
    with log.open('xb') as stream:
        process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
    # Save make's actual terminal status before interpreting generated artifacts
    # or comparing source pins. A later exception cannot erase that evidence.
    write_new(result, {'schema': 'm4rch.gravity-native-t6040-components.make.v3',
        'command': command, 'returncode': process.returncode, 'log': pin(log),
        'hardware_actions': [], 'kernel_rebuilt': False, 'module_loaded': False})
    changed = []
    for row in inputs + kernel_inputs:
        try:
            actual = pin(row['path'])
        except OSError as error:
            actual = {'error': str(error)}
        if actual != row:
            changed.append({'expected': row, 'actual': actual})
    module = owner / 'asahi_m4.ko'
    artifact = pin(module) if module.is_file() and process.returncode == 0 else None
    report = {'schema': 'm4rch.gravity-native-t6040-components.build.v3',
        'make_result': pin(result), 'make_returncode': process.returncode,
        'module': artifact, 'immutable_input_changes': changed,
        'source_count': len(inputs), 'normal_startup_enabled': False,
        'complete_native_boot_bundle': False, 'hardware_actions': [],
        'module_loaded': False, 'kernel_rebuilt': False,
        'full_module_compiled_and_linked': process.returncode == 0 and artifact is not None and not changed}
    write_new(closure, report)
    print(json.dumps(report))
    if process.returncode:
        return process.returncode
    return 1 if changed or artifact is None else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('staging', type=Path)
    parser.add_argument('--qualification', type=Path)
    parser.add_argument('--kernel', type=Path, default=ROOT / 'out/gfx-native-reset-kernel/linux')
    args = parser.parse_args()
    staging = args.staging.resolve()
    qualification = (args.qualification or staging / 'qualification-v1/qualification.json').resolve()
    raise SystemExit(build(staging, qualification, args.kernel.resolve()))
