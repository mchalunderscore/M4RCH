/* SPDX-License-Identifier: MIT */
/* Included by kboot.c after Aurora's retained M4 mapping helpers. */

/* Persist refusal evidence after any transactional DT rollback. */
static const char *j614s_dcp_stage = "entry";
static u32 j614s_dcp_line, j614s_dcp_segment_bytes;
static char j614s_dcp_uuid[80];
static u32 j614s_dcp_uuid_bytes;
static u8 j614s_dcp_segments[512];
static u32 j614s_dcp_segments_saved;
static char j614s_dcp_dart_state[3][256];

static int j614s_dcp_refuse(u32 line)
{
    j614s_dcp_line = line;
    return -1;
}

static int j614s_dcp_publish_trace(int result)
{
    int node = fdt_path_offset(dt, "/chosen");
    char identity[128], summary[256];
    if (node < 0)
        return j614s_dcp_refuse(__LINE__);
    snprintf(identity, sizeof(identity), "chip=%x board=%x os=%s", chip_id,
             board_id, os_firmware.string ? os_firmware.string : "<missing>");
    snprintf(summary, sizeof(summary), "stage=%s result=%d line=%u uuid-bytes=%u segment-bytes=%u",
             j614s_dcp_stage, result, j614s_dcp_line, j614s_dcp_uuid_bytes, j614s_dcp_segment_bytes);
#define DCP_TRACE_SET(call) do { if ((call) < 0) return j614s_dcp_refuse(__LINE__); } while (0)
    DCP_TRACE_SET(fdt_setprop_string(dt, node, "m4rch,dcp-summary", summary));
    node = fdt_path_offset(dt, "/chosen");
    DCP_TRACE_SET(fdt_setprop_string(dt, node, "m4rch,dcp-stage", j614s_dcp_stage));
    node = fdt_path_offset(dt, "/chosen");
    DCP_TRACE_SET(fdt_setprop_string(dt, node, "m4rch,dcp-identity", identity));
    node = fdt_path_offset(dt, "/chosen");
    DCP_TRACE_SET(fdt_setprop_u32(dt, node, "m4rch,dcp-result", result));
    node = fdt_path_offset(dt, "/chosen");
    DCP_TRACE_SET(fdt_setprop_u32(dt, node, "m4rch,dcp-refusal-line", j614s_dcp_line));
    node = fdt_path_offset(dt, "/chosen");
    DCP_TRACE_SET(fdt_setprop_string(dt, node, "m4rch,dcp-observed-uuid", j614s_dcp_uuid));
    node = fdt_path_offset(dt, "/chosen");
    DCP_TRACE_SET(fdt_setprop_u32(dt, node, "m4rch,dcp-segment-bytes", j614s_dcp_segment_bytes));
    node = fdt_path_offset(dt, "/chosen");
    DCP_TRACE_SET(fdt_setprop(dt, node, "m4rch,dcp-segment-snapshot", j614s_dcp_segments,
                           j614s_dcp_segments_saved));
    for (u32 i = 0; i < 3; i++) {
        char property[48];
        snprintf(property, sizeof(property), "m4rch,dcp-dart-%u", i);
        node = fdt_path_offset(dt, "/chosen");
        DCP_TRACE_SET(fdt_setprop_string(dt, node, property, j614s_dcp_dart_state[i]));
    }
#undef DCP_TRACE_SET
    printf("DCP004: handoff stage=%s result=%d refusal-line=%u identity=%s uuid=%s\n",
           j614s_dcp_stage, result, j614s_dcp_line, identity, j614s_dcp_uuid);
    return 0;
}

