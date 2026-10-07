#!/usr/bin/env python3
"""Fresh-boot validation and optional minimal-root rejection probe. Never reboot.

The publication probe deliberately expects firmware rejection. Its backing and
power reference remain pinned after publication, even if ASC stop succeeds.
"""
import argparse
import hashlib
import json
import os
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
    out = build/('boot-'+boot)
    out.mkdir(exist_ok=True)
    require(not (out/'attempt.json').exists(), 'Attempt already recorded for this boot; do not repeat')
    raw = capture(work/'adt-current/m4rch_gpu_adt.ko', '/sys/kernel/m4rch_gpu_adt/adt', out/'boot.adt', 'm4rch_gpu_adt')
    tree = parse(raw)
    chosen = tree['/device-tree/chosen']
    sgx = tree['/device-tree/arm-io/sgx']
    require(chosen['firmware-version'].rstrip(b'\0') == b'mBoot-18000.161.10', 'Loader firmware mismatch')
    require(int.from_bytes(chosen['chip-id'], 'little') == 0x6040, 'Chip mismatch')
    for key, expected in {'gfx-shared-region-base':0x105fff78000, 'gfx-shared-region-size':0x40000,
                          'gfx-data-base':0x10001d44000, 'gfx-data-size':0x138000,
                          'gpu-region-base':0x105fffb8000, 'gpu-region-size':0x4000}.items():
        require(int.from_bytes(sgx[key], 'little') == expected, 'Fresh ADT range mismatch: '+key)
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
    require(translate(0xfffffc0000000000) == 0x10000be4000, 'TEXT mapping mismatch')
    require(translate(0xfffffc0000060000) == 0x10001d44000, 'DATA mapping mismatch')
    require(struct.unpack_from('<Q',tables,16)[0] == 0, 'Candidate top-level slot occupied')
    text = capture(work/'root-text-sample/gpu-data-sample.ko', '/sys/kernel/m4rch_gpu_data_sample/data', out/'text.bin', 'gpu_data_sample')
    text_contract = qualify(text)
    # Instruction and string checks qualify the intended early rejection path.
    for offset, word in {0x2f250:0xf9400109,0x2f264:0xeb0a013f,0x2f268:0x54003d61,
                         0x2f2b4:0xb9402d29,0x2f2b8:0x34003b49,0x2fa2c:0x94004f40}.items():
        require(struct.unpack_from('<I',text,offset)[0] == word, 'Parser instruction mismatch')
    require(text[0x5b768:].startswith(b'Host-mapped FW allocations are disabled'), 'Rejection string mismatch')
    report = {'boot_id':boot, 'adt_sha256':sha(raw), 'tables_sha256':sha(tables),
              'text_sha256':sha(text), 'text_contract':text_contract, 'run_requested':args.run, 'mapping_or_publication_performed':False}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    if not args.run:
        print('Fresh metadata, table path and exact firmware parser validated; sampler helpers unloaded. No root mapping or firmware publication.')
        return
    # Persist intent and logs before any power/MMIO/PTE change.
    (out/'attempt.json').write_text(json.dumps({'boot_id':boot,'stage':'about to load','reboot_may_be_required':True},indent=2)+'\n')
    before = capture(work/'root-data-sample/gpu-data-sample.ko', '/sys/kernel/m4rch_gpu_data_sample/data', out/'data-before.bin', 'gpu_data_sample')
    (out/'dmesg-before.log').write_text(subprocess.check_output(['dmesg','--color=never'],text=True))
    os.sync()
    result = subprocess.run(['insmod',str(build/'asc-root-envelope.ko'),'run_gate=2'],capture_output=True,text=True)
    logs = subprocess.check_output(['dmesg','--color=never'],text=True)
    (out/'dmesg-after.log').write_text(logs)
    present = Path('/sys/module/asc_root_envelope').exists()
    report.update(load_returncode=result.returncode, stderr=result.stderr, module_present=present,
                  reboot_required=present, interpretation='A transmitted root is not proof of consumption. Seek a newly written disabled-host-allocations rejection in the crashlog. Never force module unload.')
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
    os.sync()
    print('Probe returned. Inspect evidence; pinned backing requires reboot.' if present else 'Probe refused; inspect evidence before retrying.')

if __name__ == '__main__':
    main()
