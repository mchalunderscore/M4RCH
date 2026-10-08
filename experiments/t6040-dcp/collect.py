#!/usr/bin/env python3
"""Read-only Linux DCP baseline. Does not load drivers, touch MMIO or set modes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

MAX_FILE = 2 * 1024 * 1024
PROPERTIES = {'compatible', 'status', 'reg', 'reg-names', 'ranges', 'interrupts',
              'interrupt-parent', 'mboxes', 'mbox-names', 'iommus', 'iommu-map',
              'clocks', 'clock-names', 'power-domains', 'phys', 'phy-names', 'phandle',
              'apple,firmware-version', 'apple,firmware-compat', 'apple,bw-scratch',
              'apple,dcp-index', 'apple,iomfb-surfaces', 'apple,iomfb-surface-order',
              'apple,iomfb-primary-surface', 'apple,iomfb-max-layers',
              'memory-region', 'linux,phandle', 'remote-endpoint', 'width', 'height',
              'stride', 'format', 'clock-frequency', 'address', 'size'}


def read_property(path):
    with path.open('rb') as f:
        raw = f.read(MAX_FILE + 1)
    if len(raw) > MAX_FILE:
        raise ValueError(f'Property too large: {path}')
    return raw


def collect_dt(root):
    result = {}
    for p in root.rglob('*'):
        if not p.is_file() or p.is_symlink() or p.name not in PROPERTIES:
            continue
        relative = str(p.relative_to(root))
        if not re.search(r'dcp|disp|framebuffer|chosen|dart|iommu|mailbox|pmgr|phy|crossbar|panel', relative, re.I):
            continue
        raw = read_property(p)
        result[relative] = {'bytes': len(raw), 'hex': raw.hex()}
    return result


def command(output, name, argv):
    try:
        with (output / name).open('wb') as f:
            completed = subprocess.run(argv, stdout=f, stderr=subprocess.STDOUT, timeout=30)
        return {'command': argv, 'exit': completed.returncode}
    except (OSError, subprocess.TimeoutExpired) as error:
        (output / (name + '.error')).write_text(str(error) + '\n')
        return {'command': argv, 'error': str(error)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True,
                   help='Existing directory in which to create a unique capture')
    p.add_argument('--label', choices=('baseline', 'hdmi-connected', 'hdmi-disconnected', 'after-trial'), default='baseline')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    capture = Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime('dcp-%Y%m%dT%H%M%SZ-')+a.label+'-', dir=a.output))
    dtroot = Path('/sys/firmware/devicetree/base')
    if dtroot.is_dir():
        (capture/'devicetree.json').write_text(json.dumps({'cell_encoding': 'Linux DT big-endian; compare with Apple ADT little-endian explicitly', 'properties': collect_dt(dtroot)}, indent=2)+'\n')
    results = {}
    commands = {'kernel.txt': ['uname', '-a'], 'kernel-log.txt': ['journalctl', '-b', '-k', '--no-pager', '-n', '20000'],
                'interrupts.txt': ['cat', '/proc/interrupts'], 'cmdline.txt': ['cat', '/proc/cmdline'],
                'framebuffers.txt': ['cat', '/proc/fb'], 'modules.txt': ['lsmod'],
                'appledrm-modinfo.txt': ['modinfo', 'appledrm']}
    for name, argv in commands.items():
        results[name] = command(capture, name, argv)
    status = {}
    for entry in sorted(Path('/sys/class/drm').glob('*')):
        if not entry.is_dir():
            continue
        props = {}
        for name in ('status', 'enabled', 'modes', 'dpms'):
            path = entry / name
            if path.is_file():
                try:
                    props[name] = read_property(path).decode(errors='replace')
                except OSError as error:
                    props[name] = {'error': str(error)}
        edid = entry/'edid'
        if edid.is_file():
            raw = read_property(edid)
            props['edid'] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        props['device_path'] = str((entry/'device').resolve())
        props['driver_path'] = str((entry/'device/driver').resolve())
        status[entry.name] = props
    (capture/'drm.json').write_text(json.dumps(status, indent=2)+'\n')
    for source in (Path('/proc/config.gz'), Path('/sys/firmware/fdt')):
        if source.is_file():
            (capture/source.name).write_bytes(read_property(source))
    (capture/'commands.json').write_text(json.dumps(results, indent=2)+'\n')
    files = sorted(f for f in capture.iterdir() if f.is_file())
    (capture/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in files))
    print(capture)


if __name__ == '__main__':
    main()
