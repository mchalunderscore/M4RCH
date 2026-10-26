#!/usr/bin/env python3
"""Fix m1n1 address decoding for the native flat-root board DT.

The native r4 trace stopped at sid23-translator: dt_get_address required an
ancestor ranges property, but our devices are direct root children with
absolute 64-bit reg addresses. No DART validation or ownership check changes.
"""
import argparse
import difflib
from pathlib import Path


def prepare(root, output):
    path = root / 'src/devicetree.c'; before = path.read_text()
    old = '''    if (parent < 0)
        return 0;

    // parse ranges for address translation'''
    new = '''    if (parent < 0) {
        /* A direct root child already uses the root's physical address
         * space. Flat native board trees need no artificial bus/ranges.
         * Keep the existing rejection for untranslated non-root buses.
         */
        int len;
        const fdt64_t *reg;
        if (fdt_parent_offset(dt, node) != 0 || fdt_address_cells(dt, 0) != 2 ||
            fdt_size_cells(dt, 0) != 2)
            return 0;
        reg = fdt_getprop(dt, node, "reg", &len);
        if (!reg || len < 16 || len % 16)
            return 0;
        return fdt64_ld(reg);
    }

    // parse ranges for address translation'''
    assert before.count(old) == 1
    after = before.replace(old, new); path.write_text(after)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'devicetree.before.c').write_text(before)
    (output / 'm1n1-flat-root.patch').write_text(''.join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True), fromfile='a/src/devicetree.c', tofile='b/src/devicetree.c')))
    print('Prepared flat-root MMIO decoder; stream validation, protection and translations unchanged')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path); p.add_argument('output', type=Path)
    a = p.parse_args(); prepare(a.root, a.output)
