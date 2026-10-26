// SPDX-License-Identifier: GPL-2.0-only
/* Read-only snapshot of an already bound Apple watchdog. No start/ping/stop. */
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/watchdog.h>
#include <linux/io.h>
#include <linux/string.h>

/* Exact private layout in this matching kernel's drivers/watchdog/apple_wdt.c. */
struct matched_apple_wdt {
 struct watchdog_device wdd;
 void __iomem *regs;
 unsigned long clk_rate;
};

static int __init capture_init(void)
{
 struct device *dev;
 struct matched_apple_wdt *wdt;
 int i, ret = -ENODEV;
 dev = bus_find_device_by_name(&platform_bus_type, NULL, "50836c000.watchdog");
 if (!dev)
  return ret;
 device_lock(dev);
 if (!dev->driver || strcmp(dev->driver->name, "apple-watchdog"))
  goto done;
 wdt = dev_get_drvdata(dev);
 if (!wdt || !wdt->regs || !wdt->clk_rate || !wdt->wdd.info ||
     strcmp(wdt->wdd.info->identity, "Apple SoC Watchdog"))
  goto done;
 pr_info("m4rch host watchdog: clock=%lu timeout=%u active=%u hw_running=%u max_heartbeat_ms=%u read_only=1\n",
         wdt->clk_rate, wdt->wdd.timeout, watchdog_active(&wdt->wdd),
         watchdog_hw_running(&wdt->wdd), wdt->wdd.max_hw_heartbeat_ms);
 for (i = 0; i < 3; i++) {
  u32 cur = readl(wdt->regs + 0x10 * i);
  u32 bite = readl(wdt->regs + 0x10 * i + 4);
  u32 ctrl = readl(wdt->regs + 0x10 * i + 12);
  pr_info("m4rch host watchdog: wd=%d current=%u bite=%u control=%#x reset_enabled=%u read_only=1\n",
          i, cur, bite, ctrl, !!(ctrl & BIT(2)));
 }
 ret = 0;
done:
 device_unlock(dev);
 put_device(dev);
 return ret;
}
static void __exit capture_exit(void) { }
module_init(capture_init);
module_exit(capture_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only bound Apple watchdog snapshot for unexpected host reset diagnosis");
