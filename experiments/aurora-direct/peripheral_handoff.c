/* SPDX-License-Identifier: GPL-2.0-only */
/* FDT representation follows aurora-silicon/m1n1 PR 41: apple,asc-mem,
 * memory-region and iommu-addresses. Addresses always come from this boot.
 * This file performs no MMIO; the earlier loader publishes DMA preparation. */
static int firmware_25g83(struct adt_view a)
{
    u32 len;
    int chosen = adt_named(a, "chosen");
    const char *p = adt_prop(a, chosen, "firmware-version", &len);
    return p && len >= sizeof("mBoot-18000.161.10") && len <= 256 &&
        !memcmp(p, "mBoot-18000.161.10", sizeof("mBoot-18000.161.10"));
}

static int dram_segment(struct adt_view a, const u8 *raw, u64 maximum,
                        u64 *physical, u64 *iova, u64 *span)
{
    u32 len;
    int chosen = adt_named(a, "chosen");
    const u8 *p = adt_prop(a, chosen, "dram-base", &len);
    u64 base, size;
    if (!p || len != 8) return BAD;
    base = le64(p);
    p = adt_prop(a, chosen, "dram-size", &len);
    if (!p || len != 8) return BAD;
    size = le64(p);
    *physical = le64(raw);
    *iova = le64(raw + 16); /* ADT remap, matching dt_reserve_asc_segments */
    *span = ((u64)le32(raw + 24) + 0x3fff) & ~0x3fffULL;
    if (!*span || *span > maximum || (*physical & 0x3fff) || (*iova & 0x3fff) ||
        *physical < base || *span > size || *physical - base > size - *span ||
        *iova > ~0ULL - *span)
        return BAD;
    return 0;
}

static int set_enabled(void *dt, const char *compatible)
{
    int n = find_compatible(dt, compatible);
    CHECK(n);
    return fdt_setprop_string(dt, n, "status", "okay");
}

static int gpu_dependencies(void *dt, int enable)
{
    static const char aliases[][24] = {"gpu-afr-domain", "gpu-core-domain", "gpu-pmp-report"};
    int n, ret;
    for (int i = 0; i < 3; i++) {
        const char *path = fdt_get_alias(dt, aliases[i]);
        if (!path) return BAD;
        n = fdt_path_offset(dt, path); CHECK(n);
        if (enable) CHECK(fdt_setprop(dt, n, "apple,always-on", NULL, 0));
        else {
            ret = fdt_delprop(dt, n, "apple,always-on");
            if (ret && ret != -FDT_ERR_NOTFOUND) return ret;
        }
    }
    const char *path = fdt_get_alias(dt, "gpu-mailbox");
    if (!path) return BAD;
    n = fdt_path_offset(dt, path); CHECK(n);
    CHECK(fdt_setprop_string(dt, n, "status", enable ? "okay" : "disabled"));
    return 0;
}

static int prune_fused_cooling(void *dt)
{
    int n = -1, depth = 0;
    while ((n = fdt_next_node(dt, n, &depth)) >= 0) {
        int len, used = 0;
        fdt32_t kept[3 * 16];
        const fdt32_t *p = fdt_getprop(dt, n, "cooling-device", &len);
        if (!p) continue;
        if (len <= 0 || len % 12 || len > sizeof(kept)) return BAD;
        for (int i = 0; i < len / 4; i += 3) {
            int cpu = fdt_node_offset_by_phandle(dt, fdt32_ld(p + i));
            CHECK(cpu);
            const char *status = fdt_getprop(dt, cpu, "status", NULL);
            if (status && !strcmp(status, "disabled")) continue;
            memcpy(kept + used, p + i, 12);
            used += 3;
        }
        if (!used) return BAD;
        CHECK(fdt_setprop(dt, n, "cooling-device", kept, used * 4));
    }
    return n == -FDT_ERR_NOTFOUND ? 0 : n;
}

/* Linux includes disabled CPU nodes in possible-CPU/OPP scans. m1n1 removes
 * fused CPUs altogether; do likewise after pruning references to them. */
