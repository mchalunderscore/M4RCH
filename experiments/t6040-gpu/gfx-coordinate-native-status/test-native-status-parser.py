#!/usr/bin/env python3
"""RAM-only qualification of the actual native STATUS0 startup parser."""
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import gfx_native_status_contract as contract

OBS_MARKER = 'm4rch gfx-coordinate-observation: '
OWNER_MARKER = 'm4rch gfx-coordinate-owner: '
WORDS = ('request_before', 'request_written', 'ack_payload', 'ack_status',
         'status_payload', 'status_raw')
OBS = dict(enabled='1', result='0', request_attempted='1', request_acked='1',
           ack_bypassed='0', ack_samples='1', votes_attempted='3', votes_verified='3',
           request_before='0x8000000000004000', request_written='0x8000000000006000',
           ack_payload='0x2000', ack_status='0x2', status_payload='0x1', status_raw='0')
OWNER = dict(phase='post-active-on', result='0', startup_retained='1',
             module_pinned='1', pmp_region='1', pmc_region='1', pmp_mapped='1',
             pmc_mapped='1', on_attempted='1', on_complete='1', off_attempted='0',
             off_complete='0', held='1', started='0', retirement_verified='0')
REPORT = dict(root_published=True, mapping_or_publication_performed=True)
CASES = []
paths = [Path(__file__), HERE / 'gfx_native_status_contract.py',
         HERE / 'gfx-coordinate-core.h',
         HERE.parent / 'gfx-native-coordinate-trial/gfx_coordinate_contract.py',
         HERE.parent / 'gfx-coordinate-execution/gfx_execution_contract.py',
         HERE.parent / 'gfx-poweroff-trial/gfx_poweroff_contract.py',
         HERE.parent / 'gfx_reset_contract.py']
before = {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
          for path in paths}


def line(marker, fields):
    return marker + ' '.join(key + '=' + value for key, value in fields.items())


def evaluate(obs=None, owner=None, report=None, returncode=0, refcount=1,
             on_lines=None, owner_lines=None):
    return contract.qualify_graph_startup(
        [line(OBS_MARKER, OBS if obs is None else obs)] if on_lines is None else on_lines,
        [line(OWNER_MARKER, OWNER if owner is None else owner)] if owner_lines is None else owner_lines,
        returncode, refcount, REPORT if report is None else report)


def check(name, expected, **arguments):
    actual = evaluate(**arguments)
    if actual is not expected:
        raise AssertionError(name + ': expected ' + repr(expected) + ', observed ' + repr(actual))
    CASES.append({'case': name, 'passed': True})


def bypass(samples=0, ack_payload='0', ack_status='0'):
    return dict(OBS, ack_bypassed='1', request_acked='0', status_payload='0',
                ack_samples=str(samples), ack_payload=ack_payload, ack_status=ack_status)


check('nonzero-status-valid-matching-ack', True)
check('nonzero-status-max-samples', True, obs=dict(OBS, ack_samples='15001'))
check('nonzero-status-ack-unrelated-bits-differ', True,
      obs=dict(OBS, ack_payload='0x40002000', ack_status='0x102'))
check('nonzero-status-zero-raw-status-not-inactivity-proof', True,
      obs=dict(OBS, status_raw='0'))
check('full64-high-request-bits-preserved', True,
      obs=dict(OBS, request_before='0x9000000000000081', request_written='0x9000000000002081'))
check('request-bit-already-on-is-preserved', True,
      obs=dict(OBS, request_before=OBS['request_written']))
check('dmesg-prefix-is-accepted', True,
      on_lines=['[   12.345678] ' + line(OBS_MARKER, OBS)],
      owner_lines=['[   12.345679] ' + line(OWNER_MARKER, OWNER)])
check('status0-no-ack-wait-observation', True, obs=bypass())
check('status0-prior-unmatched-valid-ack', True, obs=bypass(1, '0x4000', '0x2'))
check('status0-prior-matching-payload-invalid-raw-ack', True, obs=bypass(4, '0x2000', '0x1'))
check('status0-prior-zero-invalid-ack', True, obs=bypass(8))
check('status0-declared-sample-bound', True, obs=bypass(15001, '0', '0x2'))

