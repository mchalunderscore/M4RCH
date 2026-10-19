"""Internal-only J614s UEFI bridge, based on the pinned SD bridge core.

The baseline remains identical for m1n1. Only the U-Boot control DT's NVMe
aperture is widened; the handoff overlay still applies to a separate live copy.
"""
import json
import hashlib
import shutil
import struct
from boot import read_fdt
from prepare_uboot import prepare as prepare_sd, replace
from common import run

PMGR_WINDOWS = (0x502280000, 0x502800000)


def validate_power_map(dtb):
    """Check ANS's complete zero-cell power-domain chain before building."""
    nodes = read_fdt(dtb)
    refs = {struct.unpack(">I", props["phandle"])[0]: path
            for path, props in nodes.items() if "phandle" in props}
    roots = [path for path, props in nodes.items()
             if b"apple,t8132-nvme-ans2" in props.get("compatible", b"").split(b"\0")]
    if len(roots) != 1:
        raise ValueError("Expected one J614s ANS node")
    windows = set()

    def walk(path, active):
        if path in active or len(active) > 12:
            raise ValueError("ANS power-domain cycle/depth")
        props = nodes[path]
        if b"apple,t8103-pmgr-pwrstate" in props.get("compatible", b"").split(b"\0"):
            parent = nodes[path.rsplit("/", 1)[0]]
            reg = parent.get("reg", b"")
            if len(reg) != 16:
                raise ValueError("Unexpected PMGR reg layout")
            address, size = struct.unpack(">QQ", reg)
            if address not in PMGR_WINDOWS or not 0 < size <= 128 * 1024:
                raise ValueError(f"Unmapped ANS power-domain window: {address:#x}")
            windows.add(address)
        for (reference,) in struct.iter_unpack(">I", props.get("power-domains", b"")):
            target = refs[reference]
            if nodes[target].get("#power-domain-cells") != bytes(4):
                raise ValueError("Expected zero-cell ANS power domain")
            walk(target, active | {path})

    walk(roots[0], set())
    return windows


