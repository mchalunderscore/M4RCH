"""Apply the narrowly scoped J614s loader changes to pinned U-Boot sources."""
from pathlib import Path
import shutil


def replace(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError(f"Pinned source changed: {path}: {old[:70]!r}")
    path.write_text(text.replace(old, new))


def prepare(tree, recipe):
    board = tree / 'arch/arm/mach-apple/board.c'
    replace(board, 'struct mm_region *mem_map;', r'''
/* Only mapped resources can be touched by this SD-only loader. PIO avoids
 * giving U-Boot ownership of SD DMA/DART state in the first implementation. */
static struct mm_region sd_map[32];
static int sd_slots;
static void sd_map_add(u64 base, u64 size)
{
    if (!size || base == FDT_ADDR_T_NONE || sd_slots >= 29)
        panic("Invalid SD loader MMIO map\n");
    size += base & (SZ_4K - 1);
    base = ALIGN_DOWN(base, SZ_4K);
    sd_map[sd_slots++] = (struct mm_region) {
        .virt = base, .phys = base, .size = ALIGN(size, SZ_4K),
        .attrs = PTE_BLOCK_MEMTYPE(MT_DEVICE_NGNRNE) |
                 PTE_BLOCK_NON_SHARE | PTE_BLOCK_PXN | PTE_BLOCK_UXN,
    };
}
static void sd_build_map(void)
{
    ofnode node = ofnode_by_compatible(ofnode_null(), "apple,t6040-pcie");
    fdt_size_t size;
    fdt_addr_t addr;
    const fdt32_t *ranges;
    int len;
    memset(sd_map, 0, sizeof(sd_map));
    sd_slots = 0;
    if (!ofnode_valid(node))
        panic("Missing T6040 PCIe node\n");
    /* ECAM and the SD port's control/refclock registers only. */
    addr = ofnode_get_addr_size_index(node, 0, &size);
    sd_map_add(addr, size);
    addr = ofnode_get_addr_size_index(node, 3, &size);
    sd_map_add(addr, size);
    addr = ofnode_get_addr_size_index(node, 7, &size);
    sd_map_add(addr, size);
    ranges = ofnode_get_property(node, "ranges", &len);
    if (!ranges || len <= 0 || len % 28)
        panic("Unexpected T6040 PCIe ranges\n");
    for (int i = 0; i < len / 4; i += 7) {
        u64 base = ((u64)fdt32_to_cpu(ranges[i + 3]) << 32) |
                   fdt32_to_cpu(ranges[i + 4]);
        u64 count = ((u64)fdt32_to_cpu(ranges[i + 5]) << 32) |
                    fdt32_to_cpu(ranges[i + 6]);
        sd_map_add(base, count);
    }
    node = ofnode_by_compatible(ofnode_null(), "apple,t6040-pinctrl");
    addr = ofnode_get_addr_size_index(node, 0, &size);
    if (addr != 0x51c000000ULL || size < 24)
        panic("Unexpected J614s GPIO aperture\n");
    /* Only the page containing CLKREQ1 and endpoint PERST GPIO5. */
    sd_map_add(addr, SZ_4K);
    node = ofnode_by_compatible(ofnode_null(), "apple,wdt");
    addr = ofnode_get_addr_size_index(node, 0, &size);
    sd_map_add(addr, size);
    /* Existing build_mem_map fills these final RAM/framebuffer slots. */
    sd_map[sd_slots++].attrs = PTE_BLOCK_MEMTYPE(MT_NORMAL) | PTE_BLOCK_INNER_SHARE;
    sd_map[sd_slots++].attrs = PTE_BLOCK_MEMTYPE(MT_NORMAL_NC) |
        PTE_BLOCK_INNER_SHARE | PTE_BLOCK_PXN | PTE_BLOCK_UXN;
}

struct mm_region *mem_map;''')
    replace(board, 'else if (of_machine_is_compatible("apple,t6040"))\n\t\tmem_map = t6040_noio_mem_map;',
            'else if (of_machine_is_compatible("apple,t6040")) {\n\t\tsd_build_map();\n\t\tmem_map = sd_map;\n\t}')
    # LMB already excludes both U-Boot and the live DT's firmware reservations.
    # Reserve only the EFI application and handoff DT buffers. GRUB and the
    # EFI kernel stub allocate OS memory through the UEFI memory services.
    replace(board, 'lmb_alloc(SZ_1G, &addr) ? env_set_hex("loadaddr", addr)',
            'lmb_alloc(SZ_64M, &addr) ? env_set_hex("loadaddr", addr)')
    for size, name in (("SZ_128M", "kernel_addr_r"), ("SZ_1G", "ramdisk_addr_r")):
        replace(board, f'\tstatus |= !lmb_alloc({size}, &addr) ?\n\t\tenv_set_hex("{name}", addr) : 1;\n', '')
    replace(board, '''\tstatus |= !lmb_alloc(KERNEL_COMP_SIZE, &addr) ?
\t\tenv_set_hex("kernel_comp_addr_r", addr) : 1;
\tstatus |= !lmb_alloc(KERNEL_COMP_SIZE, &addr) ?
\t\tenv_set_hex("kernel_comp_size", addr) : 1;
''', '')
    replace(board, '''\tstatus |= !lmb_alloc(SZ_4M, &addr) ?
\t\tenv_set_hex("pxefile_addr_r", addr) : 1;
''', '')
    pci = tree / 'drivers/pci/pcie_apple.c'
    replace(pci, 'struct apple_pcie_priv {', '#include "arch_m4_sd_pcie.h"\n\nstruct apple_pcie_priv {')
    shutil.copyfile(recipe / 'sd_pcie.h', tree / 'drivers/pci/arch_m4_sd_pcie.h')
    replace(pci, 'static const struct udevice_id apple_pcie_of_match[] = {', '''
static const struct udevice_id apple_pcie_of_match[] = {
    { .compatible = "apple,t6040-pcie", .data = (ulong)&t602x_hw },''')
    replace(pci, '\tret = gpio_request_by_name_nodev(np, "reset-gpios", 0, &reset, 0);', '''
    /* m1n1 initializes the controller but leaves endpoint reset and
     * link training to the next stage. Finish only the J614s SD port. */
    if (IS_ENABLED(CONFIG_APPLE_NOIO)) {
        struct ofnode_phandle_args reset_spec;
        fdt_addr_t phy, gpio;
        fdt_size_t size;

        if (ofnode_read_u32_index(np, "reg", 0, &idx))
            return -EINVAL;
        if ((idx >> 11) != 1)
            return 0;
        if (!of_machine_is_compatible("apple,j614s"))
            return -EINVAL;
        addr = dev_read_addr_name(pcie->dev, "port1");
        phy = dev_read_addr_name(pcie->dev, "phy1");
        if (addr != 0x411028000ULL || phy != 0x417024000ULL ||
            ofnode_parse_phandle_with_args(np, "reset-gpios", "#gpio-cells",
                                          0, 0, &reset_spec) ||
            reset_spec.args_count != 2 || reset_spec.args[0] != 5 ||
            reset_spec.args[1] != 1 ||
            !ofnode_device_is_compatible(reset_spec.node, "apple,t6040-pinctrl"))
            return -EINVAL;
        gpio = ofnode_get_addr_size_index(reset_spec.node, 0, &size);
        if (gpio != 0x51c000000ULL || size < 24)
            return -EINVAL;
        return apple_sd_pcie_train((void *)(ulong)addr, (void *)(ulong)phy,
                                   (void *)(ulong)gpio);
    }
\tret = gpio_request_by_name_nodev(np, "reset-gpios", 0, &reset, 0);''')
    # Hide all root ports except port1; no probing of Wi-Fi or unused PHYs.
    replace(pci, '\taddr = pcie->cfg_base;\n', '''
    if (IS_ENABLED(CONFIG_APPLE_NOIO) && PCI_BUS(bdf) == 0 &&
        (PCI_DEV(bdf) != 1 || PCI_FUNC(bdf) != 0))
        return -ENODEV;
\taddr = pcie->cfg_base;
''')
    # The upstream error used an uninitialized loop index; name the DT port.
    replace(pci, '\tint i, ret;\n', '\tint ret;\n')
    replace(pci, '\t\t\tdev_err(pcie->dev, "Port %d setup fail: %d\\n", i, ret);',
            '\t\t\tdev_err(pcie->dev, "Port %s setup fail: %d\\n", ofnode_get_name(of_port), ret);')
    replace(pci, '''\treturn pci_generic_mmap_write_config(bus, apple_pcie_config_address,
''', '''
    /* PNP normally enables endpoint bus mastering. This loader reads SD
     * through the CPU FIFO only and must never initiate endpoint DMA. */
    if (IS_ENABLED(CONFIG_APPLE_NOIO) && PCI_BUS(bdf) != 0 && offset == PCI_COMMAND)
        value &= ~PCI_COMMAND_MASTER;
\treturn pci_generic_mmap_write_config(bus, apple_pcie_config_address,
''')
    # Firmware sees only the SD port and numbers it bus 1. Linux must scan
    # both ports afresh to match the DT's fixed Wi-Fi/SD IOMMU requester IDs.
    # Do this only when leaving boot services, after child MMC cleanup, so
    # GRUB can continue using EFI block I/O throughout its normal lifetime.
    shutil.copyfile(recipe / 'sd_pci_handoff.h', tree / 'drivers/pci/arch_m4_sd_pci_handoff.h')
    replace(pci, 'static const struct dm_pci_ops apple_pcie_ops = {',
            '#include "arch_m4_sd_pci_handoff.h"\n\nstatic const struct dm_pci_ops apple_pcie_ops = {')
    replace(pci, '''\treturn 0;
}

static int apple_pcie_remove''', '''    if (IS_ENABLED(CONFIG_APPLE_NOIO))
        apple_sd_pci_handoff_arm();
\treturn 0;
}

static int apple_pcie_remove''')
    replace(pci, '''\tstruct apple_pcie_port *port, *tmp;

\tlist_for_each_entry_safe''', '''\tstruct apple_pcie_port *port, *tmp;

    if (IS_ENABLED(CONFIG_APPLE_NOIO)) {
        int ret = apple_sd_pci_handoff(dev);

        /* dm_remove_devices_active ignores callback error returns. Never
         * enter Linux with a failed handoff and mismatched DMA mappings. */
        if (ret)
            panic("ARCHM4: SD PCI bus handoff failed (%d)\\n", ret);
        return 0;
    }
\tlist_for_each_entry_safe''')
    replace(pci, '\t.remove = apple_pcie_remove,', '''\t.remove = apple_pcie_remove,
    .flags = IS_ENABLED(CONFIG_APPLE_NOIO) ? DM_FLAG_OS_PREPARE : 0,''')
    mmc = tree / 'drivers/mmc/pci_mmc.c'
    # MMC's uclass pre_remove calls mmc_deinit, which unregisters its cyclic
    # card poll. Otherwise EFI's final schedule() could use the old bus after
    # the parent PCI handoff. Driver model removes children before parents.
    replace(mmc, '\t.probe\t= pci_mmc_probe,', '''\t.probe\t= pci_mmc_probe,
    .flags = IS_ENABLED(CONFIG_APPLE_NOIO) ? DM_FLAG_OS_PREPARE : 0,''')
    # IO_ACCESSORS is a hidden Kconfig symbol; a defconfig assignment alone
    # is discarded. Select it from this target's PCI MMC driver.
    replace(tree / 'drivers/mmc/Kconfig', '''config MMC_PCI
\tbool "Support for MMC controllers on PCI"
\tdepends on MMC_SDHCI''', '''config MMC_PCI
\tbool "Support for MMC controllers on PCI"
\tdepends on MMC_SDHCI
\tselect MMC_SDHCI_IO_ACCESSORS if APPLE_NOIO''')
    replace(mmc, 'static int pci_mmc_probe(struct udevice *dev)',
            '#include "arch_m4_gl9755.h"\n#include "arch_m4_gl9755_pci.h"\n\nstatic int pci_mmc_probe(struct udevice *dev)')
    shutil.copyfile(recipe / 'gl9755.h', tree / 'drivers/mmc/arch_m4_gl9755.h')
    shutil.copyfile(recipe / 'gl9755_pci.h', tree / 'drivers/mmc/arch_m4_gl9755_pci.h')
    replace(mmc, '\tret = mmc_of_parse(dev, &plat->cfg);', '''
    if (IS_ENABLED(CONFIG_APPLE_NOIO)) {
        u16 vendor, device;
        dm_pci_read_config16(dev, PCI_VENDOR_ID, &vendor);
        dm_pci_read_config16(dev, PCI_DEVICE_ID, &device);
        if (vendor != 0x17a0 || device != 0x9755)
            return -ENODEV;
        if (!of_machine_is_compatible("apple,j614s"))
            return -ENODEV;
        ret = gl9755_pci_init(dev);
        if (ret)
            return ret;
        puts("ARCHM4: GL9755 17a0:9755, PIO-only SD reader\\n");
    }
\tret = mmc_of_parse(dev, &plat->cfg);''')
    replace(mmc, '\tret = sdhci_setup_cfg(&plat->cfg, host, 0, 0);', '''
    if (IS_ENABLED(CONFIG_APPLE_NOIO)) {
        u32 bar0, bar1, caps, version, clock_reset;
        u16 command;

        /* Install before setup_cfg's first register read. With accessors
         * enabled U-Boot expects a non-NULL ops table on every access. */
        host->ops = &gl9755_ops;
        if (!host->ioaddr)
            return -ENODEV;
        if (dm_pci_read_config16(dev, PCI_COMMAND, &command) ||
            dm_pci_read_config32(dev, PCI_BASE_ADDRESS_0, &bar0) ||
            dm_pci_read_config32(dev, PCI_BASE_ADDRESS_1, &bar1))
            return -EIO;
        printf("ARCHM4: GL9755 BAR=%08x:%08x command=%04x MMIO=%p\\n",
               bar1, bar0, command, host->ioaddr);
        if (!(command & PCI_COMMAND_MEMORY) || (command & PCI_COMMAND_MASTER)) {
            puts("ARCHM4: GL9755 requires memory decoding with DMA disabled\\n");
            return -ENODEV;
        }
        caps = sdhci_readl(host, SDHCI_CAPABILITIES);
        version = sdhci_readl(host, SDHCI_HOST_VERSION & ~3);
        clock_reset = sdhci_readl(host, SDHCI_CLOCK_CONTROL);
        printf("ARCHM4: GL9755 caps=%08x version=%08x clock/reset=%08x (32-bit reads)\\n",
               caps, version, clock_reset);
        if (!caps || caps == 0xffffffff || version == 0xffffffff ||
            (version >> 16) == 0xffff || clock_reset == 0xffffffff) {
            puts("ARCHM4: GL9755 register window is unreadable; stopping before reset\\n");
            return -ENODEV;
        }
        host->quirks |= SDHCI_QUIRK_NO_1_8_V | SDHCI_QUIRK_BROKEN_HISPD_MODE;
    }
\tret = sdhci_setup_cfg(&plat->cfg, host, 0, 0);''')
    replace(mmc, '\treturn sdhci_probe(dev);', '''
    if (IS_ENABLED(CONFIG_APPLE_NOIO)) {
        /* CD/WP polarity is corrected in hardware by gl9755_pci_init.
         * Do not invert CARD_PRESENT a second time in the MMC core. */
        /* Only legacy 4-bit SD at 3.3 V; no tuning, UHS or eMMC modes. */
        plat->cfg.host_caps &= MMC_MODE_4BIT;
        plat->cfg.voltages = MMC_VDD_32_33 | MMC_VDD_33_34;
        plat->cfg.f_max = 25000000;
    }
    ret = sdhci_probe(dev);
    if (IS_ENABLED(CONFIG_APPLE_NOIO)) {
        /* GL9755 vendor reads use the WT gate too. A gate-closed zero
         * is not evidence that reset cleared the reader's settings. */
        int config_ret = gl9755_pci_verify(dev);

        printf("ARCHM4: GL9755 reader init=%d config=%d\\n", ret, config_ret);
        if (config_ret && !ret)
            ret = config_ret;
    }
    return ret;''')
    sdhci = tree / 'drivers/mmc/sdhci.c'
    # Hardware inversion follows Linux. Before powering the slot, allow
    # card detection to settle after PCI PERST and polarity changes. Do not
    # claim presence or use the raw un-debounced pin as the final decision.
    shutil.copyfile(recipe / 'gl9755_card.h', tree / 'drivers/mmc/arch_m4_gl9755_card.h')
    replace(sdhci, '#include <power/regulator.h>',
            '#include <power/regulator.h>\n#include "arch_m4_gl9755_card.h"')
    replace(sdhci, '''\t/* If nonremovable, assume that the card is always present. */''', '''
    /* This PCI reader uses its native, hardware-corrected detect signal. */
    if (IS_ENABLED(CONFIG_APPLE_NOIO)) {
        return gl9755_get_cd(host);
    }
\t/* If nonremovable, assume that the card is always present. */''')
    # Linux's GL9755 path enables SDHCI 4.10+ PLL after the internal clock
    # stabilizes and before the card clock. This is the standard controller
    # PLL-enable bit, not the vendor high-speed/SSC PLL configuration.
    replace(sdhci, '''\tclk |= SDHCI_CLOCK_CARD_EN;
\tsdhci_writew(host, clk, SDHCI_CLOCK_CONTROL);
\treturn 0;''', '''
    if (IS_ENABLED(CONFIG_APPLE_NOIO) && clk == 0xffff)
        return -EIO;
    if (IS_ENABLED(CONFIG_APPLE_NOIO) && SDHCI_GET_VERSION(host) >= 4 &&
        (sdhci_readw(host, SDHCI_HOST_CONTROL2) & BIT(12))) {
        /* SDHCI_SPEC_410, SDHCI_CTRL_V4_MODE and SDHCI_CLOCK_PLL_EN. */
        clk = (clk | BIT(3)) & ~SDHCI_CLOCK_INT_STABLE;
        sdhci_writew(host, clk, SDHCI_CLOCK_CONTROL);
        timeout = 15000;
        for (;;) {
            clk = sdhci_readw(host, SDHCI_CLOCK_CONTROL);
            if (clk == 0xffff)
                return -EIO;
            if (clk & SDHCI_CLOCK_INT_STABLE)
                break;
            if (!timeout--) {
                printf("ARCHM4: GL9755 PLL clock did not stabilise: clock=%04x\\n", clk);
                return -ETIMEDOUT;
            }
            udelay(10);
        }
    }
\tclk |= SDHCI_CLOCK_CARD_EN;
\tsdhci_writew(host, clk, SDHCI_CLOCK_CONTROL);
    if (IS_ENABLED(CONFIG_APPLE_NOIO)) {
        printf("ARCHM4: GL9755 SD clock=%uHz control=%04x power=%02x present=%08x\\n",
               clock, sdhci_readw(host, SDHCI_CLOCK_CONTROL),
               sdhci_readb(host, SDHCI_POWER_CONTROL), sdhci_readl(host, SDHCI_PRESENT_STATE));
    }
\treturn 0;''')
    replace(sdhci, '\tbool no_hispd_bit = false;', '\tbool no_hispd_bit = false;\n\tint ret;')
    replace(sdhci, '''\tif (mmc->clock != host->clock)
\t\tsdhci_set_clock(mmc, mmc->clock);

\tif (mmc->clk_disable)
\t\tsdhci_set_clock(mmc, 0);''', '''\tif (mmc->clock != host->clock) {
        ret = sdhci_set_clock(mmc, mmc->clock);
        if (ret)
            return ret;
    }

\tif (mmc->clk_disable) {
        ret = sdhci_set_clock(mmc, 0);
        if (ret)
            return ret;
    }''')
    replace(sdhci, '''\t\t\tlog_warning("Timeout for status update: %08x %08x\\n",
\t\t\t\t    stat, mask);
\t\t\treturn -ETIMEDOUT;''', '''\t\t\tlog_warning("Timeout for status update: %08x %08x\\n",
\t\t\t\t    stat, mask);
            if (IS_ENABLED(CONFIG_APPLE_NOIO)) {
                int reset_ret;
                printf("ARCHM4: GL9755 CMD%u arg=%08x timeout: present=%08x clock=%04x power=%02x ctrl2=%04x int_enable=%08x\\n",
                       cmd->cmdidx, cmd->cmdarg, sdhci_readl(host, SDHCI_PRESENT_STATE),
                       sdhci_readw(host, SDHCI_CLOCK_CONTROL),
                       sdhci_readb(host, SDHCI_POWER_CONTROL),
                       sdhci_readw(host, SDHCI_HOST_CONTROL2),
                       sdhci_readl(host, SDHCI_INT_ENABLE));
                /* The ordinary timeout return bypasses the cleanup below,
                 * leaving CMD_INHIBIT stuck for the next card-init attempt. */
                reset_ret = sdhci_reset(host, SDHCI_RESET_CMD);
                if (reset_ret)
                    return reset_ret;
                reset_ret = sdhci_reset(host, SDHCI_RESET_DATA);
                if (reset_ret)
                    return reset_ret;
            }
\t\t\treturn -ETIMEDOUT;''')
    # A failed initialization reset must fail the MMC probe, not continue
    # issuing commands against an uninitialized controller.
    replace(sdhci, 'static void sdhci_reset(struct sdhci_host *host, u8 mask)',
            'static int sdhci_reset(struct sdhci_host *host, u8 mask)')
    replace(sdhci, '''\t\t\tlog_warning("Reset %#x never completed\\n", mask);
\t\t\treturn;''', '''\t\t\tlog_warning("Reset %#x never completed\\n", mask);
            if (IS_ENABLED(CONFIG_APPLE_NOIO))
                printf("ARCHM4: GL9755 reset failed: clock/reset=%08x ctrl2=%04x present=%08x\\n",
                       sdhci_readl(host, SDHCI_CLOCK_CONTROL),
                       sdhci_readw(host, SDHCI_HOST_CONTROL2),
                       sdhci_readl(host, SDHCI_PRESENT_STATE));
\t\t\treturn -ETIMEDOUT;''')
    replace(sdhci, '''\t\tudelay(1000);
\t}
}

static void sdhci_cmd_done''', '''\t\tudelay(1000);
\t}
    if (IS_ENABLED(CONFIG_APPLE_NOIO) && (mask & SDHCI_RESET_ALL)) {
        host->clock = 0;
        /* A full reset clears the mode; Linux restores V4 afterwards. */
        sdhci_writew(host, BIT(12), SDHCI_HOST_CONTROL2);
        puts("ARCHM4: GL9755 reset complete\\n");
    }
    return 0;
}

static void sdhci_cmd_done''')
    replace(sdhci, '''static int sdhci_init(struct mmc *mmc)
{
\tstruct sdhci_host *host = mmc->priv;''', '''static int sdhci_init(struct mmc *mmc)
{
\tstruct sdhci_host *host = mmc->priv;
    int ret;''')
    replace(sdhci, '\tsdhci_reset(host, SDHCI_RESET_ALL);', '''\tret = sdhci_reset(host, SDHCI_RESET_ALL);
    if (ret)
        return ret;
    if (IS_ENABLED(CONFIG_APPLE_NOIO)) {
        ret = gl9755_wait_card(host);
        if (ret)
            return ret;
    }''')
    # Minimal GL9755 reset/power requirements from the pinned Linux
    # drivers/mmc/host/sdhci-pci-gli.c. This build rejects all other PCI MMC
    # devices. We use the standard 25 MHz clock, not vendor high-speed PLLs.
    replace(sdhci, '\t/* Wait max 100 ms */', '''
    if (IS_ENABLED(CONFIG_APPLE_NOIO) && (mask & SDHCI_RESET_ALL)) {
        unsigned int stable = 2000;
        sdhci_writew(host, SDHCI_CLOCK_INT_EN, SDHCI_CLOCK_CONTROL);
        for (;;) {
            u16 clock = sdhci_readw(host, SDHCI_CLOCK_CONTROL);
            if (clock == 0xffff) {
                puts("ARCHM4: GL9755 clock register became unreadable\\n");
                return -EIO;
            }
            if (clock & SDHCI_CLOCK_INT_STABLE)
                break;
            if (!stable--) {
                printf("ARCHM4: GL9755 internal clock did not stabilise: clock/reset=%08x\\n",
                       sdhci_readl(host, SDHCI_CLOCK_CONTROL));
                return -ETIMEDOUT;
            }
            udelay(10);
        }
        /* SDHCI_CTRL_V4_MODE, with UHS-II disabled for legacy SD. */
        sdhci_writew(host, BIT(12), SDHCI_HOST_CONTROL2);
    }
\t/* Wait max 100 ms */''')
    replace(sdhci, '''\tpwr |= SDHCI_POWER_ON;

\tsdhci_writeb(host, pwr, SDHCI_POWER_CONTROL);''', '''\tpwr |= SDHCI_POWER_ON;
    if (IS_ENABLED(CONFIG_APPLE_NOIO)) {
        /* GL9755 needs its auxiliary 1.8 V rail as well as card VDD.
         * This does not request 1.8 V SD signalling. As in Linux, enable
         * card power first and let each rail settle for five milliseconds. */
        sdhci_writeb(host, 0, SDHCI_POWER_CONTROL);
        sdhci_writeb(host, pwr, SDHCI_POWER_CONTROL);
        mdelay(5);
        pwr |= 0xa0 | 0x10; /* SDHCI_VDD2_POWER_180 | SDHCI_VDD2_POWER_ON */
        sdhci_writeb(host, pwr, SDHCI_POWER_CONTROL);
        mdelay(5);
        return;
    }
\tsdhci_writeb(host, pwr, SDHCI_POWER_CONTROL);''')
    # EFI applications see the same read-only policy as the native block
    # driver. Never advertise a writable disk when MMC_WRITE is disabled.
    disk = tree / 'lib/efi_loader/efi_disk.c'
    replace(disk, '\tdiskobj->media.media_present = 1;', '''\tdiskobj->media.media_present = 1;
    if (IS_ENABLED(CONFIG_APPLE_NOIO))
        diskobj->media.read_only = true;''')
    # Driver model ignores remove errors. A failed child callback can prevent
    # the host callback from running at all, so verify completion explicitly
    # after removal and before the kernel can start any DMA.
    replace(tree / 'lib/efi_loader/efi_boottime.c', '\t\tdm_remove_devices_active();', '''\t\tdm_remove_devices_active();
        if (IS_ENABLED(CONFIG_APPLE_NOIO)) {
            extern void apple_sd_pci_handoff_check(void);

            apple_sd_pci_handoff_check();
        }''')
    shutil.copyfile(recipe / 'uboot.config', tree / 'configs/apple_sdboot_defconfig')
    shutil.copyfile(recipe / 'archsd.c', tree / 'arch/arm/mach-apple/archsd.c')
    with (tree / 'arch/arm/mach-apple/Makefile').open('a') as f:
        f.write('\nobj-y += archsd.o\n')
