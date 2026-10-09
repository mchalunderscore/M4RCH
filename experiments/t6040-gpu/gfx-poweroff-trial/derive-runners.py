#!/usr/bin/env python3
"""Derive isolated OFF runners from the exact saved native-reset runners."""
import hashlib
from pathlib import Path

KIT = Path(__file__).resolve().parent
BASE = KIT.parent


def frozen(name, expected):
    data = (BASE / name).read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected, name + ' baseline changed'
    return data.decode()


def replace_once(text, old, new):
    assert text.count(old) == 1, 'Unexpected baseline: ' + old[:80]
    return text.replace(old, new)


def replace_function(text, name, next_name, replacement):
    start = text.index('def ' + name + '(')
    end = text.index('def ' + next_name + '(', start)
    return text[:start] + replacement.strip() + '\n\n\n' + text[end:]


root = frozen('run-root-envelope.py',
              'd4d5a8228ade3574fe876f5dcef8279091a84acfd286e4b0effa9c8f64214a2f')
root = replace_once(root, 'from live_graph_observer import observe',
                    'import sys\nfrom pathlib import Path\nBASE_KIT = Path(__file__).resolve().parents[1]\n'
                    'sys.path.insert(0, str(BASE_KIT))\nfrom live_graph_observer import observe')
root = root.replace('from gfx_reset_contract import validate_receipt',
                    'from gfx_poweroff_contract import validate_receipt')
root = root.replace('reset_scope', 'power_off_scope').replace('Reset scope', 'Power-off scope')
root = replace_once(root, '    power_off_scope = validate_receipt(receipt)\n    if power_off_scope:\n',
                    '    power_off_scope = validate_receipt(receipt)\n'
                    "    require(power_off_scope, 'Only the distinct power-off contract is admitted')\n"
                    '    if power_off_scope:\n')
root = replace_once(root, '    power_off_scope = validate_receipt(receipt)\n    require(not',
                    "    power_off_scope = validate_receipt(receipt)\n"
                    "    require(power_off_scope, 'Only the distinct power-off contract is admitted')\n"
                    "    for name, expected in receipt['graph_source_sha256'].items():\n"
                    "        require('/' not in name and sha((work/'asc-graph-init'/name).read_bytes()) == expected,\n"
                    "                'Prepared owner source changed: ' + name)\n    require(not")
root = root.replace("Path(__file__).with_name('decode-receive-journal.py')", "(BASE_KIT/'decode-receive-journal.py')")
root = root.replace('Retained no-work GFX reset scope. Only sample/gfx-snapshot, one guarded gfx-reset and packet-free stop are permitted; no restart, submission, backing release or DMA-retirement qualification.',
                    'Retained no-work GFX power-off scope. Sample/gfx-snapshot and packet-free stop precede one terminal gfx-poweroff; afterwards only PMGR/DRAM diagnostics. All backing and mappings retained; OFF does not prove DMA retirement or restart safety.')
root = root.replace('Retained GFX reset scope ready for sampling and one guarded reset. All backing pinned; no restart, work submission or unload.',
                    'Retained GFX power-off scope ready. Stop before one terminal gfx-poweroff. All backing and mappings pinned; no restart, work submission or unload.')
root = replace_once(root, root[root.index('"""'):root.index('"""', root.index('"""')+3)+3],
                    '"""Validate exact cold firmware and establish one retained no-work OFF owner.\n'
                    'Requires graph mode; rejects old/reset contracts, cycles and warm restart.\n'
                    'Never performs power-off automatically, releases backing or reboots.\n"""')
(KIT / 'run-root-poweroff.py').write_text(root)

resident = frozen('run-resident-gpu.py',
                  '16f30d6251b2c1f55a0af05263dfd789bab61d5eb8075e61c443b076d53068b4')
resident = replace_once(resident, 'from gfx_reset_contract import validate_receipt as validate_gfx_reset_receipt',
                        'BASE_KIT = Path(__file__).resolve().parents[1]\n'
                        'sys.path.insert(0, str(BASE_KIT))\n'
                        'from gfx_poweroff_contract import validate_receipt as validate_poweroff_receipt')
