#!/usr/bin/env python3
"""Exercise resolver updates and replacement without touching system DNS."""
from pathlib import Path
import os
import signal
import subprocess
import tempfile
import time

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as directory:
    base = Path(directory)
    host = base / 'host'
    runtime = base / 'run'
    etc = base / 'etc'
    (host / 'etc').mkdir(parents=True)
    (host / 'run/NetworkManager').mkdir(parents=True)
    runtime.mkdir()
    etc.mkdir()
    (host / 'etc/resolv.conf').symlink_to('/run/NetworkManager/resolv.conf')
    (etc / 'resolv.conf').symlink_to(str(runtime / 'NetworkManager/resolv.conf'))
    (runtime / 'resolv.conf').write_text('')
    inode = (runtime / 'resolv.conf').stat().st_ino
    source = (root / 'packages/muvm-m4rch/muvm-dns-sync').read_text()
    # Translate absolute guest paths to this test's isolated filesystem.
    source = source.replace('/run/muvm-host', str(host)).replace('/run/', str(runtime) + '/')
    source = source.replace('/etc/resolv.conf', str(etc / 'resolv.conf'))
    # The host's etc path must remain under the host directory.
    source = source.replace('$host' + str(etc / 'resolv.conf'), '$host/etc/resolv.conf')
    source = source.replace('$host' + str(runtime) + '/', '$host/run/')
    source = source.replace('sleep 2', 'sleep 0.1')
    # Guest symlink targets are absolute in the temporary test directory.
    source = source.replace('            /run/*)', '            ' + str(runtime) + '/*)')
    worker = base / 'worker'
    worker.write_text(source)
    process = subprocess.Popen(['/bin/sh', str(worker)], start_new_session=True)
    process.wait(timeout=3)
    def expect(value):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if (runtime / 'resolv.conf').read_text() == value and (etc / 'resolv.conf').exists() and (etc / 'resolv.conf').read_text() == value:
                return
            time.sleep(.05)
        raise AssertionError('resolver did not update to ' + repr(value))
    try:
        expect('')
        dns = host / 'run/NetworkManager/resolv.conf'
        dns.write_text('nameserver 192.0.2.1\n')
        expect('nameserver 192.0.2.1\n')
        dns.write_text('nameserver 192.0.2.2\n')
        expect('nameserver 192.0.2.2\n')
        (host / 'run/NetworkManager/no-stub-resolv.conf').write_text(
            'nameserver 192.0.2.3\nnameserver fe80::1%wlan0\n')
        dns.write_text('nameserver 127.0.0.53\n')
        expect('nameserver 192.0.2.3\n')
        dns.unlink()
        expect('')
        assert (runtime / 'resolv.conf').stat().st_ino == inode
    finally:
        os.killpg(process.pid, signal.SIGTERM)
print('PASS: offline, DNS availability, DNS change, loss, and mounted inode preservation')
