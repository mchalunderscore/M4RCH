#!/usr/bin/env python3
"""Replay the actual saved STOP pair; no main, sysfs or hardware operation."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

kit = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('confirm_stop', kit / 'confirm-stop.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    ops = helper.ROOT / 'out/gfx-poweroff-scope/candidate/asc-graph-init/boot-339b9e8e-4535-4550-97d6-840301c6baac/resident-operations'
    first = ops / '20261009T171443.925871Z-stop-23455b86'
    second = ops / '20261009T171500.207792Z-gfx-snapshot-21de0970'
    actual = [json.loads((first / 'attempt.json').read_text()),
              json.loads((second / 'attempt.json').read_text()),
              helper.fresh_rows(first), helper.fresh_rows(second)]
    helper.qualify(*copy.deepcopy(actual))
    cases = []

    def changed(label, mutate):
        data = copy.deepcopy(actual)
        mutate(data)
        try:
            helper.qualify(*data)
        except (ValueError, KeyError):
            cases.append({'case': label, 'rejected': True})
            return
        raise AssertionError('Accepted invalid confirmation: ' + label)

    def text(data, index, old, new):
        data[index] = [line.replace(old, new) for line in data[index]]

    changed('unknown-error', lambda d: d[0].update(error='OSError(5)'))
    changed('interruption', lambda d: d[0]['commands'][0].update(result='KeyboardInterrupt()'))
    changed('short-write', lambda d: d[0]['commands'][0].update(result='ValueError(short write)'))
    changed('no-completion', lambda d: d[1].update(complete=False))
    changed('prior-PM', lambda d: text(d, 3, 'pm_attempted=0', 'pm_attempted=1'))
    changed('gate-consumed', lambda d: text(d, 3, 'gate_consumed=0', 'gate_consumed=1'))
    changed('START-not-clear', lambda d: text(d, 3, 'control44=0x0', 'control44=0x10'))
    changed('idle-missing', lambda d: text(d, 3, 'status48=0x4e', 'status48=0x4c'))
    changed('usage-not-one', lambda d: text(d, 3, 'usage_count=1', 'usage_count=0'))
    changed('PM-error', lambda d: text(d, 3, 'runtime_error=0', 'runtime_error=-5'))
    changed('unexpected-stop-result', lambda d: text(d, 2, 'result=-11', 'result=-5'))
    changed('intervening-operation', lambda d: text(d, 3, 'operation=3', 'operation=4'))
    changed('duplicate-Cresult', lambda d: d[3].extend(line for line in d[3][:] if 'gfx-poweroff-result:' in line))
    changed('OFF-intent-in-report', lambda d: d[1].update(power_off_attempted=True))
    changed('work-intent-in-report', lambda d: d[1].update(submit_attempted=True))
    changed('PMGR-OFF', lambda d: text(d, 3, 'domain_on=1', 'domain_on=0'))
    changed('PMGR-busy', lambda d: text(d, 3, 'value=0x1f0003ff', 'value=0x1f000bff'))
    paths = [kit / 'confirm-stop.py', Path(__file__).resolve()]
    paths += [directory / name for directory in (first, second)
              for name in ('attempt.json', 'dmesg-before.log', 'dmesg-after.log')]
    result = {'schema': 'm4rch.known-stop-eagain-replay.v1',
              'actual_saved_pair_passed': True, 'negative_case_count': len(cases),
              'negative_cases': cases, 'hardware_access': False,
              'files': [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                        for path in paths],
              'qualification': 'Actual pure qualifier only; no main, state mutation or hardware action.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print('Actual saved pair passed and 17 targeted negative cases rejected; no hardware access.')


if __name__ == '__main__':
    main()
