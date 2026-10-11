// SPDX-License-Identifier: GPL-2.0
/* Retained PMP/PMC ownership for the native GPU firmware session. */
#include <linux/err.h>
#include <linux/io.h>
#include <linux/ioport.h>
#include <linux/of_address.h>
#include <linux/slab.h>
#include <linux/timekeeping.h>
#include <linux/delay.h>
#include <linux/soc/apple/pmgr-gfx-reset.h>
#include "native_gpu_coordinate_core.h"

#define NATIVE_GPU_PMP_BASE 0x5003c0000ULL
#define NATIVE_GPU_PMP_SIZE 0x30000ULL
#define NATIVE_GPU_PMC_BASE 0x504000000ULL
#define NATIVE_GPU_PMC_SIZE 0x1000000ULL

struct native_gpu_coordinate_owner {
	void __iomem *pmp;
	void __iomem *pmc;
	bool pmp_claimed, pmc_claimed, exposed;
	struct gfx_coord_session session;
	struct gfx_coord_observation last;
};

static int native_gpu_coordinate_aliases(void)
{
	struct device_node *node;
	struct resource resource;
	unsigned int index;
	for (node = of_find_all_nodes(NULL); node; node = of_find_all_nodes(node)) {
		if (!of_device_is_available(node))
			continue;
		for (index = 0; !of_address_to_resource(node, index, &resource); index++) {
			if (!(resource.flags & IORESOURCE_MEM))
				continue;
			if ((resource.start < NATIVE_GPU_PMP_BASE + NATIVE_GPU_PMP_SIZE &&
			     resource.end >= NATIVE_GPU_PMP_BASE) ||
			    (resource.start < NATIVE_GPU_PMC_BASE + NATIVE_GPU_PMC_SIZE &&
			     resource.end >= NATIVE_GPU_PMC_BASE)) {
				of_node_put(node);
				return -EBUSY;
			}
		}
	}
	return 0;
}

__rust_helper void rust_helper_native_gpu_coordinate_release_unexposed(
		void *data)
{
	struct native_gpu_coordinate_owner *owner = data;
	if (!owner || owner->exposed)
		return;
	if (owner->pmc)
		iounmap(owner->pmc);
	if (owner->pmp)
		iounmap(owner->pmp);
	if (owner->pmc_claimed)
		release_mem_region(NATIVE_GPU_PMC_BASE, NATIVE_GPU_PMC_SIZE);
	if (owner->pmp_claimed)
		release_mem_region(NATIVE_GPU_PMP_BASE, NATIVE_GPU_PMP_SIZE);
	kfree(owner);
}

__rust_helper void *rust_helper_native_gpu_coordinate_acquire(void)
{
	struct native_gpu_coordinate_owner *owner;
	int ret;
	if (!of_machine_is_compatible("apple,t6040") ||
	    !of_machine_is_compatible("apple,j614s"))
		return ERR_PTR(-ENODEV);
	ret = native_gpu_coordinate_aliases();
	if (ret)
		return ERR_PTR(ret);
	owner = kzalloc(sizeof(*owner), GFP_KERNEL);
	if (!owner)
		return ERR_PTR(-ENOMEM);
	if (!request_mem_region(NATIVE_GPU_PMP_BASE, NATIVE_GPU_PMP_SIZE, "native-gpu-pmp"))
		goto busy;
	owner->pmp_claimed = true;
	if (!request_mem_region(NATIVE_GPU_PMC_BASE, NATIVE_GPU_PMC_SIZE, "native-gpu-pmc"))
		goto busy;
	owner->pmc_claimed = true;
	owner->pmp = ioremap(NATIVE_GPU_PMP_BASE, NATIVE_GPU_PMP_SIZE);
	owner->pmc = ioremap(NATIVE_GPU_PMC_BASE, NATIVE_GPU_PMC_SIZE);
	if (!owner->pmp || !owner->pmc) {
		rust_helper_native_gpu_coordinate_release_unexposed(owner);
		return ERR_PTR(-ENOMEM);
	}
	return owner;
busy:
	rust_helper_native_gpu_coordinate_release_unexposed(owner);
	return ERR_PTR(-EBUSY);
}

