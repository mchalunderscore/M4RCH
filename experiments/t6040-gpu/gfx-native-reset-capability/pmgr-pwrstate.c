// SPDX-License-Identifier: GPL-2.0-only OR MIT
/*
 * Apple SoC PMGR device power state driver
 *
 * Copyright The Asahi Linux Contributors
 */

#include <linux/bitops.h>
#include <linux/bitfield.h>
#include <linux/err.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/regmap.h>
#include <linux/mfd/syscon.h>
#include <linux/reset-controller.h>
#include <linux/module.h>
#include <linux/delay.h>
#include <linux/of_platform.h>
#include <linux/soc/apple/pmgr-gfx-reset.h>

#define APPLE_PMGR_RESET        BIT(31)
#define APPLE_PMGR_AUTO_ENABLE  BIT(28)
#define APPLE_PMGR_PS_AUTO      GENMASK(27, 24)
#define APPLE_PMGR_PS_MIN       GENMASK(19, 16)
#define APPLE_PMGR_PS_RESET     BIT(12)
#define APPLE_PMGR_BUSY         BIT(11)
#define APPLE_PMGR_DEV_DISABLE  BIT(10)
#define APPLE_PMGR_WAS_CLKGATED BIT(9)
#define APPLE_PMGR_WAS_PWRGATED BIT(8)
#define APPLE_PMGR_PS_ACTUAL    GENMASK(7, 4)
#define APPLE_PMGR_PS_TARGET    GENMASK(3, 0)

#define APPLE_PMGR_FLAGS        (APPLE_PMGR_WAS_CLKGATED | APPLE_PMGR_WAS_PWRGATED)

#define APPLE_PMGR_PS_ACTIVE    0xf
#define APPLE_PMGR_PS_CLKGATE   0x4
#define APPLE_PMGR_PS_PWRGATE   0x0

#define APPLE_PMGR_PS_SET_TIMEOUT 100
#define APPLE_PMGR_RESET_TIME 1

struct apple_pmgr_ps {
	struct device *dev;
	struct generic_pm_domain genpd;
	struct reset_controller_dev rcdev;
	struct regmap *regmap;
	u32 offset;
	u32 min_state;
	bool force_disable;
	bool force_reset;
	bool externally_clocked;
	bool skip_auto_enable;
};

#define genpd_to_apple_pmgr_ps(_genpd) container_of(_genpd, struct apple_pmgr_ps, genpd)
#define rcdev_to_apple_pmgr_ps(_rcdev) container_of(_rcdev, struct apple_pmgr_ps, rcdev)

/* BEGIN T6040 GFX CHECKED CORE: also compiled by the offline fault harness. */
#define APPLE_PMGR_GFX_POLL_ATTEMPTS 101
#define APPLE_PMGR_GFX_PULSE_US 10
#define APPLE_PMGR_GFX_RUNNING_MASK \
	(APPLE_PMGR_PS_ACTUAL | APPLE_PMGR_PS_TARGET | APPLE_PMGR_AUTO_ENABLE | \
	 APPLE_PMGR_PS_RESET | APPLE_PMGR_BUSY)
#define APPLE_PMGR_GFX_RUNNING_VALUE \
	(FIELD_PREP(APPLE_PMGR_PS_ACTUAL, APPLE_PMGR_PS_ACTIVE) | \
	 FIELD_PREP(APPLE_PMGR_PS_TARGET, APPLE_PMGR_PS_ACTIVE))

static int apple_pmgr_gfx_read(struct apple_pmgr_ps *ps, u32 *value, u32 valid_bit,
			       struct apple_pmgr_gfx_reset_observation *observation)
{
	u32 sampled_reg;
	int ret = regmap_read(ps->regmap, ps->offset, &sampled_reg);

	if (!ret) {
		*value = sampled_reg;
		observation->valid |= valid_bit;
	}
	return ret;
}

static int apple_pmgr_gfx_poll(struct apple_pmgr_ps *ps, u32 mask, u32 expected,
			       u32 *value, u32 valid_bit,
			       struct apple_pmgr_gfx_reset_observation *observation)
{
	unsigned int i;
	int ret;

	for (i = 0; i < APPLE_PMGR_GFX_POLL_ATTEMPTS; ++i) {
		ret = apple_pmgr_gfx_read(ps, value, valid_bit, observation);
		if (ret)
			return ret;
		if ((*value & mask) == expected)
			return 0;
		if (i + 1 < APPLE_PMGR_GFX_POLL_ATTEMPTS)
			udelay(1);
	}
	return -ETIMEDOUT;
}

static int apple_pmgr_gfx_update(struct apple_pmgr_ps *ps, u32 mask, u32 value)
{
	/* Match the existing driver's zero writes to historical flag bits. */
	return regmap_update_bits(ps->regmap, ps->offset,
				 APPLE_PMGR_FLAGS | mask, value);
}

static void apple_pmgr_gfx_cleanup(struct apple_pmgr_ps *ps, u32 original_auto,
				   struct apple_pmgr_gfx_reset_observation *observation)
{
	int ret;

