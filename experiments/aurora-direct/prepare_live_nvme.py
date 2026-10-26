#!/usr/bin/env python3
"""Adapt the Gravity bridge's exit path to Aurora's live ANS contract.

Based on aurora-silicon/u-boot 7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c,
drivers/nvme/nvme_apple.c:apple_nvme_remove. Keep the existing T6040 probe
and separate NVMMU mapping; only the OS handoff changes. This older core
submits commands synchronously, so retire its idle queues with bounded
admin commands. Failure stops the boot instead of passing active queues on.
"""
from pathlib import Path
import argparse


def replace_once(path, old, new):
    text = path.read_text()
    if new in text:
        return
    if text.count(old) != 1:
        raise ValueError(f'Unrecognized handoff source: {path}')
    path.write_text(text.replace(old, new))


def prepare(tree):
    core = tree / 'drivers/nvme/nvme.c'
    replace_once(core, 'int nvme_shutdown(struct udevice *udev)\n', '''/* Aurora live ANS handoff: no SHN, disable, or RTKit power transition. */
int nvme_retire_io_queues(struct udevice *udev)
{
	struct nvme_dev *ndev = dev_get_priv(udev);
	int qid, ret;

	for (qid = ndev->queue_count - 1; qid > NVME_ADMIN_Q; qid--) {
		if (!ndev->queues[qid])
			continue;
		ret = nvme_delete_queue(ndev, nvme_admin_delete_sq, qid);
		if (ret)
			return ret;
		ret = nvme_delete_cq(ndev, qid);
		if (ret)
			return ret;
	}
	return 0;
}

int nvme_shutdown(struct udevice *udev)
''')
    driver = tree / 'drivers/nvme/nvme_apple.c'
    replace_once(driver, '#include <dm.h>', '#include <dm.h>\n#include <hang.h>')
    replace_once(driver, 'static int apple_nvme_remove(struct udevice *dev)\n',
                 'int nvme_retire_io_queues(struct udevice *udev);\n\nstatic int apple_nvme_remove(struct udevice *dev)\n')
    replace_once(driver, '\tu32 ctrl;\n\n\tnvme_shutdown(dev);', '''	u32 ctrl;

	if (priv->hw->needs_ioq_register) {
		/* Keep ANS, its SART mappings and RTKit buffers live. Linux
		 * adopts CC.EN/CSTS.RDY, then replaces the admin queue. The
		 * entire allocation arena is reserved by aurora_prepare_fdt.
		 * The bridge exposes its ESP read-only; no writes need flushing.
		 */
		if (nvme_retire_io_queues(dev)) {
			puts("Boot: ANS queue retirement failed; refusing Linux handoff\\n");
			hang();
		}
		nvme_writeq(0, priv->base + ANS_T8132_IOQ_CMDS);
		nvme_writeq(0, priv->base + ANS_T8132_IOQ_CQES);
		if (!(readl(&priv->ndev.bar->cc) & NVME_CC_ENABLE) ||
		    !(readl(&priv->ndev.bar->csts) & NVME_CSTS_RDY) ||
		    (readl(&priv->ndev.bar->csts) & NVME_CSTS_CFS) ||
		    !(readl(priv->asc + REG_CPU_CTRL) & REG_CPU_CTRL_RUN) ||
		    readl(priv->base + ANS_BOOT_STATUS) != ANS_BOOT_STATUS_OK) {
			puts("Boot: unhealthy live ANS; refusing Linux handoff\\n");
			hang();
		}
		puts("Boot: Aurora live ANS handoff; firmware and admin queue retained\\n");
		return 0;
	}

	nvme_shutdown(dev);''')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    prepare(parser.parse_args().tree)
