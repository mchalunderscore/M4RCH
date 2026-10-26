// SPDX-License-Identifier: GPL-2.0-only
/* Data-only bootloader J614s board port. No MMIO and no firmware execution.
 * The same translation unit is compiled against userspace libfdt for tests.
 */
#ifdef AURORA_HOST_TEST
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <libfdt.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
#else
#include <linux/types.h>
#include <linux/string.h>
#include <linux/libfdt.h>
#endif

#ifdef AURORA_HOST_TEST
#define CHECK(x) do { int err_ = (x); if (err_ < 0) { fprintf(stderr, "handoff:%d %s: %d\n", __LINE__, #x, err_); return err_; } } while (0)
#else
#define CHECK(x) do { int err_ = (x); if (err_ < 0) return err_; } while (0)
#endif
#define BAD (-FDT_ERR_BADVALUE)

static void board_copy(char *dst, const char *src)
{
	memcpy(dst, src, strlen(src) + 1);
}

static void board_append(char *dst, const char *src)
{
	board_copy(dst + strlen(dst), src);
}

static u32 le32(const void *p)
{
	const u8 *b = p;
	return (u32)b[0] | (u32)b[1] << 8 | (u32)b[2] << 16 | (u32)b[3] << 24;
}

static u64 le64(const void *p)
{
	return le32(p) | (u64)le32((const u8 *)p + 4) << 32;
}

struct adt_view { const u8 *data; u32 size; };

/* Fully bound each node before interpreting names or recursing. */
static int adt_props(struct adt_view a, u32 node, u32 *end)
{
	u32 off, count, i;
	if (node > a.size || a.size - node < 8)
		return BAD;
	count = le32(a.data + node);
	if (count > 4096 || le32(a.data + node + 4) > 4096)
		return BAD;
	off = node + 8;
	for (i = 0; i < count; i++) {
		u32 len;
		if (off > a.size || a.size - off < 36 ||
		    !memchr(a.data + off, 0, 32))
			return BAD;
		len = le32(a.data + off + 32) & 0x7fffffff;
		if (len > a.size - off - 36)
			return BAD;
		off += 36 + len;
		if (off > a.size - ((-len) & 3))
			return BAD;
		off += (-len) & 3;
	}
	*end = off;
	return 0;
}

static const void *adt_prop(struct adt_view a, u32 node, const char *name, u32 *size)
{
	u32 off = node + 8, end, i;
	if (adt_props(a, node, &end))
		return NULL;
	for (i = 0; i < le32(a.data + node); i++) {
		u32 len = le32(a.data + off + 32) & 0x7fffffff;
		if (!strcmp((const char *)a.data + off, name)) {
			*size = len;
			return a.data + off + 36;
		}
		off += 36 + ((len + 3) & ~3U);
	}
	return NULL;
}

static int adt_find(struct adt_view a, u32 node, const char *wanted,
		    u32 *next, int depth, int *budget)
{
	u32 end, len, i;
	const char *name;
	int found = -FDT_ERR_NOTFOUND;
	if (depth > 48 || --*budget < 0)
		return BAD;
	CHECK(adt_props(a, node, &end));
	name = adt_prop(a, node, "name", &len);
	if (!name || !len || !memchr(name, 0, len))
		return BAD;
	if (!strcmp(name, wanted))
		found = node;
	for (i = 0; i < le32(a.data + node + 4); i++) {
		int child = adt_find(a, end, wanted, &end, depth + 1, budget);
		if (child < 0 && child != -FDT_ERR_NOTFOUND)
			return child;
		if (child >= 0) {
			if (found >= 0)
				return BAD; /* no ambiguous firmware/GPU node */
			found = child;
		}
	}
	*next = end;
	return found;
}

static int adt_named(struct adt_view a, const char *name)
{
	u32 end;
	int budget = 10000;
	return adt_find(a, 0, name, &end, 0, &budget);
}

