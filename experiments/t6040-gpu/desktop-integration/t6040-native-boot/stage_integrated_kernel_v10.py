#!/usr/bin/env python3
"""Prepare an independent kernel tree for the complete native integration."""
import argparse
import importlib.util
import json
import subprocess
from pathlib import Path
from stage_integrated_v10 import pin


def stage(base, output, bindings):
    if output.exists():
        raise ValueError('Use a new kernel stage; never modify the compiled base')
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['cp', '--reflink=auto', '-a', str(base), str(output)], check=True)
    names = ['drivers/soc/apple/rtkit.c', 'drivers/soc/apple/rtkit-internal.h',
             'include/linux/soc/apple/rtkit.h', 'rust/kernel/soc/apple/rtkit.rs',
             'rust/helpers/helpers.c']
    files = {name: (output / name).read_text() for name in names}
    base_pins = [pin(base / name) for name in names]
    for index, path in enumerate(bindings):
        spec = importlib.util.spec_from_file_location('kernel_binding_' + str(index), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.kernel_wiring(files)
    for name, text in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    receipt = dict(schema='m4rch.native-integrated-kernel.v10',
        base=str(base.resolve()), kernel=str(output.resolve()),
        base_pins=base_pins, bindings=[pin(path) for path in bindings],
        changed_sources=[pin(output / name) for name in files],
        hardware_actions=[], installed=False, trial_ready=False)
    (output.parent / 'kernel-source-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(kernel=str(output), changed_source_count=len(files), trial_ready=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--binding', type=Path, action='append', required=True)
    args = parser.parse_args()
    stage(args.base.resolve(), args.out.resolve(), [p.resolve() for p in args.binding])
