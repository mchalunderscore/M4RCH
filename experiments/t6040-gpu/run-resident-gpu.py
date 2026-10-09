#!/usr/bin/env python3
"""Run one typed operation on an already qualified resident GPU session.

Never loads or unloads modules, frees backing, or reboots. Recovery uses only
the resident application's qualified handshake. Submit publishes the one
prepared batch once and samples at 1, 5, 15, and 30 seconds after it returns.
All backing remains pinned, including after stop or an uncertain operation.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4


SYSFS = Path('/sys/kernel/m4rch_gpu_graph_trial')
MODULE = Path('/sys/module/asc_graph_init')
MODULE_ARTIFACT = 'asc-graph-init/asc-graph-init.ko'
PAGE_SIZE = 0x4000
COMMANDS = ('sample', 'control', 'recover', 'submit', 'stop')


def require(condition, explanation):
    if not condition:
        raise ValueError(explanation)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, value):
    """Make command intent durable before entering a sysfs store callback."""
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def seal_interrupted_operation(state, state_path):
    """Sampling must never erase the quarantine of an unknown command result."""
    if state.get('in_flight'):
        state['operation_failed'] = True
        state['interrupted_operation'] = dict(state['in_flight'])
        save_json(state_path, state)


def module_build_note(blob):
    """Read the module's ELF note to bind the resident image, not only its file."""
    require(blob[:6] == b'\x7fELF\x02\x01', 'Module is not little-endian ELF64')
    require(len(blob) >= 64, 'Truncated ELF header')
    table = struct.unpack_from('<Q', blob, 40)[0]
    entry_size, count, names_index = struct.unpack_from('<HHH', blob, 58)
    require(entry_size == 64 and 0 < names_index < count,
            'Unsupported ELF section table')
    require(table + count * entry_size <= len(blob), 'Truncated ELF sections')

    def section(index):
        return struct.unpack_from('<IIQQQQIIQQ', blob, table + index * entry_size)

    names_section = section(names_index)
    names = blob[names_section[4]:names_section[4] + names_section[5]]
    for index in range(count):
        row = section(index)
        name = names[row[0]:].split(b'\0', 1)[0]
        if name == b'.note.gnu.build-id':
            require(row[4] + row[5] <= len(blob), 'Truncated module build note')
            note = blob[row[4]:row[4] + row[5]]
            require(bool(note), 'Empty module build note')
            return note
    raise ValueError('Module has no GNU build ID; cannot bind the loaded image')


