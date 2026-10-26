#!/usr/bin/env python3
"""Extend the native Aurora loader with a data-only J614s DCP handoff."""
import argparse
import difflib
from pathlib import Path
import shutil

KIT = Path(__file__).resolve().parent


def preserve_display(root):
    path = root / 'src/display.c'
    before = path.read_text()
    old = 'if (chip_id == T8140 || chip_id == T8132) {\n        printf("display: preserving inherited display'
    new = 'if (chip_id == T8140 || chip_id == T8132 || chip_id == T6040) {\n        printf("display: preserving inherited display'
    if before.count(old) != 1:
        raise ValueError('Expected inherited display setup guard')
    after = before.replace(old, new)
    path.write_text(after)
    return ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                   fromfile='a/src/display.c', tofile='b/src/display.c'))


def prepare_m1n1(root, output):
    path = root / 'src/kboot.c'
    before = path.read_text()
    text = before

    def change(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError('Expected one m1n1 anchor: ' + old[:100])
        text = text.replace(old, new)

    # Keep J713 admission exactly as before; make the frontend inventory use
    # live T6041 mappings rather than J713's fixed segment indices/counts.
    text = text.replace('dt_set_j713_display_maps', 'dt_set_m4_display_maps')
    change('''    const char *aliases[] = {"disp0", "disp0_piodma"};
    const u8 streams[] = {0, 16};
    struct j713_display_maps''', '''    bool j614s = chip_id == T6040 && !fdt_node_check_compatible(dt, 0, "apple,j614s");
    const char *marker = j614s ? "apple,j614s-inherited-mappings" : "apple,j713-inherited-mappings";
    const char *status = j614s ? "disabled" : "okay";
    const char *aliases[] = {"disp0", "disp0_piodma"};
    const u8 streams[] = {0, 16};
    struct j713_display_maps''')
    change('dart_walk_locked_t8110(0x30a300000, streams[n],', 'dart_walk_locked_t8110(j614s ? 0x402300000 : 0x30a300000, streams[n],')
    change('if (regions != (n == 0 ? 2 : 1))', 'if (j614s ? (regions < 1 || regions > 5) : (regions != (n == 0 ? 2 : 1)))')
    # These writes are inside the shared mapping helper. The candidate's
    # ordinary boot entries must leave both DART suppliers disabled.
    start = text.index('static int dt_set_m4_display_maps(')
    end = text.index('/* Publish the inherited J713', start)
    block = text[start:end]
    block = block.replace('"status", "okay"', '"status", status')
    block = block.replace('fdt_setprop_empty(dt, piodma, "apple,j713-inherited-mappings")', 'fdt_setprop_empty(dt, piodma, marker)')
    block = block.replace('dcp >= 0 && fdt_getprop(dt, dcp, "apple,j713-native-scanout", NULL)',
                          'dcp >= 0 && (j614s || fdt_getprop(dt, dcp, "apple,j713-native-scanout", NULL))')
    block = block.replace('(fdt_node_check_compatible(dt, display, "apple,t8132-display-diagnostics") &&',
                          '(fdt_node_check_compatible(dt, display, "apple,t6041-display-subsystem") &&\n             fdt_node_check_compatible(dt, display, "apple,t8132-display-diagnostics") &&')
    block = block.replace('fdt_setprop_empty(dt, display, "apple,j713-inherited-mappings")', 'fdt_setprop_empty(dt, display, marker)')
    text = text[:start] + block + text[end:]
    change('(chip_id == T8132 && !strcmp(fdt_path, "dcp"))) && seg->unk == 0xa)',
           '((chip_id == T8132 || chip_id == T6040) && !strcmp(fdt_path, "dcp"))) && seg->unk == 0xa)')
    change('static int dt_set_display(void)\n{', '''#include "j614s-dcp.h"

static int dt_set_display(void)
{
    if (chip_id == T6040 && !fdt_node_check_compatible(dt, 0, "apple,j614s")) {
        if (dt_set_j614s_dcp_handoff())
            printf("DCP001: live display handoff refused; keeping the boot framebuffer\\n");
        return 0;
    }''')
    path.write_text(text)
    shutil.copyfile(KIT / 'loader/j614s-dcp.h', root / 'src/j614s-dcp.h')
    output.mkdir(parents=True, exist_ok=True)
    patch = ''.join(difflib.unified_diff(before.splitlines(True), text.splitlines(True),
                    fromfile='a/src/kboot.c', tofile='b/src/kboot.c'))
    patch += ''.join(difflib.unified_diff([], (KIT / 'loader/j614s-dcp.h').read_text().splitlines(True),
                     fromfile='/dev/null', tofile='b/src/j614s-dcp.h'))
    patch += preserve_display(root)
    (output / 'm1n1-dcp001.patch').write_text(patch)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, default=KIT.parents[1] / 'out/aurora-dcp')
    args = parser.parse_args()
    prepare_m1n1(args.root, args.output)
