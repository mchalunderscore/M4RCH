/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
/* Data-only transfer from the live Aurora control tree to the Linux template.
 * Never copy hardware-graph phandles across trees. Every consumer and retained
 * memory-region reference is resolved again in the destination tree.
 */

static int dcp_bridge_line;
static char dcp_bridge_consumer[40] = "marker";
static int dcp_bridge_result(int value, int line)
{
    if (value < 0)
        dcp_bridge_line = line;
    return value;
}
#define DCP_CHECK(expr) do { int result = (expr); if (result < 0) return dcp_bridge_result(result, __LINE__); } while (0)

static int dcp_destination(void *out, const char *alias, u32 *phandle)
{
	const char *name = fdt_get_alias(out, alias);
	char path[128];
	int node;

	if (!name || strlen(name) >= sizeof(path))
		return dcp_bridge_result(BAD, __LINE__);
	board_copy(path, name);
	node = fdt_path_offset(out, path);
	DCP_CHECK(node);
	*phandle = fdt_get_phandle(out, node);
	if (!*phandle) {
		DCP_CHECK(fdt_generate_phandle(out, phandle));
		DCP_CHECK(fdt_setprop_u32(out, node, "phandle", *phandle));
	}
	return 0;
}

static int dcp_memory_region(void *out, const void *live, u32 source, u32 *destination)
{
	static const char * const aliases[] = {"dcp", "disp0", "disp0_piodma"};
	char path[160];
	const fdt32_t *maps;
	fdt32_t remapped[15];
	int src = fdt_node_offset_by_phandle(live, source), dst, len;
	u32 seen = 0;

	DCP_CHECK(src);
	DCP_CHECK(fdt_get_path(live, src, path, sizeof(path)));
	if (strncmp(path, "/reserved-memory/", 17) ||
	    fdt_node_check_compatible(live, src, "apple,asc-mem") ||
	    !fdt_getprop(live, src, "no-map", NULL))
		return dcp_bridge_result(BAD, __LINE__);
	dst = fdt_path_offset(out, path);
	DCP_CHECK(dst);
	*destination = fdt_get_phandle(out, dst);
	if (!*destination) {
		DCP_CHECK(fdt_generate_phandle(out, destination));
		DCP_CHECK(fdt_setprop_u32(out, dst, "phandle", *destination));
	}
	maps = fdt_getprop(live, src, "iommu-addresses", &len);
	if (!maps)
		return fdt_getprop(live, src, "apple,dcp-os-log", NULL) ? 0 : BAD;
	if (len <= 0 || len > sizeof(remapped) || len % (5 * sizeof(fdt32_t)))
		return dcp_bridge_result(BAD, __LINE__);
	for (int i = 0; i < len / sizeof(fdt32_t); i += 5) {
		int owner = fdt_node_offset_by_phandle(live, fdt32_ld(maps + i));
		int identity = -1;
		u32 phandle;

		DCP_CHECK(owner);
		for (int n = 0; n < sizeof(aliases) / sizeof(aliases[0]); n++) {
			const char *alias = fdt_get_alias(live, aliases[n]);
			if (alias && fdt_path_offset(live, alias) == owner)
				identity = n;
		}
		if (identity < 0 || (seen & (1U << identity)))
			return dcp_bridge_result(BAD, __LINE__);
		seen |= 1U << identity;
		DCP_CHECK(dcp_destination(out, aliases[identity], &phandle));
		remapped[i] = cpu_to_fdt32(phandle);
		memcpy(remapped + i + 1, maps + i + 1, 4 * sizeof(fdt32_t));
	}
	return dcp_bridge_result(fdt_setprop(out, fdt_path_offset(out, path), "iommu-addresses", remapped, len), __LINE__);
}

static int dcp_handoff_apply(void *out, const void *live)
{
	static const char * const aliases[] = {"dcp", "disp0", "disp0_piodma"};
	static const char * const properties[] = {"apple,firmware-version", "apple,firmware-compat", "apple,firmware-uuid"};
	const char *marker;
	int chosen = fdt_path_offset(live, "/chosen"), len;

	if (chosen < 0)
		return dcp_bridge_result(BAD, __LINE__);
	marker = fdt_getprop(live, chosen, "m4rch,dcp-handoff", &len);
	if (!marker || len != sizeof("DCP001-v1") || strcmp(marker, "DCP001-v1"))
		return dcp_bridge_result(BAD, __LINE__);
	for (int n = 0; n < sizeof(aliases) / sizeof(aliases[0]); n++) {
		snprintf(dcp_bridge_consumer, sizeof(dcp_bridge_consumer), "%s", aliases[n]);
		const char *from = fdt_get_alias(live, aliases[n]);
		const char *to = fdt_get_alias(out, aliases[n]);
		const fdt32_t *regions;
		fdt32_t references[8];
		char destination[128];
		int src, count;

		if (!from || !to || strlen(to) >= sizeof(destination))
			return dcp_bridge_result(BAD, __LINE__);
		board_copy(destination, to);
		src = fdt_path_offset(live, from);
		DCP_CHECK(src);
		if (!fdt_getprop(live, src, "apple,j614s-inherited-mappings", NULL))
			return dcp_bridge_result(BAD, __LINE__);
		regions = fdt_getprop(live, src, "memory-region", &len);
		if (!regions || len <= 0 || len > sizeof(references) || len % sizeof(fdt32_t))
			return dcp_bridge_result(BAD, __LINE__);
		count = len / sizeof(fdt32_t);
		if (!n && count != 8)
			return dcp_bridge_result(BAD, __LINE__);
		for (int i = 0; i < count; i++) {
			u32 phandle;
			DCP_CHECK(dcp_memory_region(out, live, fdt32_ld(regions + i), &phandle));
			references[i] = cpu_to_fdt32(phandle);
		}
		DCP_CHECK(fdt_setprop(out, fdt_path_offset(out, destination), "memory-region", references, len));
		DCP_CHECK(fdt_setprop_empty(out, fdt_path_offset(out, destination), "apple,j614s-inherited-mappings"));
		if (!n)
			for (int i = 0; i < sizeof(properties) / sizeof(properties[0]); i++)
				DCP_CHECK(copy_prop(out, destination, live, src, properties[i]));
	}
	printf("DCP001: live display reservations transferred with Linux phandles; device admission deferred to trial kernel\n");
	return 0;
}

/* Evidence survives the caller removing an invalid admission marker. */
static int dcp_handoff(void *out, const void *live)
{
    dcp_bridge_line = 0;
    snprintf(dcp_bridge_consumer, sizeof(dcp_bridge_consumer), "marker");
    int result = dcp_handoff_apply(out, live);
    int chosen = fdt_path_offset(out, "/chosen");
    char summary[160];
    snprintf(summary, sizeof(summary), "result=%d line=%d consumer=%s", result,
             dcp_bridge_line, dcp_bridge_consumer);
    if (chosen < 0)
        return dcp_bridge_result(BAD, __LINE__);
    DCP_CHECK(fdt_setprop_string(out, chosen, "m4rch,dcp-bridge-summary", summary));
    printf("DCP004: Linux bridge %s\n", summary);
    return result;
}
#undef DCP_CHECK
