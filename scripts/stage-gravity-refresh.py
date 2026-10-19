#!/usr/bin/env python3
"""Stage built Gravity components using the installed stage 2's unchanged DTB."""
import argparse
import datetime
import gzip
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT / 'sdboot'), str(PROJECT / 'lib')]
import boot
import gravity_loader
import loader
import nvme_handoff
from common import sha256, write_json, manifest_files, verify_manifest
from prepare_nvme_uboot import validate_power_map
from split_loader import ESP_UUID, stage2_payload

spec = importlib.util.spec_from_file_location('setup_split_refresh', PROJECT / 'scripts/setup-split-boot.py')
setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)


def installed_dtb(bundle):
    """Locate the single aligned FDT followed by a valid compressed U-Boot Image."""
    candidates = []
    for offset in range(16384, len(bundle) - 40, 16384):
        if bundle[offset:offset + 4] != b'\xd0\x0d\xfe\xed':
            continue
        size = struct.unpack_from('>I', bundle, offset + 4)[0]
        if not 40 <= size <= 2 * 1024**2 or offset + size >= len(bundle):
            continue
        dtb = bundle[offset:offset + size]
        try:
            image = gzip.decompress(bundle[offset + size:])
            loader.pack(bundle[:offset], dtb, image)
        except (OSError, EOFError, ValueError, struct.error):
            continue
        candidates.append(dtb)
    if len(candidates) != 1:
        raise ValueError('Installed stage 2 has no unique aligned FDT/compressed Image contract')
    return candidates[0]


def component_inputs(directory):
    receipt = json.loads((directory / 'component-build.json').read_text())
    if receipt['profile'] != gravity_loader.profile_inputs(PROJECT):
        raise ValueError('Built components do not match the current pinned profile')
    for name in ('m1n1.bin', 'u-boot-nodtb.bin', '.config'):
        if sha256(directory / 'loader' / name) != receipt['files'][name]:
            raise ValueError('Built component checksum differs: ' + name)
    boot.check_m1n1(directory / 'loader/m1n1.bin', ctrr_error=b'FDT: Could not reserve CTRR range')
    nvme_handoff.check_binary(directory / 'loader/m1n1.bin', uefi=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Back up and atomically replace ESP boot.bin')
    args = parser.parse_args()
    if platform.system() != 'Darwin' or subprocess.check_output(['sysctl', '-n', 'hw.model'], text=True).strip() != 'Mac16,8':
        raise ValueError('Only the J614s Mac16,8 host is supported')
    directory = PROJECT / 'out/sdboot/gravity-loader'
    receipt = component_inputs(directory)
    spec = importlib.util.spec_from_file_location('internal_esp_refresh', PROJECT / 'scripts/internal-esp.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    value, esp = module.mount(ESP_UUID)
    parent = module.m.info(value['ParentWholeDisk'])
    if (not parent.get('Internal') or value.get('Content') != 'EFI' or
        value.get('DiskUUID', '').lower() != ESP_UUID or
        value.get('Size') != 1073741824 or value.get('PartitionMapPartitionOffset') != 362525229056):
        raise ValueError('Internal ESP identity/extent differs')
    current = esp / 'boot.bin'
    if current.is_symlink() or not current.is_file():
        raise ValueError('Existing ESP boot.bin must be a regular file')
    previous = sha256(current)
    prior_manifest = json.loads((esp / 'loader-alignment/loader-manifest.json').read_text())
    if prior_manifest['files']['boot.bin']['sha256'] != previous:
        raise ValueError('Installed boot.bin differs from its recorded alignment manifest')
    old_dtb = installed_dtb(current.read_bytes())
    baseline = directory / 'loader/baseline.dtb'; baseline.write_bytes(old_dtb)
    if sha256(baseline) != prior_manifest['files']['loader/baseline.dtb']['sha256']:
        raise ValueError('Installed baseline differs from its recorded alignment manifest')
    validate_power_map(baseline)
    nodes = boot.read_fdt(baseline)
    if b'apple,j614s' not in nodes['/'].get('compatible', b'').split(b'\0'):
        raise ValueError('Installed baseline is not J614s')
    candidate = directory / 'boot.bin'; candidate.write_bytes(stage2_payload(directory / 'loader'))
    shutil.copyfile(PROJECT / 'profiles/gravity-loader.json', directory / 'profile.json')
    shutil.copyfile(PROJECT / 'tools/boot/collect-alignment.sh', directory / 'collect.sh')
    shutil.copyfile(PROJECT / 'templates/gravity-refresh-HANDOVER.md', directory / 'HANDOVER.md')
    files = ['boot.bin', 'profile.json', 'collect.sh', 'HANDOVER.md', 'component-build.json']
    files += ['loader/' + n for n in ('m1n1.bin', 'u-boot-nodtb.bin', '.config', 'baseline.dtb')]
    write_json(directory / 'loader-manifest.json', {
        'schema': 1, 'kind': 'j614s-gravity-stage2', 'stage2_path': 'boot.bin',
        'inputs': {'profile': receipt['profile'], 'esp_partuuid': ESP_UUID,
                   'baseline_dtb': sha256(baseline), 'previous_stage2_sha256': previous,
                   'baseline_provenance': 'Unchanged FDT extracted from installed ESP boot.bin'},
        'build_labels': {'m1n1': receipt['m1n1_label'], 'u-boot': receipt['uboot_label']},
        'hardware_tested': False, 'files': manifest_files(directory, files)})
    verify_manifest(directory / 'loader-manifest.json')
    if not args.install:
        print('Prepared candidate:', candidate)
        print('Installed stage 2 remains unchanged:', previous)
        return
    if sha256(current) != previous:
        raise ValueError('Installed boot.bin changed during preparation')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = PROJECT / 'out/split-boot-backups' / stamp
    # Preserve the old diagnostic kit before replacing any installed file.
    kit = esp / 'loader-alignment'
    if kit.is_symlink():
        raise ValueError('Alignment kit must not be a symlink')
    for name in ('HANDOVER.md', 'collect.sh', 'profile.json', 'loader-manifest.json'):
        if (kit / name).is_symlink():
            raise ValueError('Alignment kit file must not be a symlink')
    record = setup.install_stage2(candidate, esp, backup)
    record.update(esp_partuuid=ESP_UUID, baseline_dtb_sha256=sha256(baseline),
                  stage1_changed=False, native_tested=False)
    write_json(backup / 'receipt.json', record)
    try:
        kit.mkdir(exist_ok=True)
        for name in ('HANDOVER.md', 'collect.sh', 'profile.json', 'loader-manifest.json'):
            dest = kit / name
            if dest.exists():
                shutil.copyfile(dest, backup / ('alignment-' + name))
            shutil.copyfile(directory / name, dest)
            if sha256(dest) != sha256(directory / name):
                raise ValueError('Alignment kit readback differs: ' + name)
        subprocess.run(['sync'], check=True)
        assert sha256(backup / 'boot.bin') == previous
        assert sha256(current) == sha256(candidate)
    except BaseException:
        # A kit failure must not leave an unrecorded candidate selected.
        setup.install_stage2(backup / 'boot.bin', esp, backup / 'failed-candidate')
        raise
    write_json(directory / 'staging-receipt.json', record)
    print('Verified installed candidate:', current, record['stage2_sha256'])
    print('Verified rollback:', backup / 'boot.bin', previous)
    print('Stage 1, Apple enrollment, GRUB, kernel and rootfs unchanged.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
