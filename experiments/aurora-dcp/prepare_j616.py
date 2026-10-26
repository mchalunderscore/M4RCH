#!/usr/bin/env python3
"""J614s board adaptation of the merged J616s display stack (AUDP001 r10).

Start from Linux 6dc07e43 and m1n1 1efafe1f, not an earlier trial tree.
In particular, do not apply prepare_kernel/desktop/shared/buffers: those
select the J713 allocator or the superseded PMP and retained-DMA wrappers.
"""
import argparse
import difflib
import importlib.util
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def replace(path, old, new):
    text = path.read_text()
    if new != old and new in text:
        return
    assert text.count(old) == 1, (str(path), old[:100])
    path.write_text(text.replace(old, new, 1))


def kernel(root, out):
    tracked = {}
    for name in ['drivers/gpu/drm/apple/dcp.c', 'drivers/gpu/drm/apple/apple_drv.c',
                 'drivers/gpu/drm/apple/iomfb.c', 'drivers/soc/apple/Kconfig',
                 'drivers/soc/apple/Makefile']:
        tracked[name] = (root / name).read_text()
    # Keep the GPU changes which were qualified on this 16-core machine.
    module(PROJECT / 'experiments/aurora-direct/prepare_gpu16.py', 'gpu16').prepare(root, out)
    for number in [427, 429, 433]:
        patch = HERE / f'upstream/pr-{number}.patch'
        check = subprocess.run(['git', 'apply', '--check', str(patch)], cwd=root,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check.returncode:
            subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)], cwd=root, check=True)
        else:
            subprocess.run(['git', 'apply', str(patch)], cwd=root, check=True)
    dcp = root / 'drivers/gpu/drm/apple/dcp.c'
    replace(dcp, '\tint i;\n\n\tif (!of_device_is_compatible(dev->of_node, "apple,t6041-dcp"))',
            '\tbool j614s = of_machine_is_compatible("apple,j614s");\n'
            '\tunsigned int expected = ARRAY_SIZE(t6041_dcp_regs) + j614s;\n\tint i;\n\n'
            '\tif (!of_device_is_compatible(dev->of_node, "apple,t6041-dcp"))')
    replace(dcp, 'pdev->num_resources != ARRAY_SIZE(t6041_dcp_regs)', 'pdev->num_resources != expected')
    replace(dcp, '"T6041 DCP: %u register windows, the ADT has %zu\\n",\n\t\t\t\t     pdev->num_resources, ARRAY_SIZE(t6041_dcp_regs)',
            '"T6041 DCP: %u register windows, this board requires %u\\n",\n\t\t\t\t     pdev->num_resources, expected')
    anchor = '\tif (!of_property_present(dev->of_node, "iommus") ||'
    replace(dcp, anchor, '''\tif (j614s) {
\t\tstruct resource *r = platform_get_resource(pdev, IORESOURCE_MEM, 5);

\t\tif (!r || r->start != 0x504800000ULL || resource_size(r) != 0xbc000 ||
\t\t    of_property_match_string(dev->of_node, "reg-names", "disp-4") != 5)
\t\t\treturn dev_err_probe(dev, -ENODEV, "J614s DISP0 shared aperture differs from ADT\\n");
\t}

''' + anchor)
    # This is a physical resource alias on J614s, not another firmware register.
    shared = (HERE / 'prepare_shared.py').read_text()
    import ast
    tree = ast.parse(shared)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'prepare')
    value = next(n.value for n in function.body if isinstance(n, ast.Assign) and
                 any(isinstance(t, ast.Name) and t.id == 'new' for t in n.targets))
    snippet = ast.literal_eval(value.left).replace('j614s_display_board()', 'of_machine_is_compatible("apple,j614s")')
    anchor = '\t/* load pmgr bandwidth scratch resource and offset */'
    replace(dcp, anchor, snippet + anchor)
    drv = root / 'drivers/gpu/drm/apple/apple_drv.c'
    # The component inventory must match the SoC-specific compatible as well.
    replace(drv, '\t{ .compatible = "apple,dcp" },',
            '\t{ .compatible = "apple,dcp" },\n\t{ .compatible = "apple,t6041-dcp" },')
    iomfb = root / 'drivers/gpu/drm/apple/iomfb.c'
    replace(iomfb, '\tu32 best = U32_MAX;\n\tstruct dcp_desktop_state *d;',
            '\tu32 best = U32_MAX;\n\tbool j614s = of_machine_is_compatible("apple,j614s");\n\tstruct dcp_desktop_state *d;')
    replace(iomfb, '''\t\tif (!m->vrr) {
\t\t\tu32 delta = abs((int)m->mode.clock -
\t\t\t\t\tDCP_DESKTOP_BOOT_PIXEL_CLOCK_KHZ);''', '''\t\tif (!m->vrr && (!j614s ||
\t\t    (m->mode.hdisplay == 3024 && m->mode.vdisplay == 1964))) {
\t\t\tu32 delta = j614s ? abs(drm_mode_vrefresh(&m->mode) - 60) :
\t\t\t\tabs((int)m->mode.clock - DCP_DESKTOP_BOOT_PIXEL_CLOCK_KHZ);''')
    replace(iomfb, 'best <= DCP_DESKTOP_BOOT_PIXEL_CLOCK_KHZ / 100',
            'best <= (j614s ? 1 : DCP_DESKTOP_BOOT_PIXEL_CLOCK_KHZ / 100)')
    gate = root / 'drivers/soc/apple/j614s-display-boot.c'
    gate.write_text((HERE / 'kernel/j614s-merged-display-boot.c').read_text())
    with (root / 'drivers/soc/apple/Kconfig').open('a') as f:
        f.write('\nconfig APPLE_J614S_DCP_BOOT\n\tbool "J614s merged T6041 display admission"\n\tdepends on ARCH_APPLE && OF_DYNAMIC\n')
    with (root / 'drivers/soc/apple/Makefile').open('a') as f:
        f.write('\nobj-$(CONFIG_APPLE_J614S_DCP_BOOT) += j614s-display-boot.o\n')
    patch = []
    for name, before in tracked.items():
        patch += difflib.unified_diff(before.splitlines(True), (root / name).read_text().splitlines(True),
                                     fromfile='a/' + name, tofile='b/' + name)
    patch += difflib.unified_diff([], gate.read_text().splitlines(True), fromfile='/dev/null',
                                 tofile='b/drivers/soc/apple/j614s-display-boot.c')
    (out / 'kernel-j614s.patch').write_text(''.join(patch))
    dart = (root / 'drivers/iommu/apple-dart.c').read_text()
    assert 'apple,j614s' not in dart
    assert 'dart->fw_mirror' in dart and '"apple,t6041-dart"' in dart
    assert 'dcp_alloc_dma' not in dcp.read_text()
    print('Merged J616s display, native J614s resources, standard DMA and qualified GPU changes prepared')


