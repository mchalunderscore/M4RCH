#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay actual userspace reset admission/persistence with fake sysfs only."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import tempfile

from gfx_reset_contract import (CONTRACT, RELEASE, PATCH_SHA, NATIVE_CONTRACT,
                                NATIVE_RELEASE, NATIVE_PATCH_SHA, USB_PATCH_SHA, sha)

KIT = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, KIT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline_candidate', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    assert not args.output.exists()
    runner = load('resident_offline_test', 'run-resident-gpu.py')
    preparer = load('reset_preparer_offline_test', 'prepare-gfx-reset-trial.py')
    root_runner = load('reset_root_runner_offline_test', 'run-root-envelope.py')
    base_receipt = args.baseline_candidate / 'asc-root-envelope/build-receipt.json'
    old = json.loads(base_receipt.read_text())
    assert old['artifact_sha256']['asc-graph-init/asc-graph-init.ko'] == preparer.BASE_MODULE_SHA
    new = copy.deepcopy(old)
    new['kernel_release'] = RELEASE
    new['kernel_gfx_reset_api'] = {'patch_sha256': PATCH_SHA}
    new['graph_recovery_trial']['gfx_reset_scope'] = copy.deepcopy(CONTRACT)
    new['graph_power_retirement_probe'] = False
    checks = 0
    assert root_runner.owner_parameters(new, graph=True) == [
        'run_gate=2', 'observe_ms=5000', 'resident_session=1']
    checks += 1
    for key in ('graph_power_retirement_probe', 'graph_release_on_shutdown',
                'graph_submit_work'):
        incompatible = copy.deepcopy(new)
        incompatible[key] = True
        try:
            root_runner.owner_parameters(incompatible, graph=True)
        except ValueError:
            checks += 1
        else:
            raise AssertionError('Unsafe reset startup accepted: ' + key)
    try:
        root_runner.owner_parameters(new, graph=True, warm_restart=True)
    except ValueError:
        checks += 1
    else:
        raise AssertionError('Reset warm startup accepted')
    assert root_runner.owner_parameters(old, graph=True) == [
        'run_gate=2', 'request_shutdown=1', 'observe_ms=5000', 'resident_session=1']
    assert root_runner.owner_parameters(old, arena=True) == ['run_gate=1']
    checks += 2
    for mode in ({}, {'arena': True}):
        try:
            root_runner.owner_parameters(new, **mode)
        except ValueError:
            checks += 1
        else:
            raise AssertionError('Reset receipt accepted outside graph mode')
    native = copy.deepcopy(new)
    native['kernel_release'] = NATIVE_RELEASE
    native['graph_recovery_trial']['gfx_reset_scope'] = copy.deepcopy(NATIVE_CONTRACT)
    native['kernel_gfx_reset_api'] = dict(patch_sha256=NATIVE_PATCH_SHA,
                                        api_profile='native-command-v1',
                                        legacy_checked_patch_sha256=PATCH_SHA,
                                        usb_role_patch_sha256=USB_PATCH_SHA)
    assert root_runner.owner_parameters(native, graph=True) == [
        'run_gate=2', 'observe_ms=5000', 'resident_session=1']
    checks += 1
    for key in ('patch_sha256', 'api_profile', 'legacy_checked_patch_sha256',
                'usb_role_patch_sha256'):
        incompatible = copy.deepcopy(native)
        incompatible['kernel_gfx_reset_api'].pop(key)
        try:
            root_runner.owner_parameters(incompatible, graph=True)
        except ValueError:
            checks += 1
        else:
            raise AssertionError('Native profile accepted without ' + key)
    incompatible = copy.deepcopy(native)
    incompatible['graph_recovery_trial']['gfx_reset_scope']['command_bits_latch_required'] = True
    try:
        root_runner.owner_parameters(incompatible, graph=True)
    except ValueError:
        checks += 1
    else:
        raise AssertionError('Unknown native completion contract accepted')

    def state():
        return dict(boot_id='offline', resident_session_active=True,
                    submit_attempted=False, operation_failed=True, in_flight=None)

    def admits(name, receipt, history, expected):
        nonlocal checks
        try:
            runner.admit_command(name, receipt, history)
            got = True
        except ValueError:
            got = False
        assert got == expected, (name, got, expected, history)
        checks += 1

    for name in runner.COMMANDS:
        admits(name, old, state(), name in ('sample', 'stop'))
        admits(name, new, state(), name in ('sample', 'stop', 'gfx-snapshot', 'gfx-reset'))
        admits(name, native, state(), name in ('sample', 'stop', 'gfx-snapshot', 'gfx-reset'))
    for key in ('gfx_reset_attempted', 'host_stop_requested', 'submit_attempted',
                'interrupted_operation'):
        history = state()
        history[key] = True
        admits('gfx-reset', new, history, False)
    history = state()
    history['in_flight'] = {'command': 'gfx-reset'}
    admits('gfx-reset', new, history, False)
    with tempfile.TemporaryDirectory(prefix='gfx-wrapper-replay-') as directory:
        root = Path(directory)
        runner.SYSFS = root / 'fake-sysfs'
        runner.SYSFS.mkdir()
        (runner.SYSFS / 'command').touch()
        open_real, write_real = runner.os.open, runner.os.write
        for mode in ('success', 'EIO'):
            output = root / mode
            output.mkdir()
            history = state()
            state_path = output / 'state.json'
            report = dict(commands=[], validated_build_receipt=new,
                          resident_session_active=True)
            target_fd = [None]

            def intercepted_open(pathname, flags, *extra, **kwargs):
                if Path(pathname) == runner.SYSFS / 'command':
                    persisted = json.loads(state_path.read_text())
                    assert persisted['gfx_reset_attempted'] and persisted['operation_failed']
                    target_fd[0] = open_real(pathname, flags, *extra, **kwargs)
                    return target_fd[0]
                return open_real(pathname, flags, *extra, **kwargs)

            def intercepted_write(fd, payload):
                if fd == target_fd[0]:
                    persisted = json.loads(state_path.read_text())
                    assert persisted['gfx_reset_attempted'] and persisted['operation_failed']
                    if mode == 'EIO':
                        raise OSError(5, 'synthetic command write failure')
                return write_real(fd, payload)

            runner.os.open, runner.os.write = intercepted_open, intercepted_write
            try:
                try:
                    runner.command('gfx-reset', output, report, history, state_path)
                    failed = False
                except OSError:
                    failed = True
                assert failed == (mode == 'EIO')
                assert history['gfx_reset_attempted'] and history['operation_failed']
                assert history['in_flight'] is None
            finally:
                runner.os.open, runner.os.write = open_real, write_real
            admits('gfx-reset', new, history, False)
            admits('gfx-snapshot', new, history, True)
            checks += 1
        for receipt, active in ((old, False), (new, True)):
            output = root / ('stop-new' if active else 'stop-old')
            output.mkdir()
            history = state()
            report = dict(commands=[], validated_build_receipt=receipt,
                          resident_session_active=True)
            runner.command('stop', output, report, history, output / 'state.json')
            assert history['resident_session_active'] == active
            if active:
                assert history['host_stop_requested']
                admits('gfx-reset', new, history, False)
            checks += 1
        (root / 'boot-contract.h').touch()
        (root / 'boot-actual-capture').mkdir()
        (root / 'probe.o').touch()
        assert preparer.ignore_outputs(root, ['boot-contract.h', 'boot-actual-capture',
                                             'probe.o']) == {'boot-actual-capture', 'probe.o'}
        checks += 1
    report = {
        'schema': 'm4rch-gfx-reset-wrapper-offline-validation-v1', 'checks': checks,
        'intent_before_sysfs_open_and_write_verified': True,
        'successful_and_failed_write_keep_permanent_seal': True,
        'feature_and_default_stop_contracts_verified': True,
        'boot_header_preserved_while_capture_directories_excluded': True,
        'reset_startup_excludes_shutdown_release_work_and_warm_restart': True,
        'input_receipt_sha256': sha(base_receipt),
        'source_sha256': {name: sha(KIT / name) for name in
                          ('run-resident-gpu.py', 'run-root-envelope.py', 'prepare-gfx-reset-trial.py',
                           'gfx_reset_contract.py', 'test-gfx-reset-wrapper.py')},
        'hardware_access': False,
        'qualification': 'Actual admission and persistence functions, fake regular-file sysfs only. '
                         'Kernel state/hardware behavior is tested separately.',
    }
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print('Passed %d offline wrapper/copy cases; no hardware access.' % checks)


if __name__ == '__main__':
    main()
