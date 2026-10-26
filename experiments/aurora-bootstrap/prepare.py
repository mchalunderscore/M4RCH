#!/usr/bin/env python3
"""Remove Wallace inputs from both m1n1 stages and the control DT."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[2]
OUTPUT = PROJECT / 'out/aurora-bootstrap'
WORK = Path('/work/aurora-native-loader')
PIN = '9f7cdfbd0623d96f21965434c3a7dda799ffcff4'


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError('Source anchor changed: ' + str(path))
    path.write_text(text.replace(old, new))


def control_tree():
    source = PROJECT / 'out/aurora-direct/template.dtb'
    profile = json.loads((PROJECT / 'out/aurora-loader/profile.json').read_text())
    if sha(source) != profile['linux_template_sha256']:
        raise ValueError('Aurora-derived J614s template differs')
    target = OUTPUT / 'control.dtb'
    shutil.copyfile(source, target)
    # J614s has the mriya radio module. The J616s donor describes hostomel;
    # retaining that name makes Linux request firmware absent on this machine.
    for alias in ['wifi0', 'bluetooth0']:
        node = run('fdtget', str(target), '/aliases', alias)
        subprocess.run(['fdtput', '-t', 's', str(target), node, 'brcm,board-type', 'apple,mriya'], check=True)
    # Aurora leaves the firmware's usual boot CPU without spin-table fields.
    # m1n1 intentionally skips that CPU; our Linux handoff still expects the
    # fields to exist (zero is valid only for the actual boot CPU). Provide
    # placeholders for every CPU, also covering a different firmware boot CPU.
    for child in run('fdtget', '-l', str(target), '/cpus').splitlines():
        if not child.startswith('cpu@'):
            continue
        node = '/cpus/' + child
        props = run('fdtget', '-p', str(target), node).splitlines()
        if 'enable-method' not in props:
            subprocess.run(['fdtput', '-t', 's', str(target), node, 'enable-method', 'spin-table'], check=True)
        if 'cpu-release-addr' not in props:
            subprocess.run(['fdtput', '-t', 'x', str(target), node, 'cpu-release-addr', '0', '0'], check=True)
    # Bootloader control data excludes coprocessor firmware supplied separately
    # to Linux. Remove donor/placeholder reservations and their consumer refs.
    def nodes(path):
        yield path
        for child in run('fdtget', '-l', str(target), path).splitlines():
            yield from nodes(path.rstrip('/') + '/' + child)
    for node in list(nodes('/')):
        if 'memory-region' in run('fdtget', '-p', str(target), node).splitlines():
            subprocess.run(['fdtput', '-d', str(target), node, 'memory-region'], check=True)
    for node in run('fdtget', '-l', str(target), '/reserved-memory').splitlines():
        subprocess.run(['fdtput', '-r', str(target), '/reserved-memory/' + node], check=True)
    aliases = run('fdtget', '-p', str(target), '/aliases').splitlines()
    keep = {'keyboard', 'wifi0', 'bluetooth0', 'serial0', 'ethernet0'}
    for alias in aliases:
        if alias not in keep:
            subprocess.run(['fdtput', '-d', str(target), '/aliases', alias], check=True)
    subprocess.run(['fdtput', '-t', 's', str(target), '/chosen', 'm4rch,control-template', 'AUBS001'], check=True)
    required = {
        '/': ('compatible', 'apple,j614s'),
        '/nvme@44dcc0000': ('compatible', 'apple,t6041-nvme-ans2'),
        '/mailbox@409608000': ('compatible', 'apple,asc-mailbox-v4'),
        '/watchdog@50836c000': ('compatible', 'apple,t8103-wdt'),
        '/sart@40dc50000': ('compatible', 'apple,t6000-sart'),
    }
    for node, (prop, value) in required.items():
        if value not in run('fdtget', str(target), node, prop).split():
            raise ValueError('Early-driver binding missing: ' + node)
    if run('fdtget', str(target), '/nvme@44dcc0000', 'reg-names') != 'nvme ans nvmmu':
        raise ValueError('NVMe BAR names differ')
    (OUTPUT / 'control-provenance.json').write_text(json.dumps({
        'source': 'aurora-silicon/linux', 'revision': '420a1c8f5492daeaa59ffba565aac610f5218d27',
        'source_board': 't6040-j616s.dts', 'local_board': 'J614s adaptation from aurora-direct',
        'source_template_sha256': sha(source), 'result_sha256': sha(target),
        'wallace_inputs': [], 'early_driver_bindings_checked': required,
        'coprocessor_reservations': 'Populated from live firmware by m1n1 and the existing Linux handoff; no donor addresses retained',
    }, indent=2) + '\n')


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    first = WORK / 'stage1'
    if run('git', '-C', str(first), 'rev-parse', 'HEAD') != PIN or run('git', '-C', str(first), 'status', '--porcelain'):
        raise ValueError('Expected clean Aurora stage-1 source')
    # The only stage-1 source adaptation is the exact native-tested MCC change.
    subprocess.run(['git', '-C', str(first), 'apply', '--include=src/mcc.c',
                    str(PROJECT / 'out/aurora-loader/m1n1-j614s.patch')], check=True)
    with (first / 'config.h').open('a') as config:
        config.write('\n#undef EARLY_PROXY_TIMEOUT\n')
    # chainload_image reuses _base and refuses to overwrite the live NVMe heap.
    # Reserve image room before BSS/stacks so the complete stage-2 bundle fits
    # below stage 1's allocation boundary, independent of firmware's spare gap.
    for name in ['m1n1.ld', 'm1n1-raw.ld']:
        replace(first / name, '        _file_end = .;',
                '        . += 0x100000; /* J614s: room for the complete stage-2 bundle. */\n'
                '        _file_end = .;')
    control_tree()
    # New control trees use Aurora's watchdog binding and root hardware graph.
    # The Wallace-targeted board.dtbo is neither read nor applied on this path.
    uboot = WORK / 'uboot'
    replace(uboot / 'arch/arm/mach-apple/j614s-map.h',
            'ofnode_by_compatible(ofnode_null(), "apple,wdt")',
            'ofnode_by_compatible(ofnode_null(), "apple,t8103-wdt")')
    path = uboot / 'arch/arm/mach-apple/archsd.c'
    text = path.read_text()
    text = text.replace('#define OVERLAY_PATH "/dtbs/board.dtbo"\n', '')
    start = text.index('\tif (read_esp(OVERLAY_PATH,')
    end = text.index('\t/* The overlay modifies only', start)
    text = text[:start] + '''    int chosen = fdt_path_offset(gd->fdt_blob, "/chosen"), marker_len;
    const char *marker = chosen < 0 ? NULL :
        fdt_getprop(gd->fdt_blob, chosen, "m4rch,control-template", &marker_len);
    if (!marker || marker_len != sizeof("AUBS001") || strcmp(marker, "AUBS001") ||
        fdt_open_into(gd->fdt_blob, dt, DT_LIMIT) ||
        fdt_node_check_compatible(dt, 0, "apple,j614s")) {
        puts("AUBS001: missing Aurora J614s control tree\\n");
        return CMD_RET_FAILURE;
    }
''' + text[end:]
    text = text.replace('\t/* The overlay modifies only this handoff copy, not the control DT used\n'
                        '\t * by active firmware drivers. GRUB must inherit it, not load a raw DTB. */',
                        '\t/* GRUB inherits the translated live Aurora tree. */')
    text = text.replace('\tvoid *overlay = (void *)env_get_hex("scriptaddr", 0);\n', '')
    text = text.replace('size_t image_size, overlay_size, recorded_size;', 'size_t image_size, recorded_size;')
    text = text.replace('!image || !dt || !overlay ||', '!image || !dt ||')
    text = text.replace('after NVMe/EFI discovery and the existing live board overlay.',
                        'after NVMe/EFI discovery, using the live Aurora control tree.')
    path.write_text(text)
    print('Prepared AUBS001: Aurora first stage and control DT; no Wallace tree inputs')


if __name__ == '__main__':
    main()