	/* Every update may have reached the device even when it reports failure. */
	ret = apple_pmgr_gfx_update(ps, APPLE_PMGR_AUTO_ENABLE, 0);
	if (ret && !observation->cleanup_error)
		observation->cleanup_error = ret;
	ret = apple_pmgr_gfx_update(ps, APPLE_PMGR_RESET, 0);
	if (ret && !observation->cleanup_error)
		observation->cleanup_error = ret;
	ret = apple_pmgr_gfx_update(ps, APPLE_PMGR_DEV_DISABLE, 0);
	if (ret && !observation->cleanup_error)
		observation->cleanup_error = ret;
	ret = apple_pmgr_gfx_poll(ps, APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE |
				  APPLE_PMGR_AUTO_ENABLE, 0,
				  &observation->cleanup_final,
				  APPLE_PMGR_GFX_VALID_CLEANUP_FINAL, observation);
	if (ret) {
		if (!observation->cleanup_error)
			observation->cleanup_error = ret;
		/* Never restore auto-PM with an unconfirmed synchronous reset line. */
		return;
	}
	ret = apple_pmgr_gfx_update(ps, APPLE_PMGR_AUTO_ENABLE, original_auto);
	if (ret && !observation->cleanup_error)
		observation->cleanup_error = ret;
	ret = apple_pmgr_gfx_poll(ps,
		APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE | APPLE_PMGR_AUTO_ENABLE,
		original_auto, &observation->cleanup_final,
		APPLE_PMGR_GFX_VALID_CLEANUP_FINAL, observation);
	if (ret && !observation->cleanup_error)
		observation->cleanup_error = ret;
	if (!ret)
		observation->auto_policy_restored = 1;
}

static int apple_pmgr_gfx_snapshot_locked(struct apple_pmgr_ps *ps,
				       struct apple_pmgr_gfx_reset_observation *observation)
{
	if (ps->offset != 0x110 || strcmp(ps->genpd.name, "gfx"))
		return -ENODEV;
	observation->domain_on = ps->genpd.status == GENPD_STATE_ON;
	return apple_pmgr_gfx_read(ps, &observation->before,
				    APPLE_PMGR_GFX_VALID_BEFORE, observation);
}

static int apple_pmgr_gfx_pulse_locked(struct apple_pmgr_ps *ps,
				    struct apple_pmgr_gfx_reset_observation *observation)
{
	u32 original_auto, expected, mask;
	int ret;

	ret = apple_pmgr_gfx_snapshot_locked(ps, observation);
	if (ret)
		return ret;
	if (!observation->domain_on ||
	    FIELD_GET(APPLE_PMGR_PS_ACTUAL, observation->before) != APPLE_PMGR_PS_ACTIVE ||
	    FIELD_GET(APPLE_PMGR_PS_TARGET, observation->before) != APPLE_PMGR_PS_ACTIVE ||
	    observation->before & (APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE |
				   APPLE_PMGR_PS_RESET | APPLE_PMGR_BUSY))
		return -EBUSY;
	original_auto = observation->before & APPLE_PMGR_AUTO_ENABLE;
	/* From this first attempted update onward, every failure runs cleanup. */
	ret = apple_pmgr_gfx_update(ps, APPLE_PMGR_AUTO_ENABLE, 0);
	if (ret)
		goto cleanup;
	mask = APPLE_PMGR_GFX_RUNNING_MASK | APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE;
	expected = APPLE_PMGR_GFX_RUNNING_VALUE;
	ret = apple_pmgr_gfx_poll(ps, mask, expected, &observation->auto_held,
				  APPLE_PMGR_GFX_VALID_AUTO_HELD, observation);
	if (ret)
		goto cleanup;
	ret = apple_pmgr_gfx_update(ps, APPLE_PMGR_DEV_DISABLE, APPLE_PMGR_DEV_DISABLE);
	if (ret)
		goto cleanup;
	expected |= APPLE_PMGR_DEV_DISABLE;
	ret = apple_pmgr_gfx_poll(ps, mask, expected, &observation->disabled,
				  APPLE_PMGR_GFX_VALID_DISABLED, observation);
	if (ret)
		goto cleanup;
	ret = apple_pmgr_gfx_update(ps, APPLE_PMGR_RESET, APPLE_PMGR_RESET);
	if (ret)
		goto cleanup;
	expected |= APPLE_PMGR_RESET;
	ret = apple_pmgr_gfx_poll(ps, mask, expected, &observation->asserted,
				  APPLE_PMGR_GFX_VALID_ASSERTED, observation);
	if (ret)
		goto cleanup;
	udelay(APPLE_PMGR_GFX_PULSE_US);
	ret = apple_pmgr_gfx_update(ps, APPLE_PMGR_RESET, 0);
	if (ret)
		goto cleanup;
	expected &= ~APPLE_PMGR_RESET;
	ret = apple_pmgr_gfx_poll(ps, mask, expected, &observation->deasserted,
				  APPLE_PMGR_GFX_VALID_DEASSERTED, observation);
	if (ret)
		goto cleanup;
	ret = apple_pmgr_gfx_update(ps, APPLE_PMGR_DEV_DISABLE, 0);
	if (ret)
		goto cleanup;
	expected &= ~APPLE_PMGR_DEV_DISABLE;
	ret = apple_pmgr_gfx_poll(ps, mask, expected, &observation->released,
				  APPLE_PMGR_GFX_VALID_RELEASED, observation);
	if (ret)
		goto cleanup;
	ret = apple_pmgr_gfx_update(ps, APPLE_PMGR_AUTO_ENABLE, original_auto);
	if (ret)
		goto cleanup;
	/* Restored automatic policy can immediately gate ACTUAL; that is permitted. */
	mask = APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE | APPLE_PMGR_AUTO_ENABLE |
	       APPLE_PMGR_PS_TARGET | APPLE_PMGR_PS_RESET | APPLE_PMGR_BUSY;
	expected = original_auto | FIELD_PREP(APPLE_PMGR_PS_TARGET, APPLE_PMGR_PS_ACTIVE);
	if (!original_auto) {
		mask |= APPLE_PMGR_PS_ACTUAL;
		expected |= FIELD_PREP(APPLE_PMGR_PS_ACTUAL, APPLE_PMGR_PS_ACTIVE);
	}
	ret = apple_pmgr_gfx_poll(ps, mask, expected, &observation->final,
				  APPLE_PMGR_GFX_VALID_FINAL, observation);
	if (ret)
		goto cleanup;
	observation->auto_policy_restored = 1;
	return 0;

cleanup:
	apple_pmgr_gfx_cleanup(ps, original_auto, observation);
	return ret;
}
static int apple_pmgr_gfx_pulse_available(struct apple_pmgr_ps *ps,
					 struct apple_pmgr_gfx_reset_observation *observation)
{
	unsigned long flags;
	int ret;

