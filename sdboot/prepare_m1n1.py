"""J614s SD power handoff, before the pinned upstream PCIe initialization."""
from pathlib import Path


def prepare(tree: Path):
    path = tree / "src/kboot.c"
    text = path.read_text()
    anchor = "int kboot_boot(void *kernel)\n{"
    if text.count(anchor) != 1 or text.count("    usb_init();\n    pcie_init();") != 1:
        raise ValueError("Pinned m1n1 boot sequence changed")
    helper = r'''/* J614s's ADT describes the SD-reader supply through this SMC key.
 * Match the complete action before writing; never guess on another board. */
static int sdboot_power_reader(void)
{
    if (chip_id != T6040 || fdt_node_check_compatible(dt, 0, "apple,j614s")) {
        printf("SDBOOT: unsupported machine\n");
        return -1;
    }
    int node = adt_path_offset(adt, "/arm-io/apcie0/pci-bridge1/pcie-sdreader");
    u32 len = 0, action[4], smc_phandle = 0;
    const void *prop = node < 0 ? NULL : adt_getprop(adt, node, "function-sd_pwr_en", &len);
    if (!prop || len != sizeof(action)) {
        printf("SDBOOT: missing SD power action\n");
        return -1;
    }
    memcpy(action, prop, sizeof(action));
    int pmu = adt_path_offset(adt, "/arm-io/smc/iop-smc-nub/smc-pmu");
    if (pmu < 0 || adt_getprop_copy(adt, pmu, "AAPL,phandle", &smc_phandle,
                                  sizeof(smc_phandle)) < 0 || !smc_phandle ||
        action[0] != smc_phandle || action[1] != 0x704b5734 ||
        action[2] != 0x67503139 || action[3]) {
        printf("SDBOOT: unexpected SD power action\n");
        return -1;
    }
    smc_dev_t *smc = smc_init();
    if (!smc)
        return -1;
    int ret = smc_write_u32(smc, 0x67503139, 0x01000001);
    smc_shutdown(smc);
    if (ret) {
        printf("SDBOOT: SD power write failed (%d)\n", ret);
        return -1;
    }
    mdelay(100);
    printf("SDBOOT: J614s SD supply enabled; initializing PCIe once\n");
    return 0;
}

'''
    text = '#include "smc.h"\n' + text.replace(anchor, helper + anchor)
    text = text.replace("    usb_init();\n    pcie_init();",
                        "    usb_init();\n    if (sdboot_power_reader())\n        return -1;\n    pcie_init();")
    path.write_text(text)
