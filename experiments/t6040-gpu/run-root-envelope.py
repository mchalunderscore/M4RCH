#!/usr/bin/env python3
"""Fresh-boot validation and optional minimal-root rejection probe. Never reboot.

The publication probe deliberately expects firmware rejection. Its backing and
power reference remain pinned after publication, even if ASC stop succeeds.
"""
import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
from pathlib import Path
from adt import parse
from firmware_text_contract import qualify


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, explanation):
    if not condition:
        raise ValueError(explanation)


def capture(module, sysfile, output, name):
    subprocess.run(['insmod', str(module)], check=True)
    try:
        data = Path(sysfile).read_bytes()
        output.write_bytes(data)
        return data
    finally:
        subprocess.run(['rmmod', name], check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('workspace', type=Path)
    p.add_argument('--run', action='store_true')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--arena', action='store_true', help='Mapping/retirement only; never publish a root')
    mode.add_argument('--graph', action='store_true', help='Batch structural initialization, allocations enabled; published memory pins until reboot')
    args = p.parse_args()
    work = args.workspace.resolve()
    build = work/'asc-root-envelope'
    receipt = json.loads((build/'build-receipt.json').read_text())
    require(os.geteuid() == 0, 'Native sudo required')
    require(os.uname().release == receipt['kernel_release'], 'Kernel release mismatch')
    require(sha(Path('/sys/kernel/notes').read_bytes()) == receipt['kernel_notes_sha256'], 'Kernel identity mismatch')
    for relative, digest in receipt['artifact_sha256'].items():
        require(sha((work/relative).read_bytes()) == digest, 'Artifact mismatch: '+relative)
    modules = Path('/proc/modules').read_text()
    for line in modules.splitlines():
        name = line.split()[0]
        require(not (name.startswith('asc_') or name in ['asahi_m4', 'resource_overlay', 'gfx_power_test', 'gpu_data_sample', 'm4rch_gpu_adt']), 'Conflicting module: '+name)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    out = (work/'asc-graph-init' if args.graph else work/'asc-arena-preflight' if args.arena else build)/('boot-'+boot)
    out.mkdir(exist_ok=True)
    require(not (out/'attempt.json').exists() and not (out/'result.json').exists(), 'Attempt already recorded for this boot; do not repeat')
    raw = capture(work/'adt-current/m4rch_gpu_adt.ko', '/sys/kernel/m4rch_gpu_adt/adt', out/'boot.adt', 'm4rch_gpu_adt')
    tree = parse(raw)
    chosen = tree['/device-tree/chosen']
    sgx = tree['/device-tree/arm-io/sgx']
    require(chosen['firmware-version'].rstrip(b'\0') == b'mBoot-18000.161.10', 'Loader firmware mismatch')
    require(int.from_bytes(chosen['chip-id'], 'little') == 0x6040, 'Chip mismatch')
    for key, expected in {'gfx-shared-region-base':0x105fff78000, 'gfx-shared-region-size':0x40000,
                          'gfx-data-base':0x10001d44000, 'gfx-data-size':0x138000,
                          'gpu-region-base':0x105fffb8000, 'gpu-region-size':0x4000,
                          'gfx-shared-l2-region-base':0x105fff74000, 'gfx-shared-l2-region-size':0x4000}.items():
        require(int.from_bytes(sgx[key], 'little') == expected, 'Fresh ADT range mismatch: '+key)
    if args.graph:
        layout = json.loads((work/'asc-graph-init/graph-receipt.json').read_text())
        for key,digest in layout.get('voltage_input_sha256',{}).items():
            require(sha(sgx[key])==digest,'Fresh voltage input differs: '+key)
        regs=list(struct.iter_unpack('<QQ',sgx['reg']))
        require(regs==[(0x88000000,0x3758000),(0x88d00000,0x16c000)],'SGX MMIO apertures differ')
        for leaf in layout.get('mmio_leaves',[]):
            pa,va=leaf['physical'],leaf['gpu_va']
            platform=(pa,va) in ((0x502414000,0xfffffc2001a00000),(0x5003d8000,0xfffffc2001b18000))
            afr=0x28b000000<=pa<0x28b640000 and (pa-0x28b000000)%0x200000<0x40000 and va==0xfffffc2001c00000+(pa-0x28b000000)//0x200000*0x40000+(pa-0x28b000000)%0x200000
            sgx=0x288000000<=pa and pa+0x4000<=0x28b758000 and va==0xfffffc2000200000+pa-0x288000000
            require((platform and not leaf['readonly']) or (afr and (leaf['readonly'] or (pa-0x28b000000)%0x10000==0)) or (sgx and (leaf['readonly'] or pa in (0x288004000,0x288d04000,0x288d10000,0x288d40000,0x288d44000,0x288d4c000,0x288e00000,0x288e1c000,0x288e40000))),'Unqualified MMIO leaf range')
    tables = capture(work/'sample-pagetables/gpu-data-sample.ko', '/sys/kernel/m4rch_gpu_data_sample/data', out/'pagetables.bin', 'gpu_data_sample')
    base = 0x105fff78000
    def translate(va):
        table = base
        for shift, mask in [(36,63),(25,2047),(14,2047)]:
            offset = table-base+((va>>shift)&mask)*8
            require(0 <= offset <= len(tables)-8, 'Table outside captured reservation')
            entry = struct.unpack_from('<Q', tables, offset)[0]
            if not entry&1:
                return None
            require(entry&3 == 3, 'Unexpected block descriptor')
            table = entry&0x3ffffffc000
        return table+(va&0x3fff)
    initial_tables_zero = not any(tables)
    if not initial_tables_zero:
        require(translate(0xfffffc0000000000) == 0x10000be4000, 'TEXT mapping mismatch')
        require(translate(0xfffffc0000060000) == 0x10001d44000, 'DATA mapping mismatch')
    # On a genuinely cold boot the firmware populates these tables during its
    # handshake. The native probe checks the completed path before installing.

    require(struct.unpack_from('<Q',tables,16)[0] == 0, 'Candidate top-level slot occupied')
    text = capture(work/'root-text-sample/gpu-data-sample.ko', '/sys/kernel/m4rch_gpu_data_sample/data', out/'text.bin', 'gpu_data_sample')
    text_contract = qualify(text)
    # Instruction and string checks qualify the intended early rejection path.
    for offset, word in {0x2f250:0xf9400109,0x2f264:0xeb0a013f,0x2f268:0x54003d61,
                         0x2f2b4:0xb9402d29,0x2f2b8:0x34003b49,0x2fa2c:0x94004f40}.items():
        require(struct.unpack_from('<I',text,offset)[0] == word, 'Parser instruction mismatch')
    require(text[0x5b768:].startswith(b'Host-mapped FW allocations are disabled'), 'Rejection string mismatch')
    report = {'boot_id':boot, 'adt_sha256':sha(raw), 'tables_sha256':sha(tables), 'initial_tables_zero':initial_tables_zero,
              'text_sha256':sha(text), 'text_contract':text_contract, 'validated_build_receipt':receipt, 'run_requested':args.run, 'mapping_or_publication_performed':False}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    if not args.run:
        print('Fresh metadata, table path and exact firmware parser validated; sampler helpers unloaded. No root mapping or firmware publication.')
        return
    # Persist intent and logs before any power/MMIO/PTE change.
    (out/'attempt.json').write_text(json.dumps({'boot_id':boot,'stage':'about to load','reboot_may_be_required':True},indent=2)+'\n')
    before = capture(work/'root-data-sample/gpu-data-sample.ko', '/sys/kernel/m4rch_gpu_data_sample/data', out/'data-before.bin', 'gpu_data_sample')
    (out/'dmesg-before.log').write_text(subprocess.check_output(['dmesg','--color=never'],text=True))
    (out/'interrupts-before.txt').write_text(Path('/proc/interrupts').read_text())
    os.sync()
    selected = work/'asc-graph-init/asc-graph-init.ko' if args.graph else work/'asc-arena-preflight/asc-arena-preflight.ko' if args.arena else build/'asc-root-envelope.ko'
    if args.graph:
        require(sha((work/'asc-graph-init/graph-before.bin').read_bytes()) == receipt['graph_fixture_sha256'], 'Graph fixture changed')
        require(sha((work/'asc-graph-init/graph-receipt.json').read_bytes()) == receipt['graph_receipt_sha256'], 'Graph relocation receipt changed')
        shadow = subprocess.run(['insmod',str(selected),'run_gate=1'],capture_output=True,text=True)
        require(shadow.returncode == 0, 'Owned graph allocation/shadow walk failed: '+shadow.stderr)
        subprocess.run(['rmmod','asc_graph_init'],check=True)
        (out/'objects-before.bin').write_bytes((work/'asc-graph-init/graph-before.bin').read_bytes())
    result = subprocess.run(['insmod',str(selected),'run_gate=1' if args.arena else 'run_gate=2'],capture_output=True,text=True)
    logs = subprocess.check_output(['dmesg','--color=never'],text=True)
    (out/'dmesg-after.log').write_text(logs)
    (out/'interrupts-after.txt').write_text(Path('/proc/interrupts').read_text())
    if args.arena:
        module_path = Path('/sys/module/asc_arena_preflight')
        present = module_path.exists()
        count = int((module_path/'refcnt').read_text()) if present else None
        before_log = (out/'dmesg-before.log').read_text()
        delta = logs[len(before_log):] if logs.startswith(before_log) else logs
        retired = 'application-start-only retirement verified; normal unload allowed' in delta
        unloaded = False
        if present and result.returncode == 0 and count == 0 and retired:
            subprocess.run(['rmmod','asc_arena_preflight'],check=True)
            unloaded = True
        final = subprocess.check_output(['dmesg','--color=never'],text=True)
        (out/'dmesg-after-unload.log').write_text(final)
        report.update(load_returncode=result.returncode,stderr=result.stderr,
                      root_published=False,mapping_or_publication_performed=f"{receipt['arena_object_pages']} object pages mapped" in delta,
                      expected_object_pages=receipt['arena_object_pages'],
                      mapped_expected_pages=f"{receipt['arena_object_pages']} object pages mapped" in delta,
                      retirement_verified=retired,unloaded=unloaded,reboot_required=present and not unloaded,
                      interpretation='Allocation/mapping/retirement only; no root address sent or object reads established.')
        (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\n')
        if unloaded:
            table = capture(work/'sample-pagetables/gpu-data-sample.ko', '/sys/kernel/m4rch_gpu_data_sample/data', out/'tables-after-unload.bin', 'gpu_data_sample')
            l2 = capture(work/'arena-l2-sample/gpu-data-sample.ko', '/sys/kernel/m4rch_gpu_data_sample/data', out/'l2-after-unload.bin', 'gpu_data_sample')
            require(len(table)==0x40000 and len(l2)==0x4000, 'Unexpected post-unload table extent')
            owned_pages = [int(pa,16) for pa in re.findall(r'owned page \d+ physical=(0x[0-9a-f]+)',delta)]
            mask = ((1<<42)-1)&~0x3fff
            references = [hex(word) for blob in (table,l2) for (word,) in struct.iter_unpack('<Q',blob)
                          if (word & 3)==3 and (word & mask) in owned_pages]
            report.update(post_unload_tables_sha256=sha(table),post_unload_l2_sha256=sha(l2),
                          owned_page_count=len(owned_pages),owned_page_references=references,
                          reserved_l2_zero=not any(l2),
                          post_unload_verified=len(owned_pages)==receipt['arena_object_pages']+2 and not references and not any(l2))
        (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\n')
        os.sync()
        print('Arena preflight retired and unloaded; no pinned resources.' if unloaded else 'Arena preflight refused or retained resources; inspect evidence.')
        return
    present = Path('/sys/module/asc_graph_init' if args.graph else '/sys/module/asc_root_envelope').exists()
    report['root_published'] = 'G16S root sent to EP32' in logs
    report['mapping_or_publication_performed'] = (f"{receipt['graph_object_pages']} object pages mapped" in logs if args.graph else 'installed previously-empty mapping slot' in logs)
    report.update(load_returncode=result.returncode, stderr=result.stderr, module_present=present,
                  reboot_required=present, interpretation=('Allocations-enabled structural fixture. A sent root/object change does not prove initialization or rendering readiness. Never force unload.' if args.graph else 'A transmitted root is not proof of consumption. Seek a newly written disabled-host-allocations rejection in the crashlog. Never force module unload.'))
    (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\n')
    os.sync()
    # Sampler is read-only and independently unloadable; root probe stays pinned.
    if present:
        after = capture(work/'root-data-sample/gpu-data-sample.ko', '/sys/kernel/m4rch_gpu_data_sample/data', out/'data-after.bin', 'gpu_data_sample')
        report['data_before_sha256'] = sha(before)
        report['data_after_sha256'] = sha(after)
        report['data_changed_bytes'] = sum(a != b for a,b in zip(before,after))
        report['new_rejection_offsets'] = []
        needle = b'Host-mapped FW allocations are disabled'
        cursor = 0
        while True:
            found = after.find(needle,cursor)
            if found < 0:
                break
            if before[found:found+len(needle)] != needle:
                report['new_rejection_offsets'].append(hex(found))
            cursor = found+1
        (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\n')
    if args.graph and present:
        snapshot=Path('/sys/kernel/m4rch_gpu_graph_trial/objects')
        if snapshot.exists():
            objects=snapshot.read_bytes()
            initial=(out/'objects-before.bin').read_bytes()
            require(len(objects)==len(initial),'Graph snapshot extent changed')
            (out/'objects-after.bin').write_bytes(objects)
            layout=json.loads((work/'asc-graph-init/graph-receipt.json').read_text())
            report['object_changes']=[]
            for obj in layout['objects']:
                start=obj['arena_offset'];end=start+obj['reserved_bytes']
                changed=[i-start for i in range(start,end) if initial[i]!=objects[i]]
                report['object_changes'].append(dict(name=obj['name'],changed_bytes=len(changed),
                    first_changed_offsets=[hex(i) for i in changed[:32]]))
            report['objects_after_sha256']=sha(objects)
        else:
            report['object_snapshot_missing']=True
        (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\n')
    os.sync()
    print('Probe returned. Inspect evidence; pinned backing requires reboot.' if present else 'Probe refused; inspect evidence before retrying.')

if __name__ == '__main__':
    main()
