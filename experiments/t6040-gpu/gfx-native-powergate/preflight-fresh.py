#!/usr/bin/env python3
"""Read-only fresh-boot candidate/kernel/USB/OF preflight; no GPU operation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gfx_native_powergate_contract import validate_receipt, qualify_linux_dt, REFUSED_BOOT
from gfx_reset_contract import require


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_candidate(candidate):
    receipt_path = candidate / 'asc-root-envelope/build-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    require(validate_receipt(receipt), 'Distinct powergate receipt required')
    prep_path = candidate / 'powergate-preparation.json'
    prep = json.loads(prep_path.read_text())
    require(prep.get('schema') == 'm4rch.gfx-native-powergate-preparation.v1' and
            prep.get('candidate_receipt_sha256') == sha(receipt_path) and
            prep.get('selected_next_hardware_candidate') is True and
            prep.get('hardware_actions') == [], 'Powergate preparation changed')
    require(prep['owner_sha256'] == receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'],
            'Prepared owner differs')
    for name, expected in receipt['artifact_sha256'].items():
        path = (candidate / name).resolve()
        require(path.is_relative_to(candidate) and sha(path) == expected, 'Artifact changed: ' + name)
    for name, expected in receipt['graph_source_sha256'].items():
        require('/' not in name and sha(candidate / 'asc-graph-init' / name) == expected,
                'Prepared source changed: ' + name)
    for name, key in [('graph-before.bin', 'graph_fixture_sha256'), ('graph-receipt.json', 'graph_receipt_sha256')]:
        require(sha(candidate / 'asc-graph-init' / name) == receipt[key], 'Prepared graph changed: ' + name)
    for pin in prep['inputs']:
        require(sha(Path(pin['path'])) == pin['sha256'], 'Preparation input changed: ' + pin['path'])
    for pin in prep.get('analysis_input_pins', []):
        require(sha(candidate / pin['relative']) == pin['sha256'], 'Dormant analysis metadata changed')
    return receipt, prep


def qualify_fresh_boot(boot, modules):
    require(boot != REFUSED_BOOT and bool(boot), 'Retained 94cb owner boot refused; fresh normal boot required')
    conflicts = []
    for line in modules.splitlines():
        words = line.split()
        require(bool(words), 'Malformed module inventory')
        name = words[0]
        if name.startswith('asc_') or name in ('asahi_m4', 'resource_overlay', 'gfx_power_test', 'gpu_data_sample', 'm4rch_gpu_adt'):
            conflicts.append(name)
    require(not conflicts, 'Conflicting modules: ' + ','.join(conflicts))
    return conflicts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    conflicts = qualify_fresh_boot(boot, Path('/proc/modules').read_text())
    receipt, prep = validate_candidate(candidate)
    require(os.uname().release == receipt['kernel_release'] and
            sha(Path('/sys/kernel/notes')) == receipt['kernel_notes_sha256'], 'Kernel identity differs')
    require(not (candidate / 'asc-graph-init' / ('boot-' + boot) / 'attempt.json').exists(),
            'An attempt already exists for this boot')
    bindings = []
    for name in ('0-0a', '0-0c', '2-0c'):
        driver = (Path('/sys/bus/spmi/devices') / name / 'driver').resolve(strict=True)
        require(str(driver) == '/sys/bus/spmi/drivers/tps6598x-spmi', 'PD provider differs')
        bindings.append({'device': name, 'driver': str(driver)})
    roles = sorted(p.name for p in Path('/sys/class/usb_role').iterdir())
    require(roles == ['382280000.usb-role-switch', '38a280000.usb-role-switch', '392280000.usb-role-switch'],
            'USB role providers differ')
    usb = Path('/usr/lib/modules') / receipt['kernel_release'] / 'kernel/drivers/usb/dwc3/dwc3-apple.ko'
    require(sha(usb) == '0c52d7c40156465674ba0fec752e6d137d4bf38354b415770cb62db3748a647e', 'USB driver differs')
    note_reader = runpy.run_path(str(HERE / 'run-powergate.py'))['module_build_note']
    require(Path('/sys/module/dwc3_apple/notes/.note.gnu.build-id').read_bytes() == note_reader(usb.read_bytes()),
            'Loaded USB driver differs')
    layout = qualify_linux_dt()
    result = {'schema': 'm4rch.gfx-native-powergate-fresh-preflight.v1', 'boot_id': boot,
        'kernel_release': os.uname().release, 'kernel_notes_sha256': receipt['kernel_notes_sha256'],
        'candidate_receipt_sha256': sha(candidate / 'asc-root-envelope/build-receipt.json'),
        'owner_sha256': prep['owner_sha256'], 'artifact_pins_checked': len(receipt['artifact_sha256']),
        'source_pins_checked': len(receipt['graph_source_sha256']), 'conflicting_modules': conflicts,
        'pd_bindings': bindings, 'usb_role_providers': roles, 'dwc3_file_sha256': sha(usb),
        'loaded_dwc3_note_matches_file': True, 'linux_dt_resource_layout': layout,
        'cmdline': Path('/proc/cmdline').read_text().strip(), 'uptime': Path('/proc/uptime').read_text().strip(),
        'helper_sha256': sha(Path(__file__)), 'gpu_operation_performed': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
