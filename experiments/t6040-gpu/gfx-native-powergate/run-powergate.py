#!/usr/bin/env python3
"""One typed no-work powergate operation; durable intent and retained diagnostics."""
import hashlib
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
BASE_KIT = HERE.parent
BASE = BASE_KIT / 'gfx-coordinate-native-status/run-native-status.py'
BASE_SHA = 'f37a1c9a65b60f8b8636dc6edfd7be16987cc5ff6574a757ae2dfbc0a40e14c6'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BASE_KIT))


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Powergate resident insertion changed: ' + old[:100])
    return source.replace(old, new, 1)


def execution_admission(name, receipt, state):
    from gfx_native_powergate_contract import validate_receipt
    require(validate_receipt(receipt), 'Distinct native powergate scope missing')
    require(name in COMMANDS, 'Unknown powergate command')
    if name in ('sample', 'gfx-snapshot'):
        return
    require(state.get('powergate_ready') is True, 'Qualified powergate startup proof required')
    require(not any(state.get(key) for key in ('powergate_attempted', 'submit_attempted',
        'power_off_attempted', 'host_stop_requested', 'gfx_reset_attempted',
        'in_flight', 'interrupted_operation', 'operation_uncertain')),
        'Terminal or unknown intent admits retained diagnostics only')


def quarantine_operation_history(operations, receipt, state, state_path):
    """A lost state file cannot erase a durable terminal/unknown report."""
    changed = False
    for directory in operations.iterdir():
        if not directory.is_dir():
            continue
        try:
            report = json.loads((directory / 'attempt.json').read_text())
            require(report.get('schema') == 'm4rch.gfx-native-powergate-operation.v1' and
                    report.get('boot_id') == state['boot_id'] and
                    report.get('validated_build_receipt') == receipt,
                    'Operation history identity differs')
            require(report.get('requested_command') in COMMANDS and
                    isinstance(report.get('commands'), list), 'Operation history command differs')
            if report['requested_command'] == 'gfx-powergate' or any(
                    item.get('command') == 'gfx-powergate' for item in report['commands']):
                if not state.get('powergate_attempted'):
                    state['powergate_attempted'] = True
                    changed = True
            require(report.get('complete') is True and not report.get('error') and
                    not report.get('capture_errors'), 'Incomplete earlier operation')
        except (ValueError, KeyError, OSError, TypeError, AttributeError):
            if not state.get('operation_uncertain'):
                state['operation_uncertain'] = True
                changed = True
    if changed:
        state['operation_failed'] = True
        save_json(state_path, state)


