#!/usr/bin/env python3
"""Import PR445's pinned internal-panel stack over the prepared r4 kernel.

The unchanged GPU, DART ownership and board admission remain in the kernel.
Only drivers/gpu/drm/apple is replaced, from commit 579cfbd (commits 4-7).
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

KIT = Path(__file__).resolve().parent
PIN = '579cfbd0762a152be943746de22a2702b8dc0116'
PR_HEAD = '23aa40ed252ec45c3dd5612ce80406f356556d85'


def prepare(root, source, output):
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() == PIN
    relative = Path('drivers/gpu/drm/apple')
    upstream = source / relative
    target = root / relative
    assert 'J614s experimental A413' in (target / 'iomfb_m4.c').read_text()
    backup = output / 'previous-drm'
    assert not backup.exists(), 'Refuse to overwrite the prior source snapshot'
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(target, backup, ignore=shutil.ignore_patterns('*.o', '*.cmd', '*.ko', '*.mod*'))
    shutil.rmtree(target)
    shutil.copytree(upstream, target)
    before = {str(p.relative_to(target)): p.read_bytes() for p in target.rglob('*') if p.is_file()}

    def edit(name, old, new):
        path = target / name
        text = path.read_text()
        assert text.count(old) == 1, (name, old[:100])
        path.write_text(text.replace(old, new))

    # The J614s ADT has a fifth DISP0 range. Preserve it and its native index;
    # do not remove a window to pass the J616s-only register-count check.
    edit('dcp.c', '} t6041_dcp_regs[] = {', '} t6041_dcp_regs[] = {')
    edit('dcp.c', '\tint i;\n\n\tif (!of_device_is_compatible(dev->of_node, "apple,t6041-dcp"))',
         '\tbool j614s = of_machine_is_compatible("apple,j614s");\n'
         '\tunsigned int expected = ARRAY_SIZE(t6041_dcp_regs) + j614s;\n\tint i;\n\n'
         '\tif (!of_device_is_compatible(dev->of_node, "apple,t6041-dcp"))')
    edit('dcp.c', 'pdev->num_resources != ARRAY_SIZE(t6041_dcp_regs)', 'pdev->num_resources != expected')
    edit('dcp.c', '"T6041 DCP: %u register windows, the ADT has %zu\\n",\n\t\t\t\t     pdev->num_resources, ARRAY_SIZE(t6041_dcp_regs)',
         '"T6041 DCP: %u register windows, this board requires %u\\n",\n\t\t\t\t     pdev->num_resources, expected')
    anchor = '\tif (!of_property_present(dev->of_node, "iommus") ||'
    edit('dcp.c', anchor, '''\tif (j614s) {
\t\tstruct resource *r = platform_get_resource(pdev, IORESOURCE_MEM, 5);

\t\tif (!r || r->start != 0x504800000ULL || resource_size(r) != 0xbc000 ||
\t\t    of_property_match_string(dev->of_node, "reg-names", "disp-4") != 5)
\t\t\treturn dev_err_probe(dev, -ENODEV, "J614s DISP0 shared aperture differs from ADT\\n");
\t}

''' + anchor)
    # Keep the already-qualified boot power owner pinned on our machine.
    # PR445's IOMFB power chain is separate from SoC/PMP ownership.
    edit('dcp.c', '#include "iomfb_m4.h"', '#include "iomfb_m4.h"\n#include "j614s-power.h"')
    anchor = 'static int dcp_comp_bind_pipe(struct device *dev, struct device *main, void *data)'
    p = target / 'dcp.c'; text = p.read_text(); start = text.index(anchor)
    idx = text.index('\n\tint ret;', start) + len('\n\tint ret;')
    text = text[:idx] + '''

\tif (dcp->fw_compat == DCP_FIRMWARE_V_26_6_DESKTOP && j614s_display_board()) {
\t\tret = j614s_display_power_prepare(dev);
\t\tif (ret)
\t\t\treturn dev_err_probe(dev, ret, "J614s display power owner not ready\\n");
\t}
''' + text[idx:]; p.write_text(text)
    shutil.copyfile(KIT / 'kernel/j614s-power.h', target / 'j614s-power.h')

    # Explicit board binding; do not route T6041 through iomfb_m4_init().
    edit('apple_drv.c', '\t{ .compatible = "apple,t8132-dcp" },',
         '\t{ .compatible = "apple,t8132-dcp" },\n\t{ .compatible = "apple,t6041-dcp" },')
    edit('apple_drv.c', '\t{ .compatible = "apple,t8132-display-subsystem" },',
         '\t{ .compatible = "apple,t8132-display-subsystem" },\n\t{ .compatible = "apple,t6041-display-subsystem" },')
    with (target / 'Kconfig').open('a') as f:
        f.write('\nconfig DRM_APPLE_DCP_J614S\n\tbool "J614s T6041 desktop DCP candidate"\n\tdepends on DRM_APPLE && APPLE_J614S_DCP_BOOT\n')

    # J616s' boot pixel clock is not a J614s constant. Trial a firmware-listed
    # native 60-Hz mode first on J614s; retain the upstream preferred fallback.
    edit('iomfb.c', '\tu32 best = U32_MAX;\n\tstruct dcp_desktop_state *d;',
         '\tu32 best = U32_MAX;\n\tbool j614s = of_machine_is_compatible("apple,j614s");\n\tstruct dcp_desktop_state *d;')
    edit('iomfb.c', '''\t\tif (!m->vrr) {
\t\t\tu32 delta = abs((int)m->mode.clock -
\t\t\t\t\tDCP_DESKTOP_BOOT_PIXEL_CLOCK_KHZ);''', '''\t\tif (!m->vrr && (!j614s ||
\t\t    (m->mode.hdisplay == 3024 && m->mode.vdisplay == 1964))) {
\t\t\tu32 delta = j614s ? abs(drm_mode_vrefresh(&m->mode) - 60) :
\t\t\t\tabs((int)m->mode.clock - DCP_DESKTOP_BOOT_PIXEL_CLOCK_KHZ);''')
    edit('iomfb.c', 'best <= DCP_DESKTOP_BOOT_PIXEL_CLOCK_KHZ / 100',
         'best <= (j614s ? 1 : DCP_DESKTOP_BOOT_PIXEL_CLOCK_KHZ / 100)')

    # Review follow-up: validate the desktop callback envelope before reading
    # its header, then validate every typed wrapper before it touches payload.
    edit('iomfb.c', '''\tif (dcp->fw_compat == DCP_FIRMWARE_H17P &&
\t    (length < sizeof(*hdr)''', '''\tif ((dcp->fw_compat == DCP_FIRMWARE_H17P ||
\t     dcp->fw_compat == DCP_FIRMWARE_V_26_6_DESKTOP) &&
\t    (length < sizeof(*hdr)''')
    anchor = '\tin = data + sizeof(*hdr);\n\tout = in + hdr->in_len;'
    edit('iomfb.c', anchor, '''\tif (dcp->fw_compat == DCP_FIRMWARE_V_26_6_DESKTOP &&
\t    (tag < 0 || tag >= IOMFB_MAX_CB ||
\t     (u64)sizeof(*hdr) + hdr->in_len + hdr->out_len > length)) {
\t\tdev_err(dev, "invalid desktop IOMFB callback %d (%u, %u)\\n",
\t\t\ttag, hdr->in_len, hdr->out_len);
\t\tdcp->crashed = true;
\t\treturn;
\t}

''' + anchor)
    # Header lengths may include four-byte ABI padding; minimum bounds allow
    # that padding while preventing both truncated reads and oversized writes.
    helper = '''
static inline bool iomfb_callback_size(struct apple_dcp *dcp, const void *in,
\t\t\t\t       u32 need_in, u32 need_out)
{
\tconst struct dcp_packet_header *hdr = in - sizeof(*hdr);

\tif (dcp->fw_compat != DCP_FIRMWARE_V_26_6_DESKTOP)
\t\treturn true;
\tif (hdr->in_len >= need_in && hdr->out_len >= need_out)
\t\treturn true;
\tdev_err(dcp->dev, "short desktop IOMFB callback: %u/%u, need %u/%u\\n",
\t\thdr->in_len, hdr->out_len, need_in, need_out);
\tdcp->crashed = true;
\treturn false;
}

'''
    edit('iomfb_internal.h', '#define TRAMPOLINE_VOID(func, handler)', helper + '#define TRAMPOLINE_VOID(func, handler)')
    path = target / 'iomfb_internal.h'; text = path.read_text()
    for macro, needs in [('IN', 'sizeof(T_in), 0'), ('INOUT', 'sizeof(T_in), sizeof(T_out)'), ('OUT', '0, sizeof(T_out)')]:
        begin = text.index('#define TRAMPOLINE_' + macro + '(')
        end = text.find('\n#define ', begin + 1)
        if end < 0: end = text.index('/* Call a DCP function', begin)
        block = text[begin:end]
        anchor = '\t\ttrace_iomfb_callback(dcp, tag, #handler);'
        assert block.count(anchor) == 1
        block = block.replace(anchor, '\t\tif (!iomfb_callback_size(dcp, in, ' + needs + ')) \\\n\t\t\treturn false; \\\n' + anchor)
        text = text[:begin] + block + text[end:]
    path.write_text(text)
    edit('iomfb_v26_6_desktop.c', '\ttrace_iomfb_callback(dcp, tag, "dcpep_cb_passthrough_dict");',
         '\tif (!iomfb_callback_size(dcp, in, sizeof(*req), sizeof(*resp)))\n\t\treturn false;\n\n'
         '\ttrace_iomfb_callback(dcp, tag, "dcpep_cb_passthrough_dict");')
    edit('iomfb_template.c', '''static bool iomfbep_cb_match_backlight_service(struct apple_dcp *dcp, int tag, void *out, void *in)
{
''', '''static bool iomfbep_cb_match_backlight_service(struct apple_dcp *dcp, int tag, void *out, void *in)
{
\tif (!iomfb_callback_size(dcp, in, 0, sizeof(u8)))
\t\treturn false;
''')

    patches = []
    for name in sorted({*before, *(str(p.relative_to(target)) for p in target.rglob('*') if p.is_file())}):
        old = before.get(name, b'').decode()
        new = (target / name).read_text()
        if old != new:
            patches.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                fromfile='a/' + str(relative / name) if old else '/dev/null', tofile='b/' + str(relative / name)))
    (output / 'j614s-desktop.patch').write_text(''.join(patches))
    manifest = {'pr': 445, 'pr_head': PR_HEAD, 'panel_commit': PIN,
        'upstream_base': '653c489a8347b8004d2895b4da775f46e334776b',
        'excluded_commits': [1, 2, 3, 8, 9],
        'source_files': {str(p.relative_to(target)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(target.rglob('*')) if p.is_file()},
        'native_boot_tested': False}
    (output / 'desktop-source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Imported pinned PR445 panel stack with J614s adaptations and desktop callback bounds')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path); p.add_argument('source', type=Path); p.add_argument('output', type=Path)
    a = p.parse_args(); prepare(a.root, a.source, a.output)
