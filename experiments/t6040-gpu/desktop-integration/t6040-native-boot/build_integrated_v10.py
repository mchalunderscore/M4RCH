#!/usr/bin/env python3
"""Build the joined native driver once from its complete source receipt."""
import argparse
import json
import subprocess
from pathlib import Path
from stage_integrated_v10 import pin


def build(stage, kernel):
    receipt_path = stage / 'integrated-source-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    if receipt['schema'] != 'm4rch.native-integrated-source.v10' or receipt['hardware_actions']:
        raise ValueError('Offline integrated source receipt required')
    source = stage / 'source/linux/drivers/gpu/drm/asahi'
    owner = stage / 'build-owner'
    inputs = []
    for row in receipt['sources']:
        path = Path(row['path'])
        path.relative_to(source)
        if pin(path) != row:
            raise ValueError('Source changed: ' + str(path))
        target = owner / path.relative_to(source)
        other = pin(target)
        if (other['bytes'], other['sha256']) != (row['bytes'], row['sha256']):
            raise ValueError('Build owner differs: ' + str(target))
        inputs.append(other)
    command = ['make', '-C', str(kernel), 'M=' + str(owner), 'LLVM=1', 'W=1', 'modules']
    log = stage / 'integrated-module-build.log'
    with log.open('xb') as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
    # Preserve the actual terminal result even when a postbuild check fails.
    report = dict(schema='m4rch.native-integrated-build.v10', command=command,
        returncode=result.returncode, log=pin(log), source_receipt=pin(receipt_path),
        hardware_actions=[], module_loaded=False, trial_ready=False)
    (stage / 'integrated-make-result.json').write_text(json.dumps(report, indent=2) + '\n')
    report['changed_sources'] = [row for row in inputs if pin(Path(row['path'])) != row]
    module = owner / 'asahi_m4.ko'
    report['module'] = pin(module) if result.returncode == 0 and module.is_file() else None
    report['whole_module_built'] = not result.returncode and not report['changed_sources'] and report['module'] is not None
    (stage / 'integrated-build-receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return result.returncode or (0 if report['whole_module_built'] else 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--kernel', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(build(args.stage.resolve(), args.kernel.resolve()))