def runner_source():
    if hashlib.sha256(BASE.read_bytes()).hexdigest() != BASE_SHA:
        raise ValueError('Frozen native STATUS resident runner changed')
    source = runpy.run_path(str(BASE))['runner_source']()
    source = replace_once(source,
        'from gfx_native_status_contract import validate_receipt as validate_gfx_reset_receipt',
        'from gfx_native_powergate_contract import validate_receipt as validate_gfx_reset_receipt, qualify_powergate_startup')
    source = replace_once(source,
        "COMMANDS = ('sample', 'control', 'recover', 'trace-off', 'submit', 'stop',\n            'gfx-snapshot', 'gfx-poweroff')",
        "COMMANDS = ('sample', 'gfx-snapshot', 'gfx-powergate')")
    source = replace_once(source,
        "    return receipt, session, attempt\n",
        "    logs = (session / 'dmesg-after.log').read_text()\n"
        "    require(sha(logs.encode()) == attempt.get('dmesg_after_sha256'), 'Original startup log changed')\n"
        "    prior = (session / 'dmesg-before.log').read_text()\n"
        "    require(sha(prior.encode()) == attempt.get('dmesg_before_sha256'), 'Original pre-startup log changed')\n"
        "    delta = logs[len(prior):] if logs.startswith(prior) else logs\n"
        "    proof = qualify_powergate_startup(delta, attempt, attempt['load_returncode'], int((MODULE / 'refcnt').read_text()))\n"
        "    require(proof is not None and proof == attempt.get('native_powergate_startup') and\n"
        "            attempt.get('commands_admitted') == list(COMMANDS), 'Original powergate startup proof changed')\n"
        "    return receipt, session, attempt\n")
    source = replace_once(source,
        "    if name == 'gfx-poweroff':\n        state['power_off_attempted'] = True\n        state['operation_failed'] = True\n",
        "    if name == 'gfx-powergate':\n        state['powergate_attempted'] = True\n        state['operation_failed'] = True\n        report['reboot_required'] = True\n")
    source = replace_once(source,
        "        state['operation_failed'] = True\n        report['resident_session_usable'] = False\n",
        "        state['operation_failed'] = True\n        state['operation_uncertain'] = True\n        report['resident_session_usable'] = False\n")
    start = source.index("        if args.command == 'trace-off':\n")
    end = source.index('        state_path = ', start)
    source = source[:start] + source[end:]
    start = source.index("            if args.command == 'submit':\n")
    end = source.index('        except BaseException as exception:', start)
    source = source[:start] + source[end:]
    start = source.index('    # An interrupted submit is quarantined')
    end = source.index("    if name == 'gfx-powergate':", start)
    source = source[:start] + source[end:]
    start = source.index("        if name == 'recover':\n")
    end = source.index('    except BaseException as error:', start)
    source = source[:start] + source[end:]
    source = replace_once(source,
        "            'trace_disabled': False}",
        "            'trace_disabled': False, 'powergate_attempted': False,\n"
        "            'powergate_ready': original['native_powergate_startup']['qualified'],\n"
        "            'operation_uncertain': False, 'family': 'gfx_native_powergate_scope'}")
    source = replace_once(source,
        "            'completed_idle_cycles': 2 if original.get('resident_session_active') is True else 0,",
        "            'completed_idle_cycles': original['native_powergate_startup']['initial_completed_cycles'],")
    source = replace_once(source,
        "        require(state['resident_session_active'], 'Resident stop was already requested')\n",
        "        require(state.get('family') == 'gfx_native_powergate_scope', 'Operation state family differs')\n"
        "        require(state['resident_session_active'], 'Retained owner lifetime changed')\n")
    source = replace_once(source,
        "        seal_interrupted_operation(state, state_path)\n        admit_command(args.command, receipt, state)\n",
        "        seal_interrupted_operation(state, state_path)\n"
        "        quarantine_operation_history(operations, receipt, state, state_path)\n"
        "        admit_command(args.command, receipt, state)\n")
    source = replace_once(source,
        "                state['operation_failed']=True\n                save_json(state_path,state)",
        "                state['operation_failed']=True\n                state['operation_uncertain']=True\n                save_json(state_path,state)")
    source = replace_once(source,
        "            notification=report['final_capture'].get('notifications',{})\n",
        "            if report['capture_errors']:\n                state['operation_uncertain']=True\n                state['operation_failed']=True\n                save_json(state_path,state)\n"
        "            notification=report['final_capture'].get('notifications',{})\n")
    source = replace_once(source,
        "report = {'schema': 'm4rch-resident-operation-v1'",
        "report = {'schema': 'm4rch.gfx-native-powergate-operation.v1'")
    source = replace_once(source,
        "            report['power_off_attempted'] = state.get('power_off_attempted', False)",
        "            report['powergate_attempted'] = state.get('powergate_attempted', False)\n"
        "            report['operation_uncertain'] = state.get('operation_uncertain', False)")
    # No dormant old command paths remain in the generated main/store function.
    if any(token in source for token in ("name == 'submit'", "name == 'recover'", "name == 'stop'", "args.command == 'submit'")):
        raise ValueError('Unexpected old operation path in new powergate runner')
    return source


exec(compile(runner_source(), str(BASE), 'exec'), globals())