def m1n1(root, out):
    replace(root / 'src/kboot_display_handoff.c',
            'dcp_boards_t6041[] = {"apple,j616s", NULL}',
            'dcp_boards_t6041[] = {"apple,j616s", "apple,j614s", NULL}')
    replace(root / 'src/display.c', 'if (chip_id == T8140 || chip_id == T8132) {\n        printf("display: preserving inherited display',
            'if (chip_id == T8140 || chip_id == T8132 || chip_id == T6040) {\n        printf("display: preserving inherited display')
    module(HERE / 'prepare_flat_root.py', 'flat_root').prepare(root, out)
    print('Merged T6041 handoff admitted for native J614s; no custom reservation publisher')


def templates(root, out):
    # Retain the native-tested CPU, radio, USB, GPU and firmware graph. The
    # common publisher requires every display consumer, including PIODMA,
    # disabled and free of stale handoff properties before it publishes.
    for name in ['template.dtb', 'control.dtb']:
        path = out / name
        shutil.copyfile(PROJECT / 'out/aurora-dcp' / name, path)
        for node in ['/dcp@402e00000', '/dcp@402e00000/piodma', '/display-subsystem']:
            props = subprocess.check_output(['fdtget', '-p', str(path), node], text=True).splitlines()
            for prop in ['memory-region', 'memory-region-names', 'apple,j614s-inherited-mappings',
                         'apple,t6041-handoff', 'apple,firmware-uuid']:
                if prop in props:
                    subprocess.run(['fdtput', '-d', str(path), node, prop], check=True)
            subprocess.run(['fdtput', '-t', 's', str(path), node, 'status', 'disabled'], check=True)
        if name == 'control.dtb':
            subprocess.run(['fdtput', '-t', 's', str(path), '/chosen', 'asahi,t6041-dcp', '1'], check=True)
        for alias in ['wifi0', 'bluetooth0']:
            node = subprocess.check_output(['fdtget', str(path), '/aliases', alias], text=True).strip()
            subprocess.run(['fdtput', '-t', 's', str(path), node, 'brcm,board-type', 'apple,mriya'], check=True)
    print('Native templates prepared for the standard m1n1 T6041 publisher')


