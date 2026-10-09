/* SPDX-License-Identifier: GPL-2.0-only */
/* Reuses the v1 extracted-actual-C harness approach; CPU-only independent model. */
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

enum command_model { LATCHED, NONLATCHED_READBACK, SELF_CLEARING };
enum mode {
	NORMAL, DROP_INHIBIT, STUCK_DISABLE_RELEASE, STUCK_RESET_RELEASE,
	DROP_AUTO_RESTORE, POWER_LOSS_AFTER_INHIBIT, TARGET_LOSS_AFTER_INHIBIT,
	BUSY_AFTER_DISABLE, BUSY_AFTER_ASSERT, AUTOGATE_ON_RESTORE,
};
struct regmap {
	u32 value, initial, log[32];
	unsigned int reads, writes, delays, asserted, last_assert_delay, last_disable_delay;
	unsigned int fail_read, fail_write, secondary_fail_write;
	bool permanent_read_failure, permanent_write_failure, commit_then_fail;
	enum command_model disable_model, reset_model;
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
	(void)(lock); (flags) = 0; assert(mutex_depth == 1 && spin_depth == 0); spin_depth = 1; \
} while (0)
#define spin_unlock_irqrestore(lock, flags) do { \
	(void)(lock); (void)(flags); assert(mutex_depth == 1 && spin_depth == 1); spin_depth = 0; \
} while (0)
static bool list_empty(struct test_list *head) { return !head->not_empty; }
static void udelay(unsigned int duration)
{
	assert(spin_depth == 1 && duration == 1);
	active->delays += duration;
}
static int regmap_read(struct regmap *map, u32 offset, u32 *value)
{
	u32 result;
	assert(offset == 0x110 && spin_depth == 1);
	map->reads++;
	if (map->fail_read && (map->reads == map->fail_read ||
	    (map->permanent_read_failure && map->reads >= map->fail_read))) {
		*value = 0xbad00bad;
		return -EIO;
	}
	if (map->disable_model == SELF_CLEARING)
		map->value &= ~APPLE_PMGR_DEV_DISABLE;
	if (map->reset_model == SELF_CLEARING)
		map->value &= ~APPLE_PMGR_RESET;
	result = map->value;
	if (map->disable_model == NONLATCHED_READBACK)
		result &= ~APPLE_PMGR_DEV_DISABLE;
	if (map->reset_model == NONLATCHED_READBACK)
		result &= ~APPLE_PMGR_RESET;
	*value = result;
	return 0;
}
static int regmap_write(struct regmap *map, u32 offset, u32 word)
{
	u32 old = map->value, applied;
	bool fail;
	assert(offset == 0x110 && spin_depth == 1);
	assert((word & APPLE_PMGR_FLAGS) == 0);
	assert(map->writes < 32);
	map->log[map->writes++] = word;
	fail = (map->fail_write && (map->writes == map->fail_write ||
		(map->permanent_write_failure && map->writes >= map->fail_write))) ||
	       (map->secondary_fail_write && map->writes == map->secondary_fail_write);
	if (fail && !map->commit_then_fail)
		return -EIO;
	/* ACTUAL and BUSY are independently modelled read-only state; history W1C. */
	applied = (word & ~(APPLE_PMGR_PS_ACTUAL | APPLE_PMGR_BUSY | APPLE_PMGR_FLAGS)) |
		  (old & (APPLE_PMGR_PS_ACTUAL | APPLE_PMGR_BUSY)) |
		  ((old & APPLE_PMGR_FLAGS) & ~(word & APPLE_PMGR_FLAGS));
	if ((word & APPLE_PMGR_RESET)) {
		/* Command delivery is tested independently of its reported latch state. */
		assert(word & APPLE_PMGR_DEV_DISABLE);
		assert((old & (APPLE_PMGR_AUTO_ENABLE | APPLE_PMGR_PS_RESET | APPLE_PMGR_BUSY)) == 0);
		assert(FIELD_GET(APPLE_PMGR_PS_ACTUAL, old) == 15);
		assert(FIELD_GET(APPLE_PMGR_PS_TARGET, old) == 15);
		assert(map->delays >= map->last_disable_delay + 1);
		map->last_assert_delay = map->delays;
		map->asserted++;
	} else if (map->asserted) {
		assert(map->delays >= map->last_assert_delay + 1);
	}
	if ((word & APPLE_PMGR_DEV_DISABLE) && !(word & APPLE_PMGR_RESET))
		map->last_disable_delay = map->delays;
	if (map->mode == DROP_INHIBIT && !(word & APPLE_PMGR_AUTO_ENABLE))
		applied |= old & APPLE_PMGR_AUTO_ENABLE;
	if (map->mode == DROP_AUTO_RESTORE && (word & APPLE_PMGR_AUTO_ENABLE))
		applied &= ~APPLE_PMGR_AUTO_ENABLE;
	if (map->mode == STUCK_DISABLE_RELEASE && (old & APPLE_PMGR_DEV_DISABLE))
		applied |= APPLE_PMGR_DEV_DISABLE;
	if (map->mode == STUCK_RESET_RELEASE && (old & APPLE_PMGR_RESET))
		applied |= APPLE_PMGR_RESET;
	if (!(old & APPLE_PMGR_AUTO_ENABLE) && (applied & APPLE_PMGR_AUTO_ENABLE)) {
		/* A forced successful release must precede every restore in this model. */
		assert((old & (APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE | APPLE_PMGR_BUSY)) == 0);
	}
	if (map->mode == POWER_LOSS_AFTER_INHIBIT && !(applied & APPLE_PMGR_AUTO_ENABLE))
		applied &= ~APPLE_PMGR_PS_ACTUAL;
	if (map->mode == TARGET_LOSS_AFTER_INHIBIT && !(applied & APPLE_PMGR_AUTO_ENABLE))
		applied &= ~APPLE_PMGR_PS_TARGET;
	if (map->mode == BUSY_AFTER_DISABLE && (word & APPLE_PMGR_DEV_DISABLE))
		applied |= APPLE_PMGR_BUSY;
	if (map->mode == BUSY_AFTER_ASSERT && (word & APPLE_PMGR_RESET))
		applied |= APPLE_PMGR_BUSY;
	if (map->mode == AUTOGATE_ON_RESTORE && map->asserted &&
	    (applied & APPLE_PMGR_AUTO_ENABLE))
		applied &= ~APPLE_PMGR_PS_ACTUAL;
	map->value = applied;
	return fail ? -EIO : 0;
}

