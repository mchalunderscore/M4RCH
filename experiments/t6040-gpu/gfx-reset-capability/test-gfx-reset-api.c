/* SPDX-License-Identifier: GPL-2.0-only */
/* Runs the extracted actual driver core against a fault-injected PMGR model. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint32_t u32;
#define BIT(n) (1U << (n))
#define GENMASK(h, l) ((UINT32_MAX >> (31 - (h))) & (UINT32_MAX << (l)))
#define FIELD_GET(mask, value) (((value) & (mask)) >> __builtin_ctz(mask))
#define FIELD_PREP(mask, value) (((value) << __builtin_ctz(mask)) & (mask))
#define APPLE_PMGR_RESET BIT(31)
#define APPLE_PMGR_AUTO_ENABLE BIT(28)
#define APPLE_PMGR_PS_RESET BIT(12)
#define APPLE_PMGR_BUSY BIT(11)
#define APPLE_PMGR_DEV_DISABLE BIT(10)
#define APPLE_PMGR_FLAGS (BIT(9) | BIT(8))
#define APPLE_PMGR_PS_ACTUAL GENMASK(7, 4)
#define APPLE_PMGR_PS_TARGET GENMASK(3, 0)
#define APPLE_PMGR_PS_ACTIVE 15
#define GENPD_STATE_ON 0
#define GENPD_STATE_OFF 1
#include "pmgr-gfx-reset.h"

enum mode {
	NORMAL, DROP_AUTO_OFF, DROP_DISABLE_SET, DROP_RESET_SET,
	DROP_RESET_CLEAR, DROP_DISABLE_CLEAR, DROP_AUTO_RESTORE,
	POWER_LOSS_AFTER_INHIBIT, POWER_LOSS_AFTER_ASSERT,
	TARGET_LOSS_AFTER_INHIBIT, BUSY_AFTER_INHIBIT, AUTOGATE_ON_RESTORE,
};

struct regmap {
	u32 value, initial;
	unsigned int reads, writes, delays, asserted;
	unsigned int fail_read, fail_write, secondary_fail_write;
	bool permanent_read_failure, permanent_write_failure, commit_then_fail;
	enum mode mode;
};
struct test_list { bool not_empty; };
struct apple_pmgr_ps {
	struct regmap *regmap;
	u32 offset;
	struct { const char *name; int status, slock; } genpd;
	struct { int lock; struct test_list reset_control_head; } rcdev;
};
static int mutex_depth, spin_depth;
static struct regmap *active;
static unsigned int cases;

static void mutex_lock(int *lock)
{
	(void)lock;
	assert(mutex_depth == 0 && spin_depth == 0);
	mutex_depth = 1;
}
static void mutex_unlock(int *lock)
{
	(void)lock;
	assert(mutex_depth == 1 && spin_depth == 0);
	mutex_depth = 0;
}
#define spin_lock_irqsave(lock, flags) do { \
	(void)(lock); (flags) = 0; assert(spin_depth == 0); spin_depth = 1; \
} while (0)
#define spin_unlock_irqrestore(lock, flags) do { \
	(void)(lock); (void)(flags); assert(spin_depth == 1); spin_depth = 0; \
} while (0)
static bool list_empty(struct test_list *head) { return !head->not_empty; }
static void udelay(unsigned int duration)
{
	assert(spin_depth == 1 && (duration == 1 || duration == 10));
	active->delays += duration;
}

static int regmap_read(struct regmap *map, u32 offset, u32 *value)
{
	assert(offset == 0x110 && spin_depth == 1);
	map->reads++;
	if (map->fail_read && (map->reads == map->fail_read ||
	    (map->permanent_read_failure && map->reads >= map->fail_read))) {
		*value = 0xbad00bad; /* A failed provider read must not corrupt valid receipt data. */
		return -EIO;
	}
	*value = map->value;
	return 0;
}