static int copy_prop(void *to, const char *path, const void *from, int src,
		     const char *name)
{
	int len, dst = fdt_path_offset(to, path);
	const void *p = fdt_getprop(from, src, name, &len);
	if (!p)
		return 0;
	if (dst < 0)
		return dst;
	return fdt_setprop(to, dst, name, p, len);
}

/* Only use this for chosen/reservations: hardware graph phandles stay Aurora's. */
static int copy_tree(void *to, int parent, const void *from, int src, int depth)
{
	int dst, prop, child;
	char path[512];
	if (depth > 24)
		return BAD;
	dst = fdt_subnode_offset(to, parent, fdt_get_name(from, src, NULL));
	if (dst < 0)
		dst = fdt_add_subnode(to, parent, fdt_get_name(from, src, NULL));
	CHECK(dst);
	CHECK(fdt_get_path(to, dst, path, sizeof(path)));
	fdt_for_each_property_offset(prop, from, src) {
		int len;
		const char *name;
		const void *p = fdt_getprop_by_offset(from, prop, &name, &len);
		if (!p)
			return BAD;
		if (!strcmp(name, "phandle") || !strcmp(name, "linux,phandle") ||
		    !strcmp(name, "iommu-addresses"))
			continue;
		CHECK(fdt_setprop(to, fdt_path_offset(to, path), name, p, len));
	}
	fdt_for_each_subnode(child, from, src)
		CHECK(copy_tree(to, fdt_path_offset(to, path), from, child, depth + 1));
	return 0;
}

static int find_compatible(const void *dt, const char *compat)
{
	return fdt_node_offset_by_compatible(dt, -1, compat);
}

static int disable_compatible(void *dt, const char *compat)
{
	int n = -1;
	while ((n = fdt_node_offset_by_compatible(dt, n, compat)) >= 0)
		CHECK(fdt_setprop_string(dt, n, "status", "disabled"));
	return 0;
}

static int copy_calibration(void *to, const void *live, const char *alias)
{
	const char *s = fdt_get_alias(live, alias), *d = fdt_get_alias(to, alias);
	int src, prop;
	char path[512];
	if (!s || !d)
		return BAD;
	if (strlen(d) >= sizeof(path))
		return BAD;
	board_copy(path, d);
	src = fdt_path_offset(live, s);
	CHECK(src);
	fdt_for_each_property_offset(prop, live, src) {
		int len;
		const char *name;
		const void *p = fdt_getprop_by_offset(live, prop, &name, &len);
		if (!p)
			return BAD;
		if (!strncmp(name, "brcm,", 5) || !strcmp(name, "local-mac-address") ||
		    !strcmp(name, "local-bd-address") || !strcmp(name, "mac-address"))
			CHECK(fdt_setprop(to, fdt_path_offset(to, path), name, p, len));
	}
	return 0;
}

static int copy_cpus(void *to, const void *live)
{
	int cpus = fdt_path_offset(to, "/cpus"), n;
	int live_cpus = fdt_path_offset(live, "/cpus"), enabled = 0;
	CHECK(cpus); CHECK(live_cpus);
	fdt_for_each_subnode(n, to, cpus) {
		int len, src, match = -1;
		const fdt64_t *id = fdt_getprop(to, n, "reg", &len);
		char path[128];
		if (!id || len != 8 || strncmp(fdt_get_name(to, n, NULL), "cpu@", 4))
			continue;
		fdt_for_each_subnode(src, live, live_cpus) {
			const fdt64_t *other = fdt_getprop(live, src, "reg", &len);
			const char *status = fdt_getprop(live, src, "status", NULL);
			if (other && len == 8 && fdt64_ld(id) == fdt64_ld(other) &&
			    (!status || !strcmp(status, "okay") || !strcmp(status, "ok")))
				match = src;
		}
		CHECK(fdt_get_path(to, n, path, sizeof(path)));
		if (match < 0) {
			CHECK(fdt_setprop_string(to, n, "status", "disabled"));
		} else {
			CHECK(copy_prop(to, path, live, match, "cpu-release-addr"));
			CHECK(fdt_setprop_string(to, fdt_path_offset(to, path), "status", "okay"));
			enabled++;
		}
		cpus = fdt_path_offset(to, "/cpus");
	}
	return enabled == 12 ? 0 : BAD;
}