	/* Block new references and refuse all existing shared/exclusive users. */
	mutex_lock(&ps->rcdev.lock);
	if (!list_empty(&ps->rcdev.reset_control_head)) {
		observation->reset_users_present = 1;
		ret = -EBUSY;
		goto unlock;
	}
	spin_lock_irqsave(&ps->genpd.slock, flags);
	ret = apple_pmgr_gfx_pulse_locked(ps, observation);
	spin_unlock_irqrestore(&ps->genpd.slock, flags);
unlock:
	mutex_unlock(&ps->rcdev.lock);
	return ret;
}
/* END T6040 GFX CHECKED CORE. */

/* BEGIN T6040 GFX NATIVE CORE: also compiled by the offline fault harness. */
#define APPLE_PMGR_GFX_NATIVE_POLL_ATTEMPTS 101
#define APPLE_PMGR_GFX_NATIVE_ACTIVE_MASK \
	(APPLE_PMGR_PS_ACTUAL | APPLE_PMGR_PS_TARGET | APPLE_PMGR_AUTO_ENABLE | \
	 APPLE_PMGR_PS_RESET | APPLE_PMGR_BUSY)
#define APPLE_PMGR_GFX_NATIVE_ACTIVE_VALUE \
	(FIELD_PREP(APPLE_PMGR_PS_ACTUAL, APPLE_PMGR_PS_ACTIVE) | \
	 FIELD_PREP(APPLE_PMGR_PS_TARGET, APPLE_PMGR_PS_ACTIVE))

static int apple_pmgr_gfx_native_read(struct apple_pmgr_ps *ps, u32 *value,
		u32 valid_bit, enum apple_pmgr_gfx_native_read stage,
		struct apple_pmgr_gfx_native_observation *observation)
{
	u32 sampled;
	int ret;

	observation->read_attempts |= BIT(stage);
	observation->read_count[stage]++;
	ret = regmap_read(ps->regmap, ps->offset, &sampled);
	observation->read_error[stage] = ret;
	if (!ret) {
		*value = sampled;
		observation->common.valid |= valid_bit;
	}
	return ret;
}

static int apple_pmgr_gfx_native_poll(struct apple_pmgr_ps *ps, u32 mask,
		u32 expected, u32 *value, u32 valid_bit,
		enum apple_pmgr_gfx_native_read stage,
		struct apple_pmgr_gfx_native_observation *observation)
{
	unsigned int i;
	int ret;

	for (i = 0; i < APPLE_PMGR_GFX_NATIVE_POLL_ATTEMPTS; i++) {
		ret = apple_pmgr_gfx_native_read(ps, value, valid_bit, stage, observation);
		if (ret)
			return ret;
		if ((*value & mask) == expected)
			return 0;
		if (i + 1 < APPLE_PMGR_GFX_NATIVE_POLL_ATTEMPTS) {
			udelay(1);
			observation->poll_delay_us[stage]++;
		}
	}
	return -ETIMEDOUT;
}

static int apple_pmgr_gfx_native_write(struct apple_pmgr_ps *ps, u32 value,
		enum apple_pmgr_gfx_native_command command,
		struct apple_pmgr_gfx_native_observation *observation)
{
	int ret;

	/* Force every command, even if command bits read clear or the image matches. */
	observation->command_attempts |= BIT(command);
	observation->desired[command] = value;
	ret = regmap_write(ps->regmap, ps->offset, value);
	observation->write_error[command] = ret;
	return ret;
}

static u32 apple_pmgr_gfx_native_policy_mask(u32 original_auto)
{
	u32 mask = APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE | APPLE_PMGR_AUTO_ENABLE |
		   APPLE_PMGR_PS_TARGET | APPLE_PMGR_PS_RESET | APPLE_PMGR_BUSY;

	/* Restored auto-PM can immediately gate ACTUAL, as in the legacy API. */
	if (!original_auto)
		mask |= APPLE_PMGR_PS_ACTUAL;
	return mask;
}

static u32 apple_pmgr_gfx_native_policy_value(u32 original_auto)
{
	u32 value = original_auto |
		    FIELD_PREP(APPLE_PMGR_PS_TARGET, APPLE_PMGR_PS_ACTIVE);

	if (!original_auto)
		value |= FIELD_PREP(APPLE_PMGR_PS_ACTUAL, APPLE_PMGR_PS_ACTIVE);
	return value;
}

static void apple_pmgr_gfx_native_cleanup(struct apple_pmgr_ps *ps,
		struct apple_pmgr_gfx_native_observation *observation)
{
	u32 base = observation->command_base;
	int ret;

