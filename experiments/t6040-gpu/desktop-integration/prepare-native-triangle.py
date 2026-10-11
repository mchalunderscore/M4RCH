#!/usr/bin/env python3
"""Package one native DRM render trial offline; never opens a DRM device."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def checked(directory, receipt, name):
    data = (directory / name).read_bytes()
    record = receipt['files'][name]
    if len(data) != record['bytes'] or sha(data) != record['sha256']:
        raise ValueError(f'Input receipt mismatch: {directory / name}')
    return data

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--draw', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    draw_bytes = (args.draw / 'receipt.json').read_bytes()
    target_bytes = (args.target / 'receipt.json').read_bytes()
    draw, target = json.loads(draw_bytes), json.loads(target_bytes)
    if (int(draw['shader_base'], 0) != 1 << 40 or
        int(target['shader_base'], 0) != 1 << 40 or
        target['draw_receipt_sha256'] != sha(draw_bytes) or
        int(draw['candidate']['context_base'], 0) != 0x1000000000 or
        int(target['target']['address'], 0) != 0x2000010000 or
        target['target']['width'] != 64 or target['target']['height'] != 64 or
        target['target']['stride_bytes'] != 256 or
        target['background_candidate']['launch_byte_offset'] != '0x30c00' or
        target['tile_store']['launch_offset'] != '0x30800'):
        raise ValueError('Saved fixed-address graphics profile mismatch')
    state = bytearray(0x4000)
    for root, receipt, name, offset in (
        (args.draw, draw, 'vdm.bin', 0), (args.draw, draw, 'ppp.bin', 0x1000),
        (args.target, target, 'scissor.bin', 0x2000),
        (args.target, target, 'depth-bias.bin', 0x2040)):
        data = checked(root, receipt, name)
        if offset + len(data) > len(state):
            raise ValueError('State extends beyond the bound page')
        state[offset:offset + len(data)] = data
    usc = checked(args.target, target, 'usc-with-target-store.bin')
    sentinel = checked(args.target, target, 'target-sentinel.bin')
    if len(usc) != 0x50000 or sentinel != bytes([165]) * 0x4000:
        raise ValueError('Shader/linear target size mismatch')
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = args.output / 'inputs'
    inputs.mkdir()
    for name, data in [('usc.bin', usc), ('target.bin', sentinel), ('state.bin', state)]:
        (inputs / name).write_bytes(data)
    header = args.kernel / 'include/uapi/drm/asahi_drm.h'
    shutil.copy2(header, args.output / 'asahi_drm.h')
    shutil.copy2(HERE / 'native-triangle-uapi.c', args.output)
    shutil.copy2(HERE / 'run-native-triangle.py', args.output)
    flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'libdrm'], text=True).split()
    command = ['cc', '-std=gnu11', '-O2', '-Wall', '-Wextra',
               '-I' + str(args.output.resolve()), str(args.output / 'native-triangle-uapi.c'),
               '-o', str(args.output / 'native-triangle-uapi'), *flags]
    subprocess.run(command, check=True)
    files = {str(path.relative_to(args.output)): {'bytes': path.stat().st_size,
             'sha256': sha(path.read_bytes())} for path in args.output.rglob('*') if path.is_file()}
    receipt = {'schema': 't6040-native-triangle-uapi-v1', 'files': files,
        'draw_receipt_sha256': sha(draw_bytes), 'target_receipt_sha256': sha(target_bytes),
        'kernel_uapi_sha256': sha(header.read_bytes()), 'build_command': command,
        'submissions': 1, 'compute_commands': 0,
        'render': {'width': 64, 'height': 64, 'samples': 1, 'layers': 1,
                   'vertex_count': 3, 'shader_base': hex(1 << 40),
                   'target_va': '0x2000010000', 'state_va': '0x1000000000'},
        'interior_reference_samples': target['interior_reference_samples'],
        'background_candidate': target['background_candidate'],
        'trial_ready': False, 'hardware_executed': False,
        'requirements': ['Parent combined launcher validates kernel/module hashes and fresh boot',
            'Matching hash-pinned integrated driver loaded with native_t6040_experiment=1',
            'Parent captures native boot/power/dispatch/completion/recovery transcript',
            'On failure the client holds all owners until the parent finishes capture'],
        'limits': ['Saved compiler/state inputs remain hardware-unproved',
            'One render and linear CPU readback; no compute or desktop presentation',
            'No forced recovery on success; failure invokes the DRM worker recovery path'],
        'pixel_validation': 'Require successful fence, fresh sentinel replacement, background '
            'and the saved interior samples; allow y-up and vertically flipped row orientation'}
    (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(args.output)

if __name__ == '__main__':
    main()
