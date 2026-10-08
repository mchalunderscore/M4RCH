#!/usr/bin/env python3
"""Disable the GL-only Zoom effect in the current software-rendered desktop.

Run in Linux with sudo, before starting SDDM. Saves kwinrc and GRUB rollback.
"""
import configparser
import hashlib
import io
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile


def changed_config(text):
    config = configparser.ConfigParser(interpolation=None, strict=False)
    config.optionxform = str
    config.read_string(text)
    for section in ('Effect-zoom', 'Plugins'):
        if not config.has_section(section):
            config.add_section(section)
    config['Effect-zoom']['InitialZoom'] = '1'
    config['Plugins']['zoomEnabled'] = 'false'
    output = io.StringIO()
    config.write(output, space_around_delimiters=False)
    return output.getvalue()


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo')
    if subprocess.run(['systemctl', 'is-active', '--quiet', 'sddm']).returncode == 0:
        raise SystemExit('Stop SDDM before applying this fix')
    account = pwd.getpwnam('alice')
    config = Path(account.pw_dir)/'.config/kwinrc'
    if config.is_symlink() or not config.is_file():
        raise SystemExit('Expected regular alice kwinrc')
    kit = Path('/boot/DISPLAY001')
    grub = Path('/boot/grub/grub.cfg')
    console = kit/'grub-console.cfg'
    old = kit/'grub-before.cfg'
    if grub.read_bytes() not in (console.read_bytes(), old.read_bytes()):
        raise SystemExit('GRUB changed since recovery; review before restoring')
    backup = Path(tempfile.mkdtemp(prefix='zoom-fix-', dir=kit))
    backup.chmod(0o700)
    shutil.copy2(config, backup/'kwinrc-before')
    shutil.copy2(grub, backup/'grub-before')
    before = config.read_bytes()
    after = changed_config(before.decode()).encode()
    tmp = config.with_name('kwinrc.m4rch-new')
    with tmp.open('xb') as f:
        f.write(after)
    os.chown(tmp, account.pw_uid, account.pw_gid)
    tmp.chmod(config.stat().st_mode & 0o777)
    os.replace(tmp, config)
    # Restore the original graphical boot without replacing its kernel/loader.
    with grub.with_name('grub.m4rch-new').open('xb') as f:
        f.write(old.read_bytes())
    os.replace(grub.with_name('grub.m4rch-new'), grub)
    (backup/'receipt.json').write_text(json.dumps({'change': 'Zoom effect disabled; InitialZoom=1',
        'config_before': hashlib.sha256(before).hexdigest(),
        'config_after': hashlib.sha256(after).hexdigest(), 'user': 'alice'}, indent=2)+'\n')
    os.sync()
    print('Fix applied. Backup: '+str(backup))
    print('Now run: sudo systemctl start sddm')
    print('If still black, switch to tty2 and collect logs before another change.')


if __name__ == '__main__':
    main()