static int region_from_adt(void *dt, struct adt_view adt, int sgx,
			   const char *prefix, const char *path)
{
	char name[80];
	u32 len;
	u64 base, size;
	const void *p;
	fdt64_t reg[2];
	if (strlen(prefix) > 60)
		return BAD;
	board_copy(name, prefix); board_append(name, "-base");
	p = adt_prop(adt, sgx, name, &len);
	if (!p || len != 8)
		return BAD;
	base = le64(p);
	board_copy(name, prefix); board_append(name, "-size");
	p = adt_prop(adt, sgx, name, &len);
	if (!p || len != 8)
		return BAD;
	size = le64(p);
	if (!base || !size || ((base | size) & 0x3fff) || base + size < base ||
	    size > 0x40000000)
		return BAD;
	reg[0] = cpu_to_fdt64(base); reg[1] = cpu_to_fdt64(size);
	return fdt_setprop(dt, fdt_path_offset(dt, path), "reg", reg, sizeof(reg));
}

static int aux_opps(void *dt, struct adt_view adt, int sgx,
		    const char *property, const char *table)
{
	u32 len;
	const u8 *p = adt_prop(adt, sgx, property, &len);
	int i;
	if (!p || len != 16 + 8 * 16 + 8 || le64(p) != 1 || le64(p + 8) != 8)
		return BAD;
	for (i = 0; i < 8; i++) {
		char path[96];
		u64 volt = le64(p + 16 + i * 16), freq = le64(p + 24 + i * 16);
		int node;
		if (!volt || volt > 2000000 || !freq || freq > 3000000000ULL ||
		    strlen(table) + 7 >= sizeof(path))
			return BAD;
		board_copy(path, table); board_append(path, "/opp00");
		path[strlen(path) - 1] = '0' + i;
		node = fdt_path_offset(dt, path); CHECK(node);
		CHECK(fdt_setprop_inplace_u32(dt, node, "opp-microvolt", volt));
		CHECK(fdt_setprop_inplace_u64(dt, node, "opp-hz", freq));
	}
	return 0;
}

static int gpu_handoff(void *dt, struct adt_view adt)
{
	static const char prefix[][32] = {"gpu-region", "gfx-shared-region",
		"gfx-shared-l2-region", "gfx-handoff", "gfx-data"};
	static const char paths[][64] = {"/reserved-memory/uat-ttbs",
		"/reserved-memory/uat-pagetables", "/reserved-memory/uat-l2-pagetables",
		"/reserved-memory/uat-handoff", "/reserved-memory/gpu-fw-data"};
	int chosen = adt_named(adt, "chosen"), sgx = adt_named(adt, "sgx");
	const void *p, *core;
	u32 len, count, tables;
	int i, node;
	fdt32_t version[] = {cpu_to_fdt32(26), cpu_to_fdt32(6), cpu_to_fdt32(2)};
	CHECK(chosen); CHECK(sgx);
	p = adt_prop(adt, chosen, "firmware-version", &len);
	if (!p || len < sizeof("mBoot-18000.161.10") || len > 256 ||
	    memcmp(p, "mBoot-18000.161.10", sizeof("mBoot-18000.161.10")))
		return BAD;
	p = adt_prop(adt, sgx, "perf-state-count", &len);
	if (!p || len != 4 || (count = le32(p)) != 16)
		return BAD;
	p = adt_prop(adt, sgx, "perf-state-table-count", &len);
	if (!p || len != 4 || (tables = le32(p)) != 2)
		return BAD;
	core = adt_prop(adt, sgx, "perf-states", &len);
	if (!core || len != count * tables * 8)
		return BAD;
	for (i = 0; i < 5; i++)
		CHECK(region_from_adt(dt, adt, sgx, prefix[i], paths[i]));
	for (i = 0; i < count; i++) {
		char path[] = "/opp-table-gpu/opp00";
		u64 freq0 = le32((const u8 *)core + i * 8),
		    volt0 = le32((const u8 *)core + i * 8 + 4),
		    freq1 = le32((const u8 *)core + (count + i) * 8),
		    volt1 = le32((const u8 *)core + (count + i) * 8 + 4);
		fdt32_t volts[2];
		if (freq0 != freq1 || volt0 > 2000000 || volt1 > 2000000 ||
		    !volt0 || !volt1 || freq0 > 3000000000ULL)
			return BAD;
		/* indexes are derived from the actual string, not a numeric address */
		path[sizeof(path)-3] = '0' + i / 10;
		path[sizeof(path)-2] = '0' + i % 10;
		node = fdt_path_offset(dt, path); CHECK(node);
		volts[0] = cpu_to_fdt32(volt0); volts[1] = cpu_to_fdt32(volt1);
		CHECK(fdt_setprop_inplace(dt, node, "opp-microvolt", volts, sizeof(volts)));
		CHECK(fdt_setprop_inplace_u64(dt, node, "opp-hz", freq0));
	}
	CHECK(aux_opps(dt, adt, sgx, "cs-perf-states", "/opp-table-gpucs"));
	CHECK(aux_opps(dt, adt, sgx, "afr-perf-states", "/opp-table-gpuafr"));
	node = find_compatible(dt, "apple,agx-t6040"); CHECK(node);
	CHECK(fdt_setprop(dt, node, "apple,firmware-version", version, sizeof(version)));
	node = fdt_path_offset(dt, "/power-management@288e80000"); CHECK(node);
	CHECK(fdt_setprop_string(dt, node, "status", "okay"));
	node = find_compatible(dt, "apple,agx-t6040");
	CHECK(fdt_setprop_string(dt, node, "status", "okay"));
	return 0;
}