static int prune_fused_cpus(void *dt)
{
    int n, depth, removed;
    do {
        n = -1; depth = 0; removed = 0;
        while ((n = fdt_next_node(dt, n, &depth)) >= 0) {
            int len, cpu;
            const fdt32_t *ref = fdt_getprop(dt, n, "cpu", &len);
            const char *status;
            if (!ref) continue;
            if (len != 4) return BAD;
            cpu = fdt_node_offset_by_phandle(dt, fdt32_ld(ref)); CHECK(cpu);
            status = fdt_getprop(dt, cpu, "status", NULL);
            if (status && !strcmp(status, "disabled")) {
                CHECK(fdt_nop_node(dt, n));
                removed = 1;
                break; /* restart: n now points at an FDT_NOP */
            }
        }
        if (!removed && n != -FDT_ERR_NOTFOUND) return n;
    } while (removed);
    n = -1; depth = 0;
    while ((n = fdt_next_node(dt, n, &depth)) >= 0) {
        int len, used = 0;
        fdt32_t kept[32];
        const fdt32_t *p = fdt_getprop(dt, n, "interrupt-affinity", &len);
        if (!p) continue;
        if (len <= 0 || len % 4 || (unsigned)len > sizeof(kept)) return BAD;
        for (int i = 0; i < len / 4; i++) {
            int cpu = fdt_node_offset_by_phandle(dt, fdt32_ld(p + i)); CHECK(cpu);
            const char *status = fdt_getprop(dt, cpu, "status", NULL);
            if (!status || strcmp(status, "disabled")) kept[used++] = p[i];
        }
        if (!used) return BAD;
        CHECK(fdt_setprop(dt, n, "interrupt-affinity", kept, used * 4));
    }
    if (n != -FDT_ERR_NOTFOUND) return n;
    int cpus = fdt_path_offset(dt, "/cpus"), next;
    CHECK(cpus);
    for (n = fdt_first_subnode(dt, cpus); n >= 0; n = next) {
        const char *status = fdt_getprop(dt, n, "status", NULL);
        next = fdt_next_subnode(dt, n);
        if (!strncmp(fdt_get_name(dt, n, NULL), "cpu@", 4) &&
            status && !strcmp(status, "disabled"))
            CHECK(fdt_nop_node(dt, n));
    }
    return n == -FDT_ERR_NOTFOUND ? 0 : n;
}

static int asc_region(void *dt, const char *name, u32 device,
                      u64 physical, u64 iova, u64 size, u32 *handle)
{
    int parent = fdt_path_offset(dt, "/reserved-memory"), n;
    fdt64_t reg[] = {cpu_to_fdt64(physical), cpu_to_fdt64(size)};
    fdt32_t map[] = {cpu_to_fdt32(device), cpu_to_fdt32(iova >> 32),
        cpu_to_fdt32(iova), cpu_to_fdt32(size >> 32), cpu_to_fdt32(size)};
    CHECK(parent);
    n = fdt_subnode_offset(dt, parent, name);
    if (n == -FDT_ERR_NOTFOUND) n = fdt_add_subnode(dt, parent, name);
    CHECK(n);
    CHECK(fdt_setprop(dt, n, "reg", reg, sizeof(reg)));
    CHECK(fdt_setprop_string(dt, n, "compatible", "apple,asc-mem"));
    CHECK(fdt_setprop(dt, n, "no-map", NULL, 0));
    CHECK(fdt_setprop(dt, n, "iommu-addresses", map, sizeof(map)));
    *handle = fdt_get_phandle(dt, n);
    if (!*handle) {
        CHECK(fdt_generate_phandle(dt, handle));
        CHECK(fdt_setprop_u32(dt, n, "phandle", *handle));
    }
    return 0;
}

