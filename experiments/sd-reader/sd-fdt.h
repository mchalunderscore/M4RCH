/* SPDX-License-Identifier: GPL-2.0-only */
/* J614s experiment: enable the existing SD PCIe description for Linux only.
 * Called on the EFI handoff copy, after U-Boot has finished its PCI scan. */
static int j614s_sd_fdt(void *fdt)
{
	const char *pcie_path = "/pcie@1cb0000000";
	const char *port_path = "/pcie@1cb0000000/pci@1,0";
	const char *dart_path = "/iommu@411000000";
	const fdt32_t *p;
	fdt32_t range[2] = { cpu_to_fdt32(0), cpu_to_fdt32(2) };
	fdt32_t child_range[2] = { cpu_to_fdt32(2), cpu_to_fdt32(2) };
	fdt32_t child_reg[5] = { cpu_to_fdt32(0x20000), 0, 0, 0, 0 };
	fdt32_t pins[2];
	u32 wifi_dart, sd_dart;
	int node, len, err;

	if (fdt_node_check_compatible(fdt, 0, "apple,j614s"))
		return -FDT_ERR_BADVALUE;
	node = fdt_path_offset(fdt, pcie_path);
	if (node < 0 || fdt_node_check_compatible(fdt, node, "apple,t6020-pcie"))
		return -FDT_ERR_BADVALUE;
	p = fdt_getprop(fdt, node, "bus-range", &len);
	if (!p || len != 8 || fdt32_to_cpu(p[0]) != 0 || fdt32_to_cpu(p[1]) != 1)
		return -FDT_ERR_BADVALUE;
	wifi_dart = fdt_get_phandle(fdt, fdt_path_offset(fdt, "/iommu@410000000"));
	sd_dart = fdt_get_phandle(fdt, fdt_path_offset(fdt, dart_path));
	p = fdt_getprop(fdt, node, "iommu-map", &len);
	if (!wifi_dart || !sd_dart || !p || len != 32 ||
	    fdt32_to_cpu(p[0]) != 0x100 || fdt32_to_cpu(p[1]) != wifi_dart ||
	    fdt32_to_cpu(p[2]) != 1 || fdt32_to_cpu(p[3]) != 2 ||
	    fdt32_to_cpu(p[4]) != 0x200 || fdt32_to_cpu(p[5]) != sd_dart ||
	    fdt32_to_cpu(p[6]) != 1 || fdt32_to_cpu(p[7]) != 1)
		return -FDT_ERR_BADVALUE;
	/* PCIe's child port is not a platform device; select both CLKREQ
	 * pin groups on the PCIe controller itself before it probes. */
	p = fdt_getprop(fdt, node, "pinctrl-0", &len);
	if (!p || len != 4 || fdt32_to_cpu(*p) !=
	    fdt_get_phandle(fdt, fdt_path_offset(fdt, "/pinctrl@51c000000/wifi-clkreq-pins")))
		return -FDT_ERR_BADVALUE;
	pins[0] = p[0];
	node = fdt_path_offset(fdt, "/pinctrl@51c000000/sd-clkreq-pins");
	if (node < 0 || !fdt_get_phandle(fdt, node))
		return -FDT_ERR_BADVALUE;
	p = fdt_getprop(fdt, node, "pinmux", &len);
	if (!p || len != 4 || fdt32_to_cpu(*p) != 0x10001)
		return -FDT_ERR_BADVALUE;
	pins[1] = cpu_to_fdt32(fdt_get_phandle(fdt, node));
	node = fdt_path_offset(fdt, port_path);
	if (node < 0 || !fdt_getprop(fdt, node, "status", &len) ||
	    len != 9 || strcmp(fdt_getprop(fdt, node, "status", NULL), "disabled"))
		return -FDT_ERR_BADVALUE;
	if (fdt_subnode_offset(fdt, node, "mmc@0,0") != -FDT_ERR_NOTFOUND ||
	    fdt_getprop(fdt, node, "bus-range", &len))
		return -FDT_ERR_BADVALUE;
	p = fdt_getprop(fdt, node, "pinctrl-0", &len);
	if (!p || len != 4 || *p != pins[1])
		return -FDT_ERR_BADVALUE;
	{
		const char *names = fdt_getprop(fdt, node, "pinctrl-names", &len);
		if (!names || len != 8 || strcmp(names, "default"))
			return -FDT_ERR_BADVALUE;
	}
	p = fdt_getprop(fdt, node, "reg", &len);
	if (!p || len != 20 || fdt32_to_cpu(p[0]) != 0x800)
		return -FDT_ERR_BADVALUE;
	p = fdt_getprop(fdt, node, "reset-gpios", &len);
	if (!p || len != 12 || fdt32_to_cpu(p[1]) != 5 || fdt32_to_cpu(p[2]) != 1)
		return -FDT_ERR_BADVALUE;
	node = fdt_path_offset(fdt, dart_path);
	if (node < 0 || fdt_node_check_compatible(fdt, node, "apple,t8110-dart") ||
	    !fdt_getprop(fdt, node, "status", &len) || len != 9 ||
	    strcmp(fdt_getprop(fdt, node, "status", NULL), "disabled"))
		return -FDT_ERR_BADVALUE;

	/* Re-find offsets after every size-changing operation. */
	err = fdt_setprop(fdt, fdt_path_offset(fdt, pcie_path), "bus-range", range, sizeof(range));
	if (!err)
		err = fdt_setprop(fdt, fdt_path_offset(fdt, pcie_path), "pinctrl-0", pins, sizeof(pins));
	/* The parent now owns CLKREQ1. Avoid a second claim by pcieport. */
	if (!err)
		err = fdt_delprop(fdt, fdt_path_offset(fdt, port_path), "pinctrl-0");
	if (!err)
		err = fdt_delprop(fdt, fdt_path_offset(fdt, port_path), "pinctrl-names");
	if (!err)
		err = fdt_setprop_string(fdt, fdt_path_offset(fdt, dart_path), "status", "okay");
	if (!err)
		err = fdt_setprop_string(fdt, fdt_path_offset(fdt, port_path), "status", "okay");
	if (!err)
		err = fdt_setprop(fdt, fdt_path_offset(fdt, port_path), "bus-range", child_range, sizeof(child_range));
	if (!err) {
		node = fdt_add_subnode(fdt, fdt_path_offset(fdt, port_path), "mmc@0,0");
		if (node < 0)
			err = node;
	}
	if (!err)
		err = fdt_setprop_string(fdt, node, "compatible", "pci17a0,9755");
	if (!err)
		err = fdt_setprop(fdt, node, "reg", child_reg, sizeof(child_reg));
	if (!err)
		err = fdt_setprop(fdt, node, "cd-inverted", NULL, 0);
	if (!err)
		err = fdt_setprop(fdt, node, "wp-inverted", NULL, 0);
	if (!err)
		printf("J614s SD: port 1, bus 2 and DART enabled for OS\n");
	return err;
}
