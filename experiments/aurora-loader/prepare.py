#!/usr/bin/env python3
"""Pinned Aurora bootloaders with the existing native J614s handoff contract."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parents[2]
DIRECT = PROJECT / 'experiments/aurora-direct'
PINS = {
    'm1n1': '9f7cdfbd0623d96f21965434c3a7dda799ffcff4',
    'uboot': '7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c',
}


def replace(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError(f'Expected one source anchor in {path}: {old[:70]!r}')
    path.write_text(text.replace(old, new))


def prepare_m1n1(tree):
    # Debian GCC's general-registers-only build otherwise emits an unavailable
    # __popcountdi2 runtime helper. This bounded scalar count is equivalent.
    replace(tree / 'src/mcc.c', '        planes = __builtin_popcountll(mask);',
            '        planes = 0;\n        for (unsigned int bit = 0; bit < 64; bit++)\n'
            '            planes += (mask >> bit) & 1;')
    # J614s board 4 has the same four MCC apertures/count/stride as J616s.
    # Keep every upstream geometry and cache-status check; permit only these
    # two exact board identities. No J616s clock-control qualification changes.
    replace(tree / 'src/mcc.c',
            'chip_id != T6040 || board_id != 6 || reg_idx != 12',
            'chip_id != T6040 ||\n'
            '                  !((board_id == 6 && adt_is_compatible(adt, 0, "J616sAP")) ||\n'
            '                    (board_id == 4 && adt_is_compatible(adt, 0, "J614sAP"))) || reg_idx != 12')
    # Limit DMA writes to the three native-tested consumers. Retain the
    # additional bounds from the working loader for AOP and ISP.
    path = tree / 'src/dapf.c'
    replace(path, 'int dapf_init_fdt(const void *fdt)\n{',
            'u32 m4rch_dapf_ready;\n\nint dapf_init_fdt(const void *fdt)\n{')
    anchor = '    while (entry->path != NULL) {\n        if (chip_id == T8140'
    replace(path, anchor, '''    while (entry->path != NULL) {
        if (chip_id == T6040 && strcmp(entry->path, "/arm-io/dart-mtp") &&
            strcmp(entry->path, "/arm-io/dart-aop") &&
            strcmp(entry->path, "/arm-io/dart-isp0")) {
            entry++;
            continue;
        }
        if (chip_id == T8140''')
    # Result handling occurs twice: restrict to the generic final loop.
    text = path.read_text()
    start = text.index('int dapf_init_fdt(')
    old = '''        if (dapf_init(entry->path, entry->index) < 0) {
            ret = -1;
        }'''
    new = '''        if (dapf_init(entry->path, entry->index) < 0) {
            ret = -1;
        } else if (chip_id == T6040) {
            if (!strcmp(entry->path, "/arm-io/dart-aop")) m4rch_dapf_ready |= 1;
            if (!strcmp(entry->path, "/arm-io/dart-isp0")) m4rch_dapf_ready |= 2;
        }'''
    if text[start:].count(old) != 1:
        raise ValueError('DAPF result anchor changed')
    path.write_text(text[:start] + text[start:].replace(old, new))
    # Reuse the exact bounded ADT check from our native-tested preparation.
    source = (DIRECT / 'prepare_m1n1.py').read_text()
    guard = source.split("    guard = '''", 1)[1].split("'''", 1)[0]
    replace(path, '    u64 base;\n    if (adt_get_reg', guard + '    u64 base;\n    if (adt_get_reg')
    # Aurora owns ANS startup, queue retirement and live RTKit retention.
    # This ESP stage 2 has no chainload feature, so initialize ANS explicitly.
    path = tree / 'src/kboot.c'
    replace(path, '#include "kboot.h"', '#include "kboot.h"\n#include "nvme.h"\n#include "smc.h"')
    patch = (PROJECT / 'patches/gravity-m1n1-j614s.patch').read_text()
    added = '\n'.join(line[1:] for line in patch.splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    power = added.split('/* J614s\'s ADT describes', 1)[1].split('\n    if (sdboot_power_reader())', 1)[0]
    power = '/* J614s\'s ADT describes' + power
    replace(path, 'int kboot_boot(void *kernel)\n{', power + '\nint kboot_boot(void *kernel)\n{')
    replace(path, '    int described = chip_id == T8132 ? pcie_prepare_fdt(dt) : 0;',
            '    if (chip_id == T6040 && sdboot_power_reader()) return -1;\n'
            '    int described = chip_id == T8132 ? pcie_prepare_fdt(dt) : 0;')
    replace(path, '    printf("Setting SMP mode to WFE...\\n");', '''    if (chip_id == T6040) {
        extern u32 m4rch_dapf_ready;
        if (board_id != 4 || fdt_node_check_compatible(dt, 0, "apple,j614s") ||
            ret < 0 || !nvme_init() || !nvme_shutdown()) {
            printf("AURL001: J614s ANS/DMA preparation failed\\n");
            return -1;
        }
        if (fdt_open_into(dt, dt, dt_bufsize)) return -1;
        /* ANS was initialized after prepare_dt's first RAM snapshot. Its
         * RTKit buffers stay live in the allocator high-water interval. */
        u64 ram_end = cur_boot_args.phys_base + cur_boot_args.mem_size;
        u64 start = ALIGN_DOWN((u64)_base, SZ_16K);
        u64 high = max(heapblock_high_water(), cur_boot_args.top_of_kernel_data);
        if (!cur_boot_args.mem_size || ram_end < cur_boot_args.phys_base ||
            start < cur_boot_args.phys_base || high > UINT64_MAX - (SZ_16K - 1))
            return -1;
        u64 end = ALIGN_UP(high, SZ_16K);
        if (end <= start || end > ram_end || fdt_add_mem_rsv(dt, start, end - start) ||
            dt_set_memory()) return -1;
        int chosen = fdt_path_offset(dt, "/chosen");
        if (chosen < 0 ||
            fdt_setprop_u32(dt, chosen, "m4rch,dapf-ready", m4rch_dapf_ready) ||
            fdt_setprop_string(dt, chosen, "m4rch,bootloader", "AURL001") ||
            fdt_pack(dt)) return -1;
        printf("AURL001: Aurora m1n1 J614s live ANS and DMA handoff ready\\n");
    }
    printf("Setting SMP mode to WFE...\\n");''')


def prepare_uboot(tree, output):
    # Keep the limited firmware-bridge configuration: Linux initializes USB,
    # PCIe peripherals and input itself. No speaker drivers run in U-Boot.
    path = tree / 'arch/arm/Kconfig'
    text = path.read_text()
    start, end = text.index('config ARCH_APPLE\n'), text.index('\nconfig ARCH_OWL\n')
    block = text[start:end]
    for name in ['CMD_PCI', 'CMD_USB', 'DM_GPIO', 'DM_KEYBOARD', 'DM_MAILBOX',
                 'DM_RESET', 'DM_SPI', 'DM_USB', 'IOMMU', 'MTD', 'PCI', 'PHY',
                 'PINCTRL', 'POWER_DOMAIN', 'REGMAP', 'SPI', 'SYSCON',
                 'SYSRESET_WATCHDOG', 'SYSRESET_WATCHDOG_AUTO', 'USB']:
        old = '\tselect ' + name + '\n'
        if block.count(old) != 1:
            raise ValueError('ARCH_APPLE select changed: ' + name)
        block = block.replace(old, '\tselect ' + name + ' if !APPLE_NOIO\n')
    path.write_text(text[:start] + block + text[end:])
    replace(tree / 'arch/arm/mach-apple/Kconfig', 'if ARCH_APPLE\n',
            'if ARCH_APPLE\n\nconfig APPLE_NOIO\n'
            '\tbool "J614s limited NVMe firmware bridge"\n\tselect BLK\n')
    shutil.copyfile(PROJECT / 'sdboot/uboot-nvme.config', tree / 'configs/apple_sdboot_defconfig')
    replace(tree / 'configs/apple_sdboot_defconfig',
            'CONFIG_DEFAULT_DEVICE_TREE="t8103-j274"',
            'CONFIG_DEFAULT_DEVICE_TREE="apple/t8103-j274"')
    with (tree / 'configs/apple_sdboot_defconfig').open('a') as config:
        config.write('\nCONFIG_OF_UPSTREAM_BUILD_VENDOR=y\nCONFIG_OF_UPSTREAM_VENDOR="apple"\n'
                     'CONFIG_SYS_FDT_PAD=0x20000\n')
    # The old map already uses live DT resources and bounds every aperture.
    # Retain it, but use the real split NVMe BAR without widening its alias.
    patch = (PROJECT / 'patches/gravity-uboot-j614s.patch').read_text()
    added = '\n'.join(line[1:] for line in patch.splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    mapping = added.split('/* Map only the J614s resources', 1)[1]
    mapping = '/* Map only the J614s resources' + mapping.split('\n\telse if (of_machine', 1)[0]
    # The last lines in that range belong to the build_mem_map insertion.
    mapping = mapping[:mapping.index('\n\t\tsd_build_map();')] if '\n\t\tsd_build_map();' in mapping else mapping
    mapping = mapping[:mapping.rfind('\n}') + 2] + '\n'
    start = mapping.index('    /* Retain all three reg tuples')
    end = mapping.index('    nvme_map_expected(node,', start)
    mapping = mapping[:start] + mapping[end:]
    mapping = mapping.replace('"apple,t8132-nvme-ans2"', '"apple,t6041-nvme-ans2"')
    mapping = mapping.replace('nvme_map_expected(node, 0x44dcc0000ULL, 0x60000)',
                              'nvme_map_expected(node, 0x44dcc0000ULL, 0x10000)')
    (tree / 'arch/arm/mach-apple/j614s-map.h').write_text(mapping)
    path = tree / 'arch/arm/mach-apple/board.c'
    replace(path, 'struct mm_region *mem_map;', '#include "j614s-map.h"\n\nstruct mm_region *mem_map;')
    replace(path, '\telse\n\t\tpanic("Unsupported SoC\\n");',
            '\telse if (of_machine_is_compatible("apple,t6040")) {\n'
            '\t\tsd_build_map();\n\t\tmem_map = sd_map;\n\t}\n'
            '\telse\n\t\tpanic("Unsupported SoC\\n");')
    replace(path, '\tenv_set("storage_interface", blk_get_uclass_name(UCLASS_NVME));\n'
                  '\tenv_set("fw_dev_part", asahi_esp_devpart());',
                  '\t/* archnvme probes the uniquely identified ESP after video is ready. */')
    # Public Aurora Linux T6040 subtype: LSQ doorbells/control are in NVMMU.
    path = tree / 'drivers/nvme/nvme_apple.c'
    replace(path, '\tbool post_m4;', '\tbool post_m4;\n\tbool lsq_in_nvmmu;')
    replace(path, 'struct apple_nvme_priv {', '''static const struct apple_nvme_hw apple_nvme_t6041_hw = {
	.post_m4 = true,
	.lsq_in_nvmmu = true,
	.max_ns_id = 1,
};

struct apple_nvme_priv {''')
    replace(path, '\tvoid *nvmmu;\t\t/* NVMMU registers */',
                  '\tvoid *nvmmu;\t\t/* NVMMU registers */\n\tvoid *lsq; /* Linear queue controls/doorbells */')
    replace(path, '((void __iomem *)dev->bar) + ANS_ASQ_DB;', 'priv->lsq + ANS_ASQ_DB;')
    replace(path, '((void __iomem *)dev->bar) + ANS_IOSQ_DB;', 'priv->lsq + ANS_IOSQ_DB;')
    replace(path, '\tpriv->ndev.bar = priv->base;',
                  '\tpriv->lsq = priv->hw->lsq_in_nvmmu ? priv->nvmmu : priv->base;\n\tpriv->ndev.bar = priv->base;')
    replace(path, '\twritel(ANS_LINEAR_SQ_CTRL_EN, priv->base + ANS_LINEAR_SQ_CTRL);\n'
                  '\tif (!(readl(priv->base + ANS_LINEAR_SQ_CTRL) & ANS_LINEAR_SQ_CTRL_EN)) {',
                  '\t/* M4 Pro firmware has already enabled LSQ in the NVMMU. */\n'
                  '\tif (!priv->hw->lsq_in_nvmmu)\n'
                  '\t\twritel(ANS_LINEAR_SQ_CTRL_EN, priv->lsq + ANS_LINEAR_SQ_CTRL);\n'
                  '\tif (!(readl(priv->lsq + ANS_LINEAR_SQ_CTRL) & ANS_LINEAR_SQ_CTRL_EN)) {')
    replace(path, '\t{ .compatible = "apple,t8132-nvme-ans2",',
                  '\t{ .compatible = "apple,t6041-nvme-ans2",\n'
                  '\t  .data = (ulong)&apple_nvme_t6041_hw },\n'
                  '\t{ .compatible = "apple,t8132-nvme-ans2",')
    # Retain our fixed EFI entry and tested data-only board translation. The
    # old prepare_live_nvme backport is deliberately NOT applied to Aurora.
    directory = tree / 'arch/arm/mach-apple'
    shutil.copyfile(PROJECT / 'sdboot/archnvme.c', directory / 'archsd.c')
    import sys
    sys.path.insert(0, str(DIRECT))
    import prepare_loader
    original = prepare_loader.prepare_live_nvme
    prepare_loader.prepare_live_nvme = lambda _: None
    try:
        prepare_loader.prepare(tree, PROJECT / 'out/aurora-direct/template.dtb')
    finally:
        prepare_loader.prepare_live_nvme = original
    replace(directory / 'Makefile', 'obj-y += board.o', 'obj-y += board.o archsd.o')
    # Keep the existing firmware bridge's EFI block devices read-only.
    replace(tree / 'lib/efi_loader/efi_disk.c',
            '\tdiskobj->media.media_present = 1;',
            '\tdiskobj->media.media_present = 1;\n'
            '\tif (IS_ENABLED(CONFIG_APPLE_NOIO))\n\t\tdiskobj->media.read_only = true;')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, pin in PINS.items():
        tree = args.work / name
        actual = subprocess.check_output(['git', '-C', str(tree), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != pin or subprocess.check_output(['git', '-C', str(tree), 'status', '--porcelain']):
            raise ValueError('Expected clean pinned source: ' + name)
    prepare_m1n1(args.work / 'm1n1')
    prepare_uboot(args.work / 'uboot', args.output)
    (args.output / 'source-pins.json').write_text(json.dumps(PINS, indent=2) + '\n')


if __name__ == '__main__':
    main()
