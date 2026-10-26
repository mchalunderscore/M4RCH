#!/usr/bin/env python3
"""Select the fully installed native trial after audit; never reboot or probe GPU.

The user requested a boot default because GRUB input is unavailable. This is
separate from additive installation so every prior menu entry stays available.
Copy alongside the exact reviewed installer and artifact receipt before use.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

WORK = Path(__file__).resolve().parent
RESULT = WORK / 'default-selection-result.json'
BACKUP = Path('/boot/GFXN001/grub-installed-default4.cfg')
PARTIAL = Path('/boot/grub/.GFXN001-default.cfg')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--receipt-sha256', required=True)
    args = parser.parse_args()
    receipt_path = WORK / 'artifact-receipt.json'
    receipt_bytes = receipt_path.read_bytes()
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    if receipt_sha != args.receipt_sha256:
        raise RuntimeError('Reviewed artifact receipt differs')
    receipt = json.loads(receipt_bytes)
    installer_path = WORK / 'install-additive.py'
    installer_records = [r for r in receipt['artifact_files'] if r['path'] == str(installer_path)]
    if (len(installer_records) != 1 or installer_path.is_symlink() or
            installer_path.stat().st_size != installer_records[0]['bytes'] or
            hashlib.sha256(installer_path.read_bytes()).hexdigest() != installer_records[0]['sha256']):
        raise RuntimeError('Receipt-bound installer changed before import')
    spec = importlib.util.spec_from_file_location('installer', installer_path)
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    require = installer.require
    require(receipt['schema'] == 'm4rch.gfx-native-reset-additive-artifacts.v1' and
            receipt['kernel_release'] == installer.RELEASE and
            receipt['new_menu_index'] == 5 and receipt['default_preserved'] == 4,
            'Wrong native trial/default contract')
    installer.verify_files(receipt['artifact_files'])
    records = {r['path']: r for r in receipt['artifact_files']}
    require(str(Path(__file__).resolve()) in records,
            'Selector is not in the reviewed receipt')
    install_result = json.loads(installer.RESULT.read_text())
    require(install_result['status'] == 'complete' and
            install_result['artifact_receipt_sha256'] == receipt_sha and
            install_result['default'] == 4 and
            install_result['previous_boot_entries_preserved'] is True,
            'Exact reviewed additive installation has not completed')
    before = installer.read_artifact(WORK / 'grub-before.cfg', records)
    entry = installer.read_artifact(WORK / 'additive-entry.cfg', records)
    current = installer.read_artifact(WORK / 'grub-additive.cfg', records)
    require(current == before + entry and current.count(b'menuentry ') == 6 and
            current.count(b'set default=4\n') == 1,
            'Unexpected additive menu text')
    selected = current.replace(b'set default=4\n', b'set default=5\n', 1)
    require(selected.count(b'set default=5\n') == 1 and
            selected.count(b'menuentry ') == 6, 'Unexpected selected menu')
    require(install_result['current_grub_sha256'] ==
            hashlib.sha256(current).hexdigest(), 'Installed GRUB receipt differs')

    def verify_installed():
        require(installer.GRUB.read_bytes() == current, 'Installed menu changed')
        installer.verify_boot(installer.BOOT_DST, receipt['boot_files'], records)
        installer.verify_tree(installer.MODULE_DST, receipt['module_files'])
        installer.verify_host(receipt['protected_host_files'], allow_new_grub=True)

    verify_installed()
    if not args.execute:
        print('Default selection audit passed; no writes. Proposed change: 4 -> 5.')
        return
    require(os.geteuid() == 0, 'Execution requires root')
    with Path('/run/lock/arch-m4-boot.lock').open('a') as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        installer.verify_mounts()
        verify_installed()
        require(not RESULT.exists(), 'Selection already attempted; inspect result')
        require(not os.path.lexists(BACKUP) and not os.path.lexists(PARTIAL),
                'New backup/staging path already exists')
        state = {'schema': 'm4rch.gfx-native-reset-default-selection.v1',
                 'artifact_receipt_sha256': receipt_sha, 'started_unix': time.time(),
                 'previous_default': 4, 'selected_default': 5,
                 'before_sha256': hashlib.sha256(current).hexdigest(),
                 'selected_sha256': hashlib.sha256(selected).hexdigest(),
                 'backup_path': str(BACKUP), 'status': 'started',
                 'reboot_performed': False, 'gpu_action_performed': False,
                 'mount_changed': False, 'package_hooks_executed': False}

        def save():
            temporary = RESULT.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(state, indent=2) + '\n')
            os.replace(temporary, RESULT)

        save()
        try:
            installer.write_new(BACKUP, current)
            installer.write_new(PARTIAL, selected)
            subprocess.run(['grub-script-check', str(PARTIAL)], check=True)
            require(PARTIAL.read_bytes() == selected and BACKUP.read_bytes() == current,
                    'Staged menu or backup differs')
            verify_installed()
            os.replace(PARTIAL, installer.GRUB)
            os.sync()
            require(installer.GRUB.read_bytes() == selected, 'Selected menu differs')
            installer.verify_boot(installer.BOOT_DST, receipt['boot_files'], records)
            installer.verify_tree(installer.MODULE_DST, receipt['module_files'])
            installer.verify_host(receipt['protected_host_files'], allow_new_grub=True)
            state.update(status='complete', finished_unix=time.time(),
                         current_grub_sha256=installer.digest(installer.GRUB),
                         all_six_entries_preserved=True)
            save()
            print('Native trial selected as default 5; all six entries preserved. No reboot.')
        except BaseException as error:
            state.update(status='partial', failure=str(error), finished_unix=time.time())
            save()
            raise


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('REFUSED/FAILED: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