static int regmap_update_bits(struct regmap *map, u32 offset, u32 mask, u32 value)
{
	u32 old, next, applied;
	bool fail;
	int ret;

	assert((mask & APPLE_PMGR_FLAGS) == APPLE_PMGR_FLAGS);
	assert((value & APPLE_PMGR_FLAGS) == 0);
	ret = regmap_read(map, offset, &old);
	if (ret)
		return ret;
	next = (old & ~mask) | (value & mask);
	if (old == next)
		return 0;
	map->writes++;
	fail = map->fail_write && (map->writes == map->fail_write ||
	       (map->permanent_write_failure && map->writes >= map->fail_write));
	if (map->secondary_fail_write && map->writes == map->secondary_fail_write)
		return -EIO;
	if (fail && !map->commit_then_fail)
		return -EIO;
	/* Independent hardware model: ACTUAL is read-only; history is W1C. */
	applied = (next & ~(APPLE_PMGR_PS_ACTUAL | APPLE_PMGR_FLAGS)) |
		  (old & APPLE_PMGR_PS_ACTUAL) |
		  ((old & APPLE_PMGR_FLAGS) & ~(next & APPLE_PMGR_FLAGS));
	if (map->mode == DROP_AUTO_OFF && !(next & APPLE_PMGR_AUTO_ENABLE))
		applied |= old & APPLE_PMGR_AUTO_ENABLE;
	if (map->mode == DROP_AUTO_RESTORE && (next & APPLE_PMGR_AUTO_ENABLE))
		applied &= ~APPLE_PMGR_AUTO_ENABLE;
	if (map->mode == DROP_DISABLE_SET && (next & APPLE_PMGR_DEV_DISABLE))
		applied &= ~APPLE_PMGR_DEV_DISABLE;
	if (map->mode == DROP_RESET_SET && (next & APPLE_PMGR_RESET))
		applied &= ~APPLE_PMGR_RESET;
	if (map->mode == DROP_RESET_CLEAR && (old & APPLE_PMGR_RESET))
		applied |= APPLE_PMGR_RESET;
	if (map->mode == DROP_DISABLE_CLEAR && (old & APPLE_PMGR_DEV_DISABLE))
		applied |= APPLE_PMGR_DEV_DISABLE;
	if (!(old & APPLE_PMGR_RESET) && (applied & APPLE_PMGR_RESET)) {
		/* Reset may rise only after clocks held and device disable acknowledged. */
		assert((old & (APPLE_PMGR_AUTO_ENABLE | APPLE_PMGR_PS_RESET | APPLE_PMGR_BUSY)) == 0);
		assert((old & APPLE_PMGR_DEV_DISABLE) != 0);
		assert(FIELD_GET(APPLE_PMGR_PS_ACTUAL, old) == 15);
		assert(FIELD_GET(APPLE_PMGR_PS_TARGET, old) == 15);
		map->asserted++;
	}
	/* Auto-PM must never be restored while either release bit remains asserted. */
	if (!(old & APPLE_PMGR_AUTO_ENABLE) && (applied & APPLE_PMGR_AUTO_ENABLE))
		assert((old & (APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE)) == 0);
	if (map->mode == POWER_LOSS_AFTER_INHIBIT && !(applied & APPLE_PMGR_AUTO_ENABLE))
		applied &= ~APPLE_PMGR_PS_ACTUAL;
	if (map->mode == POWER_LOSS_AFTER_ASSERT && (applied & APPLE_PMGR_RESET))
		applied &= ~APPLE_PMGR_PS_ACTUAL;
	if (map->mode == TARGET_LOSS_AFTER_INHIBIT && !(applied & APPLE_PMGR_AUTO_ENABLE))
		applied &= ~APPLE_PMGR_PS_TARGET;
	if (map->mode == BUSY_AFTER_INHIBIT && !(applied & APPLE_PMGR_AUTO_ENABLE))
		applied |= APPLE_PMGR_BUSY;
	if (map->mode == AUTOGATE_ON_RESTORE && map->asserted &&
	    (applied & APPLE_PMGR_AUTO_ENABLE))
		applied &= ~APPLE_PMGR_PS_ACTUAL;
	map->value = applied;
	return fail ? -EIO : 0;
}

#include "checked-gfx-reset-core.inc"

