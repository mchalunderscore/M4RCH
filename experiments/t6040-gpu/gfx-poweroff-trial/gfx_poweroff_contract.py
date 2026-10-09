# SPDX-License-Identifier: GPL-2.0-only
"""Distinct retained power-off observation; no reset, restart or release claim."""
from pathlib import Path
import sys

BASE_KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_KIT))
from gfx_reset_contract import (NATIVE_RELEASE, NATIVE_PATCH_SHA, PATCH_SHA,
                                USB_PATCH_SHA, require, sha, validate_kernel)

CONTRACT = {
    'version': 1,
    'provider_path': '/soc/power-management@288e80000/power-controller@110',
    'snapshot_api': 'apple_pmgr_t6040_gfx_snapshot',
    'power_off_api': 'pm_runtime_put_sync_suspend',
    'maximum_power_off_commands': 1,
    'requires_host_stop': True,
    'requires_owned_pm_usage_count': 1,
    'work_submitted': False,
    'allocations_retained': True,
    'mappings_retained': True,
    'consumer_retained': True,
    'owned_pm_reference_released_once': True,
    'reset_pulse': False,
    'automatic_restart': False,
    'backing_release': False,
    'off_observation_mask': 0x90001cff,
    'off_observation_expected': 0,
    'off_requires_domain_on': 0,
    'maximum_snapshot_samples': 101,
    'minimum_poll_delay_us': 1000,
    'off_proves_dma_retirement': False,
    'no_asc_sgx_mailbox_access_after_attempt': True,
    'commands': ['sample', 'gfx-snapshot', 'stop', 'gfx-poweroff'],
    'after_attempt': ['sample', 'gfx-snapshot'],
}


def validate_receipt(receipt):
    trial = receipt.get('graph_recovery_trial', {})
    if 'gfx_power_off_scope' not in trial:
        return False
    require('gfx_reset_scope' not in trial and trial['gfx_power_off_scope'] == CONTRACT,
            'Unknown or mixed GFX power-off command contract')
    api = receipt.get('kernel_gfx_power_off_api', {})
    require(receipt['kernel_release'] == NATIVE_RELEASE and
            api.get('api_profile') == 'native-command-v1' and
            api.get('patch_sha256') == NATIVE_PATCH_SHA and
            api.get('legacy_checked_patch_sha256') == PATCH_SHA and
            api.get('usb_role_patch_sha256') == USB_PATCH_SHA,
            'Qualified OFF-capable snapshot kernel binding missing')
    require(receipt.get('joined_owned_pages') == 174 and
            trial.get('resident_session') is True and
            receipt.get('graph_submit_work') is False and
            receipt.get('graph_power_retirement_probe') is False and
            receipt.get('graph_release_on_shutdown') is False,
            'Unexpected power-off owner lifetime')
    return True
