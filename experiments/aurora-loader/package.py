#!/usr/bin/env python3
"""Package the Aurora loader without modifying the kernel or desktop kit."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from prepare import PINS, PROJECT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def package(work, output):
    output.mkdir(parents=True, exist_ok=True)
    components = output / 'loader'
    components.mkdir(exist_ok=True)
    for name, pin in PINS.items():
        tree = work / name
        if command('git', '-C', str(tree), 'rev-parse', 'HEAD') != pin:
            raise ValueError('Unexpected upstream source: ' + name)
        subprocess.run(['git', '-C', str(tree), 'diff', '--check'], check=True)
    shutil.copyfile(work / 'm1n1/build/m1n1.bin', components / 'm1n1.bin')
    shutil.copyfile(work / 'uboot/u-boot-nodtb.bin', components / 'u-boot-nodtb.bin')
    shutil.copyfile(work / 'uboot/.config', components / 'uboot.config')
    baseline = PROJECT / 'out/aurora-direct/loader/baseline.dtb'
    expected = json.loads((PROJECT / 'out/aurora-direct/kit/profile.json').read_text())['loader']['baseline_dtb_sha256']
    if sha(baseline) != expected:
        raise ValueError('The native-tested control DT baseline changed')
    control = components / 'control.dtb'
    shutil.copyfile(baseline, control)
    nvme = '/soc/nvme@44dcc0000'
    if command('fdtget', str(control), nvme, 'reg-names') != 'nvme ans nvmmu':
        raise ValueError('Unexpected split NVMe resources')
    subprocess.run(['fdtput', '-t', 's', str(control), nvme, 'compatible', 'apple,t6041-nvme-ans2'], check=True)
    # fdtput preserves the existing phandles, all reg tuples and board identity.
    for prop in ['reg', 'reg-names']:
        if command('fdtget', '-t', 'x' if prop == 'reg' else 's', str(control), nvme, prop) != command('fdtget', '-t', 'x' if prop == 'reg' else 's', str(baseline), nvme, prop):
            raise ValueError('Control DT resource changed: ' + prop)
    sys.path.insert(0, str(PROJECT / 'sdboot'))
    from loader import pack, validate_uboot_config
    validate_uboot_config(components / 'uboot.config', work / 'uboot/drivers/serial/Makefile', internal=True)
    prefix, dtb, image = [(components / n).read_bytes() for n in ['m1n1.bin', 'control.dtb', 'u-boot-nodtb.bin']]
    pack(prefix, dtb, image)  # Validates alignment, DT extent and ARM64 Image footprint.
    payload = prefix + dtb + gzip.compress(image, compresslevel=9, mtime=0)
    if gzip.decompress(payload[len(prefix) + len(dtb):]) != image:
        raise ValueError('Compressed image readback differs')
    if b'AURL001: Aurora m1n1 J614s live ANS and DMA handoff ready' not in prefix or b'2026.07-AURL001' not in image:
        raise ValueError('Missing build identity')
    (output / 'boot.bin').write_bytes(payload)
    sources = {}
    for name, pin in PINS.items():
        tree = work / name
        tracked = subprocess.check_output(['git', '-C', str(tree), 'diff', '--binary', 'HEAD'])
        new = command('git', '-C', str(tree), 'ls-files', '--others', '--exclude-standard').splitlines()
        for relative in new:
            result = subprocess.run(['git', 'diff', '--no-index', '--binary', '--', '/dev/null', relative], cwd=tree, stdout=subprocess.PIPE)
            if result.returncode not in [0, 1]:
                raise ValueError('Cannot export source addition: ' + relative)
            tracked += result.stdout
        patch = output / (name + '-j614s.patch')
        patch.write_bytes(tracked)
        changed = command('git', '-C', str(tree), 'ls-files', '--modified', '--others', '--exclude-standard').splitlines()
        sources[name] = {'url': 'https://github.com/aurora-silicon/' + ('u-boot' if name == 'uboot' else name),
                         'revision': pin, 'patch_sha256': sha(patch),
                         'result_files': {p: sha(tree / p) for p in changed}}
    profile = {'test': 'AURL001', 'revision': 1, 'sources': sources,
               'native_boot_tested': False, 'speakers_enabled': False,
               'source_date_epoch': 1792800000,
               'baseline_control_dtb_sha256': expected,
               'control_dtb_change': 'NVMe compatible -> apple,t6041-nvme-ans2; existing resource tuples retained',
               'linux_template_sha256': sha(PROJECT / 'out/aurora-direct/template.dtb'),
               'linux_and_desktop': 'Unchanged installed AURG016 revision 4',
               'runtime_changes': ['Aurora m1n1 and U-Boot source bases', 'Bounded J614s MCC qualification',
                                   'Native-tested MTP/AOP/ISP DMA and SD power preparation',
                                   'Aurora ANS startup/adoption/live handoff with M4 Pro split-LSQ subtype'],
               'retained_integration': ['Legacy bootloader control DT', 'Local J614s Linux DT translation',
                                        'Fixed read-only NVMe EFI bridge', 'Enrolled stage 1 unchanged'],
               'build_tools': {tool: command(tool, '--version').splitlines()[0] for tool in ['gcc', 'rustc', 'cargo', 'dtc']}}
    (output / 'profile.json').write_text(json.dumps(profile, indent=2) + '\n')
    files = ['boot.bin', 'profile.json', 'm1n1-j614s.patch', 'uboot-j614s.patch']
    files += ['loader/' + n for n in ['m1n1.bin', 'control.dtb', 'u-boot-nodtb.bin', 'uboot.config']]
    manifest = {'test': 'AURL001', 'files': {name: {'sha256': sha(output / name), 'bytes': (output / name).stat().st_size} for name in files}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'test': 'AURL001', 'boot_sha256': sha(output / 'boot.bin'), 'bytes': len(payload), 'native_boot_tested': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    package(args.work, args.output)
