#!/usr/bin/env python3
"""Apply the explicit, opt-in J614s retained-display port to pinned Aurora."""
import argparse
import difflib
from pathlib import Path
import shutil

KIT = Path(__file__).resolve().parent


def prepare(root, output):
    originals = {}

    def edit(relative, old, new):
        path = root / relative
        text = path.read_text()
        originals.setdefault(relative, text)
        if text.count(old) != 1:
            raise ValueError(f'Expected one anchor in {relative}: {old[:85]!r}')
        path.write_text(text.replace(old, new))

    gpu = 'drivers/gpu/drm/apple/'
    dart = 'drivers/iommu/apple-dart.c'
    fmt = 'drivers/iommu/apple-dart-dcp-format.h'
    borrowed = 'drivers/iommu/apple-dart-dcp.h'
    profile = gpu + 'dcp-m4-profile.h'
    edit(profile, '#include <linux/types.h>', '#include <linux/types.h>\n#include <linux/of.h>')
    edit(profile, '/* This generation backend admits one qualified internal-panel ABI. */\nstatic const struct dcp_m4_profile *const dcp_m4_pf = &dcp_m4_profile_j713;', '''/* Same RPC identity, explicit board/firmware qualification in iomfb_m4_init. */
static const struct dcp_m4_profile dcp_m4_profile_j614s = {
    .name = "J614s-DCP001",
    .panel_width = 3024, .panel_height = 1964, .boot_stride = 12096,
    .swap_size = 0x1bd8, .swap_surface = 0x588, .swap_dva = 0xe38,
    .swap_nullable = 0x1bcb, .swap_tail = 0x1bd6, .swap_nits = 0x35e,
    .disabled_color = 0xff000000,
    .done_method = 590, .done_size = 0x730, .open_method = 457,
    .brightness_max = 500, .brightness_default = 120,
    .width_mm = 302, .height_mm = 196,
};

static inline const struct dcp_m4_profile *dcp_m4_board_profile(void)
{
    return IS_ENABLED(CONFIG_DRM_APPLE_DCP_J614S) &&
           of_machine_is_compatible("apple,j614s") ?
           &dcp_m4_profile_j614s : &dcp_m4_profile_j713;
}
#define dcp_m4_pf (dcp_m4_board_profile())''')
    timing = gpu + 'dcp-m4-timing.h'
    edit(timing, 'static inline int dcp_m4_parse_timing(', '#include "j614s-timing.h"\n\nstatic inline int dcp_m4_parse_timing(')
    edit(timing, '\tret = -EINVAL;\n\tif (p->pos != size', '''    if (p->pos == size && dcp_m4_pf == &dcp_m4_profile_j614s) {
        ret = j614s_parse_timing(p, out);
        goto done;
    }
\tret = -EINVAL;
\tif (p->pos != size''')
    m4 = gpu + 'iomfb_m4.c'
    edit(m4, '#include "dcp-m4-profile.h"', '#include "dcp-m4-profile.h"\n#include "j614s-power.h"')
    edit(m4, '\treturn apple_pmp_j713_display_get(dev);', '\treturn j614s_display_board() ? j614s_display_power_check(dev) : apple_pmp_j713_display_get(dev);')
    edit(m4, '\treturn apple_pmp_j713_display_check(dev);', '\treturn j614s_display_board() ? j614s_display_power_check(dev) : apple_pmp_j713_display_check(dev);')
    edit(m4, '!of_property_read_bool(node, "apple,j713-inherited-mappings"))', '!of_property_read_bool(node, j614s_display_board() ? "apple,j614s-inherited-mappings" : "apple,j713-inherited-mappings"))')
    edit(m4, 'height != dcp_m4_pf->panel_height - 64', 'height != dcp_m4_pf->panel_height - (j614s_display_board() ? 74 : 64)')
    edit(m4, '''\tif (!of_machine_is_compatible("apple,j713") ||
\t    !of_device_is_compatible(dev->of_node, "apple,t8132-dcp") ||''', '''    bool j614s = IS_ENABLED(CONFIG_DRM_APPLE_DCP_J614S) && j614s_display_board();

    if ((!j614s && !of_machine_is_compatible("apple,j713")) ||
        !of_device_is_compatible(dev->of_node, j614s ? "apple,t6041-dcp" : "apple,t8132-dcp") ||''')
    edit(m4, 'strcmp(uuid, "81BAF476-679D-3CC0-8C6A-E6B6FA659D5E"))', 'strcmp(uuid, j614s ? "6CC9349E-D30B-33FB-B12B-8D6D38F9F1B3" : "81BAF476-679D-3CC0-8C6A-E6B6FA659D5E"))')
    edit(m4, 'res->start != 0x30ae00000ULL', 'res->start != (j614s ? 0x402e00000ULL : 0x30ae00000ULL)')
    edit(m4, 'ret = apple_pmp_j713_display_prepare(dev);', 'ret = j614s ? j614s_display_power_prepare(dev) : apple_pmp_j713_display_prepare(dev);')
    edit(gpu + 'dcp.c', '\t{ .compatible = "apple,t8132-dcp", .data = &apple_dcp_hw_t8132, },', '''\t{ .compatible = "apple,t8132-dcp", .data = &apple_dcp_hw_t8132, },
#if IS_ENABLED(CONFIG_DRM_APPLE_DCP_J614S)
    { .compatible = "apple,t6041-dcp", .data = &apple_dcp_hw_t8132, },
#endif''')
    driver = gpu + 'apple_drv.c'
    edit(driver, 'return (of_device_is_compatible(dev->of_node, "apple,t8132-display-subsystem") ||', 'return (of_device_is_compatible(dev->of_node, "apple,t6041-display-subsystem") ||\n                of_device_is_compatible(dev->of_node, "apple,t8132-display-subsystem") ||')
    edit(driver, '\t{ .compatible = "apple,t8132-dcp" },', '\t{ .compatible = "apple,t8132-dcp" },\n\t{ .compatible = "apple,t6041-dcp" },')
    edit(driver, '\t{ .compatible = "apple,t8132-display-subsystem" },', '\t{ .compatible = "apple,t8132-display-subsystem" },\n\t{ .compatible = "apple,t6041-display-subsystem" },')

    # Preserve the supplier through this trial's retained epoch. The predicate
    # remains false for ordinary entries, whose display node stays disabled.
    power = 'include/linux/soc/apple/pmp-display.h'
    edit(power, 'struct device;\nstruct apple_pmp_display;', '''static inline bool apple_pmp_j614s_display_board(void)
{
    struct device_node *np;
    bool active;

    if (!IS_ENABLED(CONFIG_DRM_APPLE_DCP_J614S) ||
        !of_machine_is_compatible("apple,j614s"))
        return false;
    np = of_find_node_by_path("dcp");
    active = np && of_device_is_available(np) &&
             of_property_read_bool(np, "apple,j614s-inherited-mappings");
    of_node_put(np);
    return active;
}

struct device;
struct apple_pmp_display;''')
    edit('drivers/soc/apple/pmp-display.c', '\treturn apple_pmp_j713_board();', '\treturn apple_pmp_j713_board() || apple_pmp_j614s_display_board();')

    # DART ownership is the same retained SID23/SID0/SID16 mechanism, admitted
    # by its actual T6041 MMIO windows and live, independently parsed ADT.
    edit(dart, '\t/* The J713 radio DART\'s fault interrupt', '''    if (res && !tunneled && IS_ENABLED(CONFIG_DRM_APPLE_DCP_J614S) &&
        of_machine_is_compatible("apple,j614s") &&
        of_device_is_compatible(dev->of_node, "apple,t6041-dart") &&
        (res->start == 0x402300000ULL || res->start == 0x402340000ULL))
        j713_display = true;
\t/* The J713 radio DART's fault interrupt''')
    edit(dart, '(res->start == 0x30a300000ULL && !READ_ONCE', '((res->start == 0x30a300000ULL || res->start == 0x402300000ULL) && !READ_ONCE')
    edit(dart, '(res->start == 0x30a340000ULL && !READ_ONCE', '((res->start == 0x30a340000ULL || res->start == 0x402340000ULL) && !READ_ONCE')
    edit(dart, 'ret = res->start == 0x30a340000ULL ? apple_dart_dcp_prepare(dart) :', 'ret = (res->start == 0x30a340000ULL || res->start == 0x402340000ULL) ? apple_dart_dcp_prepare(dart) :')
    edit(dart, 'dart->fw_mirror = dart->locked && !dart->fw_handoff &&',
         'dart->fw_mirror = !dart->preserve_display && dart->locked && !dart->fw_handoff &&')
    edit(fmt, '\tu32 num_segments;\n', '\tu32 num_segments;\n\tbool t6041;\n')
    edit(fmt, '''\t\tif (length != 5 || memcmp(value, "J713", 5))
\t\t\treturn -ENODEV;''', '''        if (length == 6 && !memcmp(value, "J614s", 6))
            out->t6041 = true;
        else if (length != 5 || memcmp(value, "J713", 5))
            return -ENODEV;''')
    edit(fmt, 'static const char uuid[] = "81BAF476-679D-3CC0-8C6A-E6B6FA659D5E";', 'const char *uuid = out->t6041 ? "6CC9349E-D30B-33FB-B12B-8D6D38F9F1B3" : "81BAF476-679D-3CC0-8C6A-E6B6FA659D5E";')
    edit(fmt, 'length != sizeof(uuid) || memcmp(value, uuid, sizeof(uuid))', 'length != 37 || memcmp(value, uuid, 37)')
    edit(fmt, '''\t\tstatic const char names[] =
\t\t\t"__TEXT;__DATA;__OS_LOG;unknown;unknown;unknown;unknown";''', '''        const char *names = out->t6041 ?
            "__TEXT;__DATA;__OS_LOG;unknown;unknown;unknown;unknown;unknown" :
            "__TEXT;__DATA;__OS_LOG;unknown;unknown;unknown;unknown";''')
    edit(fmt, 'length != sizeof(names) || memcmp(value, names, sizeof(names))', 'length != strlen(names) + 1 || memcmp(value, names, length)')
    edit(fmt, 'out->num_segments != 7', 'out->num_segments != (out->t6041 ? 8 : 7)')
    edit(fmt, 'static const u32 kinds[] = {1, 0, 10, 2, 2, 2, 2};', 'static const u32 kinds[] = {1, 0, 10, 2, 2, 2, 2, 2};')
    edit(borrowed, '\tu32 ttbr;\n', '\tu32 ttbr;\n\tu32 tcr;\n')
    edit(borrowed, 'readl(dart->regs + DART_TCR(dart, dcp->sid)) == DART_T8110_TCR_TRANSLATE_ENABLE',
         'readl(dart->regs + DART_TCR(dart, dcp->sid)) == dcp->tcr')
    edit(borrowed, 'dart->num_streams != 32 ||', '(bounds.t6041 ? dart->num_streams < 24 : dart->num_streams != 32) ||')
    edit(borrowed, 'tcr != DART_T8110_TCR_TRANSLATE_ENABLE || !(enabled & BIT(sid))',
         '''(bounds.t6041 ? (!(tcr & DART_T8110_TCR_TRANSLATE_ENABLE) ||
          (tcr & ~(DART_T8110_TCR_TRANSLATE_ENABLE | DART_T8110_TCR_BYPASS_DAPF))) :
          tcr != DART_T8110_TCR_TRANSLATE_ENABLE) || !(enabled & BIT(sid))''')
    edit(borrowed, '\tdcp->sid = sid;', '\tdcp->sid = sid;\n\tdcp->tcr = tcr;')
    edit(borrowed, 'return of_device_is_compatible(node, "apple,t8132-display-subsystem") ||', 'return of_device_is_compatible(node, "apple,t6041-display-subsystem") ||\n               of_device_is_compatible(node, "apple,t8132-display-subsystem") ||')
    edit(borrowed, 'of_property_read_bool(alias, "apple,j713-inherited-mappings")', 'of_property_read_bool(alias, dcp->firmware.t6041 ? "apple,j614s-inherited-mappings" : "apple,j713-inherited-mappings")')
    edit(borrowed, 'if (nr != (dcp->sid == 0 ? 2 : 1))', 'if (dcp->firmware.t6041 ? (nr < 1 || nr > 5) : (nr != (dcp->sid == 0 ? 2 : 1)))')
    edit(borrowed, 'if (++matches != 1 || !(wanted & bit) || (seen & bit))', 'if (++matches != 1 || (!dcp->firmware.t6041 && !(wanted & bit)) || (seen & bit))')
    edit(borrowed, 'return seen == wanted && apple_dart_dcp_registers(dcp) ? 0 : -EINVAL;', 'return (dcp->firmware.t6041 ? seen != 0 : seen == wanted) && apple_dart_dcp_registers(dcp) ? 0 : -EINVAL;')
    edit(borrowed, 'if (!of_device_is_compatible(dev->of_node, "apple,t8132-dcp") ||', 'if (!of_device_is_compatible(dev->of_node, dcp->firmware.t6041 ? "apple,t6041-dcp" : "apple,t8132-dcp") ||')
    edit(borrowed, 'strcmp(uuid, "81BAF476-679D-3CC0-8C6A-E6B6FA659D5E")', 'strcmp(uuid, dcp->firmware.t6041 ? "6CC9349E-D30B-33FB-B12B-8D6D38F9F1B3" : "81BAF476-679D-3CC0-8C6A-E6B6FA659D5E")')
    edit(borrowed, 'resource_size(&res) != 0x24000', '''resource_size(&res) != (dcp->firmware.t6041 ?
                ALIGN(dcp->firmware.segment[2].phys + dcp->firmware.segment[2].size, DCP_DART_PAGE) -
                ALIGN_DOWN(dcp->firmware.segment[2].phys, DCP_DART_PAGE) : 0x24000)''')

    newfiles = {
        'drivers/soc/apple/j614s-display-boot.c': 'j614s-display-boot.c',
        gpu + 'j614s-power.h': 'j614s-power.h',
        gpu + 'j614s-timing.h': 'j614s-timing.h',
    }
    for relative, source in newfiles.items():
        path = root / relative
        if path.exists():
            raise ValueError('Already prepared: ' + relative)
        originals[relative] = ''
        shutil.copyfile(KIT / 'kernel' / source, path)
    for relative, addition in {
        'drivers/soc/apple/Kconfig': '\nconfig APPLE_J614S_DCP_BOOT\n\tbool "J614s opt-in retained DCP handoff"\n\tdepends on ARCH_APPLE && OF\n\tselect OF_DYNAMIC\n',
        'drivers/soc/apple/Makefile': '\nobj-$(CONFIG_APPLE_J614S_DCP_BOOT) += j614s-display-boot.o\n',
        gpu + 'Kconfig': '\nconfig DRM_APPLE_DCP_J614S\n\tbool "Experimental J614s T6041 internal panel"\n\tdepends on DRM_APPLE_DCP_T8132 && APPLE_J614S_DCP_BOOT\n',
    }.items():
        path = root / relative
        originals[relative] = path.read_text()
        path.write_text(originals[relative] + addition)
    output.mkdir(parents=True, exist_ok=True)
    patch = []
    for relative, before in originals.items():
        patch.extend(difflib.unified_diff(before.splitlines(True), (root / relative).read_text().splitlines(True),
                     fromfile='a/' + relative if before else '/dev/null', tofile='b/' + relative))
    (output / 'kernel-dcp001.patch').write_text(''.join(patch))
    print(f'Prepared J614s retained DCP port: {len(originals)} files')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, default=KIT.parents[1] / 'out/aurora-dcp')
    args = parser.parse_args()
    prepare(args.root, args.output)