# Every supplied ACK-valid/target-bit combination is checked in both branches.
for raw_valid in (False, True):
    for target_bit in (False, True):
        payload = '0x2000' if target_bit else '0'
        raw = '0x2' if raw_valid else '0'
        check('nonzero-ack-matrix-valid%d-target%d' % (raw_valid, target_bit),
              raw_valid and target_bit, obs=dict(OBS, ack_payload=payload, ack_status=raw))
        check('bypass-prior-ack-matrix-valid%d-target%d' % (raw_valid, target_bit),
              not (raw_valid and target_bit), obs=bypass(1, payload, raw))

for name, obs in [
    ('bypass-claims-ack', dict(bypass(), request_acked='1')),
    ('bypass-nonzero-status', dict(bypass(), status_payload='1')),
    ('bypass-no-samples-nonzero-ack-payload', bypass(0, '0x2000', '0')),
    ('bypass-no-samples-nonzero-ack-status', bypass(0, '0', '0x2')),
    ('bypass-prior-valid-matching-ack', bypass(1, '0x2000', '0x2')),
    ('bypass-prior-valid-matching-ack-extra-bits', bypass(9, '0x8000000000002000', '0x102')),
    ('ack-claims-bypass', dict(OBS, ack_bypassed='1')),
    ('ack-zero-latest-status', dict(OBS, status_payload='0')),
    ('ack-not-acked', dict(OBS, request_acked='0')),
    ('ack-zero-samples', dict(OBS, ack_samples='0')),
    ('ack-wrong-target-bit', dict(OBS, ack_payload='0')),
    ('ack-no-raw-bit1', dict(OBS, ack_status='0x1')),
    ('unknown-bypass-selector', dict(OBS, ack_bypassed='2')),
    ('hex-bypass-selector', dict(OBS, ack_bypassed='0x0')),
    ('hex-acked-selector', dict(OBS, request_acked='0x1')),
    ('request-unrelated-high-bit-cleared', dict(OBS, request_written='0x6000')),
    ('request-unrelated-low-bit-added', dict(OBS, request_written='0x8000000000006001')),
    ('request-target-bit-cleared', dict(OBS, request_written='0x8000000000004000')),
    ('request-before-would-produce-all-ones', dict(OBS,
        request_before=hex(0xffffffffffffffff & ~0x2000), request_written='0xffffffffffffffff')),
]:
    check(name, False, obs=obs)

for mode, base in [('ack', OBS), ('bypass', bypass())]:
    for samples in ('-1', '15002', '0x100000000', '1junk', '00'):
        check(mode + '-invalid-sample-count-' + samples, False,
              obs=dict(base, ack_samples=samples))
    for key in WORDS:
        for value in ('-1', '0xffffffffffffffff', '0x10000000000000000',
                      '18446744073709551616', '0x1junk'):
            check(mode + '-invalid-word-' + key + '-' + value, False,
                  obs=dict(base, **{key: value}))
    for key in base:
        changed = dict(base)
        changed.pop(key)
        check(mode + '-missing-observation-' + key, False, obs=changed)
        record = line(OBS_MARKER, base)
        for appended in (base[key], '1' if base[key] != '1' else '0'):
            check(mode + '-duplicate-observation-' + key + '-' + appended, False,
                  on_lines=[record + ' ' + key + '=' + appended])
    for key, value in [('enabled', '0'), ('result', '-5'), ('request_attempted', '0'),
                       ('votes_attempted', '2'), ('votes_verified', '2')]:
        check(mode + '-wrong-observation-' + key, False, obs=dict(base, **{key: value}))

for key, value in OWNER.items():
    missing = dict(OWNER)
    missing.pop(key)
    check('missing-owner-' + key, False, owner=missing)
    wrong = 'pre-active-on' if key == 'phase' else ('0' if value == '1' else '1')
    check('wrong-owner-' + key, False, owner=dict(OWNER, **{key: wrong}))
    check('duplicate-owner-' + key, False,
          owner_lines=[line(OWNER_MARKER, OWNER) + ' ' + key + '=' + value])

