#!/usr/bin/env python3
"""Bind the exact prepared owner and saved captures before frozen analysis.

Offline only. Does not replace the pinned analyzer, infer device execution or
authorize access to hardware, reset, restart, retirement or backing release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASE_KIT = HERE.parent
sys.path.insert(0, str(HERE))
from gfx_native_status_contract import validate_receipt

RECEIPT_SHA = '2f45d761f1ba9a4b95bdb1a848c06aae9a47740cf4536ce39dc45dddd19ae29c'
PREPARATION_SHA = 'af522a6f563d2bdc194c0a30fc31dc3bc9d21fa872bad2557a29e483c6cacbf2'
ANALYZER_SHA = '4e74885c8b11cea96e12581225e5f78fae8b554b8d1b573d1753d0b5f596d541'
TEXT_CONTRACT_SHA = '4e26c2e87486970e0c8a62017760f2c95ebf24ab96e5fef65e54107ff96d3e2f'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def relative_file(base, relative):
    path = (base / relative).resolve()
    require(path.is_relative_to(base), 'Input escapes candidate: ' + relative)
    return path


def qualify(candidate, capture):
    """Read regular saved files only; checks do not form an atomic snapshot."""
    pins = {}

    def bind(path, expected, reason):
        require(digest(path) == expected, reason)
        pins[str(path)] = expected

    receipt_path = candidate / 'asc-root-envelope/build-receipt.json'
    preparation_path = candidate / 'native-status-preparation.json'
    bind(receipt_path, RECEIPT_SHA, 'Exact native-status candidate receipt changed')
    bind(preparation_path, PREPARATION_SHA, 'Exact native-status preparation changed')
    receipt, prepared = load(receipt_path), load(preparation_path)
    require(validate_receipt(receipt), 'Distinct native-status execution receipt required')
    require(prepared['candidate_receipt_sha256'] == RECEIPT_SHA,
            'Preparation receipt identity mismatch')
    for name, expected in receipt['artifact_sha256'].items():
        bind(relative_file(candidate, name), expected, 'Artifact changed: ' + name)
    for name, expected in receipt['graph_source_sha256'].items():
        bind(relative_file(candidate, 'asc-graph-init/' + name), expected,
             'Graph source changed: ' + name)
    bind(candidate / 'asc-graph-init/graph-before.bin', receipt['graph_fixture_sha256'],
         'Prepared graph fixture changed')
    bind(candidate / 'asc-graph-init/graph-receipt.json', receipt['graph_receipt_sha256'],
         'Prepared graph metadata changed')
    for pin in prepared['analysis_input_pins']:
        bind(relative_file(candidate, pin['relative']), pin['sha256'],
             'Analysis input changed: ' + pin['relative'])
    draw = load(candidate / 'asc-graph-init/preparation.json')
    backing = candidate / 'asc-graph-init/backing.bin'
    require(draw['pages'] == 56 and backing.stat().st_size == draw['pages'] * 16384,
            'Prepared draw backing extent changed')
    bind(backing, draw['data_sha256'], 'Prepared draw backing changed')
    for pin in prepared['analysis_tool_pins']:
        bind(Path(pin['path']).resolve(), pin['sha256'], 'Frozen analysis tool changed')
    analyzer = HERE / 'analyze-execution.py'
    bind(analyzer, ANALYZER_SHA, 'Frozen analysis launcher changed')
    text_contract = BASE_KIT / 'firmware_text_contract.py'
    bind(text_contract, TEXT_CONTRACT_SHA, 'Frozen TEXT contract changed')
    report_path = capture / 'attempt.json'
    report = load(report_path)
    pins[str(report_path)] = digest(report_path)
    require(report['validated_build_receipt'] == receipt,
            'Capture candidate differs from prepared owner')
    require(report['submit_attempted'] is True, 'Capture has no submitted-work intent')
    boot = report['boot_id']
    require(isinstance(boot, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', boot),
            'Capture boot identifier is malformed')
    for name, expected_bytes in [('objects', receipt['graph_object_pages'] * 16384),
                                 ('owned', receipt['joined_owned_pages'] * 16384)]:
        path = capture / (name + '-after.bin')
        observation = report['final_capture'][name]
        require(observation.get('bytes') == expected_bytes,
                'Reported capture extent differs: ' + name)
        require(path.stat().st_size == expected_bytes, 'Capture is short or oversized: ' + name)
        bind(path, observation['sha256'], 'Saved capture changed: ' + name)
    bind(capture / 'dmesg-after.log', report['final_capture']['dmesg']['sha256'],
         'Saved capture changed: dmesg')
    # Resident analysis copies the originally qualified TEXT; it never samples
    # firmware DATA. Bind that copy to the original cold-session raw identity.
    initial = candidate / 'asc-graph-init' / ('boot-' + boot)
    require(Path(report['initial_session']).resolve() == initial,
            'Capture original-session path differs')
    original_path = initial / 'attempt.json'
    original = load(original_path)
    pins[str(original_path)] = digest(original_path)
    require(original['boot_id'] == boot and original['validated_build_receipt'] == receipt,
            'Original session boot/candidate differs')
    bind(initial / 'text.bin', original['text_sha256'], 'Original TEXT evidence changed')
    bind(capture / 'text.bin', original['text_sha256'], 'Copied TEXT evidence changed')
    runpy.run_path(str(text_contract))['qualify']((capture / 'text.bin').read_bytes())
    require(not (capture / 'data-after.bin').exists() and not (capture / 'data-before.bin').exists(),
            'Resident analysis does not admit unbound firmware DATA files')
    return report, pins


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('capture', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    candidate, capture, output = (path.resolve() for path in
                                   (args.candidate, args.capture, args.output))
    require(not output.exists(), 'Never overwrite saved analysis')
    require(not output.is_relative_to(candidate), 'Analysis output must be outside frozen candidate')
    report, pins = qualify(candidate, capture)
    result = subprocess.run([sys.executable, str(HERE / 'analyze-execution.py'),
                             str(candidate), str(capture), str(output)],
                            capture_output=True, text=True)
    # Saved files and tools remain qualified after the non-atomic delegation.
    for name, expected in pins.items():
        require(digest(Path(name)) == expected, 'Saved analysis input changed during delegation')
    require(result.returncode == 0, 'Frozen analysis failed: ' + result.stderr.strip())
    qualification = {
        'schema': 'm4rch.gfx-native-status-checked-analysis.v1',
        'candidate_receipt_sha256': RECEIPT_SHA, 'preparation_sha256': PREPARATION_SHA,
        'boot_id': report['boot_id'], 'hardware_access': False,
        'gpu_execution_verified': False, 'retirement_verified': False,
        'inputs': [{'path': name, 'sha256': expected} for name, expected in sorted(pins.items())],
        'qualification': 'Exact saved candidate, graph metadata and final captures bound before frozen analysis and rechecked after delegation. Checks are not atomic. Eight target samples, boot log history and queue cursors do not prove execution, completion, all-pixel correctness, synchronization or retirement. Receive journal requires separate review.'}
    (output / 'checked-binding.json').write_text(json.dumps(qualification, indent=2) + '\n')
    sys.stdout.write(result.stdout)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, TypeError) as error:
        print('Checked saved execution analysis refused: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