static int tunable(void *dt, const char *path, struct adt_view adt,
		   int src, const char *name, const char *dest, u32 bias)
{
	u32 len, i;
	const u8 *raw = adt_prop(adt, src, name, &len);
	fdt32_t values[768];
	if (!raw || !len || len % 12 || len > sizeof(values))
		return BAD;
	for (i = 0; i < len / 12; i++) {
		u32 offset = le32(raw + i * 12);
		if ((offset & 0xf0000000) != 0x20000000 || (offset & 3) ||
		    (offset & 0x0fffffff) > 0x10000)
			return BAD;
		values[i * 3] = cpu_to_fdt32((offset & 0x0fffffff) + bias);
		values[i * 3 + 1] = cpu_to_fdt32(le32(raw + i * 12 + 4));
		values[i * 3 + 2] = cpu_to_fdt32(le32(raw + i * 12 + 8));
	}
	return fdt_setprop(dt, fdt_path_offset(dt, path), dest, values, len);
}

static int usb_handoff(void *dt, struct adt_view adt, int port)
{
	static const struct { char source[48], dest[48]; u32 bias; } phy[] = {
		{"tunable_ATC0AXI2AF", "apple,tunable-axi2af", 0},
		{"tunable_ATC_FABRIC", "apple,tunable-fabric", 0},
		{"tunable_ATC_COMMON_CFG", "apple,tunable-common-cfg", 0},
		{"tunable_ATC0AXI2AF_LIOA", "apple,tunable-axi2af-lioa", 0},
		{"tunable_LN0_RX_CFG_TX_OF_RXCLK", "apple,tunable-lane0", 0xd000},
		{"tunable_LN1_RX_CFG_TX_OF_RXCLK", "apple,tunable-lane1", 0x1d000},
		{"tunable_AUS40CMN_SHM", "apple,tunable-aus40cmn-shm", 0xa00},
		{"tunable_AUSPLL_CORE", "apple,tunable-auspll", 0x3200},
		{"tunable_CIO4PLL_CORE", "apple,tunable-cio4pll", 0x3a00},
		{"tunable_USB2PHY_HOST", "apple,tunable-usb2-host", 0},
	};
	static const struct { char source[48], dest[48]; } usb[] = {
		{"tunable_DRD_USB31_GBL_DEFAULT", "apple,tunable-gbl-default"},
		{"tunable_DRD_USB31_GBL_HOST", "apple,tunable-gbl-host"},
		{"tunable_DRD_USB31_DBG_DEFAULT", "apple,tunable-dbg"},
		{"tunable_DRD_USB31_CFG_HOST", "apple,tunable-cfg-host"},
		{"tunable_LINK_REGS_DEFAULT", "apple,tunable-link"},
	};
	char srcname[] = "atc-phy0", usbname[] = "usb-drd0";
	char alias[] = "atcphy0", ua[] = "usb0", path[128], upath[128];
	int src, usrc, i;
	const char *p;
	if (!adt.data)
		return BAD;
	srcname[7] += port; usbname[7] += port;
	alias[6] += port; ua[3] += port;
	src = adt_named(adt, srcname); CHECK(src);
	usrc = adt_named(adt, usbname); CHECK(usrc);
	p = fdt_get_alias(dt, alias);
	if (!p || strlen(p) >= sizeof(path)) return BAD;
	board_copy(path, p);
	p = fdt_get_alias(dt, ua);
	if (!p || strlen(p) >= sizeof(upath)) return BAD;
	board_copy(upath, p);
	for (i = 0; i < sizeof(phy) / sizeof(phy[0]); i++)
		CHECK(tunable(dt, path, adt, src, phy[i].source, phy[i].dest, phy[i].bias));
	CHECK(tunable(dt, path, adt, usrc, "tunable_PIPE_HANDLER_DEFAULT",
		      "apple,tunable-pipehandler", 0));
	for (i = 0; i < sizeof(usb) / sizeof(usb[0]); i++)
		CHECK(tunable(dt, upath, adt, usrc, usb[i].source, usb[i].dest, 0));
	CHECK(fdt_setprop_string(dt, fdt_path_offset(dt, path), "status", "okay"));
	return 0;
}

