#!/usr/bin/env python3
"""Build the isolated J614s board template for the test bootloader."""
from pathlib import Path
import argparse
import re
import subprocess

KIT = Path(__file__).resolve().parent


def prepare(tree):
    dts = tree / 'arch/arm64/boot/dts/apple'
    board = (dts / 't6040-j616s.dts').read_text()
    board = board.replace('"apple,j616s",', '"apple,j614s",')
    board = board.replace('Apple MacBook Pro (16-inch, M4 Pro, Nov 2024)',
                          'Apple MacBook Pro (14-inch, M4 Pro, J614s) Aurora direct')
    board = board.replace('tpmtfw-j616s.bin', 'tpmtfw-j614s.bin')
    board = board.replace('apple,panel-j616', 'apple,panel-j614').replace('width-mm = <345>', 'width-mm = <302>').replace('height-mm = <223>', 'height-mm = <196>')
    board = board.replace('apple,chassis-name = "J616"', 'apple,chassis-name = "J614"')
    # Firmware addresses must be populated from this boot, never the donor laptop.
    for name in ['isp-firmware-text', 'isp-firmware-data', 'gpu-fw-data',
                 'uat-ttbs', 'uat-pagetables', 'uat-l2-pagetables', 'uat-handoff']:
        pattern = r'(' + re.escape(name) + r')@[0-9a-f]+(\s*\{)(.*?)(\n\s*\};)'
        def zero(match):
            body = re.sub(r'reg\s*=\s*<[^;]+>;', 'reg = <0 0 0 0>;', match[3])
            return match[1] + match[2] + body + match[4]
        board, count = re.subn(pattern, zero, board, flags=re.S)
        if count != 1:
            raise ValueError('Expected exactly one reservation: ' + name)
    # Do not let genpd power GFX before the runtime firmware/OPP checks.
    board += '''
&pmgr_gfx { status = "disabled"; };
&gfx_mbox { status = "disabled"; };
&gpu { status = "disabled"; };
&dcp { status = "disabled"; };
&display { status = "disabled"; };
&isp { status = "disabled"; };
&isp_dart0 { status = "disabled"; };
&isp_dart1 { status = "disabled"; };
&isp_dart2 { status = "disabled"; };
&aop { status = "disabled"; };
&aop_dart { status = "disabled"; };
&atcphy0 { status = "disabled"; };
&atcphy1 { status = "disabled"; };
&atcphy2 { status = "disabled"; };
&pmp { status = "disabled"; };
&speaker_sdz { status = "disabled"; };
&{/aliases} {
    atcphy0 = &atcphy0; atcphy1 = &atcphy1; atcphy2 = &atcphy2;
    usb0 = &usb_drd0; usb1 = &usb_drd1; usb2 = &usb_drd2;
    aop = &aop; isp = &isp;
    gpu-mailbox = &gfx_mbox; gpu-afr-domain = &ps_afr;
    gpu-core-domain = &ps_gfx; gpu-pmp-report = &pmp_gfx;
};
'''
    # Disable every speaker amplifier and card; retain USB/Bluetooth audio.
    board = re.sub(r'(compatible\s*=\s*"(?:apple,j616-macaudio|ti,sn012776)"[^;]*;)',
                   r'\1\n\t\tstatus = "disabled";', board)
    # Do not admit unprotected speaker hardware through the test config either.
    (dts / 't6040-j614s-aurora-direct.dts').write_text(board)
    makefile = dts / 'Makefile'
    if 't6040-j614s-aurora-direct.dtb' not in makefile.read_text():
        with makefile.open('a') as f:
            f.write('\ndtb-$(CONFIG_ARCH_APPLE) += t6040-j614s-aurora-direct.dtb\n')
    subprocess.run(['make', 'LLVM=1', 'apple/t6040-j614s-aurora-direct.dtb'], cwd=tree, check=True)
    # Retire the earlier EFI-stub experiment; Linux uses its stock EFI path.
    stub = tree / 'drivers/firmware/efi/libstub'
    fdt = stub / 'fdt.c'
    text = fdt.read_text()
    text = re.sub(r'#include "aurora-template.h".*?(?=#define EFI_DT_ADDR_CELLS_DEFAULT)',
                  '', text, flags=re.S)
    text = re.sub(r'status = aurora_prepare_fdt\([^;]+;',
                  'status = fdt_open_into(orig_fdt, fdt, new_fdt_size);', text)
    text = text.replace('#include "efistub.h"\n#define EFI_DT_ADDR_CELLS_DEFAULT',
                        '#include "efistub.h"\n\n#define EFI_DT_ADDR_CELLS_DEFAULT')
    fdt.write_text(text)



if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree', type=Path)
    prepare(p.parse_args().tree.resolve())