static int aop_handoff(void *dt, struct adt_view a, u32 ready)
{
    static const char names[] = "__TEXT;__DATA;__ETEXT;__EDATA;__OS_LOG";
    static const char regions[][32] = {"aop-etext", "aop-oslog"};
    static const unsigned segments[] = {2, 4};
    fdt32_t handles[2];
    u64 physical[2], iova[2], size[2];
    const u8 *p, *raw;
    u32 len, device;
    int source = adt_named(a, "aop"), n = find_compatible(dt, "apple,t6041-aop"), map_len;
    if (!(ready & 1) || !firmware_25g83(a)) return BAD;
    CHECK(source); CHECK(n);
    device = fdt_get_phandle(dt, n);
    if (!device) {
        CHECK(fdt_generate_phandle(dt, &device));
        CHECK(fdt_setprop_u32(dt, n, "phandle", device));
    }
    p = adt_prop(a, source, "segment-names", &len);
    if (!p || len != sizeof(names) || memcmp(p, names, sizeof(names))) return BAD;
    raw = adt_prop(a, source, "segment-ranges", &len);
    if (!raw || len != 5 * 32) return BAD;
    /* T6040 boots with nCal=0. __EDATA is not used by this flow and can
     * reside in SRAM at iBoot handoff (macOS can relocate it into DRAM).
     * Match the kernel contract: external code at EC0p and identity OS log.
     * Requiring all three segments to be DRAM incorrectly disables AOP. */
    for (int i = 0; i < 2; i++) {
        CHECK(dram_segment(a, raw + segments[i] * 32, 1024 * 1024,
                           &physical[i], &iova[i], &size[i]));
        for (int j = 0; j < i; j++)
            if ((physical[i] < physical[j] + size[j] && physical[j] < physical[i] + size[i]) ||
                (iova[i] < iova[j] + size[j] && iova[j] < iova[i] + size[i])) return BAD;
    }
    if (iova[0] != 0x10000000000ULL || iova[1] != physical[1]) return BAD;
    for (int i = 0; i < 2; i++) {
        u32 handle;
        CHECK(asc_region(dt, regions[i], device, physical[i], iova[i], size[i], &handle));
        handles[i] = cpu_to_fdt32(handle);
    }
    n = find_compatible(dt, "apple,t6041-aop"); CHECK(n);
    CHECK(fdt_setprop(dt, n, "memory-region", handles, sizeof(handles)));
    CHECK(set_enabled(dt, "apple,t6041-aop"));
    /* aop_dart is uniquely identified by the AOP iommus reference. */
    n = find_compatible(dt, "apple,t6041-aop");
    p = fdt_getprop(dt, n, "iommus", &map_len);
    if (!p || map_len < 8) return BAD;
    n = fdt_node_offset_by_phandle(dt, fdt32_ld((const fdt32_t *)p)); CHECK(n);
    return fdt_setprop_string(dt, n, "status", "okay");
}

static int isp_handoff(void *dt, struct adt_view a, u32 ready)
{
    static const char names[] = "__TEXT;__DATA";
    static const char regions[][32] = {"isp-firmware-text", "isp-firmware-data"};
    const u8 *p, *raw;
    u64 physical[2], iova[2], size[2];
    u32 len, device;
    int source = adt_named(a, "isp0"), n = find_compatible(dt, "apple,t6041-isp"), map_len;
    if (!(ready & 2) || !firmware_25g83(a)) return BAD;
    CHECK(source); CHECK(n);
    device = fdt_get_phandle(dt, n);
    if (!device) {
        CHECK(fdt_generate_phandle(dt, &device));
        CHECK(fdt_setprop_u32(dt, n, "phandle", device));
    }
    p = adt_prop(a, source, "segment-names", &len);
    if (!p || len != sizeof(names) || memcmp(p, names, sizeof(names))) return BAD;
    raw = adt_prop(a, source, "segment-ranges", &len);
    if (!raw || len != 64) return BAD;
    for (int i = 0; i < 2; i++)
        CHECK(dram_segment(a, raw + i * 32, 32 * 1024 * 1024,
                           &physical[i], &iova[i], &size[i]));
    if (iova[0] != 0x10000000000ULL || iova[1] != iova[0] + size[0] ||
        size[0] + size[1] > 32 * 1024 * 1024 ||
        (physical[0] < physical[1] + size[1] && physical[1] < physical[0] + size[0])) return BAD;
    for (int i = 0; i < 2; i++) {
        u32 handle;
        CHECK(asc_region(dt, regions[i], device, physical[i], iova[i], size[i], &handle));
    }
    n = find_compatible(dt, "apple,t6041-isp");
    fdt32_t version[] = {cpu_to_fdt32(26), cpu_to_fdt32(6), cpu_to_fdt32(2)};
    CHECK(fdt_setprop(dt, n, "apple,firmware-version", version, sizeof(version)));
    CHECK(set_enabled(dt, "apple,t6041-isp"));
    /* Only the ISP's three DARTs; unrelated DARTs retain their status. */
    n = find_compatible(dt, "apple,t6041-isp");
    p = fdt_getprop(dt, n, "iommus", &map_len);
    if (!p || map_len != 3 * 8) return BAD;
    u32 darts[3];
    for (int i = 0; i < 3; i++) darts[i] = fdt32_ld((const fdt32_t *)p + i * 2);
    for (int i = 0; i < 3; i++) {
        n = fdt_node_offset_by_phandle(dt, darts[i]); CHECK(n);
        CHECK(fdt_setprop_string(dt, n, "status", "okay"));
    }
    return 0;
}
