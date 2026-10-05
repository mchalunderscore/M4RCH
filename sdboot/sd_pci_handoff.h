/* Return the SD bridge's temporary bus numbering to Linux at OS handoff.
 * Included after the Apple PCI configuration accessors in pcie_apple.c. */
#ifndef ARCH_M4_SD_PCI_HANDOFF_H
#define ARCH_M4_SD_PCI_HANDOFF_H

static bool apple_sd_pci_handoff_required;
static bool apple_sd_pci_handoff_complete;

/* Called only after a successful SD-only host probe. An EFI self-test which
 * never probes this host does not require a PCI handoff. */
static void apple_sd_pci_handoff_arm(void)
{
    apple_sd_pci_handoff_complete = false;
    apple_sd_pci_handoff_required = true;
}

/* ExitBootServices checks this after driver removal, because a child remove
 * failure can skip the host callback and driver model discards that error. */
void apple_sd_pci_handoff_check(void);
void apple_sd_pci_handoff_check(void)
{
    if (apple_sd_pci_handoff_required && !apple_sd_pci_handoff_complete)
        panic("ARCHM4: SD PCI bus handoff did not complete\n");
}

static int apple_sd_pci_handoff(struct udevice *dev)
{
    const pci_dev_t bdf = PCI_BDF(0, 1, 0);
    const fdt32_t *range;
    ofnode port;
    ulong value, buses, cleared;
    u32 reg;
    int len, ret;

    /* This loader only enumerates the SD port. Do not touch Wi-Fi, other
     * root ports, link training, the PHY, or any DART translation state. */
    if (!of_machine_is_compatible("apple,j614s") || dev_seq(dev) != 0 ||
        !ofnode_device_is_compatible(dev_ofnode(dev), "apple,t6040-pcie") ||
        dev_read_addr_index(dev, 0) != 0x1cb0000000ULL)
        return -EINVAL;
    port = ofnode_find_subnode(dev_ofnode(dev), "pci@1,0");
    if (!ofnode_valid(port) || !ofnode_is_enabled(port) ||
        ofnode_read_u32_index(port, "reg", 0, &reg) || reg != 0x800)
        return -EINVAL;
    range = ofnode_get_property(port, "bus-range", &len);
    if (!range || len != 2 * sizeof(*range) ||
        fdt32_to_cpu(range[0]) != 2 || fdt32_to_cpu(range[1]) != 2)
        return -EINVAL;

    ret = apple_pcie_read_config(dev, bdf, PCI_VENDOR_ID, &value, PCI_SIZE_16);
    if (ret)
        return ret;
    if (value != PCI_VENDOR_ID_APPLE)
        return -ENODEV;
    ret = apple_pcie_read_config(dev, bdf, PCI_HEADER_TYPE, &value, PCI_SIZE_8);
    if (ret)
        return ret;
    if ((value & 0x7f) != PCI_HEADER_TYPE_BRIDGE)
        return -ENODEV;
    ret = apple_pcie_read_config(dev, bdf, PCI_PRIMARY_BUS, &buses, PCI_SIZE_32);
    if (ret)
        return ret;
    if (buses == 0xffffffff || (buses & 0xff))
        return -EIO;
    if ((buses & 0xffffff) &&
        (!(buses & 0xff00) || ((buses >> 8) & 0xff) > ((buses >> 16) & 0xff)))
        return -EIO;

    /* U-Boot's SD-only scan uses bus 1. Linux otherwise preserves that
     * assignment, moves Wi-Fi to bus 2, and swaps the DT's DART mappings.
     * Clearing the temporary bus numbers lets Linux enumerate both ports
     * in their normal order: Wi-Fi on 1, SD on 2. Keep the latency byte. */
    cleared = buses & 0xff000000;
    if (buses != cleared) {
        ret = apple_pcie_write_config(dev, bdf, PCI_PRIMARY_BUS,
                                     cleared, PCI_SIZE_32);
        if (ret)
            return ret;
        ret = apple_pcie_read_config(dev, bdf, PCI_PRIMARY_BUS, &value, PCI_SIZE_32);
        if (ret)
            return ret;
        if (value != cleared)
            return -EIO;
    }
    apple_sd_pci_handoff_complete = true;
    printf("ARCHM4: SD PCI bus handoff %08lx -> %08lx; Linux will enumerate both ports\n",
           buses, cleared);
    return 0;
}

#endif
