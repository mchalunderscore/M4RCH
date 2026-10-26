// SPDX-License-Identifier: GPL-2.0
#include <linux/pm_runtime.h>

__rust_helper int rust_helper_pm_runtime_resume_and_get(struct device *dev)
{
	return pm_runtime_resume_and_get(dev);
}

__rust_helper int rust_helper_pm_runtime_put_sync_suspend(struct device *dev)
{
	return pm_runtime_put_sync_suspend(dev);
}

__rust_helper bool rust_helper_pm_runtime_enabled(struct device *dev)
{
	return pm_runtime_enabled(dev);
}
