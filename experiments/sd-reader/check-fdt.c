// SPDX-License-Identifier: GPL-2.0-only
/* Exercise the actual U-Boot handoff function on the installed board DTB. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libfdt.h>
typedef uint32_t u32;
#include "sd-fdt.h"

int main(int argc, char **argv)
{
	FILE *in, *out;
	void *source, *buffer;
	long size;
	int ret;
	if (argc != 3 || !(in = fopen(argv[1], "rb"))) return 2;
	if (fseek(in, 0, SEEK_END) || (size = ftell(in)) <= 0 ||
	    fseek(in, 0, SEEK_SET)) return 2;
	source = malloc(size);
	buffer = malloc(size + 65536);
	if (!source || !buffer || fread(source, 1, size, in) != (size_t)size) return 2;
	fclose(in);
	if (fdt_check_full(source, size) || fdt_open_into(source, buffer, size + 65536)) return 2;
	ret = j614s_sd_fdt(buffer);
	if (ret || fdt_pack(buffer) || !(out = fopen(argv[2], "wb"))) return 1;
	if (fwrite(buffer, 1, fdt_totalsize(buffer), out) != fdt_totalsize(buffer) || fclose(out)) return 2;
	free(buffer);
	free(source);
	return 0;
}
