#!/usr/bin/env python3
"""Connect the native desktop driver to its already-qualified retained DART APIs."""
import argparse
import difflib
from pathlib import Path


def prepare(root, out):
    out.mkdir(parents=True, exist_ok=True)
    base = root / 'drivers/gpu/drm/apple'
    names = ['dcp.c', 'dcp.h', 'dcp-internal.h', 'afk.c', 'iomfb.c', 'iomfb_template.c']
    before = {n: (base / n).read_text() for n in names}
    text = dict(before)

    def edit(name, old, new, count=1):
        assert text[name].count(old) == count, (name, old[:90], text[name].count(old))
        text[name] = text[name].replace(old, new)

    edit('dcp.c', '#include <linux/soc/apple/rtkit.h>',
         '#include <linux/soc/apple/rtkit.h>\n#include <linux/soc/apple/dart.h>')
    anchor = 'static void dcp_j614s_adopt_hw(struct apple_dcp *dcp)'
    helpers = '''bool dcp_uses_retained_dma(const struct apple_dcp *dcp)
{
\treturn dcp_j614s_desktop_live(dcp);
}

void *dcp_alloc_dma(struct apple_dcp *dcp, size_t size, dma_addr_t *dva)
{
\tvoid *buffer;

\tif (!dcp_uses_retained_dma(dcp))
\t\treturn dma_alloc_coherent(dcp->dev, size, dva, GFP_KERNEL);
\t/* No ordinary DMA fallback: SID23 deliberately reserves its whole aperture. */
\tif (!dcp->retain_dma)
\t\treturn NULL;
\tbuffer = apple_dart_dcp_alloc(dcp->dev, size, dva);
\tif (IS_ERR(buffer)) {
\t\tdev_err(dcp->dev, "retained DCP allocation of %#zx bytes failed: %ld\\n",
\t\t\tsize, PTR_ERR(buffer));
\t\treturn NULL;
\t}
\tdev_info(dcp->dev, "retained DCP buffer %#zx bytes at %pad\\n", size, dva);
\treturn buffer;
}

void dcp_free_dma(struct apple_dcp *dcp, size_t size, void *buffer, dma_addr_t dva)
{
\t/* The retained provider owns native pages and translations until reboot. */
\tif (!dcp_uses_retained_dma(dcp))
\t\tdma_free_coherent(dcp->dev, size, buffer, dva);
}

'''
    edit('dcp.c', anchor, helpers + anchor)
    edit('dcp.c', '\tif (bfr->iova && dcp->fw_compat == DCP_FIRMWARE_V_26_6_DESKTOP)',
         '\tif (dcp_uses_retained_dma(dcp))\n'
         '\t\tdev_info(dcp->dev, "native RTKit buffer request: IOVA %pad, %#zx bytes\\n",\n'
         '\t\t\t &bfr->iova, bfr->size);\n\n'
         '\tif (bfr->iova && dcp->fw_compat == DCP_FIRMWARE_V_26_6_DESKTOP)')
    edit('dcp.c', '''\t\tbfr->buffer = dma_alloc_coherent(dcp->dev, bfr->size,
\t\t\t\t\t\t &bfr->iova, GFP_KERNEL);''',
         '\t\tbfr->buffer = dcp_alloc_dma(dcp, bfr->size, &bfr->iova);')
    edit('dcp.c', '\t\tdma_free_coherent(dcp->dev, bfr->size, bfr->buffer, bfr->iova);',
         '\t\tdcp_free_dma(dcp, bfr->size, bfr->buffer, bfr->iova);')
    # Firmware-placed native payloads must be writable data, never firmware TEXT.
    anchor = '\tphy_addr = iommu_iova_to_phys(domain, bfr->iova);'
    start = text['dcp.c'].index('static int dcp_desktop_shmem_setup')
    pos = text['dcp.c'].index(anchor, start)
    text['dcp.c'] = text['dcp.c'][:pos] + '''\tif (dcp_uses_retained_dma(dcp)) {
\t\tret = apple_dart_dcp_check_buffer(dcp->dev, bfr->iova, bfr->size);
\t\tif (ret)
\t\t\treturn ret;
\t}
''' + text['dcp.c'][pos:]
    anchor = '#include "dcp-internal.h"'
    edit('dcp.h', anchor, anchor + '''

bool dcp_uses_retained_dma(const struct apple_dcp *dcp);
void *dcp_alloc_dma(struct apple_dcp *dcp, size_t size, dma_addr_t *dva);
void dcp_free_dma(struct apple_dcp *dcp, size_t size, void *buffer, dma_addr_t dva);
''')
    edit('dcp-internal.h', '\tbool piodma_mapped;',
         '\tbool piodma_mapped;\n\t/* Retained SID23/SID16 object, without a CPU alias or sg-table. */\n\tbool retained_shared;\n\tu64 retained_phys;')
    edit('afk.c', 'dma_alloc_coherent(ep->dcp->dev, size, &ep->bfr_dma, GFP_KERNEL)',
         'dcp_alloc_dma(ep->dcp, size, &ep->bfr_dma)')
    edit('afk.c', 'dma_alloc_coherent(ep->dcp->dev, output_len, &rxbuf_dma,\n\t\t\t\t   GFP_KERNEL)',
         'dcp_alloc_dma(ep->dcp, output_len, &rxbuf_dma)')
    edit('afk.c', 'dma_alloc_coherent(ep->dcp->dev, payload_len, &txbuf_dma,\n\t\t\t\t   GFP_KERNEL)',
         'dcp_alloc_dma(ep->dcp, payload_len, &txbuf_dma)')
    edit('afk.c', 'dma_free_coherent(ep->dcp->dev,', 'dcp_free_dma(ep->dcp,', count=4)
    edit('iomfb.c', 'dma_alloc_coherent(dcp->dev, DCP_SHMEM_SIZE, &shmem_iova,\n\t\t\t\t\tGFP_KERNEL)',
         'dcp_alloc_dma(dcp, DCP_SHMEM_SIZE, &shmem_iova)')
    edit('iomfb_template.c', '#include "dcp.h"', '#include "dcp.h"\n#include <linux/soc/apple/dart.h>')
    # Native descriptors use the provider's paired allocator, not generic SID16 maps.
    anchor = '\tallocated.buf = dma_alloc_coherent(dcp->dev, size, &allocated.dva,'
    edit('iomfb_template.c', anchor, '''\tif (dcp_uses_retained_dma(dcp)) {
\t\tif (!dcp->retain_dma || !dcp->piodma)
\t\t\treturn resp;
\t\tret = apple_dart_dcp_shared_alloc(dcp->dev, &dcp->piodma->dev,
\t\t\t\t\t\tsize, &allocated.retained_phys, &allocated.dva);
\t\tif (ret) {
\t\t\tdev_err(dcp->dev, "retained display allocation %#zx failed: %d\\n", size, ret);
\t\t\treturn resp;
\t\t}
\t\tallocated.retained_shared = true;
\t\tgoto publish_descriptor;
\t}

''' + anchor)
    edit('iomfb_template.c', '\t/* Callbacks are serialized; publish only a fully initialized descriptor. */',
         'publish_descriptor:\n\t/* Callbacks are serialized; publish only a fully initialized descriptor. */')
    anchor = '\tif (!test_bit(req->buffer, dcp->memdesc_map) || !map->sgl ||'
    edit('iomfb_template.c', anchor, '''\tif (dcp_uses_retained_dma(dcp) && memdesc->retained_shared) {
\t\tif (!test_bit(req->buffer, dcp->memdesc_map) || !dcp->piodma)
\t\t\tgoto reject;
\t\tif (!memdesc->piodma_mapped) {
\t\t\tret = apple_dart_dcp_shared_map(dcp->dev, &dcp->piodma->dev,
\t\t\t\tmemdesc->retained_phys, memdesc->dva, size);
\t\t\tif (ret)
\t\t\t\tgoto reject;
\t\t\tmemdesc->piodma_mapped = true;
\t\t}
\t\tgoto mapped_descriptor;
\t}

''' + anchor)
    anchor = '#if DCP_FW_H17(DCP_FW_VER)\n\tmemdesc->piodma_mapped = true;'
    edit('iomfb_template.c', anchor, 'mapped_descriptor:\n' + anchor)
    anchor = '\tif (!test_bit(request->buffer, dcp->memdesc_map) || !memdesc->buf ||'
    edit('iomfb_template.c', anchor, '''\tif (dcp_uses_retained_dma(dcp) && memdesc->retained_shared) {
\t\t/* Acknowledge logical retirement; the provider retains the actual mapping. */
\t\treturn test_bit(request->buffer, dcp->memdesc_map) &&
\t\t       memdesc->piodma_mapped && memdesc->dva == request->dva;
\t}

''' + anchor)
    anchor = '\tsize = ALIGN(memdesc->size, SZ_16K);\n\n\t/*\n\t * Tear down'
    edit('iomfb_template.c', anchor, '''\tif (dcp_uses_retained_dma(dcp) && memdesc->retained_shared) {
\t\t/* Never unmap or free a paired retained object through generic DMA APIs. */
\t\tclear_bit(id, dcp->memdesc_map);
\t\tmemset(memdesc, 0, sizeof(*memdesc));
\t\treturn 0;
\t}
\tsize = ALIGN(memdesc->size, SZ_16K);

\t/*
\t * Tear down''')
    patches = []
    for name in names:
        (out / (name + '.before')).write_text(before[name])
        (out / name).write_text(text[name])
        (base / name).write_text(text[name])
        patches.extend(difflib.unified_diff(before[name].splitlines(True), text[name].splitlines(True),
            fromfile='a/drivers/gpu/drm/apple/' + name, tofile='b/drivers/gpu/drm/apple/' + name))
    (out / 'kernel-buffers.patch').write_text(''.join(patches))
    print('Prepared native retained RTKit, AFK, IOMFB and paired firmware descriptor allocations')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path); p.add_argument('out', type=Path)
    a = p.parse_args(); prepare(a.root, a.out)
