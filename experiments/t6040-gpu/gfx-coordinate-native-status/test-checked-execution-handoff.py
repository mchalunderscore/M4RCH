#!/usr/bin/env python3
"""RAM replay of the separate checked launcher over the qualified handoff.

The preserved direct replay separately demonstrates the frozen helper's gap.
This test changes fixture paths and expected refusals, not downstream tools.
"""
import hashlib
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE / 'test-execution-handoff.py'
BASE_SHA = '27c3e59a84f7c8c36cacd0918f134f559d36182e86fc0b2b1555bafae5f32a33'
CHECKED_SHA = '2e2792a6c863f2aa24e50e27a64bba17022779df6b6f0f85a7355d8bb445671e'


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Checked handoff insertion point changed: ' + repr(old[:80]))
    return source.replace(old, new, 1)


def runner_source():
    raw = BASE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_SHA:
        raise ValueError('Qualified direct handoff replay changed')
    source = raw.decode()
    source = replace_once(source, "ANALYZER = HERE / 'analyze-execution.py'",
                          "ANALYZER = HERE / 'analyze-checked-execution.py'")
    source = replace_once(source,
        "ANALYZER_SHA = '4e74885c8b11cea96e12581225e5f78fae8b554b8d1b573d1753d0b5f596d541'",
        "ANALYZER_SHA = '" + CHECKED_SHA + "'")
    source = replace_once(source, "    bound.add(HERE.parent / 'firmware_text_contract.py')",
                          "    bound.add(HERE / 'test-execution-handoff.py')\n    bound.add(HERE.parent / 'firmware_text_contract.py')")
    source = replace_once(source,
        "        (path / 'text.bin').write_bytes(frozen_text)\n        save(path / 'attempt.json', report)",
        "        (path / 'text.bin').write_bytes(frozen_text)\n"
        "        initial = active / 'asc-graph-init/boot-SYNTHETIC-CPU-NO-HARDWARE'\n"
        "        initial.mkdir(exist_ok=True)\n"
        "        (initial / 'text.bin').write_bytes(frozen_text)\n"
        "        save(initial / 'attempt.json', {'synthetic_fixture': True,\n"
        "            'boot_id': report['boot_id'], 'validated_build_receipt': receipt,\n"
        "            'text_sha256': sha(frozen_text)})\n"
        "        report['initial_session'] = str(initial)\n"
        "        save(path / 'attempt.json', report)")
    source = replace_once(source, '        ram = Path(directory)\n',
                          "        ram = Path(directory)\n        active = ram / 'checked-candidate'\n        shutil.copytree(CANDIDATE, active)\n")
    # All checked positive calls address byte-identical cloned candidate files.
    source = source.replace(', CANDIDATE, capture,', ', active, capture,')
    source = replace_once(source, ', CANDIDATE, sample,', ', active, sample,')
    source = replace_once(source,
        "        else:\n            assert not (output / 'summary.json').exists()",
        "        else:\n            if label != 'refuse-existing-output':\n                assert not output.exists(), 'Refusal must precede frozen downstream analysis'\n            assert not (output / 'summary.json').exists()")
    old = """        output = invoke('observed-unbound-graph-receipt-changes-cursor', clone, capture, True)
        work = json.loads((output / 'work/result.json').read_text())
        assert work['root_channels'][0]['cursors'] == [2, 2, 3]
        cases[-1].update(expected_refusal_missing=True,
                         root_cursor_changed_by_unbound_layout=True,
                         original_root_cursors=[1, 2, 3], altered_root_cursors=[2, 2, 3])"""
    new = """        output = invoke('checked-refuses-graph-receipt-cursor-mutation', clone, capture, False)
        assert not output.exists()
        assert 'Prepared graph metadata changed' in cases[-1]['refusal_last_line']"""
    source = replace_once(source, old, new)
    old = """        output = invoke('observed-unbound-graph-before-not-consumed', clone, capture, True)
        cases[-1].update(expected_refusal_missing=True,
                         consumed_by_downstream_analyzer=False)"""
    new = """        output = invoke('checked-refuses-graph-before-mutation', clone, capture, False)
        assert not output.exists()
        assert 'Prepared graph fixture changed' in cases[-1]['refusal_last_line']"""
    source = replace_once(source, old, new)
    insertion = """        # Mutations occur only in a RAM clone, never the frozen candidate."""
    extra = """        # Every consumed final capture is required and cannot silently shorten.
        path = capture / 'attempt.json'
        original = path.read_bytes()
        path.unlink()
        output = invoke('checked-missing-operation-report', active, capture, False)
        assert not output.exists()
        path.write_bytes(original)
        for filename in ('objects-after.bin', 'owned-after.bin', 'dmesg-after.log', 'text.bin'):
            path = capture / filename
            original = path.read_bytes()
            path.unlink()
            output = invoke('checked-missing-' + filename, active, capture, False)
            assert not output.exists()
            path.write_bytes(original)
        for name in ('objects', 'owned'):
            path = capture / (name + '-after.bin')
            original = path.read_bytes()
            short = original[:-1]
            path.write_bytes(short)
            changed = copy.deepcopy(report)
            changed['final_capture'][name]['sha256'] = sha(short)
            save(capture / 'attempt.json', changed)
            output = invoke('checked-short-' + name + '-even-rehashed', active, capture, False)
            assert not output.exists()
            path.write_bytes(original)
            changed['final_capture'][name]['bytes'] -= 1
            save(capture / 'attempt.json', changed)
            output = invoke('checked-wrong-reported-extent-' + name, active, capture, False)
            assert not output.exists()
            save(capture / 'attempt.json', report)
        path = capture / 'text.bin'
        original = path.read_bytes()
        path.write_bytes(original + b'\\n')
        output = invoke('checked-copied-text-mutation', active, capture, False)
        assert not output.exists()
        path.write_bytes(original)
        initial = Path(report['initial_session'])
        original_attempt = (initial / 'attempt.json').read_bytes()
        changed = json.loads(original_attempt)
        changed['boot_id'] = 'wrong-boot'
        save(initial / 'attempt.json', changed)
        output = invoke('checked-original-boot-mismatch', active, capture, False)
        assert not output.exists()
        (initial / 'attempt.json').write_bytes(original_attempt)
        changed = copy.deepcopy(report)
        changed['initial_session'] = str(initial.parent / 'wrong-session')
        save(capture / 'attempt.json', changed)
        output = invoke('checked-original-session-path-mismatch', active, capture, False)
        assert not output.exists()
        save(capture / 'attempt.json', report)
        for name in ('data-before.bin', 'data-after.bin'):
            path = capture / name
            path.write_bytes(b'UNBOUND-FIRMWARE-DATA-CPU-FIXTURE')
            output = invoke('checked-unbound-' + name, active, capture, False)
            assert not output.exists()
            path.unlink()
        forbidden_output = active / 'new-analysis-output'
        result = subprocess.run([sys.executable, str(ANALYZER), str(active),
                                 str(capture), str(forbidden_output)], capture_output=True, text=True)
        assert result.returncode != 0 and not forbidden_output.exists()
        cases.append({'case': 'checked-refuses-output-inside-frozen-candidate',
                      'passed': True, 'synthetic_capture': True, 'hardware_access': False})
"""
    source = replace_once(source, insertion, extra + insertion)
    source = replace_once(source,
        "'schema': 'm4rch.gfx-native-status-execution-handoff-qualification.v1'",
        "'schema': 'm4rch.gfx-native-status-checked-execution-handoff-qualification.v1'")
    source = replace_once(source, "'all_candidate_pins_enforced': False", "'all_candidate_pins_enforced': True")
    source = replace_once(source,
        "'blocking_findings': ['Frozen analyzer omits graph_receipt_sha256 check; changed in-bounds cursor address is accepted and changes reported root cursors.']",
        "'blocking_findings': []")
    source = replace_once(source,
        "'graph-before.bin is not consumed and is not separately checked by the frozen offline wrapper. graph-receipt.json is consumed but its expected receipt hash is not checked.',",
        "'Separate checked launcher closes the frozen offline graph metadata/fixture omission before delegation and binds original/copied TEXT plus exact final snapshot extents.',")
    return source


namespace = {'__name__': 'checked_execution_handoff_qualification',
             '__file__': str(Path(__file__).resolve())}
source = runner_source()
exec(compile(source, str(BASE), 'exec'), namespace)
if __name__ == '__main__':
    namespace['main']()