	/* A previous policy restore may have committed despite a reported error. */
	observation->common.auto_policy_restored = 0;
	observation->release_command_verified = 0;
	ret = apple_pmgr_gfx_native_write(ps, base,
		APPLE_PMGR_GFX_NATIVE_CLEANUP_INHIBIT, observation);
	if (ret && !observation->common.cleanup_error)
		observation->common.cleanup_error = ret;
	/* Never elide the forced release, even when inhibition errored or reads fail. */
	ret = apple_pmgr_gfx_native_write(ps, base,
		APPLE_PMGR_GFX_NATIVE_CLEANUP_RELEASE, observation);
	if (ret && !observation->common.cleanup_error)
		observation->common.cleanup_error = ret;
	if (ret) {
		/* Read for diagnostics only: a committed-error release is still uncertain. */
		ret = apple_pmgr_gfx_native_read(ps, &observation->common.cleanup_final,
			APPLE_PMGR_GFX_VALID_CLEANUP_FINAL,
			APPLE_PMGR_GFX_NATIVE_READ_CLEANUP_RELEASE, observation);
		if (ret && !observation->common.cleanup_error)
			observation->common.cleanup_error = ret;
		return;
	}
	ret = apple_pmgr_gfx_native_poll(ps,
		APPLE_PMGR_GFX_NATIVE_ACTIVE_MASK | APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE,
		APPLE_PMGR_GFX_NATIVE_ACTIVE_VALUE, &observation->common.cleanup_final,
		APPLE_PMGR_GFX_VALID_CLEANUP_FINAL,
		APPLE_PMGR_GFX_NATIVE_READ_CLEANUP_RELEASE, observation);
	if (ret) {
		if (!observation->common.cleanup_error)
			observation->common.cleanup_error = ret;
		return;
	}
	observation->release_command_verified = 1;
	ret = apple_pmgr_gfx_native_write(ps, base | observation->original_auto,
		APPLE_PMGR_GFX_NATIVE_CLEANUP_RESTORE, observation);
	if (ret) {
		if (!observation->common.cleanup_error)
			observation->common.cleanup_error = ret;
		/* This restore may have committed; preserve that uncertainty in the receipt. */
		apple_pmgr_gfx_native_read(ps, &observation->common.cleanup_final,
			APPLE_PMGR_GFX_VALID_CLEANUP_FINAL,
			APPLE_PMGR_GFX_NATIVE_READ_CLEANUP_FINAL, observation);
		return;
	}
	ret = apple_pmgr_gfx_native_poll(ps,
		apple_pmgr_gfx_native_policy_mask(observation->original_auto),
		apple_pmgr_gfx_native_policy_value(observation->original_auto),
		&observation->common.cleanup_final, APPLE_PMGR_GFX_VALID_CLEANUP_FINAL,
		APPLE_PMGR_GFX_NATIVE_READ_CLEANUP_FINAL, observation);
	if (ret && !observation->common.cleanup_error)
		observation->common.cleanup_error = ret;
	if (!ret)
		observation->common.auto_policy_restored = 1;
}

static int apple_pmgr_gfx_native_locked(struct apple_pmgr_ps *ps,
		struct apple_pmgr_gfx_native_observation *observation)
{
	u32 base, mask;
	int ret;