static int pmp_handoff(void *dt, struct adt_view adt)
{
	static const char excluded[][32] = {"compatible", "AAPL,phandle", "region-base",
		"region-size", "segment-names", "segment-ranges", "pre-loaded",
		"firmware-name", "dram-capacity", "coredump-enable", "name"};
	int chosen, pmp, node, i;
	u32 len, end, off, count;
	const void *p;
	char path[128];
	if (!adt.data) return BAD;
	chosen = adt_named(adt, "chosen"); CHECK(chosen);
	pmp = adt_named(adt, "iop-pmp-nub"); CHECK(pmp);
	node = find_compatible(dt, "apple,t6041-pmp-v2"); CHECK(node);
	CHECK(fdt_get_path(dt, node, path, sizeof(path)));
	p = adt_prop(adt, chosen, "board-id", &len);
	if (!p || len != 4) return BAD;
	CHECK(fdt_setprop_u32(dt, fdt_path_offset(dt, path), "apple,board-id", le32(p)));
	p = adt_prop(adt, chosen, "dram-vendor-id", &len);
	if (!p || len != 4) return BAD;
	CHECK(fdt_setprop_u32(dt, fdt_path_offset(dt, path), "apple,dram-vendor-id", le32(p)));
	p = adt_prop(adt, pmp, "dram-capacity", &len);
	if (p && len == 4)
		CHECK(fdt_setprop_u32(dt, fdt_path_offset(dt, path), "apple,dram-capacity", le32(p)));
	CHECK(adt_props(adt, pmp, &end));
	off = pmp + 8; count = le32(adt.data + pmp);
	while (count--) {
		const char *name = (const char *)adt.data + off;
		char property[64];
		int skip = 0;
		len = le32(adt.data + off + 32) & 0x7fffffff;
		for (i = 0; i < sizeof(excluded) / sizeof(excluded[0]); i++)
			if (!strcmp(name, excluded[i])) skip = 1;
		if (!skip) {
			board_copy(property, "apple,tunable-"); board_append(property, name);
			CHECK(fdt_setprop(dt, fdt_path_offset(dt, path), property,
					 adt.data + off + 36, len));
		}
		off += 36 + ((len + 3) & ~3U);
	}
	return fdt_setprop_string(dt, fdt_path_offset(dt, path), "status", "okay");
}

