#!/usr/bin/env python3
"""Build the explicit retained-backing GFX reset candidate; never load or install.

Preserves the qualified mask3 graph and immutable triangle, recompiles every
helper for the separately qualified kernel, and gates the new owner commands.
No firmware restart, GPU execution or safe-retirement result is implied.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from gfx_reset_contract import CONTRACT, validate_kernel, validate_receipt, require, sha

KIT = Path(__file__).resolve().parent
BASE_MODULE_SHA = '332d9d04f3dc2ada1de5b312910a5d5e65eb92165a28f9a6f3768cb627b81191'
BASE_GRAPH_SHA = '287f2c53bc6ef7ed226c4a2995b9d9904e7623acae9713af105be6b04fc690a9'
TARGETS = {
    'adt-current': 'm4rch_gpu_adt.ko',
    'sample-pagetables': 'gpu-data-sample.ko',
    'root-text-sample': 'gpu-data-sample.ko',
    'root-data-sample': 'gpu-data-sample.ko',
    'arena-l2-sample': 'gpu-data-sample.ko',
    'asc-root-envelope': 'asc-root-envelope.ko',
    'asc-arena-preflight': 'asc-arena-preflight.ko',
    'asc-graph-init': 'asc-graph-init.ko',
}


def ignore_outputs(directory, names):
    compiled = shutil.ignore_patterns('*.ko', '*.o', '*.mod', '*.mod.c',
                                     '*.cmd', 'Module.symvers', 'modules.order')
    ignored = set(compiled(directory, names))
    ignored.update(name for name in names if
                   (name.startswith('boot-') or name == 'resident-operations') and
                   (Path(directory) / name).is_dir())
    return ignored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline_candidate', type=Path)
    parser.add_argument('kernel_manifest', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    base = args.baseline_candidate.resolve()
    kernel, tree, notes = validate_kernel(args.kernel_manifest)
    receipt = json.loads((base / 'asc-root-envelope/build-receipt.json').read_text())
    require(receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'] == BASE_MODULE_SHA and
            receipt['graph_fixture_sha256'] == BASE_GRAPH_SHA, 'Wrong baseline candidate')
    for relative, expected in receipt['artifact_sha256'].items():
        p = (base / relative).resolve()
        require(p.is_relative_to(base) and sha(p) == expected, 'Baseline artifact changed: ' + relative)
    for name, expected in receipt['graph_source_sha256'].items():
        require('/' not in name and sha(base / 'asc-graph-init' / name) == expected,
                'Baseline owner source changed: ' + name)
    require(receipt['graph_recovery_trial']['resident_session'] is True and
            receipt['joined_owned_pages'] == 174 and not receipt['graph_submit_work'] and
            not receipt['graph_release_on_shutdown'], 'Unexpected baseline lifetime')
    require(sha(base / 'asc-graph-init/graph-before.bin') == BASE_GRAPH_SHA and
            sha(base / 'asc-graph-init/graph-receipt.json') == receipt['graph_receipt_sha256'],
            'Baseline graph changed')
    output = args.output.resolve()
    require(not output.exists(), 'Output already exists; do not overwrite a candidate')
    output.mkdir(parents=True)
    for tag in TARGETS:
        shutil.copytree(base / tag, output / tag, ignore=ignore_outputs)
    graph = output / 'asc-graph-init'
    for name in ('asc-graph-init.c', 'joined-context-init.h', 'recovery-cycle.h',
                 'receive-service.h', 'gfx-reset-scope.h'):
        shutil.copyfile(KIT / 'asc-graph-init' / name, graph / name)
    makefile = graph / 'Makefile'
    makefile.write_text(makefile.read_text() + '\nccflags-y += -DGFX_RESET_SCOPE_TRIAL\n')
    (output / 'kernel-qualification.json').write_bytes(args.kernel_manifest.read_bytes())
    (output / 'kernel.notes.bin').write_bytes(notes)
    commands, build_logs = [], []
    for tag in TARGETS:
        command = ['make', '-C', str(tree), 'ARCH=arm64', 'LLVM=1',
                   'KERNELRELEASE=' + kernel['kernel_release'], 'M=' + str(output / tag),
                   'W=1', 'modules']
        result = subprocess.run(command, capture_output=True, text=True)
        (output / tag / 'reset-build.log').write_text(result.stdout + result.stderr)
        commands.append(command)
        build_logs.append({'path': tag + '/reset-build.log',
                           'sha256': sha(output / tag / 'reset-build.log'),
                           'returncode': result.returncode})
        require(result.returncode == 0, 'Module build failed: ' + tag)
        vermagic = subprocess.check_output(['modinfo', '-F', 'vermagic',
                                           str(output / tag / TARGETS[tag])], text=True).split()[0]
        require(vermagic == kernel['kernel_release'], 'Module release mismatch: ' + tag)
    require(sha(graph / 'graph-before.bin') == BASE_GRAPH_SHA and
            sha(graph / 'backing.bin') == sha(base / 'asc-graph-init/backing.bin'),
            'Frozen graph or backing changed')
    receipt = copy.deepcopy(receipt)
    receipt.update(kernel_release=kernel['kernel_release'],
                   kernel_notes_sha256=kernel['kernel_notes_sha256'])
    receipt['graph_recovery_trial']['gfx_reset_scope'] = copy.deepcopy(CONTRACT)
    receipt['kernel_gfx_reset_api'] = {
        'patch_sha256': kernel['patch_sha256'],
        'qualification_sha256': sha(args.kernel_manifest),
        'vmlinux_sha256': kernel['vmlinux_sha256'],
        'image_sha256': kernel['image_sha256'],
        'module_symvers_sha256': kernel['module_symvers_sha256'],
        'kernel_build_id': kernel['kernel_build_id'],
        'qualification_path': 'kernel-qualification.json',
        'notes_path': 'kernel.notes.bin',
    }
    receipt['artifact_sha256'] = {tag + '/' + name: sha(output / tag / name)
                                  for tag, name in TARGETS.items()}
    receipt['artifact_sha256'].update({
        'kernel-qualification.json': sha(output / 'kernel-qualification.json'),
        'kernel.notes.bin': sha(output / 'kernel.notes.bin'),
    })
    receipt['module_sha256'] = receipt['artifact_sha256']['asc-root-envelope/asc-root-envelope.ko']
    receipt['graph_source_sha256'] = {p.name: sha(p) for p in graph.glob('*.h')}
    receipt['graph_source_sha256'].update({name: sha(graph / name) for name in
                                         ('asc-graph-init.c', 'Makefile')})
    validate_receipt(receipt)
    (output / 'asc-root-envelope/build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    preparation = {
        'schema': 'm4rch-gfx-reset-owner-preparation-v1',
        'baseline_candidate': str(base), 'baseline_module_sha256': BASE_MODULE_SHA,
        'baseline_build_receipt_sha256': sha(base / 'asc-root-envelope/build-receipt.json'),
        'kernel_qualification_sha256': sha(args.kernel_manifest),
        'graph_sha256': BASE_GRAPH_SHA, 'backing_sha256': sha(graph / 'backing.bin'),
        'build_commands': commands, 'build_logs': build_logs,
        'candidate_build_receipt_sha256': sha(output / 'asc-root-envelope/build-receipt.json'),
        'preparer_sha256': sha(Path(__file__)),
        'shared_contract_sha256': sha(KIT / 'gfx_reset_contract.py'),
        'module_loaded': False, 'kernel_installed': False, 'hardware_reset_performed': False,
        'qualification': 'Build only. No fresh firmware, reset coverage, recovery or DMA-retirement proof.',
    }
    (output / 'gfx-reset-preparation.json').write_text(json.dumps(preparation, indent=2) + '\n')
    print('Built explicit checked GFX reset owner. All backing retained; no module loaded or reset performed.')


if __name__ == '__main__':
    main()
