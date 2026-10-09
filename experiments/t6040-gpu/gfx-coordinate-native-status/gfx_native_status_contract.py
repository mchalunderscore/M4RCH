# SPDX-License-Identifier: GPL-2.0-only
"""Separate native STATUS0 success predicate; no inactivity or ACK claim."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE_KIT = HERE.parent
sys.path.insert(0, str(BASE_KIT / 'gfx-coordinate-execution'))
from gfx_execution_contract import CONTRACT as EXECUTION_CONTRACT
from gfx_execution_contract import validate_receipt as validate_execution_receipt
from gfx_coordinate_contract import (qualify_adt, qualify_startup_retention,
                                    record_fields, LINUX_DT_CONTRACT_SHA)
from gfx_reset_contract import require

FLASH_GUARD_SHA = 'abad8c1f67d8d6974672f9790ee6b43ea57c615046ee60339cbf909b0fe9a07d'
FAMILY_KEY = 'gfx_native_status_execution_scope'
CONTRACT = copy.deepcopy(EXECUTION_CONTRACT)
CONTRACT.update({
    'version': 4,
    'native_status_zero_ack_bypass': True,
    'on_order': ['physical-active', 'pmp-request-and-native-success', 'pmc-rail-votes', 'firmware-start'],
    'off_order': ['packet-free-stop', 'pmp-request-and-native-success', 'pmc-rail-votes', 'physical-off'],
    'native_success_predicate': 'After full REQ write: STATUS.payload==0 OR ACK.raw_status.bit1 and matching ACK.bit13; before deadline',
    'native_status_branches': {
        'zero': 'Skip ACK WAIT after REQ; diagnostic ACK preflight remains; not ACK or inactivity',
        'nonzero': 'Read raw ACK; require valid bit1 and requested bit13 before deadline',
    },
    'require_nonzero_status_for_ack_wait': True,
    'success_requires_nonzero_status': False,
    'zero_status_proves_inactivity': False,
    'status_zero_is_acknowledgement': False,
    'status_word_observation_required': True,
    'ack_bypass_and_acknowledgement_mutually_exclusive': True,
    'bounded_single_phram_flash_relocation': True,
    'flash_layout_guard_sha256': FLASH_GUARD_SHA,
})


def validate_receipt(receipt):
    trial = receipt.get('graph_recovery_trial', {})
    selected = trial.get(FAMILY_KEY)
    if selected is None:
        return False
    require(selected == CONTRACT and not any(key in trial for key in
            ('gfx_coordinated_execution_scope', 'gfx_coordinated_power_off_scope',
             'gfx_power_off_scope', 'gfx_reset_scope')),
            'Unknown or mixed native STATUS success contract')
    view = copy.deepcopy(receipt)
    view['graph_recovery_trial'].pop(FAMILY_KEY)
    view['graph_recovery_trial']['gfx_coordinated_execution_scope'] = EXECUTION_CONTRACT
    return validate_execution_receipt(view)


def qualify_linux_dt(base='/sys/firmware/devicetree/base'):
    from linux_dt_contract import encoded_layout
    expected = (BASE_KIT / 'gfx-native-coordinate-trial/linux-dt-contract.json').read_bytes()
    require(hashlib.sha256(expected).hexdigest() == LINUX_DT_CONTRACT_SHA,
            'Frozen Linux resource-layout baseline changed')
    path = HERE / 'flash-layout-guard.py'
    require(hashlib.sha256(path.read_bytes()).hexdigest() == FLASH_GUARD_SHA,
            'Bounded flash resource guard changed')
    spec = importlib.util.spec_from_file_location('native_status_flash_guard', path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    return guard.qualify_flash_layout(expected, encoded_layout(base))


def qualify_graph_startup(on_records, owner_records, returncode, refcount, report):
    try:
        require(returncode == 0 and refcount > 0 and len(on_records) == 1 and
                len(owner_records) == 1 and report.get('root_published') is True and
                report.get('mapping_or_publication_performed') is True,
                'Unqualified native STATUS retained graph startup')
        obs = record_fields(on_records[0], 'm4rch gfx-coordinate-observation: ')
        owner = record_fields(owner_records[0], 'm4rch gfx-coordinate-owner: ', True)
        words = {key: int(obs.get(key, '-1'), 0) for key in
                 ('request_before', 'request_written', 'ack_payload', 'ack_status',
                  'status_payload', 'status_raw')}
        require(all(0 <= value < 0xffffffffffffffff for value in words.values()),
                'Missing, out-of-range or all-ones native STATUS word')
        require(all(obs.get(key) == value for key, value in {
                    'enabled': '1', 'result': '0', 'request_attempted': '1',
                    'votes_attempted': '3', 'votes_verified': '3'}.items()) and
                words['request_written'] == (words['request_before'] | 0x2000),
                'Missing verified request/vote observations')
        samples = int(obs.get('ack_samples', '-1'), 0)
        matched = bool(words['ack_status'] & 2 and words['ack_payload'] & 0x2000)
        if obs.get('ack_bypassed') == '1':
            require(obs.get('request_acked') == '0' and words['status_payload'] == 0 and
                    0 <= samples <= 15001,
                    'Contradictory STATUS0 bypass observation')
            if samples == 0:
                require(words['ack_payload'] == 0 and words['ack_status'] == 0,
                        'Unobserved ACK-wait fields must remain zero')
            else:
                require(not matched, 'A prior matching ACK contradicts the bypass branch')
        else:
            require(obs.get('ack_bypassed') == '0' and obs.get('request_acked') == '1' and
                    words['status_payload'] != 0 and 0 < samples <= 15001 and matched,
                    'Missing acknowledged nonzero-STATUS observation')
        require(all(owner.get(key) == value for key, value in {
                    'phase': 'post-active-on', 'result': '0',
                    'startup_retained': '1', 'module_pinned': '1',
                    'pmp_region': '1', 'pmc_region': '1',
                    'pmp_mapped': '1', 'pmc_mapped': '1',
                    'on_attempted': '1', 'on_complete': '1',
                    'off_attempted': '0', 'off_complete': '0',
                    'held': '1', 'started': '0', 'retirement_verified': '0'}.items()),
                'Unqualified native STATUS ON owner boundary')
    except (ValueError, TypeError):
        return False
    return True
