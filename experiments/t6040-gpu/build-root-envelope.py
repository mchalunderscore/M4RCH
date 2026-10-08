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
    p.add_argument('--control-refresh', action='store_true', help='One opcode16 initial control record; work remains empty')
    p.add_argument('--control-refresh-count', type=int, default=1, help='With --control-refresh, stage1..32 identical records; no wraparound')
    p.add_argument('--receive14', action='store_true', help='Experimental four-buffer receive14 fixture; no jobs')
    p.add_argument('--receive13', action='store_true', help='With receive14, add four-buffer receive13 using device-disjoint GPU pages')
    p.add_argument('--retirement-probe', action='store_true', help='Request AP quiesce/IOP sleep after observation; never release published backing yet')
    args = p.parse_args()
    if args.receive13 and not args.receive14:p.error('Receive13 currently requires receive14')
    if not 1 <= args.control_refresh_count <= 32 or (not args.control_refresh and args.control_refresh_count != 1):
        p.error('Require --control-refresh and count1..32 for a batch')
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
    graph = work/'asc-graph-init'
    graph.mkdir(exist_ok=True)
    for name in ['Makefile','asc-graph-init.c','graph-map.h']:
        shutil.copy2(KIT/'asc-graph-init'/name,graph/name)
    shutil.copy2(out/'boot-contract.h',graph/'boot-contract.h')
    spec = importlib.util.spec_from_file_location('parser_model', KIT/'emulate-init-parser.py')
    parser_model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser_model)
    graph_bytes, graph_receipt = parser_model.graph_fixture(True)
    batch_spec = importlib.util.spec_from_file_location('register_batch', KIT/'graph-register-batch.py')
    register_batch = importlib.util.module_from_spec(batch_spec)
    batch_spec.loader.exec_module(register_batch)
    seed = work/'asc-graph-init/boot-e1e8db50-10f6-46b5-8d73-a593b7e2c611/boot.adt'
    graph_bytes, graph_receipt = register_batch.extend(graph_bytes,graph_receipt,seed.read_bytes())
    if args.receive14:
        from receive14_fixture import extend
        graph_bytes, graph_receipt = extend(graph_bytes,graph_receipt)
    if args.receive13:
        from receive13_fixture import extend
        graph_bytes, graph_receipt = extend(graph_bytes,graph_receipt)
    if args.control_refresh:
        from control_refresh import stage
        graph_bytes, graph_receipt = stage(graph_bytes, graph_receipt, args.control_refresh_count)
    graph_pages = len(graph_bytes)//graph_plan.PAGE
    if len(graph_bytes)%graph_plan.PAGE or graph_pages!=(69 if args.receive13 else 54 if args.receive14 else 47):
        raise ValueError('Unexpected structural fixture geometry')
    from owned_gpu_layout import validate
    owned_vas = validate(graph_bytes,graph_receipt)
    header = '/* Explicit experimental zero-opaque fixture, NOT a complete render graph. */\n'
    header += f'#define ARENA_OBJECT_PAGES {graph_pages}U\n'
    header += f'#define GRAPH_MAPPED_PAGES {graph_receipt["mapped_pages"]}U\n'
    header += f'#define GRAPH_MMIO_BASE {graph_receipt["mmio_virtual_base"]}ULL\n'
    header += 'static const u64 owned_page_vas[] = {\n' + ''.join(f' {va:#x}ULL,\n' for va in owned_vas) + '};\n'
    header += 'struct graph_mmio_leaf { u64 physical, gpu_va; bool writable; };\n'
    header += 'static const struct graph_mmio_leaf mmio_leaves[] = {\n'
    header += ''.join(f' {{ {v["physical"]:#x}ULL, {v["gpu_va"]:#x}ULL, {int(not v["readonly"])} }},\n' for v in graph_receipt['mmio_leaves'])
    header += '};\n'
    header += f'static const u8 graph_bytes[{len(graph_bytes)}] = {{\n'
    header += ''.join(f' [{i:#x}] = {value:#x},\n' for i,value in enumerate(graph_bytes) if value)
    header += '};\n'
    (graph/'graph-contract.h').write_text(header)
    (graph/'graph-before.bin').write_bytes(graph_bytes)
    (graph/'graph-receipt.json').write_text(json.dumps(graph_receipt,indent=2)+'\n')
    targets['asc-graph-init'] = 'asc-graph-init.ko'
    for tag in targets:
        subprocess.run(['make','-C',str(tree),'LLVM=1','KERNELRELEASE='+RELEASE,
                        'LOCALVERSION=','M='+str(work/tag),'W=1','modules'],check=True)
    receipt = dict(kernel_release=RELEASE,kernel_notes_sha256=NOTES,
                   module_sha256=sha(out/'asc-root-envelope.ko'),
                   artifact_sha256={tag+'/'+module:sha(work/tag/module) for tag,module in targets.items()},
                   source_sha256={name:sha(out/name) for name in ['asc-root-envelope.c','root-map.h','boot-contract.h']},
                   arena_object_pages=arena_pages,arena_unknown_extent_marker_pages=unknown,
                   arena_source_sha256={name:sha(arena/name) for name in ['asc-arena-preflight.c','arena-map.h','arena-contract.h']},
                   graph_object_pages=graph_pages,graph_fixture_sha256=sha(graph/'graph-before.bin'),
                   graph_source_sha256={name:sha(graph/name) for name in ['asc-graph-init.c','graph-map.h','graph-contract.h']},
                   graph_receipt_sha256=sha(graph/'graph-receipt.json'),
                   graph_power_retirement_probe=args.retirement_probe,hardware_trial_performed=False,default_gate=0,preflight_gate=1,cold_publication_gate=2)
    (out/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Built matching isolated modules; no loading or firmware publication.')

if __name__ == '__main__':
    main()