resident = replace_once(resident, "COMMANDS = ('sample', 'control', 'recover', 'trace-off', 'submit', 'stop',\n            'gfx-snapshot', 'gfx-reset')",
                        "COMMANDS = ('sample', 'gfx-snapshot', 'stop', 'gfx-poweroff')")
resident = replace_once(resident, '    receipt = json.loads(receipt_path.read_text())\n',
                        '    receipt = json.loads(receipt_path.read_text())\n'
                        "    require(validate_poweroff_receipt(receipt), 'Distinct power-off contract missing')\n")
resident = resident.replace("Path(__file__).with_name('decode-receive-journal.py')", "(BASE_KIT/'decode-receive-journal.py')")
resident = replace_function(resident, 'command', 'admit_command', '''
def command(name, output, report, state, state_path):
    """Persist a terminal attempt before opening sysfs; never retry its write."""
    admit_command(name, report['validated_build_receipt'], state)
    operation = {'command': name, 'stage': 'intent-recorded',
                 'started_monotonic': time.monotonic(), 'result': None}
    report['commands'].append(operation)
    state['in_flight'] = {'command': name, 'operation_directory': str(output)}
    if name == 'gfx-poweroff':
        state['power_off_attempted'] = True
        state['operation_failed'] = True
    save_json(output / 'attempt.json', report)
    save_json(state_path, state)
    descriptor = None
    try:
        descriptor = os.open(SYSFS / 'command', os.O_WRONLY)
        payload = (name + '\\n').encode('ascii')
        count = os.write(descriptor, payload)
        require(count == len(payload), 'Short command write; outcome uncertain')
        operation.update(stage='returned', result='success')
        if name == 'stop':
            state['host_stop_requested'] = True
            state['operation_failed'] = True
            report['reboot_required'] = True
    except BaseException as error:
        operation.update(stage='failed-or-interrupted', result=repr(error))
        state['operation_failed'] = True
        # Keep an unknown result diagnostic even if the wrapper survives it.
        state['interrupted_operation'] = dict(state['in_flight'])
        report['resident_session_usable'] = False
        report['reboot_required'] = True
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
        operation['finished_monotonic'] = time.monotonic()
        state['in_flight'] = None
        save_json(output / 'attempt.json', report)
        save_json(state_path, state)
''')
resident = replace_function(resident, 'admit_command', 'main', '''
def admit_command(name, receipt, state):
    """Exactly one OFF after confirmed STOP; uncertainty closes mutation."""
    require(validate_poweroff_receipt(receipt), 'Distinct power-off contract missing')
    require(name in COMMANDS, 'Command is outside the retained power-off scope')
    require(not state.get('submit_attempted'), 'Work excludes this no-work scope')
    if name in ('sample', 'gfx-snapshot'):
        return
    require(not state.get('power_off_attempted'),
            'An OFF was already attempted or has an uncertain outcome')
    require(not state.get('in_flight') and not state.get('interrupted_operation'),
            'Unknown earlier command permits PMGR/DRAM diagnostics only')
    if name == 'gfx-poweroff':
        require(state.get('host_stop_requested') is True,
                'Confirmed packet-free STOP must precede power-off')
''')
start = resident.index("        if args.command == 'trace-off':")
end = resident.index("        state_path = ", start)
resident = resident[:start] + resident[end:]
start = resident.index("            if args.command == 'submit':")
end = resident.index('        except BaseException as exception:', start)
resident = resident[:start] + resident[end:]
resident = resident.replace("report['gfx_reset_attempted'] = state.get('gfx_reset_attempted', False)",
                            "report['power_off_attempted'] = state.get('power_off_attempted', False)")
resident = resident.replace("'schema': 'm4rch-resident-operation-v1'", "'schema': 'm4rch-resident-power-off-operation-v1'")
resident = replace_once(resident, resident[resident.index('"""'):resident.index('"""', resident.index('"""')+3)+3],
                        '"""Run one typed diagnostic, STOP or terminal power-off on the distinct owner.\n'
                        'Retains every allocation, mapping and consumer on all results. After OFF\n'
                        'intent, only PMGR snapshots and DRAM diagnostics are admitted. Never loads\n'
                        'or unloads modules, resets, restarts, submits, frees backing or reboots.\n"""')
(KIT / 'run-poweroff.py').write_text(resident)
print('Derived isolated power-off runners; no hardware access.')
