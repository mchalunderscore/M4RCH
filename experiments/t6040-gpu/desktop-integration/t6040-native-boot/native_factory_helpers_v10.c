// SPDX-License-Identifier: GPL-2.0
#include <linux/io.h>
#include <linux/of.h>

/* Read-only factory input used by AGX G16X populateChipLeakageData. */
__rust_helper int rust_helper_native_gpu_factory_leakage_snapshot(u32 *words)
{
	static const unsigned int offsets[] = { 0xc10, 0xc1c, 0xc20, 0xc24, 0xc28 };
	void __iomem *fuses;
	unsigned int index;
	if (!words || !of_machine_is_compatible("apple,t6040"))
		return -ENODEV;
	fuses = ioremap(0x508374000ULL, 0x1000);
	if (!fuses)
		return -ENOMEM;
	for (index = 0; index < ARRAY_SIZE(offsets); index++)
		words[index] = readl(fuses + offsets[index]);
	iounmap(fuses);
	return 0;
}