static int native_gpu_read_ptd(void *context, unsigned int entry, u64 *value, u64 *status)
{
	struct native_gpu_coordinate_owner *owner = context;
	if (entry != 1 && entry != 0x1e0 && entry != 0x1e8)
		return -EINVAL;
	*value = readq(owner->pmp + entry * 16);
	*status = readq(owner->pmp + entry * 16 + 8);
	return 0;
}

static int native_gpu_write_ptd(void *context, unsigned int entry, u64 value)
{
	struct native_gpu_coordinate_owner *owner = context;
	if (entry != 0x1e0)
		return -EINVAL;
	writeq(value, owner->pmp + 0x10000 + entry * 8);
	return 0;
}

static int native_gpu_read_vote(void *context, unsigned int rail, u32 *value)
{
	struct native_gpu_coordinate_owner *owner = context;
	if (rail >= 3)
		return -EINVAL;
	*value = readl(owner->pmc + 0x8ac000 + rail * 4);
	return 0;
}

static int native_gpu_write_vote(void *context, unsigned int rail, u32 value)
{
	struct native_gpu_coordinate_owner *owner = context;
	if (rail >= 3)
		return -EINVAL;
	writel(value, owner->pmc + 0x8ac000 + rail * 4);
	return 0;
}

static u64 native_gpu_coordinate_now(void *context) { return ktime_get_ns(); }
static void native_gpu_coordinate_delay(void *context) { usleep_range(1000, 1100); }
static void native_gpu_coordinate_event(void *context, const char *phase,
		unsigned int entry, u64 value, u64 status, int result)
{
	if (result)
		pr_err("native-gpu coordinate %s entry=%x value=%llx status=%llx error=%d\n",
		       phase, entry, value, status, result);
}

__rust_helper int rust_helper_native_gpu_coordinate_transition(
		void *data, bool enabled)
{
	struct native_gpu_coordinate_owner *owner = data;
	const struct gfx_coord_ops ops = {
		.context = owner, .read_ptd = native_gpu_read_ptd,
		.write_ptd = native_gpu_write_ptd, .read_vote = native_gpu_read_vote,
		.write_vote = native_gpu_write_vote, .now_ns = native_gpu_coordinate_now,
		.delay = native_gpu_coordinate_delay, .event = native_gpu_coordinate_event,
	};
	int ret;
	if (!owner || !owner->pmp || !owner->pmc)
		return -EINVAL;
	ret = native_gpu_coordinate_aliases();
	if (ret)
		return ret;
	if (enabled && owner->session.off_complete) {
		struct apple_pmgr_gfx_reset_observation observation = {};
		ret = apple_pmgr_t6040_gfx_snapshot(&observation);
		if (ret)
			return ret;
		/* A new paired cycle starts only after the completed old OFF and
		 * provider ON. BUSY is observable, not an invented admission bit. */
		if (!(observation.valid & APPLE_PMGR_GFX_VALID_BEFORE) ||
		    !observation.domain_on || (observation.before & 0xff) != 0xff ||
		    (observation.before & 0x80001400))
			return -EBUSY;
		owner->session = (struct gfx_coord_session){};
	}
	/* A failed external write may commit: never auto-release after intent. */
	owner->exposed = true;
	return gfx_coord_transition(&owner->session, &ops, enabled, &owner->last);
}

__rust_helper int rust_helper_native_gpu_provider_snapshot(u32 *word, bool *on)
{
	struct apple_pmgr_gfx_reset_observation observation = {};
	int ret = apple_pmgr_t6040_gfx_snapshot(&observation);
	if (ret)
		return ret;
	if (!(observation.valid & APPLE_PMGR_GFX_VALID_BEFORE))
		return -EIO;
	*word = observation.before;
	*on = observation.domain_on;
	return 0;
}
