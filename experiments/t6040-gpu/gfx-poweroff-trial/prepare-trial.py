#!/usr/bin/env python3
"""Prepare a distinct no-work power-off owner; never load, install or reboot."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess

from gfx_poweroff_contract import CONTRACT, require, sha, validate_kernel, validate_receipt

KIT = Path(__file__).resolve().parent
SOURCE_KIT = KIT.parent / 'gfx-poweroff-scope'
BASE_RECEIPT_SHA = '96d5dda793adf700017b5e28b33b2ee6e2964ab058a08ec4bcdcdf68fbe7909e'
BASE_OWNER_SHA = '51aeeab15ff4a369ce11717e24d7ba6507c176981eedfa3da61747b47959e432'


def ignore_history(directory, names):
    return [n for n in names if n == '__pycache__' or
            (n.startswith('boot-') or n == 'resident-operations') and
            (Path(directory) / n).is_dir()]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline_candidate', type=Path)
    p.add_argument('kernel_manifest', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    base = args.baseline_candidate.resolve()
    kernel, tree, notes = validate_kernel(args.kernel_manifest)
    receipt_path = base / 'asc-root-envelope/build-receipt.json'
    require(sha(receipt_path) == BASE_RECEIPT_SHA, 'Wrong frozen native baseline receipt')
    receipt = json.loads(receipt_path.read_text())
    require(receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'] == BASE_OWNER_SHA,
            'Wrong native baseline owner')
    for rel, expected in receipt['artifact_sha256'].items():
        source = (base / rel).resolve()
        require(source.is_relative_to(base) and sha(source) == expected,
                'Baseline artifact changed: ' + rel)
    for name, expected in receipt['graph_source_sha256'].items():
        require('/' not in name and sha(base / 'asc-graph-init' / name) == expected,
                'Baseline owner source changed: ' + name)
    qualification_path = SOURCE_KIT / 'owner-qualification.json'
    qualification = json.loads(qualification_path.read_text())
    require(qualification.get('hardware_access') is False and
            qualification.get('qualification_complete') is True,
            'Power-off owner source has not been qualified')
    for rec in qualification['source_files']:
        source = Path(rec['path'])
        require(source.is_file() and sha(source) == rec['sha256'],
                'Power-off source qualification changed: ' + str(source))
    wrapper_path = KIT / 'wrapper-qualification.json'
    wrapper = json.loads(wrapper_path.read_text())
    require(wrapper.get('hardware_access') is False and
            wrapper.get('qualification_complete') is True and
            wrapper.get('case_count', 0) >= 84,
            'Power-off runners have not been qualified')
    for rec in wrapper['source_files']:
        source = Path(rec['path'])
        require(source.parent == KIT and sha(source) == rec['sha256'],
                'Power-off runner qualification changed: ' + str(source))
    output = args.output.resolve()
    require(not output.exists(), 'Output exists; never overwrite a candidate')
    shutil.copytree(base, output, ignore=ignore_history)
    graph = output / 'asc-graph-init'
    shutil.copyfile(SOURCE_KIT / 'gfx-poweroff-scope.h', graph / 'gfx-reset-scope.h')
    shutil.copyfile(SOURCE_KIT / 'recovery-cycle.h', graph / 'recovery-cycle.h')
    makefile = graph / 'Makefile'
    text = makefile.read_text()
    require(text.count('ccflags-y += -DGFX_RESET_NATIVE_SEQUENCE_TRIAL') == 1,
            'Native baseline flags changed')
    makefile.write_text(text.replace('ccflags-y += -DGFX_RESET_NATIVE_SEQUENCE_TRIAL',
                                    'ccflags-y += -DGFX_POWER_OFF_SCOPE_TRIAL'))
    main_c = graph / 'asc-graph-init.c'
    text = main_c.read_text()
    require(text.count('/gfx-snapshot and guarded one-attempt gfx-reset') == 1,
            'Baseline retained-scope log changed')
    main_c.write_text(text.replace('/gfx-snapshot and guarded one-attempt gfx-reset',
                                   '/gfx-snapshot and one terminal gfx-poweroff after stop'))
    command = ['make', '-C', str(tree), 'ARCH=arm64', 'LLVM=1',
               'KERNELRELEASE=' + kernel['kernel_release'], 'M=' + str(graph), 'W=1', 'modules']
    result = subprocess.run(command, capture_output=True, text=True)
    log = graph / 'poweroff-build.log'
    log.write_text(result.stdout + result.stderr)
    require(result.returncode == 0, 'Power-off owner compilation failed')
    module = graph / 'asc-graph-init.ko'
    magic = subprocess.check_output(['modinfo', '-F', 'vermagic', str(module)], text=True).split()[0]
    require(magic == kernel['kernel_release'], 'Power-off owner release differs')
    undefined = subprocess.check_output(['nm', '-u', str(module)], text=True)
    require('apple_pmgr_t6040_gfx_snapshot' in undefined and
            'apple_pmgr_t6040_gfx_native_probe' not in undefined and
            'apple_pmgr_t6040_gfx_checked_pulse' not in undefined and
            '__pm_runtime_suspend' in undefined, 'Unexpected power-off owner API imports')
    require((output / 'kernel.notes.bin').read_bytes() == notes and
            sha(output / 'kernel-qualification.json') == sha(args.kernel_manifest),
            'Baseline and future kernel identities differ')
    for name in ['graph-before.bin', 'backing.bin', 'graph-receipt.json']:
        require(sha(graph / name) == sha(base / 'asc-graph-init' / name),
                'Frozen draw or graph changed: ' + name)
    receipt = copy.deepcopy(receipt)
    del receipt['graph_recovery_trial']['gfx_reset_scope']
    receipt['graph_recovery_trial']['gfx_power_off_scope'] = copy.deepcopy(CONTRACT)
    receipt['kernel_gfx_power_off_api'] = receipt.pop('kernel_gfx_reset_api')
    receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'] = sha(module)
    receipt['graph_source_sha256'] = {p.name: sha(p) for p in graph.glob('*.h')}
    receipt['graph_source_sha256'].update({n: sha(graph / n) for n in ['asc-graph-init.c', 'Makefile']})
    require(validate_receipt(receipt), 'New power-off receipt refused')
    new_receipt = output / 'asc-root-envelope/build-receipt.json'
    new_receipt.write_text(json.dumps(receipt, indent=2) + '\n')
    preparation = {'schema': 'm4rch.gfx-power-off-owner-preparation.v1',
                   'baseline_candidate': str(base), 'baseline_receipt_sha256': BASE_RECEIPT_SHA,
                   'baseline_owner_sha256': BASE_OWNER_SHA,
                   'candidate': str(output), 'candidate_receipt_sha256': sha(new_receipt),
                   'owner_sha256': sha(module), 'kernel_release': kernel['kernel_release'],
                   'kernel_qualification_sha256': sha(args.kernel_manifest),
                   'source_qualification_path': str(qualification_path),
                   'source_qualification_sha256': sha(qualification_path),
                   'wrapper_qualification_path': str(wrapper_path),
                   'wrapper_qualification_sha256': sha(wrapper_path),
                   'build_command': command, 'build_log_sha256': sha(log),
                   'preparer_sha256': sha(Path(__file__)),
                   'contract_sha256': sha(KIT / 'gfx_poweroff_contract.py'),
                   'only_owner_recompiled': True, 'other_seven_helpers_unchanged': True,
                   'native_reset_api_imported': False, 'graph_and_backing_unchanged': True,
                   'module_loaded': False, 'kernel_rebuilt': False, 'hardware_power_off_performed': False,
                   'qualification': 'Build only; no successful OFF, DMA cessation, restart, retirement or rendering proof.'}
    (output / 'power-off-preparation.json').write_text(json.dumps(preparation, indent=2) + '\n')
    print('Prepared distinct retained power-off owner; no hardware operation or kernel rebuild.')


if __name__ == '__main__':
    main()
