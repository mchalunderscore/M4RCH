#!/usr/bin/env python3
"""Layer the DCP data transfer over the native AUBS001 U-Boot bridge."""
import argparse
import difflib
from pathlib import Path
import shutil

KIT = Path(__file__).resolve().parent


def refresh_template(root, output):
    data = (output / 'template.dtb').read_bytes()
    (root / 'arch/arm/mach-apple/aurora-template.h').write_text(
        'static const unsigned char aurora_template[] __aligned(8) = {\n' +
        ',\n'.join(','.join(str(x) for x in data[i:i+24]) for i in range(0, len(data), 24)) + '\n};\n')


def prepare(root, output):
    directory = root / 'arch/arm/mach-apple'
    path = directory / 'aurora-handoff.c'
    before = path.read_text()
    text = before
    old = '#include "peripheral_handoff.c"'
    if text.count(old) != 1:
        raise ValueError('Expected the native peripheral handoff')
    text = text.replace(old, old + '\n#include "dcp_handoff.c"')
    old = '\tCHECK(disable_compatible(out, "apple,t6041-dcp"));'
    if text.count(old) != 1:
        raise ValueError('Expected the native disabled DCP boundary')
    text = text.replace(old, '''    if (dcp_handoff(out, live)) {
        int chosen = fdt_path_offset(out, "/chosen");
        if (chosen >= 0)
            fdt_delprop(out, chosen, "m4rch,dcp-handoff");
        printf("DCP001: Linux display metadata transfer refused; retaining framebuffer boot\\n");
    }
    CHECK(disable_compatible(out, "apple,t6041-dcp"));''')
    path.write_text(text)
    shutil.copyfile(KIT / 'loader/dcp_handoff.c', directory / 'dcp_handoff.c')
    refresh_template(root, output)
    patch = ''.join(difflib.unified_diff(before.splitlines(True), text.splitlines(True),
                    fromfile='a/arch/arm/mach-apple/aurora-handoff.c', tofile='b/arch/arm/mach-apple/aurora-handoff.c'))
    patch += ''.join(difflib.unified_diff([], (KIT / 'loader/dcp_handoff.c').read_text().splitlines(True),
                     fromfile='/dev/null', tofile='b/arch/arm/mach-apple/dcp_handoff.c'))
    (output / 'uboot-dcp001.patch').write_text(patch)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, default=KIT.parents[1] / 'out/aurora-dcp')
    args = parser.parse_args()
    prepare(args.root, args.output)
