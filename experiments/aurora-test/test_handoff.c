// SPDX-License-Identifier: GPL-2.0-only
#define AURORA_HOST_TEST
#include "board_handoff.c"
#include <assert.h>
#include <stdlib.h>

static void *read_file(const char *name, size_t *size)
{
	FILE *f = fopen(name, "rb");
	void *p;
	assert(f);
	assert(!fseek(f, 0, SEEK_END)); *size = ftell(f); rewind(f);
	p = malloc(*size); assert(p);
	assert(fread(p, 1, *size, f) == *size); fclose(f);
	return p;
}

int main(int argc, char **argv)
{
	size_t len, adt_len;
	void *baseline, *template, *live = malloc(2 << 20), *out = malloc(2 << 20);
	struct adt_view adt;
	int cpus, n, count = 0, r;
	const fdt64_t *reg;
	const char *status;
	assert((argc == 4 || argc == 5) && live && out);
	baseline = read_file(argv[1], &len);
	template = read_file(argv[2], &len);
	adt.data = read_file(argv[3], &adt_len); adt.size = adt_len;
	assert(!fdt_open_into(baseline, live, 2 << 20));
	assert(!fdt_add_mem_rsv(live, 0x800000000ULL, 0x400000));
	cpus = fdt_path_offset(live, "/cpus");
	fdt_for_each_subnode(n, live, cpus) {
		if (strncmp(fdt_get_name(live, n, NULL), "cpu@", 4)) continue;
		reg = fdt_getprop(live, n, "reg", NULL); assert(reg);
		if ((fdt64_ld(reg) & 0xff) >= 4)
			assert(!fdt_setprop_string(live, n, "status", "disabled"));
		else {
			count++;
			assert(!fdt_setprop_inplace_u64(live, n, "cpu-release-addr", 0x800004000ULL + count * 8));
		}
	}
	n = fdt_path_offset(live, "/memory@0");
	if (n < 0) n = fdt_path_offset(live, "/memory");
	assert(n >= 0);
	{
		fdt64_t ranges[] = {cpu_to_fdt64(0x900000000ULL), cpu_to_fdt64(0x12340000)};
		assert(!fdt_setprop(live, n, "reg", ranges, sizeof(ranges)));
	}
	n = fdt_path_offset(live, "/chosen");
	assert(!fdt_setprop_string(live, n, "test-live-only", "sentinel"));
	assert(!aurora_j614s_handoff(live, out, 2 << 20, template, adt));
	{
		uint64_t address, size;
		int i, found = 0;
		assert(fdt_num_mem_rsv(out) >= fdt_num_mem_rsv(live));
		for (i = 0; i < fdt_num_mem_rsv(out); i++) {
			assert(!fdt_get_mem_rsv(out, i, &address, &size));
			if (address == 0x800000000ULL && size == 0x400000)
				found++;
		}
		assert(found);
	}
	assert(!fdt_node_check_compatible(out, 0, "apple,j614s"));
	n = fdt_path_offset(out, "/chosen");
	assert(!strcmp(fdt_getprop(out, n, "test-live-only", NULL), "sentinel"));
	reg = fdt_getprop(out, fdt_path_offset(out, "/memory@0"), "reg", NULL);
	assert(reg && fdt64_ld(reg) == 0x900000000ULL && fdt64_ld(reg + 1) == 0x12340000);
	count = 0; cpus = fdt_path_offset(out, "/cpus");
	fdt_for_each_subnode(n, out, cpus) {
		if (strncmp(fdt_get_name(out, n, NULL), "cpu@", 4)) continue;
		status = fdt_getprop(out, n, "status", NULL);
		if (status && !strcmp(status, "okay")) {
			reg = fdt_getprop(out, n, "cpu-release-addr", NULL);
			assert(reg && fdt64_ld(reg) > 0x800004000ULL); count++;
		}
	}
	assert(count == 12);
	n = find_compatible(out, "apple,j616-macaudio");
	assert(n >= 0 && !strcmp(fdt_getprop(out, n, "status", NULL), "disabled"));
	n = -1;
	while ((n = fdt_node_offset_by_compatible(out, n, "ti,tas2764")) >= 0)
		assert(!strcmp(fdt_getprop(out, n, "status", NULL), "disabled"));
	for (n = 0; n < 3; n++) {
		char alias[] = "atcphy0";
		const fdt32_t *tuning;
		alias[6] += n;
		r = fdt_path_offset(out, fdt_get_alias(out, alias)); assert(r >= 0);
		assert(!strcmp(fdt_getprop(out, r, "status", NULL), "okay"));
		tuning = fdt_getprop(out, r, "apple,tunable-auspll", NULL);
		assert(tuning && fdt32_to_cpu(tuning[0]) == 0x3224);
	}
	/* The fixture's real macOS firmware is unsupported: no false GPU admission. */
	n = find_compatible(out, "apple,agx-t6040");
	assert(!strcmp(fdt_getprop(out, n, "status", NULL), argc == 5 ? "okay" : "disabled"));
	if (argc == 5) {
		const fdt32_t *volts;
		const u8 *raw;
		u32 length;
		int sgx = adt_named(adt, "sgx");
		raw = adt_prop(adt, sgx, "perf-states", &length); assert(raw && length == 256);
		n = fdt_path_offset(out, "/opp-table-gpu/opp01"); assert(n >= 0);
		volts = fdt_getprop(out, n, "opp-microvolt", NULL); assert(volts);
		assert(fdt32_ld(volts) == le32(raw + 12));
		assert(fdt32_ld(volts + 1) == le32(raw + 16 * 8 + 12));
		reg = fdt_getprop(out, n, "opp-hz", NULL); assert(reg);
		assert(fdt64_ld(reg) == le32(raw + 8));
		n = fdt_path_offset(out, "/power-management@288e80000"); assert(n >= 0);
		assert(!strcmp(fdt_getprop(out, n, "status", NULL), "okay"));
	}
	/* Wrong machine and truncated ADT must not gain GPU access. */
	assert(!fdt_setprop_string(live, 0, "compatible", "apple,j616s"));
	assert(aurora_j614s_handoff(live, out, 2 << 20, template, adt) < 0);
	assert(!fdt_setprop_string(live, 0, "compatible", "apple,j614s"));
	adt.size = 7;
	assert(!aurora_j614s_handoff(live, out, 2 << 20, template, adt));
	n = find_compatible(out, "apple,agx-t6040");
	assert(!strcmp(fdt_getprop(out, n, "status", NULL), "disabled"));
	assert(aurora_j614s_handoff(live, out, 64, template, adt) < 0);
	puts("PASS: live memory, fused CPUs, release addresses, calibration, USB tuning, speaker exclusion, firmware refusal, bounds");
	return 0;
}
