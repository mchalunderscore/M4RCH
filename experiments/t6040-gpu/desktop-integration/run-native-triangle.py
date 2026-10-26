#!/usr/bin/env python3
"""Called by the combined trial owner after fresh-boot/module validation.

This client never loads a module or alters power/boot policy. Failure leaves the
child holding owners so the parent can collect the complete recovery transcript.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render-node', required=True)
    parser.add_argument('--expected-boot', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot != args.expected_boot:
        raise ValueError('Fresh boot identity changed since combined owner admission')
    receipt = json.loads((HERE / 'receipt.json').read_text())
    for name, record in receipt['files'].items():
        data = (HERE / name).read_bytes()
        if len(data) != record['bytes'] or hashlib.sha256(data).hexdigest() != record['sha256']:
            raise ValueError(f'Packaged artifact mismatch: {name}')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'attempt.json').write_text(json.dumps({
        'boot_id': boot, 'schema': receipt['schema'], 'render_node': args.render_node,
        'intent': 'One native render, completion fence and direct linear GEM readback',
        'receipt_sha256': hashlib.sha256((HERE / 'receipt.json').read_bytes()).hexdigest(),
        'compute_commands': 0, 'client_exit': None}, indent=2) + '\n')
    result = subprocess.run([str(HERE / 'native-triangle-uapi'), args.render_node,
        str(HERE / 'inputs'), str(args.output)])
    attempt = json.loads((args.output / 'attempt.json').read_text())
    attempt['client_exit'] = result.returncode
    pixels = args.output / 'triangle.rgba'
    if result.returncode == 0 and pixels.exists():
        data = pixels.read_bytes()
        def match(actual, expected, tolerance=2):
            return all(abs(a - b) <= tolerance for a, b in zip(actual, expected))
        background = [round(x * 255) for x in receipt['background_candidate']['float_rgba']]
        orientations = []
        for flipped in (False, True):
            def pixel(x, y):
                y = 63-y if flipped else y
                return data[(y*64+x)*4:(y*64+x)*4+4]
            passed = (len(data) == 16384 and data != bytes([165])*16384
                      and all(value == 255 for value in data[3::4]))
            passed &= match(pixel(2, 2), background)
            for sample in receipt['interior_reference_samples']:
                x, y = sample['pixel_y_up']
                passed &= match(pixel(x, y), sample['rgba8_nearest'], sample['tolerance_per_channel'])
            if passed: orientations.append('flipped' if flipped else 'y-up')
        attempt.update(pixel_validation_passed=bool(orientations), orientations=orientations,
                       target_sha256=hashlib.sha256(data).hexdigest())
    (args.output / 'attempt.json').write_text(json.dumps(attempt, indent=2) + '\n')
    if result.returncode != 0 or not attempt.get('pixel_validation_passed', False):
        raise SystemExit(1)

if __name__ == '__main__':
    main()
