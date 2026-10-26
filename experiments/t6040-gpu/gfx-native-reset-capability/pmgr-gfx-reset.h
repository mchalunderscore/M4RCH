/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
#ifndef _LINUX_SOC_APPLE_PMGR_GFX_RESET_H
#define _LINUX_SOC_APPLE_PMGR_GFX_RESET_H

#include <linux/bits.h>
#include <linux/types.h>

#define APPLE_PMGR_GFX_VALID_BEFORE	BIT(0)
#define APPLE_PMGR_GFX_VALID_AUTO_HELD	BIT(1)
#define APPLE_PMGR_GFX_VALID_DISABLED	BIT(2)
#define APPLE_PMGR_GFX_VALID_ASSERTED	BIT(3)
#define APPLE_PMGR_GFX_VALID_DEASSERTED	BIT(4)
#define APPLE_PMGR_GFX_VALID_RELEASED	BIT(5)
#define APPLE_PMGR_GFX_VALID_FINAL		BIT(6)
#define APPLE_PMGR_GFX_VALID_CLEANUP_FINAL	BIT(7)

/* Valid bits describe successful register reads, including timed-out polls. */
struct apple_pmgr_gfx_reset_observation {
	u32 valid;
	u32 domain_on;
	u32 reset_users_present;
	u32 before;
	u32 auto_held;
	u32 disabled;
	u32 asserted;
	u32 deasserted;
	u32 released;
	u32 final;
	u32 cleanup_final;
	u32 auto_policy_restored;
	int operation_error;
	int cleanup_error;
};

/* Exact T6040/J614s GFX provider only. Snapshot performs no register writes. */
int apple_pmgr_t6040_gfx_snapshot(struct apple_pmgr_gfx_reset_observation *observation);

/*
 * Experimental explicit device-reset pulse, inactive unless called.
 * Caller holds GFX runtime-PM ownership, serializes its resident worker, stops
 * publication, excludes other reset users and retains all GPU/DMA backing.
 * The pulse refuses existing reset-core references and blocks new references
 * under the reset-controller lock. It uses the existing domain lock for the
 * register sequence. Both APIs are sleepable; callers must not already hold
 * the provider device lock, reset-controller lock or domain spinlock. Success proves
 * command readback only; no ASC/GPU reset coverage or DMA retirement guarantee.
 * AUTO_ENABLE is temporarily inhibited and restored after confirmed release.
 * Cleanup attempts to inhibit AUTO_ENABLE before release; failed bus operations
 * can leave that inhibition unconfirmed. It restores policy only after confirmed
 * inhibition and release, and reports errors/readback for uncertain cleanup.
 * Inspect both errors and valid observation fields; do not release backing.
 */
int apple_pmgr_t6040_gfx_checked_pulse(struct apple_pmgr_gfx_reset_observation *observation);

/* Attempt bits are set before the call, even if an errored write committed. */
enum apple_pmgr_gfx_native_command {
	APPLE_PMGR_GFX_NATIVE_INHIBIT,
	APPLE_PMGR_GFX_NATIVE_DISABLE,
	APPLE_PMGR_GFX_NATIVE_ASSERT,
	APPLE_PMGR_GFX_NATIVE_RELEASE,
	APPLE_PMGR_GFX_NATIVE_RESTORE,
	APPLE_PMGR_GFX_NATIVE_CLEANUP_INHIBIT,
	APPLE_PMGR_GFX_NATIVE_CLEANUP_RELEASE,
	APPLE_PMGR_GFX_NATIVE_CLEANUP_RESTORE,
	APPLE_PMGR_GFX_NATIVE_COMMAND_COUNT,
};

enum apple_pmgr_gfx_native_read {
	APPLE_PMGR_GFX_NATIVE_READ_BEFORE,
	APPLE_PMGR_GFX_NATIVE_READ_AUTO_HELD,
	APPLE_PMGR_GFX_NATIVE_READ_DISABLED,
	APPLE_PMGR_GFX_NATIVE_READ_ASSERTED,
	APPLE_PMGR_GFX_NATIVE_READ_RELEASED,
	APPLE_PMGR_GFX_NATIVE_READ_FINAL,
	APPLE_PMGR_GFX_NATIVE_READ_CLEANUP_RELEASE,
	APPLE_PMGR_GFX_NATIVE_READ_CLEANUP_FINAL,
	APPLE_PMGR_GFX_NATIVE_READ_COUNT,
};

struct apple_pmgr_gfx_native_observation {
	struct apple_pmgr_gfx_reset_observation common;
	u32 command_attempts;
	u32 command_base;
	u32 base_from_auto_held;
	u32 original_auto;
	u32 release_command_verified;
	u32 sequence_completed;
	u32 disable_delay_us;
	u32 pulse_delay_us;
	/* Every desired word is a complete forced regmap_write image, not an RMW payload. */
	u32 desired[APPLE_PMGR_GFX_NATIVE_COMMAND_COUNT];
	int write_error[APPLE_PMGR_GFX_NATIVE_COMMAND_COUNT];
	/* read_error is the last bus-read result; read_count includes failures. */
	/* common.valid/value retain the last successful sample, even after later errors. */
	/* Cleanup-release/final share common.cleanup_final: inspect both stage receipts. */
	u32 read_attempts;
	u32 read_count[APPLE_PMGR_GFX_NATIVE_READ_COUNT];
	u32 poll_delay_us[APPLE_PMGR_GFX_NATIVE_READ_COUNT];
	int read_error[APPLE_PMGR_GFX_NATIVE_READ_COUNT];
};

/*
 * Separate experimental command-delivery probe on the exact v1 provider.
 * Caller retains GFX runtime-PM ownership, serializes and seals its no-work
 * resident session, and keeps all GPU/DMA backing. Same sleepable provider,
 * reset-reference and domain locks as checked_pulse; no caller-held locks.
 * Disable is followed by a minimum 1us delay and a bounded 100us BUSY-clear
 * check: deliberately stricter than the unqualified native object policy.
 * Reset/disable command bits need not latch; reads are diagnostics, not ACKs.
 * Explicit combined assertion and explicit release use one preserved image.
 * AUTO policy is restored only after successful release write plus compatible
 * power and clear reset/disable/BUSY reads. Cleanup forces inhibited release;
 * bus failure can leave actual state uncertain despite the attempted image.
 * Success/sequence_completed means delivery/checks only, never reset coverage,
 * DMA retirement or permission to unmap, free backing or restart firmware.
 */
int apple_pmgr_t6040_gfx_native_probe(struct apple_pmgr_gfx_native_observation *observation);

#endif
