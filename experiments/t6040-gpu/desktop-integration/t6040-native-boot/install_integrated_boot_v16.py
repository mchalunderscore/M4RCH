#!/usr/bin/env python3
"""Install the isolated reviewed payload and select it; never reboot or load GPU."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil


def check(row):
    path = Path(row['path'])
    data = path.read_bytes()
    if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
        raise ValueError('Package changed: ' + str(path))


def install(package):
    if os.geteuid() != 0:
        raise ValueError('Root required for boot/module installation')
    package = package.resolve()
    receipt = json.loads((package / 'boot-package-receipt.json').read_text())
    release = receipt['release']
    if release != '7.1.13-m4rch-gpu-native-integrated+':
        raise ValueError('Unexpected release')
    # A concrete launcher package is mandatory before selecting the next boot.
    launcher = package / 'launcher'
    if not launcher.is_dir() or not (launcher / 'manifest.json').is_file():
        raise ValueError('Complete combined launcher package required')
    manifest = json.loads((launcher / 'manifest.json').read_text())
    for row in receipt['boot_files'] + [receipt['module']]:
        check(row)
    for row in manifest['files']:
        name = row['path']
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Invalid launcher artifact path')
        check(dict(row, path=str(launcher / name)))
    boot = Path('/boot/NATI001')
    modules = Path('/usr/lib/modules') / release
    if boot.exists() or modules.exists():
        raise ValueError('Isolated destination already exists; review before replacement')
    config = Path('/boot/grub/grub.cfg')
    previous = config.read_text()
    fragment = (package / 'grub-entry.cfg').read_text()
    if 'NATI001' in previous or previous.count('set default=') != 1:
        raise ValueError('Unexpected GRUB state')
    index = len(re.findall(r'^menuentry ', previous, flags=re.M))
    updated = re.sub(r'^set default=.*$', 'set default=' + str(index), previous,
                     count=1, flags=re.M) + '\n' + fragment
    backup = config.with_name('grub.cfg.pre-native-integrated-v16')
    if backup.exists():
        raise ValueError('Backup already exists')
    shutil.copy2(config, backup)
    shutil.copytree(package / 'boot/NATI001', boot)
    shutil.copytree(package / 'rootfs/usr/lib/modules' / release, modules)
    for row in receipt['boot_files']:
        check(dict(row, path=str(boot / Path(row['path']).name)))
    check(dict(receipt['module'], path=str(modules / 'kernel/drivers/gpu/drm/asahi/asahi_m4.ko')))
    temporary = config.with_name('grub.cfg.native-integrated-new')
    temporary.write_text(updated)
    os.replace(temporary, config)
    os.sync()
    result = dict(schema='m4rch.integrated-boot-install.v16', release=release,
                  package=str(package), boot=str(boot), module_root=str(modules),
                  grub_backup=str(backup), grub_default=index,
                  hardware_actions=[], rebooted=False, module_loaded=False)
    (package / 'install-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    install(parser.parse_args().package)
