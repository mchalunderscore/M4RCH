#!/usr/bin/env python3
"""Recover private display journals/config from unmounted NVMe, read-only."""
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import tempfile
import uuid

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reader', PROJECT/'sdboot/collect_sd_logs.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def main():
    if os.geteuid() != 0:
        raise ValueError('Run with sudo for read-only NVMe access')
    if hashlib.sha256(r.DEBUGFS.read_bytes()).hexdigest() != r.DEBUGFS_SHA256:
        raise ValueError('Unexpected debugfs binary')
    info = r.disk_info('/dev/disk0s4')
    if not info.get('Internal') or info.get('MountPoint') or info.get('Mounted') or info.get('Content') != 'Linux Filesystem':
        raise ValueError('Expected unmounted internal Linux partition')
    device = info['DeviceNode']
    with open(device, 'rb', buffering=0) as f:
        f.seek(1024)
        sb = f.read(1024)
    if sb[56:58] != b'\x53\xef' or str(uuid.UUID(bytes=sb[104:120])) != '7568fe83-378f-5b78-ab12-ccc36ff09a90':
        raise ValueError('Unexpected ext4 root filesystem identity')
    base = PROJECT/'out/display-recovery'
    base.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='nvme-logs-', dir=base))
    output.chmod(0o700)
    capture = r.Capture(device, output)
    try:
        for i, source in enumerate(('/home/alice/.config/kwinoutputconfig.json',
                                    '/home/alice/.config/kwinrc',
                                    '/home/alice/.config/kscreenlockerrc')):
            capture.dump(source, output/Path(source).name)
        journals = output/'journal'
        journals.mkdir(mode=0o700)
        for machine, mode in capture.listing('/var/log/journal'):
            if not r.MACHINE.fullmatch(machine) or not stat.S_ISDIR(mode):
                continue
            target = journals/machine
            target.mkdir(mode=0o700)
            for name, mode in capture.listing('/var/log/journal/'+machine):
                if not r.JOURNAL.fullmatch(name) or not stat.S_ISREG(mode):
                    continue
                if not (name.startswith('system') or name.startswith('user-1000')):
                    continue
                capture.dump('/var/log/journal/'+machine+'/'+name, target/name)
    finally:
        (output/'debugfs.txt').write_text('\n'.join(capture.messages))
        r.restore_ownership(output)
    print('Read-only recovery complete: '+str(output))


if __name__ == '__main__':
    main()
