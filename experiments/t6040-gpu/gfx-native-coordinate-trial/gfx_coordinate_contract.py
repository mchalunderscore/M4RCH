# SPDX-License-Identifier: GPL-2.0-only
"""Experimental paired native notification; no reset/restart/retirement."""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
BASE_KIT = HERE.parent
sys.path.insert(0, str(BASE_KIT / 'gfx-poweroff-trial'))
from gfx_poweroff_contract import CONTRACT as BASE_CONTRACT
from gfx_poweroff_contract import validate_receipt as validate_base_receipt
from gfx_reset_contract import require

ADT_CONTRACT_SHA = '838ce60f5f5d88aebfbfd39a1159bfff239ca20e432c38a31e2d327869554561'
LINUX_DT_CONTRACT_SHA = '71236d89511e3689fef2d7485f2e7d7557f50603c83cbc3ce6bffa77d9d9b32b'
CONTRACT = copy.deepcopy(BASE_CONTRACT)
CONTRACT.update({
    'version': 2,
    'paired_native_coordination': True,
    'native_policy_hypothesis': {'pmp': 2, 'pmc': 1, 'pmc_pmgr': 0x3f},
    'hardware_policy_equivalent_observed': False,
    'on_order': ['physical-active', 'pmp-request-and-ack', 'pmc-rail-votes', 'firmware-start'],
    'off_order': ['packet-free-stop', 'pmp-request-and-ack', 'pmc-rail-votes', 'physical-off'],
    'pmp_physical_base': 0x5003c0000,
    'pmp_size': 0x30000,
    'request_entry': 0x1e0,
    'ack_entry': 0x1e8,
    'status_entry': 1,
    'request_bit': 13,
    'ack_raw_status_bit': 1,
    'require_nonzero_status_for_ack_wait': True,
    'zero_status_proves_inactivity': False,
    'pmc_physical_base': 0x504000000,
    'pmc_size': 0x1000000,
    'pmc_vote_offsets': [0x8ac000, 0x8ac004, 0x8ac008],
    'pmc_vote_bit': 2,
    'maximum_on_notifications': 1,
    'maximum_off_notifications': 1,
    'maximum_ack_samples': 15001,
    'ack_deadline_ns': 15000000000,
    'ack_minimum_delay_us': 1000,
    'startup_retained_before_coordination': True,
    'failed_startup_commands': [],
    'unrelated_bits_preserved_from_read_snapshot': True,
    'atomicity_against_external_writers_verified': False,
    'native_evidence_sha256': 'a9c0ca4b3cc6aa0ebe668ae5fb95e63643f4edd0b3d941b7907f5a60b148dffe',
    'native_adt_sha256': ADT_CONTRACT_SHA,
    'linux_dt_layout_sha256': LINUX_DT_CONTRACT_SHA,
})


def record_fields(line, marker, allow_phase=False):
    require(line.count(marker) == 1, 'Missing or ambiguous record prefix')
    pairs = re.findall(r'\b(\w+)=([^\s]+)', line)
    require(len({key for key, _ in pairs}) == len(pairs), 'Duplicate record fields')
    require(all((allow_phase and key == 'phase') or
                re.fullmatch(r'-?(0|[1-9]\d*)|0x[0-9a-f]+', value)
                for key, value in pairs), 'Malformed record fields')
    return dict(pairs)