static void fixture(struct regmap *map, struct apple_pmgr_ps *ps, bool automatic)
{
	memset(map, 0, sizeof(*map));
	memset(ps, 0, sizeof(*ps));
	map->value = 0xff | APPLE_PMGR_FLAGS | (3U << 16) | (5U << 24) |
		     (automatic ? APPLE_PMGR_AUTO_ENABLE : 0);
	map->initial = map->value;
	ps->regmap = map;
	ps->offset = 0x110;
	ps->genpd.name = "gfx";
	ps->genpd.status = GENPD_STATE_ON;
	active = map;
	assert(mutex_depth == 0 && spin_depth == 0);
}

static int pulse(struct regmap *map, struct apple_pmgr_ps *ps,
		 struct apple_pmgr_gfx_reset_observation *obs)
{
	int ret;

	memset(obs, 0, sizeof(*obs));
	ret = apple_pmgr_gfx_pulse_available(ps, obs);
	assert(mutex_depth == 0 && spin_depth == 0);
	assert(map->reads < 1024 && map->delays <= 500);
	cases++;
	return ret;
}

int main(void)
{
	struct regmap map;
	struct apple_pmgr_ps ps;
	struct apple_pmgr_gfx_reset_observation obs;
	unsigned int baseline_reads, baseline_writes, i, automatic;
	int ret;

	for (automatic = 0; automatic < 2; automatic++) {
		fixture(&map, &ps, automatic);
		assert(pulse(&map, &ps, &obs) == 0);
		assert(map.value == map.initial && map.asserted == 1 && map.delays == 10);
		assert(obs.valid == 127 && obs.auto_policy_restored == 1 && obs.cleanup_error == 0);
	}
	baseline_reads = map.reads;
	baseline_writes = map.writes;

	/* Snapshot is one read, zero updates, and accepts an inactive observation. */
	fixture(&map, &ps, true);
	ps.genpd.status = GENPD_STATE_OFF;
	memset(&obs, 0, sizeof(obs));
	spin_depth = 1;
	assert(apple_pmgr_gfx_snapshot_locked(&ps, &obs) == 0);
	spin_depth = 0;
	assert(map.reads == 1 && map.writes == 0 && obs.valid == 1 && !obs.domain_on);
	cases++;

	for (i = 0; i < 9; i++) {
		fixture(&map, &ps, true);
		switch (i) {
		case 0: ps.offset = 0x100; break;
		case 1: ps.genpd.name = "afr"; break;
		case 2: ps.genpd.status = GENPD_STATE_OFF; break;
		case 3: map.value &= ~APPLE_PMGR_PS_ACTUAL; break;
		case 4: map.value &= ~APPLE_PMGR_PS_TARGET; break;
		case 5: map.value |= APPLE_PMGR_RESET; break;
		case 6: map.value |= APPLE_PMGR_DEV_DISABLE; break;
		case 7: map.value |= APPLE_PMGR_PS_RESET; break;
		case 8: map.value |= APPLE_PMGR_BUSY; break;
		}
		map.initial = map.value;
		assert(pulse(&map, &ps, &obs) < 0);
		assert(map.writes == 0 && map.value == map.initial);
	}
	fixture(&map, &ps, true);
	ps.rcdev.reset_control_head.not_empty = true;
	assert(pulse(&map, &ps, &obs) == -EBUSY);
	assert(obs.reset_users_present == 1 && map.reads == 0 && map.writes == 0);

	for (automatic = 0; automatic < 2; automatic++) {
		for (i = 1; i <= baseline_reads; i++) {
			fixture(&map, &ps, automatic);
			map.fail_read = i;
			assert(pulse(&map, &ps, &obs) == -EIO);
			assert(map.value == map.initial);
			if (i > 1)
				assert(obs.auto_policy_restored == 1 && obs.cleanup_error == 0);
		}
		for (i = 1; i <= baseline_writes; i++) {
			for (unsigned int committed = 0; committed < 2; committed++) {
				fixture(&map, &ps, automatic);
				map.fail_write = i;
				map.commit_then_fail = committed;
				assert(pulse(&map, &ps, &obs) == -EIO);
				assert(map.value == map.initial && obs.auto_policy_restored == 1);
			}
		}
	}
	for (i = 1; i <= baseline_reads; i++) {
		fixture(&map, &ps, true);
		map.fail_read = i;
		map.permanent_read_failure = true;
		assert(pulse(&map, &ps, &obs) == -EIO);
		assert(obs.auto_policy_restored == 0);
		if (i > 1)
			assert(obs.cleanup_error == -EIO);
	}
	for (i = 1; i <= baseline_writes; i++) {
		fixture(&map, &ps, true);
		map.fail_write = i;
		map.permanent_write_failure = true;
		ret = pulse(&map, &ps, &obs);
		assert(ret == -EIO && obs.cleanup_error != 0);
	}
	for (i = DROP_AUTO_OFF; i <= AUTOGATE_ON_RESTORE; i++) {
		fixture(&map, &ps, true);
		map.mode = (enum mode)i;
		ret = pulse(&map, &ps, &obs);
		if (i == AUTOGATE_ON_RESTORE) {
			assert(ret == 0 && FIELD_GET(APPLE_PMGR_PS_ACTUAL, map.value) == 0);
		} else {
			assert(ret == -ETIMEDOUT);
			if (i == DROP_RESET_CLEAR || i == DROP_DISABLE_CLEAR) {
				assert(obs.cleanup_error == -ETIMEDOUT && !obs.auto_policy_restored);
				assert(!(map.value & APPLE_PMGR_AUTO_ENABLE));
			}
		}
	}
	/* Failed policy restore can have committed; subsequent reads may all fail. */
	fixture(&map, &ps, true);
	map.fail_write = baseline_writes;
	map.commit_then_fail = true;
	map.fail_read = baseline_reads;
	map.permanent_read_failure = true;
	assert(pulse(&map, &ps, &obs) == -EIO);
	assert(obs.cleanup_error == -EIO && !obs.auto_policy_restored);
	assert((map.value & APPLE_PMGR_AUTO_ENABLE) != 0);
	/* Committed restore EIO, failed cleanup inhibit, then unobservable release. */
	fixture(&map, &ps, true);
	map.fail_write = baseline_writes;
	map.commit_then_fail = true;
	map.secondary_fail_write = baseline_writes + 1;
	map.fail_read = baseline_reads + 1;
	map.permanent_read_failure = true;
	assert(pulse(&map, &ps, &obs) == -EIO);
	assert(obs.cleanup_error == -EIO && !obs.auto_policy_restored);
	assert((map.value & APPLE_PMGR_AUTO_ENABLE) != 0);
	/* Initial inhibit failed without commit, followed by permanently failed cleanup reads. */
	fixture(&map, &ps, true);
	map.fail_write = 1;
	map.fail_read = 3;
	map.permanent_read_failure = true;
	assert(pulse(&map, &ps, &obs) == -EIO);
	assert(obs.cleanup_error == -EIO && !obs.auto_policy_restored);
	assert((map.value & APPLE_PMGR_AUTO_ENABLE) != 0);
	/* Cleanup itself cannot restore policy after a second write error. */
	fixture(&map, &ps, true);
	map.fail_write = 3;
	map.commit_then_fail = true;
	map.secondary_fail_write = 7;
	assert(pulse(&map, &ps, &obs) == -EIO);
	assert(obs.cleanup_error == -EIO && !obs.auto_policy_restored);
	assert(!(map.value & (APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE | APPLE_PMGR_AUTO_ENABLE)));
	fixture(&map, &ps, true);
	map.mode = DROP_RESET_SET;
	map.fail_read = 8;
	assert(pulse(&map, &ps, &obs) == -EIO);
	assert(obs.valid & APPLE_PMGR_GFX_VALID_ASSERTED);
	assert(obs.asserted == ((map.initial & ~APPLE_PMGR_AUTO_ENABLE) | APPLE_PMGR_DEV_DISABLE));

	printf("{\"cases\":%u,\"baseline_reads\":%u,\"baseline_writes\":%u,\"hardware_access\":false}\n",
	       cases, baseline_reads, baseline_writes);
	return 0;
}
