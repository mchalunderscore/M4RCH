#!/usr/bin/env python3
"""Integrate the tested data-only board handoff into the existing U-Boot bridge."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys

KIT = Path(__file__).resolve().parent
PROJECT = KIT.parents[1]


def prepare(tree, template):
    directory = tree / 'arch/arm/mach-apple'
    raw = template.read_bytes()
    (directory / 'aurora-template.h').write_text(
        'static const unsigned char aurora_template[] __aligned(8) = {\n' +
        ',\n'.join(','.join(str(x) for x in raw[i:i+24]) for i in range(0, len(raw), 24)) + '\n};\n')
    shutil.copyfile(KIT / 'board_handoff.c', directory / 'aurora-handoff.c')
    shutil.copyfile(KIT / 'uboot_handoff.h', directory / 'aurora-uboot-handoff.h')
    source = directory / 'archsd.c'
    text = source.read_text()
    if 'aurora-uboot-handoff.h' in text:
        raise ValueError('Loader is already prepared; inspect before reapplying')
    text = text.replace('DECLARE_GLOBAL_DATA_PTR;', '#include "aurora-uboot-handoff.h"\n\nDECLARE_GLOBAL_DATA_PTR;')
    needle = '\t/* fs_read alone does not record an EFI device path.'
    if text.count(needle) != 1:
        raise ValueError('Expected exactly one EFI handoff boundary')
    replacement = '''
    /* Preserve U-Boot's active control tree. Translate only Linux's handoff
     * after NVMe/EFI discovery and the existing live board overlay. */
    {
        char mode[32] = {};
        size_t mode_size;
        void *translated = memalign(16384, DT_LIMIT);
        int ret;
        if (!translated || read_esp("/AURT002/mode", mode, sizeof(mode) - 1, &mode_size) ||
            (strcmp(mode, "test\\n") && strcmp(mode, "framebuffer\\n"))) {
            puts("Boot: missing Aurora test mode or handoff buffer\\n");
            return CMD_RET_FAILURE;
        }
        ret = aurora_prepare_fdt(dt, translated, DT_LIMIT, !strcmp(mode, "framebuffer\\n"));
        if (ret) {
            printf("Boot: Aurora live board handoff failed (%d)\\n", ret);
            return CMD_RET_FAILURE;
        }
        dt = translated;
    }
'''
    source.write_text(text.replace(needle, replacement + needle))


def pack(tree, components, output):
    prefix = (components / 'm1n1.bin').read_bytes()
    baseline = (components / 'baseline.dtb').read_bytes()
    uboot = (tree / 'u-boot-nodtb.bin').read_bytes()
    sys.path.insert(0, str(PROJECT / 'sdboot'))
    from loader import pack as validate_payload
    validate_payload(prefix, baseline, uboot)
    output.write_bytes(prefix + baseline + gzip.compress(uboot, compresslevel=9, mtime=0))
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [components / 'm1n1.bin', components / 'baseline.dtb', tree / 'u-boot-nodtb.bin', output]}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree', type=Path)
    p.add_argument('--template', type=Path, required=True)
    p.add_argument('--pack', type=Path)
    a = p.parse_args()
    if a.pack:
        result = pack(a.tree, PROJECT / 'out/sdboot/gravity-loader/loader', a.pack)
        (a.pack.parent / 'loader-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    else:
        prepare(a.tree, a.template)
