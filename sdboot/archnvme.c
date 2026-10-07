// SPDX-License-Identifier: GPL-2.0+
/* Fixed J614s UEFI firmware bridge. The SD's EFI application owns OS boot.
 * Start from a copy of m1n1's live DT: never discard its memory, CPU release
 * addresses, firmware reservations, framebuffer or calibration fixups.
 */
#include <command.h>
#include <efi_loader.h>
#include <env.h>
#include <fs.h>
#include <init.h>
#include <nvme.h>
#include <blk.h>
#include <part.h>
#include <asm/global_data.h>
#include <linux/libfdt.h>
#include <linux/sizes.h>

DECLARE_GLOBAL_DATA_PTR;

#define EFI_LIMIT SZ_64M
#define DT_LIMIT SZ_2M
#define EFI_PATH "/EFI/BOOT/BOOTAA64.EFI"
static char esp_device[32];
#define OVERLAY_PATH "/dtbs/board.dtbo"

/* fs_size/read close their filesystem. Select the same ESP for each call. */
static int read_esp(const char *path, void *buffer, size_t limit, size_t *size)
{
	loff_t length, actual;

	if (fs_set_blk_dev("nvme", esp_device, FS_TYPE_FAT) ||
	    fs_size(path, &length) || length <= 0 || length > limit ||
	    fs_set_blk_dev("nvme", esp_device, FS_TYPE_FAT) ||
	    fs_read(path, (ulong)buffer, 0, length, &actual) || actual != length)
		return -1;
	*size = length;
	return 0;
}

static int do_archnvme(struct cmd_tbl *cmdtp, int flag, int argc, char *const argv[])
{
	void *image = (void *)env_get_hex("loadaddr", 0);
	void *dt = (void *)env_get_hex("fdt_addr_r", 0);
	void *overlay = (void *)env_get_hex("scriptaddr", 0);
	void *recorded_image;
	size_t image_size, overlay_size, recorded_size;
	char command[96];

	puts("ARCHM4 UEFI bridge: framebuffer console ready\n");
	if (!image || !dt || !overlay ||
	    fdt_node_check_compatible(gd->fdt_blob, 0, "apple,j614s")) {
		puts("ARCHM4: missing boot buffers or unexpected board\n");
		return CMD_RET_FAILURE;
	}
	puts("M4RCH UEFI bridge: probing internal Apple NVMe (no SD fallback)\n");
	if (nvme_scan_namespace()) {
		puts("M4RCH: NVMe scan failed\n");
		return CMD_RET_FAILURE;
	}
	/* Choose an EFI partition by its unique GPT UUID, never by slot alone. */
	struct blk_desc *desc;
	struct disk_partition part;
	int found = 0;
	for (int disk = 0; disk < 8; disk++) {
		if (blk_get_desc(UCLASS_NVME, disk, &desc))
			continue;
		for (int slot = 1; slot <= 16; slot++) {
			if (part_get_info(desc, slot, &part) ||
			    strcasecmp(part.uuid, "5fdb35c6-3a66-416d-8358-6555fd99fcc5"))
				continue;
			if (strcasecmp(part.type_guid, "c12a7328-f81f-11d2-ba4b-00a0c93ec93b") ||
			    (u64)part.start * desc->blksz != 362525229056ULL ||
			    (u64)part.size * desc->blksz != 1073741824ULL || found++) {
				puts("M4RCH: ambiguous or unexpected internal ESP\n");
				return CMD_RET_FAILURE;
			}
			snprintf(esp_device, sizeof(esp_device), "%d:%d", disk, slot);
		}
	}
	if (found != 1) {
		puts("M4RCH: internal ESP not found\n");
		return CMD_RET_FAILURE;
	}
	if (read_esp(OVERLAY_PATH, overlay, DT_LIMIT, &overlay_size) ||
	    fdt_check_full(overlay, overlay_size) ||
	    fdt_totalsize(overlay) != overlay_size ||
	    fdt_open_into(gd->fdt_blob, dt, DT_LIMIT) ||
	    fdt_overlay_apply(dt, overlay) ||
	    fdt_node_check_compatible(dt, 0, "apple,j614s")) {
		puts("ARCHM4: missing or invalid /dtbs/board.dtbo\n");
		return CMD_RET_FAILURE;
	}
	/* The overlay modifies only this handoff copy, not the control DT used
	 * by active firmware drivers. GRUB must inherit it, not load a raw DTB. */
	if (read_esp(EFI_PATH, image, EFI_LIMIT, &image_size) ||
	    efi_check_pe(image, image_size, NULL) != EFI_SUCCESS) {
		puts("ARCHM4: missing or invalid /EFI/BOOT/BOOTAA64.EFI\n");
		return CMD_RET_FAILURE;
	}
	/* fs_read alone does not record an EFI device path. This must be set
	 * explicitly so GRUB can locate the ESP from its loaded-image handle.
	 * bootefi addr:size would clear that path and create a memory device. */
	efi_set_bootdev("nvme", esp_device, EFI_PATH, image, image_size);
	efi_get_image_parameters(&recorded_image, &recorded_size);
	if (recorded_image != image || recorded_size != image_size) {
		puts("ARCHM4: could not establish the NVMe EFI device path\n");
		return CMD_RET_FAILURE;
	}
	if (env_set("bootargs", NULL))
		return CMD_RET_FAILURE;
	printf("ARCHM4 UEFI bridge: starting %s (%zu bytes)\n", EFI_PATH, image_size);
	snprintf(command, sizeof(command), "bootefi %lx %lx", (ulong)image, (ulong)dt);
	return run_command(command, 0) ? CMD_RET_FAILURE : CMD_RET_SUCCESS;
}

U_BOOT_CMD(archnvme, 1, 0, do_archnvme, "boot the internal NVMe's ARM64 EFI application", "");
