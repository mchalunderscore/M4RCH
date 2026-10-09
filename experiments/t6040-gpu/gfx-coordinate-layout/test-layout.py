#!/usr/bin/env python3
"""Qualify the inspected metadata delta and unchanged wrapper transforms."""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import gfx_layout_contract as contract

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

candidate = ROOT / 'out/gfx-native-coordinate-layout/candidate'
receipt = json.loads((candidate / 'asc-root-envelope/build-receipt.json').read_text())
cold = runpy.run_path(str(HERE / 'run-root-coordinate.py'))
resident = runpy.run_path(str(HERE / 'run-coordinate.py'))
cases = []
def check(name, function, expected):
    try:
        accepted = function() is not False
    except (ValueError, KeyError):
        accepted = False
    assert accepted == expected, name
    cases.append({'case': name, 'passed': True})

check('fresh-layout-receipt', lambda: contract.validate_receipt(receipt), True)
check('same-cold-parameters', lambda: cold['owner_parameters'](receipt, graph=True) ==
      ['run_gate=2', 'observe_ms=5000', 'resident_session=1'], True)
old = json.loads((ROOT / 'out/gfx-native-coordinate/candidate/asc-root-envelope/build-receipt.json').read_text())
check('old-layout-receipt-refuses', lambda: contract.validate_receipt(old), False)
check('old-cold-wrapper-refuses-fresh-layout', lambda: contract.frozen.validate_receipt(receipt), False)
state = dict(submit_attempted=False, host_stop_requested=True,
             power_off_attempted=False, in_flight=None)
check('same-eligible-no-work-off', lambda: resident['admit_command']('gfx-poweroff', receipt, state), True)
for command in ('submit', 'recover', 'gfx-reset'):
    check('no-expanded-command-' + command, lambda c=command: resident['admit_command'](c, receipt, state), False)
check('same-after-off-seal', lambda: resident['admit_command']('stop', receipt,
      dict(state, power_off_attempted=True)), False)
check('actual-current-metadata-matches', contract.qualify_linux_dt, True)
layout = json.loads((HERE / 'linux-dt-contract.json').read_text())
with tempfile.TemporaryDirectory(prefix='gfx-inspected-of-') as directory:
    base = Path(directory)
    for node in layout:
        path = base / node['node'].lstrip('/')
        path.mkdir(parents=True, exist_ok=True)
        for key, data in node['properties'].items():
            (path / key).write_bytes(bytes.fromhex(data))
    check('actual-parser-exact-312-node-fixture', lambda: contract.qualify_linux_dt(base), True)
    target = base / 'reserved-memory/flash@10005cf8000/reg'
    before = target.read_bytes()
    target.write_bytes(before[:-4])
    check('malformed-flash-tuple-refuses', lambda: contract.qualify_linux_dt(base), False)
    target.write_bytes(before)
    alias = base / 'soc/competing-coordinate-alias'
    alias.mkdir()
    (alias / 'reg').write_bytes(bytes.fromhex('00000005003c00000000000000030000'))
    check('added-resource-alias-refuses', lambda: contract.qualify_linux_dt(base), False)

for module in (cold, resident):
    compile(module['runner_source'](), str(module['BASE']), 'exec')
    cases.append({'case': 'actual-' + str(module['BASE'].name) + '-transform-compiles', 'passed': True})
result = {'schema': 'm4rch.gfx-inspected-of-layout-qualification.v1',
          'passed': True, 'hardware_access': False, 'case_count': len(cases), 'cases': cases,
          'input_pins': [{'path': str(p), 'sha256': sha(p)} for p in
              [HERE / n for n in ('gfx_layout_contract.py', 'run-root-coordinate.py',
                                  'run-coordinate.py', 'linux-dt-contract.json', Path(__file__).name)]],
          'qualification': 'One explicit flash relocation; fresh exact metadata matching remains mandatory. Frozen 353-case cold/typed flow and actual owner are unchanged. No GPU helper, START, MMIO or powered sampler accessed.'}
with Path(sys.argv[1]).open('x') as f:
    json.dump(result, f, indent=2)
    f.write('\n')
print(f'{len(cases)} inspected-layout checks passed; no hardware access')