def qualify_graph_startup(on_records, owner_records, returncode, refcount, report):
    try:
        require(returncode == 0 and refcount > 0 and len(on_records) == 1 and
                len(owner_records) == 1 and report.get('root_published') is True and
                report.get('mapping_or_publication_performed') is True,
                'Unqualified retained graph startup')
        obs = record_fields(on_records[0], 'm4rch gfx-coordinate-observation: ')
        owner = record_fields(owner_records[0], 'm4rch gfx-coordinate-owner: ', True)
        words = [int(obs.get(key, '-1'), 0) for key in
                 ('request_before', 'request_written', 'ack_payload', 'ack_status')]
        require(all(0 <= value < 0xffffffffffffffff for value in words),
                'Out-of-range or all-ones ON word')
        require(all(obs.get(key) == value for key, value in {
                    'enabled': '1', 'result': '0', 'request_attempted': '1',
                    'request_acked': '1', 'votes_attempted': '3',
                    'votes_verified': '3'}.items()) and
                0 < int(obs.get('ack_samples', '0'), 0) <= 15001 and
                int(obs.get('request_written', '0'), 0) & 0x2000 and
                int(obs.get('ack_payload', '0'), 0) & 0x2000 and
                int(obs.get('ack_status', '0'), 0) & 2,
                'Missing acknowledged ON request/vote observations')
        require(all(owner.get(key) == value for key, value in {
                    'phase': 'post-active-on', 'result': '0',
                    'startup_retained': '1', 'module_pinned': '1',
                    'pmp_region': '1', 'pmc_region': '1',
                    'pmp_mapped': '1', 'pmc_mapped': '1',
                    'on_attempted': '1', 'on_complete': '1',
                    'off_attempted': '0', 'off_complete': '0',
                    'held': '1', 'started': '0', 'retirement_verified': '0'}.items()),
                'Unqualified ON owner boundary')
    except (ValueError, TypeError):
        return False
    return True


def qualify_startup_retention(lines, returncode, refcount, report):
    require(len(lines) == 1 and returncode == 0 and refcount > 0,
            'Missing or ambiguous retained startup result')
    require('m4rch gfx-native-coordinate: startup-retained result=' in lines[0],
            'Wrong retained startup record')
    pairs = re.findall(r'\b(\w+)=([^\s]+)', lines[0])
    require(len({key for key, _ in pairs}) == len(pairs) and
            all(re.fullmatch(r'-?(0|[1-9]\d*)', value) for _, value in pairs),
            'Duplicate or malformed retained startup fields')
    fields = dict(pairs)
    require(int(fields.get('result', '0')) < 0 and
            all(fields.get(key) == value for key, value in {
                'consumer': '1', 'held': '1', 'module_pinned': '1',
                'started': '0', 'root_published': '0',
                'cleanup_attempted': '0'}.items()) and
            report.get('root_published') is False and
            report.get('mapping_or_publication_performed') is False,
            'Startup retention boundary is not qualified')
    return {'startup_coordination_result': int(fields['result']),
            'startup_retention_record': lines[0],
            'own_pm_reference_retained': True,
            'startup_before_firmware_verified': True,
            'backing_release_qualified': False, 'restart_qualified': False,
            'reboot_required': True}


def qualify_adt(tree):
    path = HERE / 'adt-contract.json'
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ADT_CONTRACT_SHA,
            'Native ADT selection contract changed')
    for pin in json.loads(raw):
        value = tree.get(pin['node'], {}).get(pin['name'])
        require(value is not None and len(value) == pin['bytes'] and
                hashlib.sha256(value).hexdigest() == pin['sha256'],
                'Fresh native coordination selection differs: ' + pin['node'] + '/' + pin['name'])


def qualify_linux_dt(base='/sys/firmware/devicetree/base'):
    from linux_dt_contract import encoded_layout
    expected = (HERE / 'linux-dt-contract.json').read_bytes()
    require(hashlib.sha256(expected).hexdigest() == LINUX_DT_CONTRACT_SHA,
            'Linux OF resource contract changed')
    observed = encoded_layout(base)
    require(observed == expected, 'Fresh Linux OF resource layout differs; inspect metadata before hardware')


def validate_receipt(receipt):
    trial = receipt.get('graph_recovery_trial', {})
    selected = trial.get('gfx_coordinated_power_off_scope')
    if selected is None:
        return False
    require(selected == CONTRACT and 'gfx_power_off_scope' not in trial and
            'gfx_reset_scope' not in trial, 'Unknown or mixed paired coordination contract')
    # Reuse the unchanged retained lifetime/kernel checks on a local view.
    # The real receipt lacks the old scope key so old runners refuse it.
    view = copy.deepcopy(receipt)
    view['graph_recovery_trial'].pop('gfx_coordinated_power_off_scope')
    view['graph_recovery_trial']['gfx_power_off_scope'] = BASE_CONTRACT
    return validate_base_receipt(view)