static int j614s_dcp_tables(u64 base, u32 sid, const char *path, const char *property,
                            u64 dram_base, u64 dram_size)
{
    int trace[8] = {};
    int node = adt_path_offset_trace(adt, path, trace);
    u64 region[2] = {};
    u64 actual_base = 0, actual_size = 0;
    u32 index = sid == 0 ? 0 : sid == 16 ? 1 : 2;
    j614s_dcp_stage = sid == 0 ? "dart-sid0-adt" : sid == 16 ? "dart-sid16-adt" : "dart-sid23-adt";
    if (node < 0 || !adt_is_compatible(adt, node, "dart,t8110") ||
        adt_get_reg(adt, trace, "reg", 0, &actual_base, &actual_size) < 0 ||
        actual_base != base || actual_size < 0x8000 ||
        ADT_GETPROP_ARRAY(adt, node, property, region) != sizeof(region))
        return j614s_dcp_refuse(__LINE__);
    u64 start = region[0], end = region[1];
    snprintf(j614s_dcp_dart_state[index], sizeof(j614s_dcp_dart_state[index]),
             "base=%lx aperture=%lx region=[%lx,%lx)", actual_base, actual_size, start, end);
    j614s_dcp_stage = sid == 0 ? "dart-sid0-region" : sid == 16 ? "dart-sid16-region" : "dart-sid23-region";
    u64 usable_end = cur_boot_args.phys_base + cur_boot_args.mem_size;
    if (end <= start || end - start > 0x100000 ||
        ((start | end) & (SZ_16K - 1)) || start < dram_base ||
        end - dram_base > dram_size ||
        (start < usable_end && cur_boot_args.phys_base < end))
        return j614s_dcp_refuse(__LINE__);
    u32 tcr = read32(base + 0x1000 + 4 * sid);
    u32 ttbr = read32(base + 0x1400 + 4 * sid);
    /* Match the production T8110 TTBR address field, excluding bits 31:30. */
    u64 root = ((u64)(ttbr & GENMASK(29, 2)) >> 2) << 14;
    u32 enabled = read32(base + 0xc00);
    snprintf(j614s_dcp_dart_state[index], sizeof(j614s_dcp_dart_state[index]),
             "base=%lx aperture=%lx region=[%lx,%lx) tcr=%x ttbr=%x root=%lx enabled=%x",
             actual_base, actual_size, start, end, tcr, ttbr, root, enabled);
    j614s_dcp_stage = sid == 0 ? "dart-sid0-registers" : sid == 16 ? "dart-sid16-registers" : "dart-sid23-registers";
    if (!(tcr & 1) || (tcr & ~5U) || (ttbr & 3) != 1 || root < start || root > end - SZ_16K ||
        !(enabled & BIT(sid)))
        return j614s_dcp_refuse(__LINE__);
    printf("DCP001: retained SID%u root 0x%lx in live ADT [0x%lx,0x%lx)\n",
           sid, root, start, end);
    return 0;
}

