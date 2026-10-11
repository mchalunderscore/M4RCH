#!/usr/bin/env python3
"""Verify a frozen v24 module receipt and unchanged native triangle inputs.

Offline only. This review does not select READY or perform fresh admission.
Historical qualification scripts may differ from current scripts; the receipt
and exact frozen object are checked, without claiming transitive source identity.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review(receipt, output):
    receipt = Path(receipt).resolve()
    data = json.loads(receipt.read_text())
    assert data['returncode'] == 0 and data['errors'] == 0
    assert data['warnings'] == 0
    assert not data['module_loaded'] and not data['hardware_actions']
    checked = []
    for pin in [data['module'], data['rust_object'], data['log'],
                *data['source_pins'], *data['qualification_pins']]:
        path = Path(pin['path'])
        assert path.stat().st_size == pin['bytes'], path
        assert digest(path) == pin['sha256'], path
        checked.append(str(path))
    stage = Path(data['stage'])
    source = json.loads((stage / 'v24-source-receipt.json').read_text())
    old = Path(source['source'])
    preserved = []
    for name in ['job-data.h', 'render-data.h', 'render-backing-map.h',
                 'joined-context-init.h', 'graph-before.bin', 'backing.bin']:
        assert (stage/name).read_bytes() == (old/name).read_bytes(), name
        preserved.append(dict(name=name, sha256=digest(stage/name)))
    assert data['page_ownership']['current176'] == 176
    assert not data['postdraw_wake_reachable']
    assert not data['postdraw_on_symbol_present']
    result = dict(schema='m4rch.native-v24-frozen-build-root-review.v1',
                  receipt=str(receipt), receipt_sha256=digest(receipt),
                  stage=str(stage), pins_checked=len(checked),
                  preserved_triangle_inputs=preserved,
                  hardware_actions=[], ready=False,
                  scope='Frozen build and triangle preservation; fresh launch and hardware outcomes remain separate')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as f:
        f.write(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(review(args.receipt, args.output)))