def prepare(tree, recipe):
    prepare_sd(tree, recipe)
    board = tree / 'arch/arm/mach-apple/board.c'
    text = board.read_text()
    start = text.index('static void sd_build_map(void)')
    end = text.index('\nstruct mm_region *mem_map;', start)
    text = text[:start] + r'''static void nvme_map_power(ofnode node, int depth)
{
    struct ofnode_phandle_args spec;
    ofnode parent;
    fdt_size_t size;
    fdt_addr_t addr;
    if (depth > 12)
        panic("NVMe power-domain cycle\n");
    if (ofnode_device_is_compatible(node, "apple,t8103-pmgr-pwrstate")) {
        parent = ofnode_get_parent(node);
        addr = ofnode_get_addr_size_index(parent, 0, &size);
        if ((addr != M4RCH_PMGR0 && addr != M4RCH_PMGR1) || size > SZ_128K)
            panic("Unexpected NVMe PMGR aperture\n");
        /* One mapping per parent. Repeated phandles share the same window. */
        bool exists = false;
        for (int i = 0; i < sd_slots; i++)
            if (sd_map[i].phys == addr)
                exists = true;
        if (!exists)
            sd_map_add(addr, size);
    }
    for (int i = 0; !ofnode_parse_phandle_with_args(node, "power-domains",
                  "#power-domain-cells", 0, i, &spec); i++)
        nvme_map_power(spec.node, depth + 1);
}
static void nvme_map_expected(ofnode node, u64 expected, u64 minimum)
{
    fdt_size_t size;
    fdt_addr_t addr = ofnode_get_addr_size_index(node, 0, &size);
    if (!ofnode_valid(node) || addr != expected || size < minimum || size > SZ_1M)
        panic("Unexpected J614s NVMe resource\n");
    sd_map_add(addr, size);
}
static void sd_build_map(void)
{
    ofnode node = ofnode_by_compatible(ofnode_null(), "apple,t8132-nvme-ans2");
    struct ofnode_phandle_args spec;
    fdt_size_t size;
    fdt_addr_t addr;
    u32 phandle;
    memset(sd_map, 0, sizeof(sd_map));
    sd_slots = 0;
    if (!of_machine_is_compatible("apple,j614s"))
        panic("Internal NVMe loader requires J614s\n");
    /* Retain all three reg tuples and the property's original length.
     * Shrinking a flat-DT property here invalidates offsets in nodes which
     * U-Boot may already have bound. Preserve the separate NVMMU tuple and
     * the matching reg-names, even though this driver uses the first window. */
    fdt32_t reg[] = { cpu_to_fdt32(4), cpu_to_fdt32(0x4dcc0000), 0,
                     cpu_to_fdt32(0x60000), cpu_to_fdt32(4),
                     cpu_to_fdt32(0x09600000), 0, cpu_to_fdt32(0x4000),
                     cpu_to_fdt32(4), cpu_to_fdt32(0x0dcc0000), 0,
                     cpu_to_fdt32(0x60000) };
    if (!ofnode_valid(node) || ofnode_write_prop(node, "reg", reg, sizeof(reg), true))
        panic("Cannot widen NVMe control DT\n");
    nvme_map_expected(node, 0x44dcc0000ULL, 0x60000);
    addr = ofnode_get_addr_size_index(node, 2, &size);
    if (addr != 0x40dcc0000ULL || size != 0x60000)
        panic("Unexpected NVMMU aperture\n");
    sd_map_add(addr, size);
    addr = ofnode_get_addr_size_index(node, 1, &size);
    if (addr != 0x409600000ULL || size != SZ_16K)
        panic("Unexpected NVMe ASC aperture\n");
    sd_map_add(addr, size);
    if (ofnode_parse_phandle_with_args(node, "mboxes", "#mbox-cells", 0, 0, &spec))
        panic("Missing NVMe mailbox\n");
    nvme_map_expected(spec.node, 0x409608000ULL, SZ_16K);
    if (ofnode_read_u32(node, "apple,sart", &phandle))
        panic("Missing NVMe SART\n");
    nvme_map_expected(ofnode_get_by_phandle(phandle), 0x40dc50000ULL, 0xc000);
    nvme_map_power(node, 0);
    node = ofnode_by_compatible(ofnode_null(), "apple,wdt");
    nvme_map_expected(node, 0x50836c000ULL, SZ_16K);
    sd_map[sd_slots++].attrs = PTE_BLOCK_MEMTYPE(MT_NORMAL) | PTE_BLOCK_INNER_SHARE;
    sd_map[sd_slots++].attrs = PTE_BLOCK_MEMTYPE(MT_NORMAL_NC) |
        PTE_BLOCK_INNER_SHARE | PTE_BLOCK_PXN | PTE_BLOCK_UXN;
}
''' + text[end:]
    for index, address in enumerate(PMGR_WINDOWS):
        text = text.replace("M4RCH_PMGR" + str(index), hex(address) + "ULL")
    text = text.replace('#if CONFIG_IS_ENABLED(NVME)\n\tenv_set("storage_interface", blk_get_uclass_name(UCLASS_NVME));\n\tenv_set("fw_dev_part", asahi_esp_devpart());\n#endif', '/* Probe ANS only from archnvme, after boot buffers and console exist. */')
    board.write_text(text)
    # The SD handoff checker references the disabled PCI driver. The NVMe
    # driver's OS_PREPARE callback instead performs its own controller shutdown.
    path = tree / 'lib/efi_loader/efi_boottime.c'
    text = path.read_text()
    start = text.index('        if (IS_ENABLED(CONFIG_APPLE_NOIO)) {\n            extern void apple_sd_pci_handoff_check')
    end = text.index('\n        }', start) + len('\n        }')
    path.write_text(text[:start] + text[end:])
    # This older pinned base predates the explicit sizes.h include used by
    # the upstream alignment patch; add its prerequisite without editing it.
    replace(tree / "drivers/nvme/nvme_apple.c", "#include <linux/iopoll.h>", "#include <linux/iopoll.h>\n#include <linux/sizes.h>")
    for source in json.loads((recipe / 'uboot-nvme-sources.json').read_text()):
        patch = recipe.parent / 'patches' / source['file']
        if hashlib.sha256(patch.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('Upstream NVMe patch checksum mismatch')
        run(['git', '-C', tree, 'apply', '--check', patch])
        run(['git', '-C', tree, 'apply', patch])
    driver = tree / 'drivers/nvme/nvme_apple.c'
    replace(driver, 'struct apple_nvme_priv {', '#define ANS_IOQ_CMDS 0x1200\n#define ANS_IOQ_CQES 0x1208\n#define ANS_IOQ_SIZE 0x1210\n\nstruct apple_nvme_priv {')
    # NVMe core casts dev_get_priv() directly to struct nvme_dev. Keep ndev
    # first; inserting a flag before it silently shifts the controller BAR.
    replace(driver, '\tstruct nvme_dev ndev;', '\tstruct nvme_dev ndev;\n\tbool ioq_register;')
    replace(driver, '\tvoid *base;\t\t/* NVMe registers */',
            '\tvoid *base;\t\t/* NVMe registers */\n\tvoid *nvmmu;\t\t/* Separate M4 NVMMU registers */')
    replace(driver, 'static const struct nvme_ops apple_nvme_ops = {',
            'static_assert(offsetof(struct apple_nvme_priv, ndev) == 0);\n\nstatic const struct nvme_ops apple_nvme_ops = {')
    replace(driver, '\tpriv->base = dev_read_addr_ptr(dev);', '\tpriv->ioq_register = device_is_compatible(dev, "apple,t8132-nvme-ans2");\n\tputs("M4RCH: Apple NVMe probe, ANS v2 IOQ registration\\n");\n\tpriv->base = dev_read_addr_ptr(dev);')
    replace(driver, '\taddr = dev_read_addr_index(dev, 1);',
            '\tpriv->nvmmu = priv->base;\n\tif (priv->ioq_register) {\n\t\taddr = dev_read_addr_index(dev, 2);\n\t\tif (addr != 0x40dcc0000ULL)\n\t\t\treturn -EINVAL;\n\t\tpriv->nvmmu = (void *)(ulong)addr;\n\t}\n\taddr = dev_read_addr_index(dev, 1);')
    text_driver = driver.read_text()
    # M4 moves NVMMU away from the NVMe BAR. Match m1n1's working split;
    # submission doorbells and controller registers remain in the NVMe BAR.
    for old in ('((void __iomem *)dev->bar) + ANS_NVMMU',
                '((void __iomem *)nvmeq->dev->bar) + ANS_NVMMU',
                'priv->base + ANS_NVMMU'):
        if old not in text_driver:
            raise ValueError("Pinned NVMMU register accesses changed")
        text_driver = text_driver.replace(old, 'priv->nvmmu + ANS_NVMMU')
    driver.write_text(text_driver)
    replace(driver, '\twritel(((ANS_MAX_QUEUE_DEPTH << 16) | ANS_MAX_QUEUE_DEPTH),\n\t       priv->base + ANS_MAX_PEND_CMDS_CTRL);', '\tif (!priv->ioq_register)\n\t\twritel(((ANS_MAX_QUEUE_DEPTH << 16) | ANS_MAX_QUEUE_DEPTH),\n\t\t       priv->base + ANS_MAX_PEND_CMDS_CTRL);')
    replace(driver, 'static const struct nvme_ops apple_nvme_ops = {', r'''static void apple_nvme_queue_created(struct nvme_queue *q)
{
    struct apple_nvme_priv *priv = container_of(q->dev, struct apple_nvme_priv, ndev);
    if (!priv->ioq_register || q->qid != NVME_IO_Q)
        return;
    /* After successful Create CQ and Create SQ, as in the working Linux
     * T8132 driver. 0x1210 is the queue-size register on this generation. */
    nvme_writeq((ulong)q->sq_cmds, priv->base + ANS_IOQ_CMDS);
    nvme_writeq((ulong)q->cqes, priv->base + ANS_IOQ_CQES);
    writel((q->q_depth - 1) | ((q->q_depth - 1) << 16), priv->base + ANS_IOQ_SIZE);
    puts("M4RCH: ANS v2 I/O queue registered\n");
}
static const struct nvme_ops apple_nvme_ops = {
    .queue_created = apple_nvme_queue_created,''')
    replace(driver, '\t{ .compatible = "apple,nvme-ans2" },', '\t{ .compatible = "apple,nvme-ans2" },\n\t{ .compatible = "apple,t8132-nvme-ans2" },')
    # Working Linux does not cold-reset ANS after firmware has gone to sleep.
    replace(driver, '\treset_assert_bulk(&priv->resets);\n\treset_deassert_bulk(&priv->resets);', '\tif (!priv->ioq_register) {\n\t\treset_assert_bulk(&priv->resets);\n\t\treset_deassert_bulk(&priv->resets);\n\t}')
    replace(tree / 'drivers/nvme/nvme.h', 'struct nvme_ops {', 'struct nvme_ops {\n\t/* Called after successful Create CQ/SQ, before issuing I/O. */\n\tvoid (*queue_created)(struct nvme_queue *nvmeq);')
    replace(tree / 'drivers/nvme/nvme.c', '\tnvme_init_queue(nvmeq, qid);\n\n\treturn result;', '\tnvme_init_queue(nvmeq, qid);\n\tconst struct nvme_ops *ops = dev->udev->driver->ops;\n\tif (ops && ops->queue_created)\n\t\tops->queue_created(nvmeq);\n\n\treturn result;')
    # Prevent the boot firmware from writing ANY namespace. Linux has a separate
    # writable driver; UEFI/GRUB only need reads from the internal ESP.
    replace(tree / 'drivers/nvme/nvme.c', '\treturn nvme_blk_rw(udev, blknr, blkcnt, (void *)buffer, false);', '\t/* Firmware reads only; never write the internal SSD. */\n\treturn 0;')
    replace(tree / 'drivers/power/domain/apple-pmgr.c', '\t{ .compatible = "apple,pmgr-pwrstate" },', '\t{ .compatible = "apple,pmgr-pwrstate" },\n\t{ .compatible = "apple,t8103-pmgr-pwrstate" },')
    shutil.copyfile(recipe / 'uboot-nvme.config', tree / 'configs/apple_sdboot_defconfig')
    shutil.copyfile(recipe / 'archnvme.c', tree / 'arch/arm/mach-apple/archsd.c')
