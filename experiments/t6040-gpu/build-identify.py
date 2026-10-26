#!/usr/bin/env python3
"""Build the leaf preflight module in an already reconstructed maintained tree.

No installation, DT mutation, module loading, or GPU access occurs here.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'lib'))
import hardware_profile

RELEASE = '7.1.3-m4rch-gpu-id'
KCONFIG = '''\nconfig M4RCH_GPU_IDENTIFY
\ttristate "T6040 GPU identification preflight"
\tdepends on RUST && ARM64 && ARCH_APPLE && PAGE_SIZE_16KB
'''
MAKEFILE = '\nobj-$(CONFIG_M4RCH_GPU_IDENTIFY) += m4rch_gpu_identify.o\n'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(tree, config, receipt):
    protected = {
        x['source']: x['result_source_sha256']
        for x in [*hardware_profile.USB_CABLE_FIXES,
                  hardware_profile.FRAMEBUFFER_FIX,
                  hardware_profile.CPUFREQ_SNAPSHOT,
                  hardware_profile.EARLY_FAULT,
                  hardware_profile.MAINTAINED_WFI]
    }
    for source, expected in protected.items():
        if digest(tree / source) != expected:
            raise ValueError('Maintained driver mismatch: ' + source)
    for name, addition, marker in [
        ('Kconfig', KCONFIG, 'config M4RCH_GPU_IDENTIFY'),
        ('Makefile', MAKEFILE, 'obj-$(CONFIG_M4RCH_GPU_IDENTIFY)'),
    ]:
        path = tree / 'drivers/gpu/drm/asahi' / name
        text = path.read_text()
        if marker in text:
            if text.count(marker) != 1 or addition.strip() not in text:
                raise ValueError('Conflicting identification build wiring: ' + name)
        else:
            path.write_text(text + addition)
    parent = tree / 'drivers/gpu/drm/Makefile'
    wiring = 'obj-$(CONFIG_M4RCH_GPU_IDENTIFY) += asahi/'
    text = parent.read_text()
    if wiring not in text:
        parent.write_text(text + '\n' + wiring + '\n')
    source = REPO / 'experiments/t6040-gpu/identify.rs'
    (tree / 'drivers/gpu/drm/asahi/m4rch_gpu_identify.rs').write_bytes(source.read_bytes())
    data = config.read_bytes()
    if data.startswith(b'\x1f\x8b'):
        data = gzip.decompress(data)
    (tree / '.config').write_bytes(data)
    subprocess.run([str(tree / 'scripts/config'), '--file', str(tree / '.config'),
                    '-e', 'RUST', '-m', 'M4RCH_GPU_IDENTIFY', '-d', 'DRM_ASAHI',
                    '-d', 'APPLE_PMP', '-d', 'RUST_APPLE_RTKIT',
                    '--set-str', 'LOCALVERSION', '', '-d', 'LOCALVERSION_AUTO'], check=True)
    command = ['make', '-C', str(tree), 'LLVM=1', 'KERNELRELEASE=' + RELEASE, 'LOCALVERSION=']
    subprocess.run(command + ['olddefconfig'], check=True)
    values = (tree / '.config').read_text().splitlines()
    for option in ['CONFIG_RUST=y', 'CONFIG_M4RCH_GPU_IDENTIFY=m']:
        if option not in values:
            raise ValueError('Required config missing: ' + option)
    for option in ['CONFIG_DRM_ASAHI=y', 'CONFIG_DRM_ASAHI=m',
                   'CONFIG_APPLE_PMP=y', 'CONFIG_APPLE_PMP=m',
                   'CONFIG_RUST_APPLE_RTKIT=y']:
        if option in values:
            raise ValueError('Unexpected hardware driver in leaf trial: ' + option)
    receipt.write_text(json.dumps({
        'release': RELEASE, 'source_sha256': digest(source),
        'config_sha256': digest(tree / '.config'),
        'preserved_driver_hashes': protected,
        'default_reads': False, 'gpu_dt_installed': False,
        'build_succeeded': False,
    }, indent=2) + '\n')
    return command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--configure-only', action='store_true')
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    command = prepare(args.tree.resolve(), args.config.resolve(), args.receipt.resolve())
    if not args.configure_only:
        subprocess.run(command + ['-j' + str(args.jobs), 'Image', 'modules'], check=True)
        receipt = json.loads(args.receipt.read_text())
        receipt['build_succeeded'] = True
        receipt['artifact_hashes'] = {name: digest(args.tree / name) for name in [
            'arch/arm64/boot/Image', 'drivers/gpu/drm/asahi/m4rch_gpu_identify.ko']}
        args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
