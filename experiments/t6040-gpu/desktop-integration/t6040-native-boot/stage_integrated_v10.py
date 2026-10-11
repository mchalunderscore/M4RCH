#!/usr/bin/env python3
"""Compose the complete current native source changes into one build owner.

This is source preparation, not a trial launcher. It keeps the input stage
immutable and records every source used by the subsequent whole-module build.
Optional source bindings are applied in order after completion integration.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

KIT = Path(__file__).resolve().parent


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def stage(base, output, bindings):
    source = base / 'source/linux/drivers/gpu/drm/asahi'
    files = {str(p.relative_to(source)): p.read_text()
             for p in sorted(source.rglob('*')) if p.is_file()}
    if 'g16_t6040_event_timeline_v9.rs' not in files:
        raise ValueError('Native timeline and completion stage required')
    receipts = []
    for index, path in enumerate(bindings):
        spec = importlib.util.spec_from_file_location('integrated_binding_' + str(index), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.wiring(files)
        receipts.append(pin(path))
    output.mkdir(parents=True, exist_ok=False)
    destination = output / 'source/linux/drivers/gpu/drm/asahi'
    owner = output / 'build-owner'
    for name, text in files.items():
        for root in (destination, owner):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    receipt = dict(schema='m4rch.native-integrated-source.v10',
        base=str(base.resolve()), bindings=receipts,
        base_sources=[pin(p) for p in sorted(source.rglob('*')) if p.is_file()],
        sources=[pin(p) for p in sorted(destination.rglob('*')) if p.is_file()],
        hardware_actions=[], trial_ready=False,
        validation='Whole-module compile follows source closure; no component trial')
    (output / 'integrated-source-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(stage=str(output), source_count=len(files), trial_ready=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--binding', type=Path, action='append', default=[])
    args = parser.parse_args()
    bindings = args.binding or [KIT / 'wire_telemetry_v9.py', KIT / 'wire_native_lifecycle_v10.py']
    stage(args.base.resolve(), args.out.resolve(), [p.resolve() for p in bindings])