	if (ps->offset != 0x110 || strcmp(ps->genpd.name, "gfx"))
		return -ENODEV;
	observation->common.domain_on = ps->genpd.status == GENPD_STATE_ON;
	ret = apple_pmgr_gfx_native_read(ps, &observation->common.before,
		APPLE_PMGR_GFX_VALID_BEFORE, APPLE_PMGR_GFX_NATIVE_READ_BEFORE, observation);
	if (ret)
		return ret;
	if (!observation->common.domain_on ||
	    FIELD_GET(APPLE_PMGR_PS_ACTUAL, observation->common.before) != APPLE_PMGR_PS_ACTIVE ||
	    FIELD_GET(APPLE_PMGR_PS_TARGET, observation->common.before) != APPLE_PMGR_PS_ACTIVE ||
	    observation->common.before & (APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE |
					  APPLE_PMGR_PS_RESET | APPLE_PMGR_BUSY))
		return -EBUSY;
	observation->original_auto = observation->common.before & APPLE_PMGR_AUTO_ENABLE;
	/* This pre-inhibit image is also the bounded fallback for failed fresh reads. */
	observation->command_base = observation->common.before &
		~(APPLE_PMGR_FLAGS | APPLE_PMGR_AUTO_ENABLE);
	ret = apple_pmgr_gfx_native_write(ps, observation->command_base,
		APPLE_PMGR_GFX_NATIVE_INHIBIT, observation);
	if (ret)
		goto cleanup;
	mask = APPLE_PMGR_GFX_NATIVE_ACTIVE_MASK | APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE;
	ret = apple_pmgr_gfx_native_poll(ps, mask, APPLE_PMGR_GFX_NATIVE_ACTIVE_VALUE,
		&observation->common.auto_held, APPLE_PMGR_GFX_VALID_AUTO_HELD,
		APPLE_PMGR_GFX_NATIVE_READ_AUTO_HELD, observation);
	if (ret)
		goto cleanup;
	base = observation->common.auto_held & ~APPLE_PMGR_FLAGS;
	observation->command_base = base;
	observation->base_from_auto_held = 1;
	ret = apple_pmgr_gfx_native_write(ps, base | APPLE_PMGR_DEV_DISABLE,
		APPLE_PMGR_GFX_NATIVE_DISABLE, observation);
	/* Errored writes may have committed: delay also precedes their cleanup. */
	udelay(1);
	observation->disable_delay_us = 1;
	if (ret)
		goto cleanup;
	/* Experimental conservative policy: minimum delay AND bounded BUSY-clear. */
	mask = APPLE_PMGR_GFX_NATIVE_ACTIVE_MASK | APPLE_PMGR_RESET;
	ret = apple_pmgr_gfx_native_poll(ps, mask, APPLE_PMGR_GFX_NATIVE_ACTIVE_VALUE,
		&observation->common.disabled, APPLE_PMGR_GFX_VALID_DISABLED,
		APPLE_PMGR_GFX_NATIVE_READ_DISABLED, observation);
	if (ret)
		goto cleanup;
	ret = apple_pmgr_gfx_native_write(ps, base | APPLE_PMGR_DEV_DISABLE | APPLE_PMGR_RESET,
		APPLE_PMGR_GFX_NATIVE_ASSERT, observation);
	udelay(1);
	observation->pulse_delay_us = 1;
	if (ret)
		goto cleanup;
	/* Diagnostic raw read only; neither command bit is an assertion ACK. */
	ret = apple_pmgr_gfx_native_read(ps, &observation->common.asserted,
		APPLE_PMGR_GFX_VALID_ASSERTED, APPLE_PMGR_GFX_NATIVE_READ_ASSERTED, observation);
	if (ret)
		goto cleanup;
	ret = apple_pmgr_gfx_native_write(ps, base,
		APPLE_PMGR_GFX_NATIVE_RELEASE, observation);
	if (ret)
		goto cleanup;
	mask = APPLE_PMGR_GFX_NATIVE_ACTIVE_MASK | APPLE_PMGR_RESET | APPLE_PMGR_DEV_DISABLE;
	ret = apple_pmgr_gfx_native_poll(ps, mask, APPLE_PMGR_GFX_NATIVE_ACTIVE_VALUE,
		&observation->common.released, APPLE_PMGR_GFX_VALID_RELEASED,
		APPLE_PMGR_GFX_NATIVE_READ_RELEASED, observation);
	if (ret)
		goto cleanup;
	observation->release_command_verified = 1;
	ret = apple_pmgr_gfx_native_write(ps, base | observation->original_auto,
		APPLE_PMGR_GFX_NATIVE_RESTORE, observation);
	if (ret)
		goto cleanup;
	ret = apple_pmgr_gfx_native_poll(ps,
		apple_pmgr_gfx_native_policy_mask(observation->original_auto),
		apple_pmgr_gfx_native_policy_value(observation->original_auto),
		&observation->common.final, APPLE_PMGR_GFX_VALID_FINAL,
		APPLE_PMGR_GFX_NATIVE_READ_FINAL, observation);
	if (ret)
		goto cleanup;
	observation->common.auto_policy_restored = 1;
	observation->sequence_completed = 1;
	return 0;

cleanup:
	apple_pmgr_gfx_native_cleanup(ps, observation);
	return ret;
}

static int apple_pmgr_gfx_native_available(struct apple_pmgr_ps *ps,
		struct apple_pmgr_gfx_native_observation *observation)
{
	unsigned long flags;
	int ret;

	mutex_lock(&ps->rcdev.lock);
	if (!list_empty(&ps->rcdev.reset_control_head)) {
		observation->common.reset_users_present = 1;
		ret = -EBUSY;
		goto unlock;
	}
	spin_lock_irqsave(&ps->genpd.slock, flags);
	ret = apple_pmgr_gfx_native_locked(ps, observation);
	spin_unlock_irqrestore(&ps->genpd.slock, flags);
unlock:
	mutex_unlock(&ps->rcdev.lock);
	return ret;
}
/* END T6040 GFX NATIVE CORE. */

static int apple_pmgr_ps_set(struct generic_pm_domain *genpd, u32 pstate, bool auto_enable)
{
	int ret;
	struct apple_pmgr_ps *ps = genpd_to_apple_pmgr_ps(genpd);
	u32 reg, cur;

	ret = regmap_read(ps->regmap, ps->offset, &reg);
	if (ret < 0)
		return ret;

	/* Resets are synchronous, and only work if the device is powered and clocked. */
	if (reg & APPLE_PMGR_RESET && pstate != APPLE_PMGR_PS_ACTIVE)
		dev_err(ps->dev, "PS %s: powering off with RESET active\n",
			genpd->name);

	if (pstate != APPLE_PMGR_PS_ACTIVE && (ps->force_disable || ps->force_reset)) {
		u32 reg_pre = reg & ~(APPLE_PMGR_AUTO_ENABLE | APPLE_PMGR_FLAGS);

		if (ps->force_disable)
			reg_pre |= APPLE_PMGR_DEV_DISABLE;
		if (ps->force_reset)
			reg_pre |= APPLE_PMGR_PS_RESET;

		regmap_write(ps->regmap, ps->offset, reg_pre);

		ret = regmap_read_poll_timeout_atomic(
			ps->regmap, ps->offset, cur,
			(cur & (APPLE_PMGR_DEV_DISABLE | APPLE_PMGR_PS_RESET)) ==
			(reg_pre & (APPLE_PMGR_DEV_DISABLE | APPLE_PMGR_PS_RESET)), 1,
			APPLE_PMGR_PS_SET_TIMEOUT);

		if (ret < 0)
			dev_err(ps->dev, "PS %s: Failed to set reset/disable bits (now: 0x%x)\n",
				genpd->name, reg);
	}

	reg &= ~(APPLE_PMGR_DEV_DISABLE | APPLE_PMGR_PS_RESET |
		 APPLE_PMGR_AUTO_ENABLE | APPLE_PMGR_FLAGS | APPLE_PMGR_PS_TARGET);
	reg |= FIELD_PREP(APPLE_PMGR_PS_TARGET, pstate);

	dev_dbg(ps->dev, "PS %s: pwrstate = 0x%x: 0x%x\n", genpd->name, pstate, reg);

	regmap_write(ps->regmap, ps->offset, reg);

	if (ps->externally_clocked && pstate == APPLE_PMGR_PS_ACTIVE) {
		/*
		 * If this clock domain requires an external clock, then
		 * consider the "clock gated" state to be good enough.
		 */
		ret = regmap_read_poll_timeout_atomic(
			ps->regmap, ps->offset, cur,
			FIELD_GET(APPLE_PMGR_PS_ACTUAL, cur) >= APPLE_PMGR_PS_CLKGATE, 1,
			APPLE_PMGR_PS_SET_TIMEOUT);
	} else {
		ret = regmap_read_poll_timeout_atomic(
			ps->regmap, ps->offset, cur,
			FIELD_GET(APPLE_PMGR_PS_ACTUAL, cur) == pstate, 1,
			APPLE_PMGR_PS_SET_TIMEOUT);
	}

	if (ret < 0)
		dev_err(ps->dev, "PS %s: Failed to reach power state 0x%x (now: 0x%x)\n",
			genpd->name, pstate, reg);

	if (auto_enable && !ps->skip_auto_enable) {
		/* Not all devices implement this; this is a no-op where not implemented. */
		reg |= APPLE_PMGR_AUTO_ENABLE;
		regmap_write(ps->regmap, ps->offset, reg);
	}

	return ret;
}

