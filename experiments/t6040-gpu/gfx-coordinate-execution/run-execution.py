#!/usr/bin/env python3
"""Typed operations on the distinct execution owner; no load/free/reboot."""
import hashlib
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE_KIT = HERE.parent
BASE = BASE_KIT / 'run-resident-gpu.py'
BASE_SHA = '16f30d6251b2c1f55a0af05263dfd789bab61d5eb8075e61c443b076d53068b4'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BASE_KIT))


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Resident execution insertion point changed: ' + old[:80])
    return source.replace(old, new, 1)


def execution_admission(name, receipt, state):
    from gfx_execution_contract import validate_receipt
    require(validate_receipt(receipt), 'Distinct execution scope missing')
    require(name in COMMANDS, 'Unknown execution command')
    if name in ('sample', 'gfx-snapshot'):
        return
    require(not state.get('submit_attempted'), 'Work intent admits retained diagnostics only')
    require(not state.get('power_off_attempted'), 'OFF intent admits retained diagnostics only')
    require(not state.get('in_flight') and not state.get('interrupted_operation'),
            'Unknown earlier operation admits retained diagnostics only')
    if name == 'gfx-poweroff':
        require(state.get('host_stop_requested') is True, 'Confirmed STOP must precede OFF')
        return
    if name == 'stop':
        require(not state.get('host_stop_requested'), 'STOP already confirmed; never repeat')
        return
    require(not state.get('host_stop_requested') and not state.get('operation_failed'),
            'Stopped or failed session cannot publish or recover')
    if name == 'trace-off':
        require(state.get('completed_idle_cycles', 0) >= 4 and
                not state.get('trace_disabled'), 'Four completed cycles must precede trace-off')
    if name == 'submit':
        require(state.get('completed_idle_cycles', 0) >= 4 and state.get('trace_disabled') is True,
                'Four completed cycles and confirmed trace-off must precede submit')


def runner_source():
    raw = BASE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_SHA:
        raise ValueError('Frozen retained execution runner changed')
    source = raw.decode()
    source = replace_once(source,
        'from gfx_reset_contract import validate_receipt as validate_gfx_reset_receipt',
        'from gfx_execution_contract import validate_receipt as validate_gfx_reset_receipt')
    source = replace_once(source,
        "            'gfx-snapshot', 'gfx-reset')", "            'gfx-snapshot', 'gfx-poweroff')")
    source = replace_once(source, "    receipt = json.loads(receipt_path.read_text())\n",
        "    receipt = json.loads(receipt_path.read_text())\n"
        "    require(validate_gfx_reset_receipt(receipt), 'Distinct execution owner missing')\n")
    source = replace_once(source,
        "str(Path(__file__).with_name('decode-receive-journal.py'))",
        "str(BASE_KIT/'decode-receive-journal.py')")
    source = replace_once(source,
        "    operation = {'command': name, 'stage': 'intent-recorded',",
        "    execution_admission(name, report['validated_build_receipt'], state)\n"
        "    operation = {'command': name, 'stage': 'intent-recorded',")
    source = replace_once(source,
        "    if name == 'gfx-reset':\n"
        "        # Persist before opening sysfs: an interrupted write may have pulsed.\n"
        "        state['gfx_reset_attempted'] = True\n"
        "        state['operation_failed'] = True\n",
        "    if name == 'gfx-poweroff':\n"
        "        state['power_off_attempted'] = True\n"
        "        state['operation_failed'] = True\n")
    source = replace_once(source,
        "        operation.update(stage='returned', result='success')\n",
        "        operation.update(stage='returned', result='success')\n"
        "        if name == 'recover':\n"
        "            state['completed_idle_cycles'] += 2\n"
        "        if name == 'trace-off':\n"
        "            state['trace_disabled'] = True\n")
    start = source.index('def admit_command(name, receipt, state):\n')
    end = source.index('\n\ndef main():\n', start)
    source = source[:start] + ('def admit_command(name, receipt, state):\n'
                              '    execution_admission(name, receipt, state)\n') + source[end:]
    source = replace_once(source,
        "            'operation_failed': bool(original.get('diagnostic_session_active')), 'in_flight': None}",
        "            'operation_failed': bool(original.get('diagnostic_session_active')), 'in_flight': None,\n"
        "            'completed_idle_cycles': 2 if original.get('resident_session_active') is True else 0,\n"
        "            'trace_disabled': False}")
    source = replace_once(source,
        "            report['gfx_reset_attempted'] = state.get('gfx_reset_attempted', False)",
        "            report['power_off_attempted'] = state.get('power_off_attempted', False)\n"
        "            report['completed_idle_cycles'] = state.get('completed_idle_cycles', 0)\n"
        "            report['trace_disabled'] = state.get('trace_disabled', False)")
    return source


exec(compile(runner_source(), str(BASE), 'exec'), globals())