def uboot(root, out):
    directory = root / 'arch/arm/mach-apple'
    # These two complete file additions capture the tested AUBS001 root-DT
    # boot path, with no board.dtbo dependency. Their upstream pin is unchanged.
    patch = (PROJECT / 'out/aurora-bootstrap/uboot.patch').read_text()
    for name in ['archsd.c', 'j614s-map.h']:
        rel = 'arch/arm/mach-apple/' + name
        section = patch.split('diff --git a/' + rel + ' b/' + rel + '\n', 1)[1].split('\ndiff --git ', 1)[0]
        assert '--- /dev/null\n' in section
        data = ''.join(line[1:] for line in section.splitlines(True) if line.startswith('+') and not line.startswith('+++'))
        assert data
        (directory / name).write_text(data)
    path = directory / 'aurora-handoff.c'
    replace(path, '#include "peripheral_handoff.c"',
            '#include "peripheral_handoff.c"\n#include "dcp_merged_handoff.c"')
    anchor = '\tCHECK(disable_compatible(out, "apple,t6041-dcp"));'
    replace(path, anchor, '''    if (dcp_handoff(out, live))
        printf("AUDP010: standard display handoff unavailable; retaining framebuffer boot\\n");
''' + anchor)
    shutil.copyfile(HERE / 'loader/dcp_merged_handoff.c', directory / 'dcp_merged_handoff.c')
    module(HERE / 'prepare_uboot.py', 'template').refresh_template(root, out)
    print('Native-tested U-Boot path prepared with complete named-region transfer')


def fixtures(root, out):
    path = root / 'tools/testing/selftests/drivers/gpu/apple-dcp/lifecycle.py'
    before = path.read_text()
    # The upstream resource mock predates the board branch; keep production
    # function extraction intact and extend only its mock and test cases.
    start = before.index('def profile(root):')
    end = before.index('\ndef firmware(root):', start)
    part = before[start:end]
    part = part.replace('#define DCP_FIRMWARE_H17P 3', '''#define DCP_FIRMWARE_H17P 3
#define DCP_FIRMWARE_V_26_6_DESKTOP 4
#define dev_err_probe(dev, error, ...) (error)
#define dev_info(...) ((void)0)
static bool native_j614s, mismatch;
static bool of_machine_is_compatible(const char *name)
{ return native_j614s && !strcmp(name, "apple,j614s"); }''')
    part = part.replace('struct device *dev; struct apple_dcp_hw_data hw;',
                        'struct device *dev; struct apple_dcp_hw_data hw; int fw_compat;')
    part = part.replace('static int dcp_get_bw_scratch_reg(struct apple_dcp *p,u32 count) { (void)p;(void)count;return -ENOENT; }',
                        '''static int dcp_get_bw_scratch_reg(struct apple_dcp *p,u32 count)
{
    if (!native_j614s) return -ENOENT;
    assert(count==4);
    p->disp_bw_scratch_res=*p->disp_registers[4];
    if (mismatch) p->disp_bw_scratch_res.start++;
    return 0;
}''')
    part = part.replace('    puts("PASS: actual internal/external profiles, resource admission and D003 bandwidth reply");', '''    reset(false,true); native_j614s=true;
    d.hw=(struct apple_dcp_hw_data){0}; d.fw_compat=DCP_FIRMWARE_V_26_6_DESKTOP;
    assert(!dcp_get_disp_regs(&d) && d.nr_disp_registers==5);
    mismatch=true; assert(dcp_get_disp_regs(&d)==-EINVAL); mismatch=false;
    node.count=4; assert(dcp_get_disp_regs(&d)==-EINVAL);
    puts("PASS: actual internal/external/J614s profiles, resource admission and D003 bandwidth reply");''')
    assert part != before[start:end]
    after = before[:start] + part + before[end:]
    path.write_text(after)
    (out / 'resource-fixture.patch').write_text(''.join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True), fromfile='a/' + str(path.relative_to(root)),
        tofile='b/' + str(path.relative_to(root)))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', choices=['kernel', 'm1n1', 'templates', 'uboot', 'fixtures'])
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    globals()[args.component](args.root, args.output)
