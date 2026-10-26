#!/usr/bin/env python3
"""Join saved execution cursors, backing changes and target samples offline."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASE_KIT = HERE.parent
sys.path.insert(0, str(HERE))
from gfx_execution_contract import validate_receipt


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate', type=Path)
    p.add_argument('capture', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    candidate, capture = a.candidate.resolve(), a.capture.resolve()
    receipt_path = candidate / 'asc-root-envelope/build-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    assert validate_receipt(receipt), 'Distinct execution receipt required'
    prepared = json.loads((candidate / 'execution-preparation.json').read_text())
    assert digest(receipt_path) == prepared['candidate_receipt_sha256']
    for name, expected in receipt['artifact_sha256'].items():
        assert digest(candidate / name) == expected, name
    for name, expected in receipt['graph_source_sha256'].items():
        assert digest(candidate / 'asc-graph-init' / name) == expected, name
    for pin in prepared['analysis_input_pins']:
        assert digest(candidate / pin['relative']) == pin['sha256'], pin['relative']
    report = json.loads((capture / 'attempt.json').read_text())
    assert report['validated_build_receipt'] == receipt
    assert report['submit_attempted'] is True, 'No submitted-work attempt in this capture'
    for name in ('objects', 'owned', 'dmesg'):
        filename = 'dmesg-after.log' if name == 'dmesg' else name + '-after.bin'
        assert digest(capture / filename) == report['final_capture'][name]['sha256'], filename
    assert not a.output.exists(), 'Never overwrite saved analysis'
    a.output.mkdir(parents=True)
    tool = BASE_KIT / 'analyze-owned-work.py'
    checker = BASE_KIT / 'check-first-render-readback.py'
    for item in prepared['analysis_tool_pins']:
        assert digest(Path(item['path'])) == item['sha256'], item['path']
    result = subprocess.run([sys.executable, str(tool), str(candidate / 'asc-graph-init'),
                             str(capture), str(a.output / 'work')], capture_output=True, text=True)
    (a.output / 'work-analysis.stdout.txt').write_text(result.stdout)
    (a.output / 'work-analysis.stderr.txt').write_text(result.stderr)
    assert result.returncode == 0, 'Saved work analysis failed; preserve output for diagnosis'
    work = json.loads((a.output / 'work/result.json').read_text())
    pixels = runpy.run_path(str(checker))['check'](
        json.loads((candidate / 'analysis-inputs/target-receipt.json').read_text()),
        (a.output / 'work/target-after.bin').read_bytes())
    (a.output / 'target-samples.json').write_text(json.dumps(pixels, indent=2) + '\n')
    summary = {
        'schema': 'm4rch.gfx-coordinate-execution-analysis.v1',
        'boot_id': report['boot_id'], 'candidate_receipt_sha256': digest(receipt_path),
        'capture': str(capture), 'target_changed_bytes': work['target_changed_bytes'],
        'completion_changed_bytes': work['completion_changed_bytes'],
        'eight_target_reference_samples_passed': pixels['passed'],
        'gpu_execution_verified': False, 'retirement_verified': False,
        'qualification': 'Joined saved evidence only. Inspect work/result.json, target-samples.json and receive journal together. Eight sample pixels and firmware cursor consumption alone cannot prove device completion, all-pixel triangle correctness or DMA/UAT retirement. All backing remains retained.'}
    (a.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