#include "native-gfx-reset-core.inc"

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
static int probe(struct regmap *map, struct apple_pmgr_ps *ps,
		 struct apple_pmgr_gfx_native_observation *obs)
{
	int ret;
	memset(obs, 0, sizeof(*obs));
	ret = apple_pmgr_gfx_native_available(ps, obs);
	obs->common.operation_error = ret; /* Identical exported-wrapper assignment. */
	assert(mutex_depth == 0 && spin_depth == 0);
	assert(map->reads <= 600 && map->delays <= 502);
	for (unsigned int j = 0; j < 8; j++) {
		assert(obs->read_count[j] <= 101 && obs->poll_delay_us[j] <= 100);
		assert(!!(obs->read_attempts & BIT(j)) == !!obs->read_count[j]);
	}
	assert(!(obs->common.valid & APPLE_PMGR_GFX_VALID_DEASSERTED));
	cases++;
	return ret;
}
static void normal_result(struct regmap *map, struct apple_pmgr_gfx_native_observation *obs)
{
	u32 base = map->initial & ~(APPLE_PMGR_FLAGS | APPLE_PMGR_AUTO_ENABLE);
	assert(obs->command_attempts == 31 && map->writes == 5);
	assert(obs->read_attempts == 63 && map->reads == 6);
	assert(obs->command_base == base && obs->base_from_auto_held == 1);
	assert(obs->desired[0] == base && obs->desired[1] == (base | APPLE_PMGR_DEV_DISABLE));
	assert(obs->desired[2] == (base | APPLE_PMGR_DEV_DISABLE | APPLE_PMGR_RESET));
	assert(obs->desired[3] == base && obs->desired[4] == (base | obs->original_auto));
	for (unsigned int j = 0; j < 5; j++)
		assert(map->log[j] == obs->desired[j] && obs->write_error[j] == 0);
	assert(obs->release_command_verified && obs->sequence_completed);
	assert(obs->common.auto_policy_restored && !obs->common.cleanup_error);
	assert(obs->disable_delay_us == 1 && obs->pulse_delay_us == 1 && map->delays == 2);
	assert(map->value == map->initial && map->asserted == 1);
}
int main(void)
{
	struct regmap map;
	struct apple_pmgr_ps ps;
	struct apple_pmgr_gfx_native_observation obs;
	unsigned int automatic, d, r, i, committed;
	int ret;

	for (automatic = 0; automatic < 2; automatic++) {
		/* All nine independent bit10/bit31 models; no latch prerequisites. */
		for (d = 0; d < 3; d++) for (r = 0; r < 3; r++) {
			fixture(&map, &ps, automatic);
			map.disable_model = d; map.reset_model = r;
			assert(probe(&map, &ps, &obs) == 0);
			normal_result(&map, &obs);
			if (d || r) {
				assert(obs.desired[APPLE_PMGR_GFX_NATIVE_ASSERT] & APPLE_PMGR_DEV_DISABLE);
				assert(map.log[3] == obs.command_base); /* Forced despite raw reads equalling B. */
			}
		}
		for (d = 0; d < 3; d++) for (r = 0; r < 3; r++) {
		for (i = 1; i <= 6; i++) {
			fixture(&map, &ps, automatic); map.fail_read = i;
			map.disable_model = d; map.reset_model = r;
			assert(probe(&map, &ps, &obs) == -EIO);
			assert(map.value == map.initial && !obs.sequence_completed);
			if (i > 1)
				assert(obs.common.auto_policy_restored && obs.common.cleanup_error == 0);
		}
		for (i = 1; i <= 5; i++) for (committed = 0; committed < 2; committed++) {
			fixture(&map, &ps, automatic); map.fail_write = i; map.commit_then_fail = committed;
			map.disable_model = d; map.reset_model = r;
			assert(probe(&map, &ps, &obs) == -EIO);
			assert(map.value == map.initial && !obs.sequence_completed);
			assert(obs.write_error[i - 1] == -EIO && (obs.command_attempts & BIT(i - 1)));
			assert(obs.common.auto_policy_restored && obs.common.cleanup_error == 0);
			if (i == 3)
				assert(obs.pulse_delay_us == 1); /* Including commit-then-error assertion. */
		}
		}
	}
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
		assert(probe(&map, &ps, &obs) < 0);
		assert(map.writes == 0 && obs.command_attempts == 0 && map.value == map.initial);
	}
	fixture(&map, &ps, true); ps.rcdev.reset_control_head.not_empty = true;
	assert(probe(&map, &ps, &obs) == -EBUSY);
	assert(obs.common.reset_users_present && map.reads == 0 && map.writes == 0);

	for (i = 1; i <= 6; i++) {
		fixture(&map, &ps, true); map.fail_read = i; map.permanent_read_failure = true;
		assert(probe(&map, &ps, &obs) == -EIO);
		assert(!obs.common.auto_policy_restored && !obs.release_command_verified);
		if (i > 1) {
			assert(obs.common.cleanup_error == -EIO);
			assert(obs.command_attempts & BIT(APPLE_PMGR_GFX_NATIVE_CLEANUP_RELEASE));
			assert(!(map.value & (APPLE_PMGR_AUTO_ENABLE | APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE)));
		}
	}
	for (i = 1; i <= 5; i++) for (committed = 0; committed < 2; committed++) {
		fixture(&map, &ps, true); map.fail_write = i;
		map.permanent_write_failure = true; map.commit_then_fail = committed;
		assert(probe(&map, &ps, &obs) == -EIO);
		assert(obs.common.cleanup_error == -EIO && !obs.common.auto_policy_restored);
		assert(!obs.release_command_verified);
	}
	/* All cleanup writes fail independently after a primary asserted-read error. */
	for (d = 0; d < 3; d++) for (r = 0; r < 3; r++) {
	for (i = 4; i <= 6; i++) for (committed = 0; committed < 2; committed++) {
		fixture(&map, &ps, true); map.fail_read = 4; map.fail_write = i;
		map.commit_then_fail = committed;
		map.disable_model = d; map.reset_model = r;
		assert(probe(&map, &ps, &obs) == -EIO);
		assert(obs.common.cleanup_error == -EIO && !obs.sequence_completed);
		if (i == 5) {
			assert(!obs.common.auto_policy_restored && !obs.release_command_verified);
			assert(!(obs.command_attempts & BIT(APPLE_PMGR_GFX_NATIVE_CLEANUP_RESTORE)));
			assert(!(map.value & APPLE_PMGR_AUTO_ENABLE));
		} else if (i == 6) {
			assert(!obs.common.auto_policy_restored && obs.release_command_verified);
		} else {
			assert(obs.common.auto_policy_restored && obs.release_command_verified);
		}
	}
	}
	/* Shared cleanup_final valid value stays the earlier successful sample on error. */
	fixture(&map, &ps, true); map.fail_write = 3; map.fail_read = 5;
	assert(probe(&map, &ps, &obs) == -EIO);
	assert(obs.common.valid & APPLE_PMGR_GFX_VALID_CLEANUP_FINAL);
	assert(obs.read_error[APPLE_PMGR_GFX_NATIVE_READ_CLEANUP_FINAL] == -EIO);
	assert(!obs.common.auto_policy_restored && obs.release_command_verified);
	assert(obs.common.cleanup_final == ((map.initial & ~APPLE_PMGR_AUTO_ENABLE)));

	for (i = DROP_INHIBIT; i <= AUTOGATE_ON_RESTORE; i++) {
		fixture(&map, &ps, true); map.mode = i;
		ret = probe(&map, &ps, &obs);
		if (i == AUTOGATE_ON_RESTORE) {
			assert(ret == 0 && FIELD_GET(APPLE_PMGR_PS_ACTUAL, map.value) == 0);
		} else {
			assert(ret == -ETIMEDOUT && !obs.sequence_completed);
			assert(!obs.common.auto_policy_restored);
			if (i != DROP_AUTO_RESTORE)
				assert(!obs.release_command_verified);
		}
	}
	printf("{\"cases\":%u,\"baseline_reads\":6,\"baseline_writes\":5,\"independent_command_models\":9,\"hardware_access\":false}\n", cases);
	return 0;
}