static bool apple_pmgr_ps_is_active(struct apple_pmgr_ps *ps)
{
	u32 reg = 0;

	regmap_read(ps->regmap, ps->offset, &reg);
	/*
	 * We consider domains as active if they are actually on, or if they have auto-PM
	 * enabled and the intended target is on.
	 */
	return (FIELD_GET(APPLE_PMGR_PS_ACTUAL, reg) == APPLE_PMGR_PS_ACTIVE ||
		(FIELD_GET(APPLE_PMGR_PS_TARGET, reg) == APPLE_PMGR_PS_ACTIVE &&
		 reg & APPLE_PMGR_AUTO_ENABLE));
}

static int apple_pmgr_ps_power_on(struct generic_pm_domain *genpd)
{
	return apple_pmgr_ps_set(genpd, APPLE_PMGR_PS_ACTIVE, true);
}

static int apple_pmgr_ps_power_off(struct generic_pm_domain *genpd)
{
	return apple_pmgr_ps_set(genpd, APPLE_PMGR_PS_PWRGATE, false);
}

static int apple_pmgr_reset_assert(struct reset_controller_dev *rcdev, unsigned long id)
{
	struct apple_pmgr_ps *ps = rcdev_to_apple_pmgr_ps(rcdev);
	unsigned long flags;

	spin_lock_irqsave(&ps->genpd.slock, flags);

	if (ps->genpd.status == GENPD_STATE_OFF)
		dev_err(ps->dev, "PS 0x%x: asserting RESET while powered down\n", ps->offset);

	dev_dbg(ps->dev, "PS 0x%x: assert reset\n", ps->offset);
	/* Quiesce device before asserting reset */
	regmap_update_bits(ps->regmap, ps->offset, APPLE_PMGR_FLAGS | APPLE_PMGR_DEV_DISABLE,
			   APPLE_PMGR_DEV_DISABLE);
	regmap_update_bits(ps->regmap, ps->offset, APPLE_PMGR_FLAGS | APPLE_PMGR_RESET,
			   APPLE_PMGR_RESET);

	spin_unlock_irqrestore(&ps->genpd.slock, flags);

	return 0;
}

static int apple_pmgr_reset_deassert(struct reset_controller_dev *rcdev, unsigned long id)
{
	struct apple_pmgr_ps *ps = rcdev_to_apple_pmgr_ps(rcdev);
	unsigned long flags;

	spin_lock_irqsave(&ps->genpd.slock, flags);

	dev_dbg(ps->dev, "PS 0x%x: deassert reset\n", ps->offset);
	regmap_update_bits(ps->regmap, ps->offset, APPLE_PMGR_FLAGS | APPLE_PMGR_RESET, 0);
	regmap_update_bits(ps->regmap, ps->offset, APPLE_PMGR_FLAGS | APPLE_PMGR_DEV_DISABLE, 0);

	if (ps->genpd.status == GENPD_STATE_OFF)
		dev_err(ps->dev, "PS 0x%x: RESET was deasserted while powered down\n", ps->offset);

	spin_unlock_irqrestore(&ps->genpd.slock, flags);

	return 0;
}

static int apple_pmgr_reset_reset(struct reset_controller_dev *rcdev, unsigned long id)
{
	int ret;

	ret = apple_pmgr_reset_assert(rcdev, id);
	if (ret)
		return ret;

	usleep_range(APPLE_PMGR_RESET_TIME, 2 * APPLE_PMGR_RESET_TIME);

	return apple_pmgr_reset_deassert(rcdev, id);
}

static int apple_pmgr_reset_status(struct reset_controller_dev *rcdev, unsigned long id)
{
	struct apple_pmgr_ps *ps = rcdev_to_apple_pmgr_ps(rcdev);
	u32 reg = 0;

	regmap_read(ps->regmap, ps->offset, &reg);

	return !!(reg & APPLE_PMGR_RESET);
}

