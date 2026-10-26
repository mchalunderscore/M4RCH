#!/usr/bin/env python3
"""Bind qualified kernel, retained owner and additive menu; workspace writes only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
from gfx_reset_contract import NATIVE_CONTRACT, NATIVE_RELEASE, require, sha, validate_kernel, validate_receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('install_directory', type=Path)
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    work = args.install_directory.resolve()
    candidate = args.candidate.resolve()
    receipt_path = work / 'artifact-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    require(receipt['schema'] == 'm4rch.gfx-native-reset-additive-artifacts.v1' and
            receipt['kernel_release'] == NATIVE_RELEASE and
            receipt['not_ready_for_install'] is True and
            receipt['new_menu_index'] == 5 and receipt['default_preserved'] == 4,
            'Wrong or already finalized staging receipt')
    require(not (work / 'install-result.json').exists(), 'Installation already attempted')
    for rec in receipt['artifact_files']:
        p = Path(rec['path'])
        require(p.is_file() and p.stat().st_size == rec['bytes'] and
                sha(p) == rec['sha256'], 'Staged input changed: ' + str(p))
    kernel_path = Path(receipt['kernel_qualification_path'])
    kernel, tree, notes = validate_kernel(kernel_path)
    require(kernel['kernel_release'] == NATIVE_RELEASE and
            sha(kernel_path) == receipt['kernel_qualification_sha256'],
            'Native kernel qualification differs')
    owner_path = candidate / 'asc-root-envelope/build-receipt.json'
    owner = json.loads(owner_path.read_text())
    require(validate_receipt(owner) and
            owner['graph_recovery_trial']['gfx_reset_scope'] == NATIVE_CONTRACT and
            owner['kernel_notes_sha256'] == kernel['kernel_notes_sha256'] and
            owner['kernel_gfx_reset_api']['qualification_sha256'] == sha(kernel_path),
            'Owner differs from native kernel contract')
    artifact_paths = [Path(r['path']) for r in receipt['artifact_files']]
    artifact_paths.extend([owner_path, candidate / 'gfx-reset-preparation.json'])
    for name, expected in owner['artifact_sha256'].items():
        p = (candidate / name).resolve()
        require(p.is_relative_to(candidate) and sha(p) == expected,
                'Owner artifact changed: ' + name)
        artifact_paths.append(p)
    for name, expected in owner['graph_source_sha256'].items():
        require('/' not in name, 'Unexpected owner source name')
        p = candidate / 'asc-graph-init' / name
        require(sha(p) == expected, 'Owner source changed: ' + name)
        artifact_paths.append(p)
    for name in ['graph-before.bin', 'backing.bin', 'graph-receipt.json']:
        artifact_paths.append(candidate / 'asc-graph-init' / name)
    require(sha(candidate / 'asc-graph-init/graph-before.bin') == owner['graph_fixture_sha256'],
            'Frozen graph differs')

    installer_path = work / 'install-additive.py'
    require(installer_path.read_bytes() == (KIT / 'gfx-native-reset-boot/install-additive.py').read_bytes(),
            'Copied installer differs')
    selector_path = work / 'select-default.py'
    require(not selector_path.exists(), 'Selector destination already exists')
    shutil.copyfile(KIT / 'gfx-native-reset-boot/select-default.py', selector_path)
    artifact_paths.extend([installer_path, selector_path, Path(__file__).resolve(),
                           KIT / 'gfx_reset_contract.py'])
    before = Path('/boot/grub/grub.cfg').read_bytes()
    before_record = receipt['protected_host_files']['/boot/grub/grub.cfg']
    require(hashlib.sha256(before).hexdigest() == before_record['sha256'] and
            len(before) == before_record['bytes'] and
            before.count(b'menuentry ') == 5 and before.count(b'set default=4\n') == 1,
            'Existing GRUB differs from qualified protected input')
    title = '7.1.13-m4rch-gpu-native-reset (GFXN001 native command trial)'
    entry = ("\nmenuentry '" + title + "' {\n"
             "    search --no-floppy --fs-uuid --set=root 33CE-1F10\n"
             "    linux /GFXN001/vmlinuz root=UUID=7568fe83-378f-5b78-ab12-ccc36ff09a90 rw console=ttydc0 console=tty0 rdinit=/init idle=nop arm64.nowfxt pd_ignore_unused clk_ignore_unused asahi_m4.probe_only=1\n"
             "    initrd /GFXN001/initramfs.img\n}\n").encode()
    for name, data in [('grub-before.cfg', before), ('additive-entry.cfg', entry),
                       ('grub-additive.cfg', before + entry)]:
        p = work / name
        with p.open('xb') as f:
            f.write(data)
        artifact_paths.append(p)
    subprocess.run(['grub-script-check', str(work / 'grub-additive.cfg')], check=True)
    receipt['boot_files'].update({str(work / 'grub-before.cfg'): 'grub-before.cfg',
                                  str(owner_path): 'owner-build-receipt.json',
                                  str(candidate / 'kernel.notes.bin'): 'kernel.notes.bin'})
    paths = sorted(set(p.resolve() for p in artifact_paths))
    receipt['artifact_files'] = [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                                 for p in paths]
    records = {r['path']: r for r in receipt['artifact_files']}
    receipt.update(candidate_build_receipt_path=str(owner_path),
                   candidate_build_receipt_sha256=sha(owner_path),
                   owner_module_sha256=owner['artifact_sha256']['asc-graph-init/asc-graph-init.ko'],
                   graph_fixture_sha256=owner['graph_fixture_sha256'],
                   new_menu_entry=title,
                   boot_bytes=sum(records[p]['bytes'] for p in receipt['boot_files']),
                   not_ready_for_install=False,
                   state='qualified-native-kernel-initramfs-owner-and-additive-menu; not-installed')
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    subprocess.run([sys.executable, str(installer_path), '--receipt-sha256', sha(receipt_path)], check=True)
    print('Finalized exact native boot/owner receipt SHA256 ' + sha(receipt_path))


if __name__ == '__main__':
    main()
