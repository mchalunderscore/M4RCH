#!/usr/bin/env python3
"""Build isolated root-envelope probe and read-only samplers; never load modules."""
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

KIT = Path(__file__).resolve().parent
RELEASE = '7.1.13-m4rch-gpu-contract'
NOTES = 'ab3d4a13f2cfe6403d9a75e9d03f55202f12c200894e24dd773a8c7ec6d8663a'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('workspace', type=Path)
    args = p.parse_args()
    work = args.workspace.resolve()
    tree = work/'linux'
    source = json.loads((work/'source-receipt.json').read_text())
    if source['release'] != RELEASE or (tree/'include/config/kernel.release').read_text().strip() != RELEASE:
        raise ValueError('Wrong successful trial build')
    if sha(tree/'.config') != source['config_sha256']:
        raise ValueError('Kernel configuration changed')
    for name, digest in source['protected_maintained_files'].items():
        if sha(tree/name) != digest:
            raise ValueError('Maintained source changed: '+name)
    targets = {}
    for tag, base, size in [('sample-pagetables',0x105fff78000,0x40000),
                            ('root-text-sample',0x10000be4000,0x60000),
                            ('root-data-sample',0x10001d44000,0x138000),
                            ('arena-l2-sample',0x105fff74000,0x4000)]:
        out = work/tag
        out.mkdir(exist_ok=True)
        for name in ['Makefile','gpu-data-sample.c']:
            shutil.copy2(KIT/'data-sample'/name,out/name)
        (out/'sample-contract.h').write_text(f'#define SAMPLE_BASE {base:#x}ULL\n#define SAMPLE_BYTES {size:#x}UL\n')
        targets[tag] = 'gpu-data-sample.ko'
    out = work/'adt-current'
    out.mkdir(exist_ok=True)
    shutil.copy2(KIT/'m4rch_gpu_adt.c',out/'m4rch_gpu_adt.c')
    (out/'Makefile').write_text('obj-m += m4rch_gpu_adt.o\n')
    targets['adt-current'] = 'm4rch_gpu_adt.ko'
    out = work/'asc-root-envelope'
    out.mkdir(exist_ok=True)
    for name in ['Makefile','asc-root-envelope.c','root-map.h']:
        shutil.copy2(KIT/'asc-root-envelope'/name,out/name)
    (out/'boot-contract.h').write_text('#define FW_DATA_BASE 0x10001d44000ULL\n#define FW_DATA_BYTES 0x138000ULL\n')
    targets['asc-root-envelope'] = 'asc-root-envelope.ko'
    arena = work/'asc-arena-preflight'
    arena.mkdir(exist_ok=True)
    for name in ['Makefile','asc-arena-preflight.c','arena-map.h']:
        shutil.copy2(KIT/'asc-arena-preflight'/name,arena/name)
    shutil.copy2(out/'boot-contract.h',arena/'boot-contract.h')
    spec = importlib.util.spec_from_file_location('graph_plan', KIT/'plan-init-graph.py')
    graph_plan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(graph_plan)
    plan = graph_plan.plan()
    unknown = [o['name'] for o in plan['objects'] if o['extent'] is None]
    # One marker page per unknown target for allocation testing ONLY. This is
    # neither a complete-extent assertion nor a graph published to firmware.
    arena_pages = plan['arena_bytes']//graph_plan.PAGE + len(unknown)
    (arena/'arena-contract.h').write_text(f'/* Candidate mapping capacity only, no object contents. */\n#define ARENA_OBJECT_PAGES {arena_pages}U\n')
    targets['asc-arena-preflight'] = 'asc-arena-preflight.ko'
    for tag in targets:
        subprocess.run(['make','-C',str(tree),'LLVM=1','KERNELRELEASE='+RELEASE,
                        'LOCALVERSION=','M='+str(work/tag),'W=1','modules'],check=True)
    receipt = dict(kernel_release=RELEASE,kernel_notes_sha256=NOTES,
                   module_sha256=sha(out/'asc-root-envelope.ko'),
                   artifact_sha256={tag+'/'+module:sha(work/tag/module) for tag,module in targets.items()},
                   source_sha256={name:sha(out/name) for name in ['asc-root-envelope.c','root-map.h','boot-contract.h']},
                   arena_object_pages=arena_pages,arena_unknown_extent_marker_pages=unknown,
                   arena_source_sha256={name:sha(arena/name) for name in ['asc-arena-preflight.c','arena-map.h','arena-contract.h']},
                   hardware_trial_performed=False,default_gate=0,preflight_gate=1,cold_publication_gate=2)
    (out/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Built matching isolated modules; no loading or firmware publication.')

if __name__ == '__main__':
    main()