static const struct reset_control_ops apple_pmgr_reset_ops = {
	.assert		= apple_pmgr_reset_assert,
	.deassert	= apple_pmgr_reset_deassert,
	.reset		= apple_pmgr_reset_reset,
	.status		= apple_pmgr_reset_status,
};

static int apple_pmgr_reset_xlate(struct reset_controller_dev *rcdev,
				  const struct of_phandle_args *reset_spec)
{
	return 0;
}

static int apple_pmgr_ps_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct device_node *node = dev->of_node;
	struct apple_pmgr_ps *ps;
	struct regmap *regmap;
	struct of_phandle_iterator it;
	int ret;
	const char *name;
	bool active;

	regmap = syscon_node_to_regmap(node->parent);
	if (IS_ERR(regmap))
		return PTR_ERR(regmap);

	ps = devm_kzalloc(dev, sizeof(*ps), GFP_KERNEL);
	if (!ps)
		return -ENOMEM;

	ps->dev = dev;
	ps->regmap = regmap;

	ret = of_property_read_string(node, "label", &name);
	if (ret < 0) {
		dev_err(dev, "missing label property\n");
		return ret;
	}

	/* T6041 raw boot firmware locks auto-PM on the display CPU domains. */
	ps->skip_auto_enable =
		of_property_read_bool(node, "apple,skip-auto-enable") ||
		(of_device_is_compatible(node, "apple,t6041-pmgr-pwrstate") &&
		 (!strcmp(name, "dispext0_cpu") ||
		  !strcmp(name, "dispext1_cpu")));

	ret = of_property_read_u32(node, "reg", &ps->offset);
	if (ret < 0) {
		dev_err(dev, "missing reg property\n");
		return ret;
	}

	ps->genpd.flags |= GENPD_FLAG_IRQ_SAFE;
	ps->genpd.name = name;
	ps->genpd.power_on = apple_pmgr_ps_power_on;
	ps->genpd.power_off = apple_pmgr_ps_power_off;

	ret = of_property_read_u32(node, "apple,min-state", &ps->min_state);
	if (ret == 0 && ps->min_state <= APPLE_PMGR_PS_ACTIVE)
		regmap_update_bits(regmap, ps->offset, APPLE_PMGR_FLAGS | APPLE_PMGR_PS_MIN,
				   FIELD_PREP(APPLE_PMGR_PS_MIN, ps->min_state));

	if (of_property_read_bool(node, "apple,force-disable"))
		ps->force_disable = true;

	if (of_property_read_bool(node, "apple,force-reset"))
		ps->force_reset = true;

	if (of_property_read_bool(node, "apple,externally-clocked"))
		ps->externally_clocked = true;

	active = apple_pmgr_ps_is_active(ps);
	/* T6041 raw boot has no earlier OS stage to quiesce firmware-owned domains. */
	if (active && (of_property_read_bool(node->parent, "apple,preserve-active") ||
		       of_device_is_compatible(node, "apple,t6041-pmgr-pwrstate")))
		ps->genpd.flags |= GENPD_FLAG_ALWAYS_ON;

	if (of_property_read_bool(node, "apple,always-on")) {
		ps->genpd.flags |= GENPD_FLAG_ALWAYS_ON;
		if (!active) {
			dev_warn(dev, "always-on domain %s is not on at boot\n", name);
			/* Turn it on so pm_genpd_init does not fail */
			active = apple_pmgr_ps_power_on(&ps->genpd) == 0;
		}
	} else if (active) {
		ps->genpd.flags |= GENPD_FLAG_DEFER_OFF | GENPD_FLAG_ACTIVE_WAKEUP;
	}

	/* Turn on auto-PM if the domain is already on */
	if (active && !ps->skip_auto_enable)
		regmap_update_bits(regmap, ps->offset, APPLE_PMGR_FLAGS | APPLE_PMGR_AUTO_ENABLE,
				   APPLE_PMGR_AUTO_ENABLE);

	ret = pm_genpd_init(&ps->genpd, NULL, !active);
	if (ret < 0) {
		dev_err(dev, "pm_genpd_init failed\n");
		return ret;
	}

	ret = of_genpd_add_provider_simple(node, &ps->genpd);
	if (ret < 0) {
		dev_err(dev, "of_genpd_add_provider_simple failed\n");
		return ret;
	}

	of_for_each_phandle(&it, ret, node, "power-domains", "#power-domain-cells", -1) {
		struct of_phandle_args parent, child;

		parent.np = it.node;
		parent.args_count = of_phandle_iterator_args(&it, parent.args, MAX_PHANDLE_ARGS);
		child.np = node;
		child.args_count = 0;
		ret = of_genpd_add_subdomain(&parent, &child);

		if (ret == -EPROBE_DEFER) {
			of_node_put(parent.np);
			goto err_remove;
		} else if (ret < 0) {
			dev_err(dev, "failed to add to parent domain: %d (%s -> %s)\n",
				ret, it.node->name, node->name);
			of_node_put(parent.np);
			goto err_remove;
		}
	}

	/*
	 * Do not participate in regular PM; parent power domains are handled via the
	 * genpd hierarchy.
	 */
	pm_genpd_remove_device(dev);

	ps->rcdev.owner = THIS_MODULE;
	ps->rcdev.nr_resets = 1;
	ps->rcdev.ops = &apple_pmgr_reset_ops;
	ps->rcdev.of_node = dev->of_node;
	ps->rcdev.of_reset_n_cells = 0;
	ps->rcdev.of_xlate = apple_pmgr_reset_xlate;

	ret = devm_reset_controller_register(dev, &ps->rcdev);
	if (ret < 0)
		goto err_remove;

	platform_set_drvdata(pdev, ps);
	return 0;
