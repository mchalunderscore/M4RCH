// SPDX-License-Identifier: GPL-2.0-only
/* Temporary read-only J614s SMC key metadata inventory. */
#include <linux/cpufreq.h>
#include <linux/debugfs.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/fs.h>
#include <linux/mfd/macsmc.h>
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/seq_file.h>

static struct device *smc_dev;
static struct apple_smc *smc;
static struct dentry *directory;

static void *inventory_start(struct seq_file *m, loff_t *pos)
{
	return *pos < smc->key_count ? (void *)(unsigned long)(*pos + 1) : NULL;
}

static void *inventory_next(struct seq_file *m, void *v, loff_t *pos)
{
	++*pos;
	return inventory_start(m, pos);
}

static void inventory_stop(struct seq_file *m, void *v) { }

static int inventory_show(struct seq_file *m, void *v)
{
	unsigned long index = (unsigned long)v - 1;
	struct apple_smc_key_info info;
	smc_key key;
	int ret;

	ret = apple_smc_get_key_by_index(smc, index, &key);
	if (ret < 0) {
		seq_printf(m, "%lu index-error %d\n", index, ret);
		return 0;
	}
	ret = apple_smc_get_key_info(smc, key, &info);
	if (ret < 0) {
		seq_printf(m, "%lu %08x info-error %d\n", index, key, ret);
		return 0;
	}
	seq_printf(m, "%lu %08x %08x %u %02x\n", index, key,
		   info.type_code, info.size, info.flags);
	return 0;
}

static const struct seq_operations inventory_seq_ops = {
	.start = inventory_start,
	.next = inventory_next,
	.stop = inventory_stop,
	.show = inventory_show,
};

static int inventory_open(struct inode *inode, struct file *file)
{
	return seq_open(file, &inventory_seq_ops);
}

static const struct file_operations inventory_fops = {
	.owner = THIS_MODULE,
	.open = inventory_open,
	.read = seq_read,
	.llseek = seq_lseek,
	.release = seq_release,
};

/* Read only a fixed set of reporting floats absent from the board table. */
static const char * const sample_keys[] = {
	"PHPB", "PHPM", "PHPS", "TDTC", "TSCP", "TSG2", "TVMD", "TVMx",
	"TVS3", "TVXs", "TVmD", "TVmS", "TVms", "Ta00", "Ta01", "Ta04",
	"Ta05", "Ta08", "Ta09", "Ta0K", "Ta0L", "Ta0O", "Ta0P", "Ta0R",
	"Ta0S", "Tz11", "Tz12", "Tz13", "Tz14", "Tz15", "Tz16", "Tz17",
	"Tz18", "Tz1j",
};

static int samples_show(struct seq_file *m, void *unused)
{
	unsigned int i;
	for (i = 0; i < ARRAY_SIZE(sample_keys); ++i) {
		struct apple_smc_key_info info;
		smc_key key = _SMC_KEY(sample_keys[i]);
		u32 value;
		int ret = apple_smc_get_key_info(smc, key, &info);
		if (ret < 0 || !(info.flags & APPLE_SMC_READABLE) ||
		    (info.flags & APPLE_SMC_FUNCTION) ||
		    info.type_code != __SMC_KEY('f', 'l', 't', ' ') || info.size != sizeof(value)) {
			seq_printf(m, "%s unavailable %d\n", sample_keys[i], ret);
			continue;
		}
		ret = apple_smc_read_u32(smc, key, &value);
		if (ret < 0)
			seq_printf(m, "%s error %d\n", sample_keys[i], ret);
		else
			seq_printf(m, "%s %08x\n", sample_keys[i], value);
	}
	return 0;
}

static int samples_open(struct inode *inode, struct file *file)
{
	return single_open(file, samples_show, NULL);
}

static const struct file_operations samples_fops = {
	.owner = THIS_MODULE,
	.open = samples_open,
	.read = seq_read,
	.llseek = seq_lseek,
	.release = single_release,
};

/* Read the two fan modes using the same read operation as macsmc_hwmon. */
static int fan_modes_show(struct seq_file *m, void *unused)
{
	static const char * const keys[] = { "F0Md", "F1Md" };
	unsigned int i;
	for (i = 0; i < ARRAY_SIZE(keys); i++) {
		struct apple_smc_key_info info;
		smc_key key = _SMC_KEY(keys[i]);
		u8 mode;
		int ret = apple_smc_get_key_info(smc, key, &info);
		if (ret < 0 || !(info.flags & APPLE_SMC_READABLE) ||
		    info.type_code != __SMC_KEY('u', 'i', '8', ' ') || info.size != 1)
			return -ENODEV;
		ret = apple_smc_read_u8(smc, key, &mode);
		if (ret < 0) return ret;
		seq_printf(m, "%s %u\n", keys[i], mode);
	}
	return 0;
}

static int fan_modes_open(struct inode *inode, struct file *file)
{
	return single_open(file, fan_modes_show, NULL);
}

static const struct file_operations fan_modes_fops = {
	.owner = THIS_MODULE,
	.open = fan_modes_open,
	.read = seq_read,
	.llseek = seq_lseek,
	.release = single_release,
};

/* The cpufreq sysfs values are effective limits, not the user QoS requests.
 * Report those original requests before any reversible frequency experiment. */
static int qos_show(struct seq_file *m, void *unused)
{
	static const unsigned int cpus[] = { 0, 1, 8 };
	unsigned int i;
	for (i = 0; i < ARRAY_SIZE(cpus); i++) {
		struct cpufreq_policy *p = cpufreq_cpu_get(cpus[i]);
		if (!p) return -ENODEV;
		seq_printf(m, "%u %d %d %u %u\n", cpus[i],
			   READ_ONCE(p->min_freq_req.pnode.prio),
			   READ_ONCE(p->max_freq_req.pnode.prio),
			   READ_ONCE(p->min), READ_ONCE(p->max));
		cpufreq_cpu_put(p);
	}
	return 0;
}

static int qos_open(struct inode *inode, struct file *file)
{
	return single_open(file, qos_show, NULL);
}

static const struct file_operations qos_fops = {
	.owner = THIS_MODULE,
	.open = qos_open,
	.read = seq_read,
	.llseek = seq_lseek,
	.release = single_release,
};

static int __init inventory_init(void)
{
	int err;

	if (!of_machine_is_compatible("apple,j614s"))
		return -ENODEV;
	smc_dev = bus_find_device_by_name(&platform_bus_type, NULL, "50c600000.smc");
	if (!smc_dev)
		return -ENODEV;
	smc = dev_get_drvdata(smc_dev);
	if (!smc || !smc->key_count) {
		put_device(smc_dev);
		return -ENODEV;
	}
	directory = debugfs_create_dir("m4rch_smc_inventory", NULL);
	if (IS_ERR(directory)) {
		err = PTR_ERR(directory);
		put_device(smc_dev);
		return err;
	}
	debugfs_create_file("keys", 0400, directory, NULL, &inventory_fops);
	debugfs_create_file("samples", 0400, directory, NULL, &samples_fops);
	debugfs_create_file("qos", 0400, directory, NULL, &qos_fops);
	debugfs_create_file("fan_modes", 0400, directory, NULL, &fan_modes_fops);
	pr_info("m4rch_smc_inventory: read-only metadata for %u keys\n", smc->key_count);
	return 0;
}

static void __exit inventory_exit(void)
{
	debugfs_remove_recursive(directory);
	put_device(smc_dev);
}

module_init(inventory_init);
module_exit(inventory_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only SMC key metadata inventory for J614s investigation");