def validate(work, boot):
    receipt_path = work / 'asc-root-envelope/build-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    session = work / 'asc-graph-init' / ('boot-' + boot)
    attempt = json.loads((session / 'attempt.json').read_text())
    require(attempt.get('boot_id') == boot, 'Session boot identity mismatch')
    require(attempt.get('resident_session_active') is True or attempt.get('diagnostic_session_active') is True,
            'This boot has no retained running session')
    require(attempt.get('load_returncode') == 0 and attempt.get('module_present'),
            'Original module load was not successful')
    require(attempt.get('validated_build_receipt') == receipt,
            'Candidate changed since the resident session was established')
    require(receipt.get('graph_recovery_trial', {}).get('resident_session') is True,
            'Candidate does not implement the resident recovery contract')
    require(receipt.get('joined_context_init') and
            not receipt.get('graph_release_on_shutdown') and
            not receipt.get('graph_submit_work'), 'Unexpected candidate lifetime contract')
    require(os.uname().release == receipt['kernel_release'], 'Kernel release mismatch')
    require(sha(Path('/sys/kernel/notes').read_bytes()) == receipt['kernel_notes_sha256'],
            'Kernel identity mismatch')
    require(MODULE.is_dir(), 'Resident asc_graph_init module is absent')
    require(int((MODULE / 'refcnt').read_text()) > 0, 'Resident module is not pinned')
    require((MODULE / 'parameters/resident_session').read_text().strip() in ('Y', '1'),
            'Loaded module did not request a resident session')
    require((MODULE / 'parameters/run_gate').read_text().strip() == '2',
            'Loaded module is not the published graph instance')
    for relative, expected in receipt['artifact_sha256'].items():
        path = (work / relative).resolve()
        require(path.is_relative_to(work), 'Artifact escapes the candidate directory')
        require(sha(path.read_bytes()) == expected, 'Artifact mismatch: ' + relative)
    module = (work / MODULE_ARTIFACT).read_bytes()
    require((MODULE / 'notes/.note.gnu.build-id').read_bytes() == module_build_note(module),
            'Loaded module build ID differs from the validated candidate')
    require(sha((work / 'asc-graph-init/graph-before.bin').read_bytes()) ==
            receipt['graph_fixture_sha256'], 'Prepared graph changed')
    require(sha((work / 'asc-graph-init/graph-receipt.json').read_bytes()) ==
            receipt['graph_receipt_sha256'], 'Prepared graph receipt changed')
    for name, expected in receipt['graph_source_sha256'].items():
        require(sha((work / 'asc-graph-init' / name).read_bytes()) == expected,
                'Prepared graph source changed: ' + name)
    for name in ('command', 'objects', 'owned'):
        require((SYSFS / name).exists(), 'Resident interface is missing: ' + name)
    require((session / 'text.bin').is_file(), 'Original qualified firmware TEXT capture missing')
    require(sha((session / 'text.bin').read_bytes()) == attempt['text_sha256'],
            'Original firmware TEXT evidence changed')
    return receipt, session, attempt


def capture(destination, receipt, report):
    """Snapshots serialize with host writes in the module; firmware may advance."""
    destination.mkdir(exist_ok=True)
    results = {}
    for name, size in (('objects', receipt['graph_object_pages'] * PAGE_SIZE),
                       ('owned', receipt['joined_owned_pages'] * PAGE_SIZE)):
        output = destination / (name + '-after.bin')
        try:
            data = (SYSFS / name).read_bytes()
            output.write_bytes(data)
            require(len(data) == size, name + ' snapshot extent mismatch')
            results[name] = {'bytes': len(data), 'sha256': sha(data)}
        except Exception as error:
            results[name] = {'error': repr(error)}
            report['capture_errors'].append(str(output) + ': ' + repr(error))
    try:
        logs = subprocess.check_output(['dmesg', '--color=never'], text=True, timeout=10)
        (destination / 'dmesg-after.log').write_text(logs)
        results['dmesg'] = {'sha256': sha(logs.encode())}
    except Exception as error:
        results['dmesg'] = {'error': repr(error)}
        report['capture_errors'].append(str(destination / 'dmesg-after.log') + ': ' + repr(error))
    return results