/* template has all donor firmware reservations zeroed and devices disabled. */
int aurora_j614s_handoff(const void *live, void *out, int capacity,
			const void *template, struct adt_view adt)
{
	int n, parent, memory = -1, depth = 0, port, gpu_error, pmp_error;
	fdt32_t usb_errors[3];
	if (fdt_check_header(live) || fdt_node_check_compatible(live, 0, "apple,j614s"))
		return BAD;
	CHECK(fdt_open_into(template, out, capacity));
	/* m1n1's image and spin-table trampolines are reserved in the FDT header,
	 * separately from /reserved-memory. Both reservation forms must survive. */
	{
		int i, reservations = fdt_num_mem_rsv(live);
		u64 address, size;
		if (reservations < 0 || reservations > 128)
			return BAD;
		for (i = 0; i < reservations; i++) {
			CHECK(fdt_get_mem_rsv(live, i, &address, &size));
			CHECK(fdt_add_mem_rsv(out, address, size));
		}
	}
	n = fdt_path_offset(live, "/chosen"); CHECK(n);
	CHECK(copy_tree(out, 0, live, n, 0));
	while ((n = fdt_next_node(live, memory, &depth)) >= 0) {
		const char *type = fdt_getprop(live, n, "device_type", NULL);
		memory = n;
		if (type && !strcmp(type, "memory")) {
			CHECK(copy_prop(out, "/memory@0", live, n, "reg"));
			break;
		}
	}
	if (n < 0)
		return BAD;
	CHECK(copy_cpus(out, live));
	parent = fdt_path_offset(live, "/reserved-memory"); CHECK(parent);
	fdt_for_each_subnode(n, live, parent) {
		const char *name = fdt_get_name(live, n, NULL);
		if (fdt_subnode_offset(out, fdt_path_offset(out, "/reserved-memory"), name) >= 0)
			return BAD;
		CHECK(copy_tree(out, fdt_path_offset(out, "/reserved-memory"), live, n, 0));
	}
	CHECK(copy_calibration(out, live, "wifi0"));
	CHECK(copy_calibration(out, live, "bluetooth0"));
	pmp_error = pmp_handoff(out, adt);
	/* No donor display/DMA/ISP reservations or J616 speaker topology. */
	CHECK(disable_compatible(out, "apple,j616-macaudio"));
	CHECK(disable_compatible(out, "ti,tas2764"));
	CHECK(disable_compatible(out, "apple,t6041-isp"));
	CHECK(disable_compatible(out, "apple,t6041-aop"));
	CHECK(disable_compatible(out, "apple,t6041-dcp"));
	for (port = 0; port < 3; port++) {
		/* A port without this boot's tuning remains disabled. */
		usb_errors[port] = cpu_to_fdt32(usb_handoff(out, adt, port));
	}
	/* A missing/unknown GPU handoff retains framebuffer-only operation. */
	gpu_error = adt.data ? gpu_handoff(out, adt) : BAD;
	if (gpu_error) {
		CHECK(disable_compatible(out, "apple,agx-t6040"));
		n = fdt_path_offset(out, "/power-management@288e80000"); CHECK(n);
		CHECK(fdt_setprop_string(out, n, "status", "disabled"));
	}
	n = fdt_path_offset(out, "/chosen"); CHECK(n);
	CHECK(fdt_setprop_string(out, n, "m4rch,aurora-test", "AURT002"));
	n = fdt_path_offset(out, "/chosen");
	CHECK(fdt_setprop_u32(out, n, "m4rch,gpu-handoff-error", gpu_error));
	n = fdt_path_offset(out, "/chosen");
	CHECK(fdt_setprop_u32(out, n, "m4rch,pmp-handoff-error", pmp_error));
	n = fdt_path_offset(out, "/chosen");
	CHECK(fdt_setprop(out, n, "m4rch,usb-handoff-errors", usb_errors, sizeof(usb_errors)));
	return 0;
}