err_remove:
	of_genpd_del_provider(node);
	pm_genpd_remove(&ps->genpd);
	return ret;
}

static const struct of_device_id apple_pmgr_ps_of_match[] = {
	{ .compatible = "apple,t8103-pmgr-pwrstate" },
	{ .compatible = "apple,pmgr-pwrstate" },
	{}
};

MODULE_DEVICE_TABLE(of, apple_pmgr_ps_of_match);

static struct platform_driver apple_pmgr_ps_driver = {
	.probe = apple_pmgr_ps_probe,
	.driver = {
		.name = "apple-pmgr-pwrstate",
		.of_match_table = apple_pmgr_ps_of_match,
	},
};

static int apple_pmgr_t6040_gfx_provider_get(struct platform_device **result)
{
	struct device_node *node;
	struct platform_device *pdev;
	struct apple_pmgr_ps *ps;
	const char *label, *compatible;
	u32 reg[2], cells;
	int ret = -ENODEV;

	if (!of_machine_is_compatible("apple,t6040") ||
	    !of_machine_is_compatible("apple,j614s"))
		return -ENODEV;
	node = of_find_node_by_path("/soc/power-management@288e80000/power-controller@110");
	if (!node)
		return -ENODEV;
	if (of_property_count_u32_elems(node, "reg") != 2 ||
	    of_property_read_u32_array(node, "reg", reg, 2) ||
	    reg[0] != 0x110 || reg[1] != 4 ||
	    of_property_count_u32_elems(node, "#reset-cells") != 1 ||
	    of_property_read_u32(node, "#reset-cells", &cells) || cells ||
	    of_property_count_strings(node, "label") != 1 ||
	    of_property_read_string(node, "label", &label) || strcmp(label, "gfx") ||
	    of_property_count_strings(node, "compatible") != 2 ||
	    of_property_read_string_index(node, "compatible", 0, &compatible) ||
	    strcmp(compatible, "apple,t6041-pmgr-pwrstate") ||
	    of_property_read_string_index(node, "compatible", 1, &compatible) ||
	    strcmp(compatible, "apple,t8103-pmgr-pwrstate"))
		goto put_node;
	pdev = of_find_device_by_node(node);
	if (!pdev)
		goto put_node;
	device_lock(&pdev->dev);
	ps = dev_get_drvdata(&pdev->dev);
	if (pdev->dev.driver != &apple_pmgr_ps_driver.driver || !ps ||
	    ps->dev != &pdev->dev || ps->offset != 0x110 ||
	    strcmp(ps->genpd.name, "gfx") ||
	    strcmp(dev_name(&pdev->dev),
		   "288e80000.power-management:power-controller@110")) {
		device_unlock(&pdev->dev);
		put_device(&pdev->dev);
		goto put_node;
	}
	of_node_put(node);
	*result = pdev; /* Device reference and device lock belong to the caller. */
	return 0;

put_node:
	of_node_put(node);
	return ret;
}

static int apple_pmgr_t6040_gfx_observe(bool pulse,
				     struct apple_pmgr_gfx_reset_observation *observation)
{
	struct platform_device *pdev;
	struct apple_pmgr_ps *ps;
	unsigned long flags;
	int ret;

	if (!observation)
		return -EINVAL;
	memset(observation, 0, sizeof(*observation));
	ret = apple_pmgr_t6040_gfx_provider_get(&pdev);
	if (ret)
		goto result;
	ps = dev_get_drvdata(&pdev->dev);
	if (pulse) {
		ret = apple_pmgr_gfx_pulse_available(ps, observation);
	} else {
		spin_lock_irqsave(&ps->genpd.slock, flags);
		ret = apple_pmgr_gfx_snapshot_locked(ps, observation);
		spin_unlock_irqrestore(&ps->genpd.slock, flags);
	}
	device_unlock(&pdev->dev);
	put_device(&pdev->dev);

result:
	observation->operation_error = ret;
	return ret;
}

int apple_pmgr_t6040_gfx_snapshot(struct apple_pmgr_gfx_reset_observation *observation)
{
	return apple_pmgr_t6040_gfx_observe(false, observation);
}
EXPORT_SYMBOL_GPL(apple_pmgr_t6040_gfx_snapshot);

int apple_pmgr_t6040_gfx_checked_pulse(struct apple_pmgr_gfx_reset_observation *observation)
{
	return apple_pmgr_t6040_gfx_observe(true, observation);
}
EXPORT_SYMBOL_GPL(apple_pmgr_t6040_gfx_checked_pulse);

int apple_pmgr_t6040_gfx_native_probe(struct apple_pmgr_gfx_native_observation *observation)
{
	struct platform_device *pdev;
	struct apple_pmgr_ps *ps;
	int ret;

	if (!observation)
		return -EINVAL;
	memset(observation, 0, sizeof(*observation));
	ret = apple_pmgr_t6040_gfx_provider_get(&pdev);
	if (ret)
		goto result;
	ps = dev_get_drvdata(&pdev->dev);
	ret = apple_pmgr_gfx_native_available(ps, observation);
	device_unlock(&pdev->dev);
	put_device(&pdev->dev);
result:
	observation->common.operation_error = ret;
	return ret;
}
EXPORT_SYMBOL_GPL(apple_pmgr_t6040_gfx_native_probe);

MODULE_AUTHOR("Hector Martin <marcan@marcan.st>");
MODULE_DESCRIPTION("PMGR power state driver for Apple SoCs");

module_platform_driver(apple_pmgr_ps_driver);
