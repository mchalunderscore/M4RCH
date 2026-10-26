/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
/* Consume Aurora m1n1's same-boot DRAM reservations. The kernel's T6040
 * nCal=0 flow needs external code and the identity OS log, not EDATA. */
static int aop_standard_handoff(void *out, const void *live, u32 ready)
{
    fdt32_t handles[8];
    u32 device;
    int source = find_compatible(live, "apple,t6041-aop"), dest;
    int len, count = 0, code = 0, log = 0;
    const fdt32_t *refs;

    if (!(ready & 1)) return BAD;
    CHECK(source);
    dest = find_compatible(out, "apple,t6041-aop"); CHECK(dest);
    device = fdt_get_phandle(out, dest);
    if (!device) {
        CHECK(fdt_generate_phandle(out, &device));
        CHECK(fdt_setprop_u32(out, dest, "phandle", device));
    }
    refs = fdt_getprop(live, source, "memory-region", &len);
    if (!refs || len <= 0 || len > sizeof(handles) || len % 4) return BAD;
    for (int i = 0; i < len / 4; i++) {
        char path[160];
        int node = fdt_node_offset_by_phandle(live, fdt32_ld(refs + i)), bytes, target;
        const fdt32_t *maps;
        const fdt64_t *reg;
        u64 phys, size, iova, span;
        fdt32_t remapped[5];
        u32 handle;
        CHECK(node);
        CHECK(fdt_get_path(live, node, path, sizeof(path)));
        reg = fdt_getprop(live, node, "reg", &bytes);
        if (!reg || bytes != 16 || !fdt_getprop(live, node, "no-map", NULL)) return BAD;
        phys = fdt64_ld(reg); size = fdt64_ld(reg + 1);
        maps = fdt_getprop(live, node, "iommu-addresses", &bytes);
        if (!maps || bytes != 20 || fdt32_ld(maps) != fdt_get_phandle(live, source)) return BAD;
        iova = fdt64_ld((const fdt64_t *)(maps + 1));
        span = fdt64_ld((const fdt64_t *)(maps + 3));
        if (!size || size != span || (phys & 0x3fff) || (size & 0x3fff) ||
            (iova & 0x3fff) || phys > ~0ULL - size || iova > ~0ULL - size) return BAD;
        target = fdt_path_offset(out, path); CHECK(target);
        /* Leave unused calibration RAM reserved, without a stale consumer. */
        if (iova != 0x10000000000ULL && iova != phys) {
            int r = fdt_delprop(out, target, "iommu-addresses");
            if (r != -FDT_ERR_NOTFOUND) CHECK(r);
            continue;
        }
        code += iova == 0x10000000000ULL;
        log += iova == phys;
        memcpy(remapped, maps, sizeof(remapped)); remapped[0] = cpu_to_fdt32(device);
        CHECK(fdt_setprop(out, target, "iommu-addresses", remapped, sizeof(remapped)));
        target = fdt_path_offset(out, path);
        handle = fdt_get_phandle(out, target);
        if (!handle) {
            CHECK(fdt_generate_phandle(out, &handle));
            CHECK(fdt_setprop_u32(out, target, "phandle", handle));
        }
        handles[count++] = cpu_to_fdt32(handle);
    }
    if (code != 1 || log != 1 || count != 2) return BAD;
    dest = find_compatible(out, "apple,t6041-aop"); CHECK(dest);
    CHECK(fdt_setprop(out, dest, "memory-region", handles, count * sizeof(handles[0])));
    CHECK(set_enabled(out, "apple,t6041-aop"));
    dest = find_compatible(out, "apple,t6041-aop");
    refs = fdt_getprop(out, dest, "iommus", &len);
    if (!refs || len < 8) return BAD;
    dest = fdt_node_offset_by_phandle(out, fdt32_ld(refs)); CHECK(dest);
    printf("AUMI013: Aurora m1n1 AOP code/log reservations transferred\n");
    return fdt_setprop_string(out, dest, "status", "okay");
}
