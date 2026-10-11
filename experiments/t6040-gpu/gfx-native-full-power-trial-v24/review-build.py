#!/usr/bin/env python3
"""Verify a frozen v24 module receipt and unchanged native triangle inputs.

Offline only. This review does not select READY or perform fresh admission.
Historical qualification scripts may differ from current scripts; the receipt
and exact frozen object are checked, without claiming transitive source identity.
"""
import argparse
import hashlib
import json
import struct
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
    assert '#define GFX_COLD_PAGES ARRAY_SIZE(owned)' in (stage/'gfx-cold-runtime.h').read_text()
    assert 'static_assert(GFX_COLD_PAGES == ARRAY_SIZE(owned));' in (stage/'gfx-cold-render.h').read_text()
    source = json.loads((stage / 'v24-source-receipt.json').read_text())
    old = Path(source['source'])
    preserved = []
    for name in ['job-data.h', 'render-data.h', 'render-backing-map.h',
                 'joined-context-init.h', 'backing.bin']:
        assert (stage/name).read_bytes() == (old/name).read_bytes(), name
        preserved.append(dict(name=name, sha256=digest(stage/name)))
    if (stage/'slot10-patch.json').exists():
        patch=json.loads((stage/'slot10-patch.json').read_text())
        for pin in [*patch['source_pins'],patch['script_pin'],*patch['output_pins']]:
            path=Path(pin['path']);assert path.stat().st_size==pin['bytes'] and digest(path)==pin['sha256']
        base=Path(patch['source_pins'][0]['path']).parent
        before=(base/'graph-before.bin').read_bytes();after=(stage/'graph-before.bin').read_bytes()
        expected=bytearray(before)
        struct.pack_into('<QQIIQI',expected,0x87d0,0x5003c0000,0xfffffc2001b00000,0x4000,0x4000,0,0)
        if (stage/'slot14-patch.json').exists():
            patch14=json.loads((stage/'slot14-patch.json').read_text())
            for pin in [*patch14['source_pins'],patch14['script_pin'],*patch14['output_pins']]:
                path=Path(pin['path']);assert path.stat().st_size==pin['bytes'] and digest(path)==pin['sha256']
            struct.pack_into('<QQIIQI',expected,0x8870,0x500658000,0xfffffc2001b20000,0x10000,0x10000,0,0)
            assert set(patch14['changed_source_files'])=={'graph-contract.h','graph-receipt.json','graph-before.bin'}
        assert after==expected and len(before)==len(after)
        graph=json.loads((stage/'graph-receipt.json').read_text())
        leaves=[x for x in graph['mmio_leaves'] if x['physical']==0x5003c0000]
        assert leaves==[dict(physical=0x5003c0000,gpu_va=0xfffffc2001b00000,readonly=True)]
        assert graph['mapped_pages']==(175 if (stage/'slot14-patch.json').exists() else 171)
        assert ' { 0x5003c0000ULL, 0xfffffc2001b00000ULL, 0 },' in (stage/'graph-contract.h').read_text()
        allowed={'graph-contract.h','graph-receipt.json','graph-before.bin'}
        assert set(patch['changed_source_files'])==allowed
        for name in data['source_changes_from_v9']:
            assert name in allowed
        preserved.append(dict(name='graph-before.bin',sha256=digest(stage/'graph-before.bin'),only_change='Exact slot10 and optional slot14 descriptors; read-only leaves added'))
    else:
        assert (stage/'graph-before.bin').read_bytes()==(old/'graph-before.bin').read_bytes()
        preserved.append(dict(name='graph-before.bin',sha256=digest(stage/'graph-before.bin')))
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
