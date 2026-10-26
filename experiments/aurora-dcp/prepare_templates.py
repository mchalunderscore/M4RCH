#!/usr/bin/env python3
"""Add inert DCP graph metadata to the working Linux/control templates."""
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parents[2]
OUTPUT = PROJECT / 'out/aurora-dcp'


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update(path):
    def put(node, prop, *values, kind='s'):
        subprocess.run(['fdtput', '-t', kind, str(path), node, prop, *values], check=True)

    consumers = {'dcp': '/dcp@402e00000', 'disp0': '/display-subsystem',
                 'disp0_piodma': '/dcp@402e00000/piodma', 'pmp': '/pmp@500700000'}
    for alias, node in consumers.items():
        if alias != 'pmp':
            put('/aliases', alias, node)
    for alias in ['dcp', 'disp0', 'disp0_piodma']:
        put(consumers[alias], '#address-cells', '2', kind='x')
        put(consumers[alias], '#size-cells', '2', kind='x')
        # PR429 preserves this explicit device policy on LoC-zero CPUs.
        # These retained DCP paths require Normal-NC payload mappings. The
        # separately qualified T6040 GPU keeps its existing DMA policy.
        subprocess.run(['fdtput', '-t', 'x', str(path), consumers[alias],
                        'dma-noncoherent'], check=True)
    put(consumers['disp0'], 'compatible', 'apple,t6041-display-subsystem', 'apple,display-subsystem')
    if 'phandle' not in run('fdtget', '-p', str(path), consumers['pmp']).splitlines():
        source = subprocess.check_output(['dtc', '-I', 'dtb', '-O', 'dts', str(path)],
                                         text=True, stderr=subprocess.DEVNULL)
        maximum = max((int(value, 16) for value in re.findall(r'\bphandle\s*=\s*<0x([0-9a-fA-F]+)>', source)), default=0)
        if maximum >= 0xfffffffe:
            raise ValueError('No free PMP phandle')
        put(consumers['pmp'], 'phandle', format(maximum + 1, 'x'), kind='x')
    put(consumers['dcp'], 'apple,pmp', run('fdtget', '-t', 'x', str(path), consumers['pmp'], 'phandle'), kind='x')
    # Describe the full native DISP0 register set, including its T604x shared
    # aperture. Keep the existing separate PMGR supplier graph intact.
    put(consumers['dcp'], 'reg', '4', '2e00000', '0', '4000', '4', '0', '0', '4000000',
        '4', '2240000', '0', '10000', '4', '23a8000', '0', '4000',
        '4', '2800000', '0', '800000', '5', '4800000', '0', 'bc000', kind='x')
    put(consumers['dcp'], 'reg-names', 'coproc', 'disp-0', 'disp-1', 'disp-2', 'disp-3', 'disp-4')
    for node in ['/iommu@402300000', '/iommu@402340000']:
        put(node, 'apple,dma-range', '100', '0', '10', '0', kind='x')
    for node in ['/iommu@402300000', '/iommu@402340000', '/mailbox@402e08000',
                 consumers['dcp'], consumers['disp0']]:
        put(node, 'status', 'disabled')
    # All reservations and ownership markers come from this native boot.
    for node in consumers.values():
        props = run('fdtget', '-p', str(path), node).splitlines()
        for prop in ['memory-region', 'memory-region-names', 'apple,j614s-inherited-mappings']:
            if prop in props:
                subprocess.run(['fdtput', '-d', str(path), node, prop], check=True)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sources = {'template.dtb': PROJECT / 'out/aurora-direct/template.dtb',
               'control.dtb': PROJECT / 'out/aurora-bootstrap/control.dtb'}
    record = {}
    for name, source in sources.items():
        path = OUTPUT / name
        shutil.copyfile(source, path)
        update(path)
        record[name] = {'source_sha256': sha(source), 'result_sha256': sha(path)}
    if run('fdtget', str(OUTPUT / 'control.dtb'), '/chosen', 'm4rch,control-template') != 'AUBS001':
        raise ValueError('Expected the native Aurora bootstrap control graph')
    for alias in ['wifi0', 'bluetooth0']:
        node = run('fdtget', str(OUTPUT / 'control.dtb'), '/aliases', alias)
        if run('fdtget', str(OUTPUT / 'control.dtb'), node, 'brcm,board-type') != 'apple,mriya':
            raise ValueError('Candidate must preserve the prepared radio identity fix')
    (OUTPUT / 'templates.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
