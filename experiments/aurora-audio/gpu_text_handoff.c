/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
/* Aurora #428 identifies the loaded image through a named fw-text region.
 * Publish its address from this boot's ADT, never from the donor board. */
static int gpu_text_handoff(void *dt, struct adt_view adt)
{
    int source = adt_named(adt, "gfx-asc"), node, parent;
    const u8 *raw, *names;
    u32 len, handle;
    u64 physical, iova, size;
    CHECK(source);
    names = adt_prop(adt, source, "segment-names", &len);
    if (!names || len < sizeof("__TEXT;") || len > 256 ||
        memcmp(names, "__TEXT;", sizeof("__TEXT;") - 1)) return BAD;
    raw = adt_prop(adt, source, "segment-ranges", &len);
    if (!raw || len < 64 || len > 128 || len % 32) return BAD;
    CHECK(dram_segment(adt, raw, 1024 * 1024, &physical, &iova, &size));
    parent = fdt_path_offset(dt, "/reserved-memory"); CHECK(parent);
    node = fdt_subnode_offset(dt, parent, "gpu-fw-text");
    if (node == -FDT_ERR_NOTFOUND) node = fdt_add_subnode(dt, parent, "gpu-fw-text");
    CHECK(node);
    fdt64_t reg[] = {cpu_to_fdt64(physical), cpu_to_fdt64(size)};
    CHECK(fdt_setprop(dt, node, "reg", reg, sizeof(reg)));
    CHECK(fdt_setprop(dt, node, "no-map", NULL, 0));
    handle = fdt_get_phandle(dt, node);
    if (!handle) {
        CHECK(fdt_generate_phandle(dt, &handle));
        CHECK(fdt_setprop_u32(dt, node, "phandle", handle));
    }
    node = find_compatible(dt, "apple,agx-t6040"); CHECK(node);
    /* The template has the five established regions; add the same-boot TEXT. */
    if (fdt_stringlist_search(dt, node, "memory-region-names", "fw-text") >= 0) return BAD;
    CHECK(fdt_appendprop_u32(dt, node, "memory-region", handle));
    return fdt_appendprop_string(dt, node, "memory-region-names", "fw-text");
}
