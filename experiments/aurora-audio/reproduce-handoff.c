/* Run the production AOP bridge against a captured ADT and board template. */
#define AURORA_HOST_TEST
#ifndef BRIDGE_SOURCE
#define BRIDGE_SOURCE "../aurora-direct/board_handoff.c"
#endif
#include BRIDGE_SOURCE
#include <assert.h>
#include <stdlib.h>
static void *load(const char *path, size_t *size) {
    FILE *f = fopen(path, "rb"); assert(f);
    assert(!fseek(f, 0, SEEK_END)); *size = ftell(f); rewind(f);
    void *p = calloc(1, 2 << 20); assert(p && *size < (2 << 20));
    assert(fread(p, 1, *size, f) == *size); fclose(f); return p;
}
int main(int argc, char **argv) {
    assert(argc == 3); size_t length; void *dt = load(argv[1], &length);
    assert(!fdt_open_into(dt, dt, 2 << 20));
    struct adt_view adt; adt.data = load(argv[2], &length); adt.size = length;
    int r = aop_handoff(dt, adt, 3);
    if (!r) {
        int n = find_compatible(dt, "apple,t6041-aop"), len;
        const fdt32_t *refs = fdt_getprop(dt, n, "memory-region", &len);
        assert(refs && len == 8);
        for (int i = 0; i < 2; i++) {
            int reserved = fdt_node_offset_by_phandle(dt, fdt32_ld(refs + i));
            const fdt32_t *map = fdt_getprop(dt, reserved, "iommu-addresses", &len);
            const fdt64_t *reg = fdt_getprop(dt, reserved, "reg", NULL);
            assert(map && len == 20 && fdt32_ld(map) == fdt_get_phandle(dt, n));
            assert(fdt64_ld((const fdt64_t *)(map + 1)) ==
                   (i ? fdt64_ld(reg) : 0x10000000000ULL));
        }
        n = find_compatible(dt, "apple,j616-macaudio");
        assert(n >= 0 && !strcmp(fdt_getprop(dt, n, "status", NULL), "disabled"));
    }
    printf("AOP production handoff: %d; code/log contract and speaker exclusion checked\n", r);
    return r != 0;
}
