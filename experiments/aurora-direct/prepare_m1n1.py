#!/usr/bin/env python3
"""Add bounded J614s AOP/ISP DMA preparation to the proven loader baseline."""
from pathlib import Path
import argparse


def prepare(tree):
    path = tree / 'src/dapf.c'
    s = path.read_text()
    old = 'if (chip_id == T6040 && strcmp(entry->path, "/arm-io/dart-mtp")) {'
    if s.count(old) != 1:
        raise ValueError('Expected the reviewed T6040 DMA guard')
    s = s.replace(old, '''if (chip_id == T6040 && strcmp(entry->path, "/arm-io/dart-mtp") &&
            strcmp(entry->path, "/arm-io/dart-aop") &&
            strcmp(entry->path, "/arm-io/dart-isp0")) {''')
    anchor = 'int dapf_init_all(void)\n{'
    s = s.replace(anchor, 'u32 m4rch_dapf_ready;\n\n' + anchor)
    old = '''        if (dapf_init(entry->path, entry->index) < 0) {
            ret = -1;
        }'''
    new = '''        /* The two additional T6040 filters use the documented T8110
         * layout and their own ADT register windows/tables. No donor data. */
        if (dapf_init(entry->path, entry->index) < 0) {
            ret = -1;
        } else if (chip_id == T6040) {
            if (!strcmp(entry->path, "/arm-io/dart-aop"))
                m4rch_dapf_ready |= 1;
            if (!strcmp(entry->path, "/arm-io/dart-isp0"))
                m4rch_dapf_ready |= 2;
        }'''
    if s.count(old) != 1:
        raise ValueError('Unexpected DAPF result handling')
    path.write_text(s.replace(old, new))
    # Existing dapf_init does type selection. Bound the table to the actual
    # aperture before its first write, and reject ambiguous record layouts.
    s = path.read_text()
    needle = '    u64 base;\n    if (adt_get_reg'
    guard = '''    if (chip_id == T6040 && (!strcmp(path, "/arm-io/dart-aop") ||
                              !strcmp(path, "/arm-io/dart-isp0"))) {
        u32 len;
        u64 check_base, check_size;
        const void *table = adt_getprop(adt, node, "dapf-instance-0", &len);
        if (!adt_is_compatible(adt, node, "dart,t8110") || !table ||
            !len || len % sizeof(struct dapf_t8110_config) ||
            len % sizeof(struct dapf_t8110b_config) == 0 ||
            adt_get_reg(adt, dart_path, "reg", index, &check_base, &check_size) < 0 ||
            !check_base || (check_base & 0x3fff) ||
            len / sizeof(struct dapf_t8110_config) > check_size / 0x40)
            return -1;
    }

'''
    if s.count(needle) != 1:
        raise ValueError('Unexpected DAPF address lookup')
    path.write_text(s.replace(needle, guard + needle))
    path = tree / 'src/kboot.c'
    s = path.read_text()
    old = '    int chosen = fdt_path_offset(dt, "/chosen");\n    if (chosen < 0 || fdt_setprop_string(dt, chosen, "arch-m4,ans-handoff", "v2") ||'
    new = '''    extern u32 m4rch_dapf_ready;
    int chosen = fdt_path_offset(dt, "/chosen");
    if (chosen < 0 || fdt_setprop_u32(dt, chosen, "m4rch,dapf-ready", m4rch_dapf_ready) ||
        fdt_setprop_string(dt, chosen, "arch-m4,ans-handoff", "v2") ||'''
    if s.count(old) != 1:
        raise ValueError('Unexpected live handoff publication')
    path.write_text(s.replace(old, new))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree', type=Path)
    prepare(p.parse_args().tree)
