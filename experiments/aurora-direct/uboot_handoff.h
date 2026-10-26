/* SPDX-License-Identifier: GPL-2.0-only */
#include <malloc.h>
#include <env_internal.h>
#include <asm/system.h>
#include "aurora-template.h"
#include "aurora-handoff.c"

static int aurora_prepare_fdt(const void *live, void *out, int capacity, bool gpu_off)
{
    struct adt_view adt = {};
    int parent = fdt_path_offset(live, "/reserved-memory"), n, ret;
    if (parent >= 0) {
        fdt_for_each_subnode(n, live, parent) {
            int len;
            const char *label = fdt_getprop(live, n, "label", &len);
            const fdt64_t *reg;
            if (!label || len != 4 || memcmp(label, "adt", 4))
                continue;
            reg = fdt_getprop(live, n, "reg", &len);
            if (!reg || len != 16 || !fdt64_ld(reg) ||
                fdt64_ld(reg + 1) < 8 || fdt64_ld(reg + 1) > 16 * 1024 * 1024)
                return -FDT_ERR_BADVALUE;
            adt.data = (const void *)(unsigned long)fdt64_ld(reg);
            adt.size = fdt64_ld(reg + 1);
            break;
        }
    }
    ret = aurora_j614s_handoff(live, out, capacity, aurora_template, adt, read_mpidr() & 0xffffff);
    if (!ret)
        ret = retain_live_ans_memory(out, mem_malloc_start, mem_malloc_end,
                                    TOTAL_MALLOC_LEN);
    if (!ret && gpu_off) {
        ret = gpu_dependencies(out, 0);
        if (ret) return ret;
        ret = disable_compatible(out, "apple,agx-t6040");
        if (!ret)
            ret = fdt_setprop_string(out, fdt_path_offset(out, "/power-management@288e80000"),
                                     "status", "disabled");
    }
    return ret;
}
