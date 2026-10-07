/* Verify the actual generated reg property against libfdt node offsets. */
#include <assert.h>
#include <libfdt.h>
int main(void)
{
    char tree[8192];
    fdt32_t original[12] = {0};
    assert(!fdt_create_empty_tree(tree, sizeof(tree)));
    assert(fdt_add_subnode(tree, 0, "later") >= 0);
    int nvme = fdt_add_subnode(tree, 0, "nvme");
    assert(nvme >= 0);
    assert(!fdt_setprop(tree, nvme, "reg", original, sizeof(original)));
    int saved = fdt_path_offset(tree, "/later");
    /* ACTUAL_REG */
    assert(sizeof(reg) == sizeof(original));
    assert(!fdt_setprop(tree, nvme, "reg", reg, sizeof(reg)));
    assert(fdt_path_offset(tree, "/later") == saved);
    assert(fdt32_to_cpu(reg[8]) == 4 && fdt32_to_cpu(reg[9]) == 0x0dcc0000);
    /* Reproduce the previous shortening bug: cached offsets become stale. */
    assert(!fdt_setprop(tree, nvme, "reg", reg, 8 * sizeof(fdt32_t)));
    assert(fdt_path_offset(tree, "/later") != saved);
}