static int dt_set_j614s_dcp_handoff(void)
{
    static const u32 kinds[] = {1, 0, 10, 2, 2, 2, 2, 2};
    const char *uuid_expected = "6CC9349E-D30B-33FB-B12B-8D6D38F9F1B3";
    j614s_dcp_stage = "control-dcp-alias";
    int dcp = fdt_path_offset(dt, "dcp");
    if (dcp < 0)
        return j614s_dcp_refuse(__LINE__);
    j614s_dcp_stage = "board-firmware-identity";
    if (chip_id != T6040 || board_id != 4 || os_firmware.version != V26_6_2 ||
        fdt_node_check_compatible(dt, 0, "apple,j614s") ||
        fdt_node_check_compatible(dt, dcp, "apple,t6041-dcp"))
        return j614s_dcp_refuse(__LINE__);
    j614s_dcp_stage = "adt-dcp-nub";
    int nub = adt_path_offset(adt, "/arm-io/dcp/iop-dcp-nub");
    int chosen = adt_path_offset(adt, "/chosen");
    u32 len = 0;
    if (nub < 0 || chosen < 0)
        return j614s_dcp_refuse(__LINE__);
    const char *uuid = adt_getprop(adt, nub, "uuid", &len);
    j614s_dcp_stage = "firmware-uuid";
    j614s_dcp_uuid_bytes = len;
    if (uuid && len && len < sizeof(j614s_dcp_uuid)) {
        memcpy(j614s_dcp_uuid, uuid, len);
        j614s_dcp_uuid[len] = 0;
    }
    if (!uuid || len != 37 || memcmp(uuid, uuid_expected, 37))
        return j614s_dcp_refuse(__LINE__);
    len = 0;
    const struct adt_segment_ranges *segments = adt_getprop(adt, nub, "segment-ranges", &len);
    j614s_dcp_stage = "segment-count";
    j614s_dcp_segment_bytes = len;
    if (segments && len <= sizeof(j614s_dcp_segments)) {
        memcpy(j614s_dcp_segments, segments, len);
        j614s_dcp_segments_saved = len;
    }
    if (!segments || len != sizeof(*segments) * ARRAY_SIZE(kinds))
        return j614s_dcp_refuse(__LINE__);
    j614s_dcp_stage = "dram-range";
    u64 dram_base, dram_size;
    if (ADT_GETPROP(adt, chosen, "dram-base", &dram_base) != sizeof(dram_base) ||
        ADT_GETPROP(adt, chosen, "dram-size", &dram_size) != sizeof(dram_size) ||
        !dram_size || dram_base > UINT64_MAX - dram_size)
        return j614s_dcp_refuse(__LINE__);
    j614s_dcp_stage = "segment-layout";
    for (u32 i = 0; i < ARRAY_SIZE(kinds); i++) {
        const struct adt_segment_ranges *seg = &segments[i];
        u64 size = ALIGN_UP((u64)seg->size, SZ_16K);
        if (seg->unk != kinds[i] || !size ||
            ((seg->phys | seg->remap) & (SZ_16K - 1)) || seg->phys < dram_base ||
            seg->phys - dram_base >= dram_size || size > dram_size - (seg->phys - dram_base) ||
            (seg->remap >> 36) != 0x10 ||
            size > (1ULL << 36) - (seg->remap & ((1ULL << 36) - 1)))
            return j614s_dcp_refuse(__LINE__);
    }
    if (j614s_dcp_tables(0x402300000, 0, "/arm-io/dart-disp0", "pt-region-0", dram_base, dram_size) ||
        j614s_dcp_tables(0x402300000, 16, "/arm-io/dart-disp0", "pt-region-16", dram_base, dram_size) ||
        j614s_dcp_tables(0x402340000, 23, "/arm-io/dart-dcp", "pt-region-23", dram_base, dram_size))
        return j614s_dcp_refuse(__LINE__);

    /* Firmware already owns every stream. Only set the protection bit; never
     * allocate a root, change a TCR/TTBR, flush or reset an inherited context.
     */
    j614s_dcp_stage = "dart-protection";
    dart_lock_adt("/arm-io/dart-disp0", 0);
    dart_lock_adt("/arm-io/dart-dcp", 0);
    /* An unlocked dart_init may configure a context. Verify protection
     * before opening the inherited SID23 translator, including write failure.
     */
    if (!(read32(0x402300200) & 1) || !(read32(0x402340200) & 1))
        return j614s_dcp_refuse(__LINE__);
    j614s_dcp_stage = "sid23-translator";
    dart_dev_t *dart = dt_init_dart_by_node(dcp, 0);
    if (!dart)
        return j614s_dcp_refuse(__LINE__);
    int ret = 0;
    j614s_dcp_stage = "sid23-firmware-mappings";
    for (u32 i = 0; !ret && i < ARRAY_SIZE(kinds); i++) {
        const struct adt_segment_ranges *seg = &segments[i];
        if (seg->unk == 10)
            continue;
        u64 size = ALIGN_UP((u64)seg->size, SZ_16K);
        for (u64 off = 0; off < size; off += SZ_16K) {
            u64 actual = (u64)dart_translate_silent(dart, seg->remap + off);
            if (actual != seg->phys + off) {
                printf("DCP001: SID23 segment %u mismatch at 0x%lx: 0x%lx != 0x%lx\n",
                       i, seg->remap + off, actual, seg->phys + off);
                ret = j614s_dcp_refuse(__LINE__);
                break;
            }
        }
    }
    dart_shutdown(dart);
    if (ret)
        return ret;
    /* This is data handoff only. The kernel's explicit trial option performs
     * device admission; the default desktop entry keeps the nodes disabled.
     */
    j614s_dcp_stage = "dt-transaction-snapshot";
    void *saved = malloc(dt_bufsize);
    if (!saved)
        return j614s_dcp_refuse(__LINE__);
    memcpy(saved, dt, dt_bufsize);
    j614s_dcp_stage = "dt-firmware-version";
    ret = dt_set_dcp_firmware("dcp");
    if (ret) { j614s_dcp_line = __LINE__; goto out; }
    j614s_dcp_stage = "dt-firmware-reservations";
    ret = dt_reserve_asc_firmware("/arm-io/dcp/iop-dcp-nub", NULL, "dcp", true, 0);
    if (ret) { j614s_dcp_line = __LINE__; goto out; }
    j614s_dcp_stage = "dt-display-mappings";
    ret = dt_set_m4_display_maps(segments, ARRAY_SIZE(kinds), dram_base, dram_size);
    if (ret) { j614s_dcp_line = __LINE__; goto out; }
    j614s_dcp_stage = "dt-owner-marker";
    dcp = fdt_path_offset(dt, "dcp");
    if (dcp < 0 || fdt_setprop_string(dt, dcp, "apple,firmware-uuid", uuid) ||
        fdt_setprop_empty(dt, dcp, "apple,j614s-inherited-mappings")) {
        ret = j614s_dcp_refuse(__LINE__);
        goto out;
    }
    j614s_dcp_stage = "dt-admission-marker";
    chosen = fdt_path_offset(dt, "/chosen");
    if (chosen < 0 || fdt_setprop_string(dt, chosen, "m4rch,dcp-handoff", "DCP001-v1")) {
        ret = j614s_dcp_refuse(__LINE__);
        goto out;
    }
    j614s_dcp_stage = "complete";
    printf("DCP001: native J614s firmware and SID23/SID0/SID16 mappings published; devices disabled\n");
out:
    if (ret)
        memcpy(dt, saved, dt_bufsize);
    free(saved);
    return ret;
}
