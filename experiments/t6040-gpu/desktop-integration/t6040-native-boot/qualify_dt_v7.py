#!/usr/bin/env python3
"""Exercise the new actual DT resource/input bridge, entirely offline."""
import argparse
import json
from pathlib import Path
import subprocess

import libfdt
from native_adt_bridge_v7 import bridge, node_properties, pin
from prepare_dt_v7 import candidate, original, GPU, MAILBOX, REGIONS

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]


def qualify(stage, destination):
    destination = destination.resolve()
    destination.relative_to(ROOT / 'out')
    destination.mkdir(parents=True, exist_ok=False)
    receipt_path = stage / 'dt-stage-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    if receipt['schema'] != 'm4rch.gravity-native-t6040.dt.stage.v7':
        raise ValueError('New native DT resource stage required')
    for row in receipt['inputs'] + [receipt['output']]:
        if pin(row['path']) != row:
            raise ValueError('DT stage input changed: ' + row['path'])
    adt = next(Path(row['path']) for row in receipt['inputs'] if row['path'].endswith('/boot.adt'))
    dtb = next(Path(row['path']) for row in receipt['inputs'] if row['path'].endswith('/kernel-live-of.dtb'))
    tree, parser = original(adt)
    selected = Path(receipt['output']['path']).read_bytes()
    replay, details = candidate(dtb.read_bytes(), tree)
    if replay != selected or json.loads(json.dumps(details)) != receipt['details']:
        raise ValueError('Actual new DT producer is not deterministic')
    props = node_properties(selected)
    assert props[GPU]['status'] == b'disabled\0'
    assert props[MAILBOX]['status'] == b'disabled\0'
    assert props[GPU]['apple,firmware-build'] == b'mBoot-18000.161.10\0'
    assert props[GPU]['apple,chip-revision'] == b'\0\0\0\x11'
    for name in REGIONS:
        node = props['/reserved-memory/gpu-' + name]
        assert node['status'] == b'disabled\0' and 'reg' not in node
    sgx = tree['/device-tree/arm-io/sgx']
    assert len(sgx) == 53
    assert all(props[GPU]['apple,sgx-' + name] == raw for name, raw in sgx.items())
    assert 'apple,m4-max-power-mw' not in props[GPU]
    assert 'apple,m4-core-masks' not in props[GPU]
    cases = [{'name': 'actual saved ADT + saved Linux DT deterministic whole production', 'pass': True},
             {'name': 'disabled resources with five missing loader-owned reg extents', 'pass': True},
             {'name': '53 exact raw aliases and distinct firmware/revision metadata', 'pass': True}]

    # Exercise the actual bridge's deletion path, which is essential for native
    # absent-property defaults when a loader carries an older modeled value.
    fdt = libfdt.Fdt(selected)
    fdt.resize(fdt.totalsize() + 1024)
    fdt.setprop(fdt.path_offset(GPU), 'apple,sgx-stale-absent-value', b'\x01\0\0\0')
    fdt.setprop(fdt.path_offset(GPU), 'unrelated-test-marker', b'preserve\0')
    fdt.pack()
    repaired, _ = bridge(bytes(fdt.as_bytearray()), sgx, GPU)
    after = node_properties(repaired)
    assert 'apple,sgx-stale-absent-value' not in after[GPU]
    assert after[GPU]['unrelated-test-marker'] == b'preserve\0'
    cases.append({'name': 'actual bridge deletes stale raw default while preserving unrelated metadata', 'pass': True})
    no_aic = dict(sgx)
    del no_aic['gpu-pwr-sample-period-aic-clks']
    changed, _ = bridge(selected, no_aic, GPU)
    assert 'apple,sgx-gpu-pwr-sample-period-aic-clks' not in node_properties(changed)[GPU]
    cases.append({'name': 'absent native AIC input stays absent instead of inheriting stale alias', 'pass': True})

    malformed = {name: dict(value) for name, value in tree.items()}
    malformed['/device-tree/arm-io/sgx']['reg'] = b'\0' * 32
    try:
        candidate(dtb.read_bytes(), malformed)
    except ValueError:
        cases.append({'name': 'unsupported original resource refuses before mutation', 'pass': True})
    else:
        raise AssertionError('Malformed original resources accepted')
    try:
        candidate(selected, tree)
    except ValueError:
        cases.append({'name': 'existing native GPU node refuses replacement', 'pass': True})
    else:
        raise AssertionError('Existing node replaced')
    dtc = ROOT / 'out/gfx-native-reset-kernel/linux/scripts/dtc/dtc'
    dts = destination / 'candidate.dts'
    errors = destination / 'dtc-stderr.txt'
    with errors.open('xb') as stderr:
        process = subprocess.run([str(dtc), '-I', 'dtb', '-O', 'dts', '-o', str(dts),
                                  receipt['output']['path']], stderr=stderr, check=False)
    if process.returncode:
        raise ValueError('Actual DT compiler rejected native candidate')
    roundtrip = destination / 'roundtrip.dtb'
    with errors.open('ab') as stderr:
        process2 = subprocess.run([str(dtc), '-I', 'dts', '-O', 'dtb', '-o', str(roundtrip), str(dts)],
                                   stderr=stderr, check=False)
    if process2.returncode or node_properties(roundtrip.read_bytes()) != props:
        raise ValueError('DT compiler changed the semantic native candidate')
    cases.append({'name': 'actual dtc decode/recompile preserves every semantic property', 'pass': True})
    report = {'schema': 'm4rch.gravity-native-t6040.dt.qualification.v7',
              'inputs': [pin(p) for p in [Path(__file__), receipt_path, parser, dtc]]
                        + receipt['inputs'] + [receipt['output']],
              'cases': cases, 'case_count': len(cases), 'complete': True,
              'raw_property_count': 53, 'dtc_returncodes': [process.returncode, process2.returncode],
              'dtc_diagnostics': pin(errors), 'normal_startup_enabled': False,
              'live_loader_contract_complete': False, 'system_installed': False,
              'hardware_actions': []}
    (destination / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'complete': True, 'case_count': len(cases), 'report': pin(destination / 'qualification.json')}))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    qualify(args.stage.resolve(), args.destination)