for marker, record, argument in [(OBS_MARKER, line(OBS_MARKER, OBS), 'on_lines'),
                                (OWNER_MARKER, line(OWNER_MARKER, OWNER), 'owner_lines')]:
    for name, records in [('missing-record', []), ('two-records', [record, record]),
                          ('wrong-prefix', [record.replace(marker, 'unqualified: ')]),
                          ('two-prefixes', [marker + record]),
                          ('malformed-extra-field', [record + ' extra=0x1junk'])]:
        check(argument + '-' + name, False, **{argument: records})

for key in REPORT:
    missing = dict(REPORT)
    missing.pop(key)
    check('missing-report-' + key, False, report=missing)
    for value in (False, None, 1, 'true'):
        check('wrong-report-' + key + '-' + repr(value), False,
              report=dict(REPORT, **{key: value}))
for value in (1, -1, None, '0'):
    check('failed-or-invalid-load-' + repr(value), False, returncode=value)
for value in (0, -1, None, '1'):
    check('missing-or-invalid-pin-' + repr(value), False, refcount=value)
check('positive-pinned-refcount-two', True, refcount=2)

# Family isolation uses an existing qualified execution receipt in RAM only.
receipt_path = REPO / 'out/gfx-coordinate-execution/candidate/asc-root-envelope/build-receipt.json'
if not receipt_path.is_file():
    raise ValueError('Existing execution receipt is required for family-isolation qualification')
original_receipt = json.loads(receipt_path.read_text())
native_receipt = copy.deepcopy(original_receipt)
trial = native_receipt['graph_recovery_trial']
trial.pop('gfx_coordinated_execution_scope')
trial[contract.FAMILY_KEY] = copy.deepcopy(contract.CONTRACT)
assert contract.validate_receipt(native_receipt) is True
CASES.append({'case': 'separate-native-status-family-qualifies', 'passed': True})
assert contract.validate_receipt(original_receipt) is False
CASES.append({'case': 'old-execution-family-refused', 'passed': True})
for family in ('gfx_coordinated_execution_scope', 'gfx_coordinated_power_off_scope',
               'gfx_power_off_scope', 'gfx_reset_scope'):
    mixed = copy.deepcopy(native_receipt)
    mixed['graph_recovery_trial'][family] = {}
    try:
        contract.validate_receipt(mixed)
    except ValueError:
        CASES.append({'case': 'mixed-family-refused-' + family, 'passed': True})
    else:
        raise AssertionError('Mixed receipt admitted: ' + family)
assert not contract.CONTRACT['status_zero_is_acknowledgement']
assert not contract.CONTRACT['zero_status_proves_inactivity']
assert not contract.CONTRACT['rendering_verified']
CASES.append({'case': 'bypass-does-not-claim-ack-inactivity-or-rendering', 'passed': True})

after = {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
if before != after:
    raise ValueError('Parser/test inputs changed during qualification')
inputs = [{'path': path, 'sha256': digest} for path, digest in before.items()]
inputs.append({'path': str(receipt_path), 'sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest()})
receipt = {
    'schema': 'm4rch.gfx-native-status-parser-qualification.v1',
    'passed': True, 'hardware_access': False, 'case_count': len(CASES),
    'inputs': inputs, 'cases': CASES, 'hardware_actions': [], 'candidate_build_actions': [],
    'qualification': 'Actual native STATUS0 helper and inherited record parser called in RAM. Valid ACK, zero-sample bypass and prior-unmatched-sample bypass are separate; malformed/contradictory observations, altered full requests and unqualified owners/reports refuse. Receipt families remain distinct.',
    'limitations': [
        'Software log parsing is qualified; core/adapter MMIO, timeout behavior and real PMP policy are not executed by this test.',
        'STATUS0 bypass is neither acknowledgement nor proof of inactivity, work execution, completion, rendering or DMA retirement.',
        'The declared parser sample interval is 0..15001 for bypass; this parser test does not establish reachability of every count in the current C loop.',
    ],
}
destination = REPO / 'out/gfx-coordinate-native-status/parser-qualification.json'
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'receipt': str(destination), 'passed': True,
                  'hardware_access': False, 'case_count': len(CASES)}))