def command(name, output, report, state, state_path):
    """One write, without retry, with its intent persisted before publication."""
    operation = {'command': name, 'stage': 'intent-recorded',
                 'started_monotonic': time.monotonic(), 'result': None}
    report['commands'].append(operation)
    state['in_flight'] = {'command': name, 'operation_directory': str(output)}
    # An interrupted submit is quarantined even when its write outcome is unknown.
    if name == 'submit':
        state['submit_attempted'] = True
    save_json(output / 'attempt.json', report)
    save_json(state_path, state)
    descriptor = None
    try:
        descriptor = os.open(SYSFS / 'command', os.O_WRONLY)
        payload = (name + '\n').encode('ascii')
        count = os.write(descriptor, payload)
        require(count == len(payload), 'Short resident command write; outcome uncertain')
        operation.update(stage='returned', result='success')
        if name == 'stop':
            state['resident_session_active'] = False
            report['resident_session_active'] = False
            report['reboot_required'] = True
    except BaseException as error:
        operation.update(stage='failed-or-interrupted', result=repr(error))
        state['operation_failed'] = True
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path, help='The validated live-candidate directory')
    parser.add_argument('command', choices=COMMANDS)
    args = parser.parse_args()
    require(os.geteuid() == 0, 'Native sudo required')
    work = args.workspace.resolve()
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    session = work / 'asc-graph-init' / ('boot-' + boot)
    require((session / 'attempt.json').is_file(), 'No initial session attempt for this boot')
    operations = session / 'resident-operations'
    operations.mkdir(exist_ok=True)
    with (operations / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt, session, original = validate(work, boot)
        state_path = operations / 'state.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else {
            'boot_id': boot, 'candidate_module_sha256': receipt['artifact_sha256'][MODULE_ARTIFACT],
            'resident_session_active': True, 'submit_attempted': False,
            'operation_failed': bool(original.get('diagnostic_session_active')), 'in_flight': None}
        require(state['boot_id'] == boot and state['candidate_module_sha256'] ==
                receipt['artifact_sha256'][MODULE_ARTIFACT], 'Resident operation history differs')
        require(state['resident_session_active'], 'Resident stop was already requested')
        seal_interrupted_operation(state, state_path)
        require(args.command in ('sample', 'stop') or (not state['operation_failed'] and not state['in_flight']),
                'Prior command failed or was interrupted; only sample/stop is permitted')
        require(args.command in ('sample', 'stop') or not state['submit_attempted'],
                'An immutable work batch was already attempted; no further publication or recovery')
        name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '-' + args.command + '-' + uuid4().hex[:8]
        output = operations / name
        output.mkdir()
        report = {'schema': 'm4rch-resident-operation-v1', 'boot_id': boot,
                  'requested_command': args.command, 'initial_session': str(session),
                  'validated_build_receipt': receipt, 'commands': [], 'capture_errors': [],
                  'resident_session_active': True, 'reboot_required': False,
                  'allocations_retained': True, 'snapshots_atomic': False,
                  'qualification': 'Retained live backing only. Snapshots serialize with host writes per read, but firmware may advance during capture. No completion, DMA retirement, safe unload, or rendering claim.'}
        save_json(output / 'attempt.json', report)
        error = None
        try:
            # This is the original read-only TEXT capture, not a new sampler load.
            (output / 'text.bin').write_bytes((session / 'text.bin').read_bytes())
            (output / 'objects-before.bin').write_bytes((work / 'asc-graph-init/graph-before.bin').read_bytes())
            logs = subprocess.check_output(['dmesg', '--color=never'], text=True, timeout=10)
            (output / 'dmesg-before.log').write_text(logs)
            command(args.command, output, report, state, state_path)
            if args.command == 'submit':
                submitted = time.monotonic()
                for seconds in (1, 5, 15, 30):
                    time.sleep(max(0, submitted + seconds - time.monotonic()))
                    command('sample', output, report, state, state_path)
                    target = output / ('sample-%02ds' % seconds)
                    report.setdefault('samples', []).append({
                        'requested_seconds': seconds, 'elapsed_seconds': time.monotonic() - submitted,
                        'capture': capture(target, receipt, report)})
                    save_json(output / 'attempt.json', report)
        except BaseException as exception:
            error = exception
            report['error'] = repr(exception)
        finally:
            report['final_capture'] = capture(output, receipt, report)
            report['module_present'] = MODULE.exists()
            report['resident_session_active'] = state['resident_session_active']
            report['operation_failed'] = state['operation_failed']
            report['resident_session_usable'] = state['resident_session_active'] and not state['operation_failed']
            report['diagnostic_session_active'] = state['resident_session_active'] and state['operation_failed']
            report['reboot_required'] = not report['resident_session_usable']
            report['submit_attempted'] = state['submit_attempted']
            report['complete'] = error is None and not report['capture_errors']
            save_json(output / 'attempt.json', report)
        print(output)
        if error is not None:
            raise error
        require(not report['capture_errors'], 'Operation returned; one or more evidence captures failed')


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print('Resident operation refused or incomplete: ' + str(error), file=sys.stderr)
        sys.exit(1)
