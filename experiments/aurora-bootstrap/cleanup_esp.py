#!/usr/bin/env python3
"""Archive and remove explicitly retired ESP test kernels and their menu entries."""
import argparse
import datetime
import importlib.util
import json
from pathlib import Path
import re
import shutil

from stage import PROJECT, GRUB, sha, write, json_bytes

KEEP_IDS = {'m4rch-aurora-gpu16', 'm4rch-aurora-gpu16-console',
            'm4rch-aurora-direct1', 'm4rch-aurora-direct1-fb', 'm4rch-aurora-native-r5'}
RETIRED = ['AURA001', 'AURD001.saved-r4-20261024T112354Z', 'AURG016.saved-r3', 'AURT002',
           'GFXN001', 'GFXR001', 'GPUC001', 'GPUC003', 'GRAVK001', 'NATI001', 'USBR001']


def default(text):
    values = re.findall(r"(?m)^set default='([^']+)'$", text)
    if values != ['m4rch-aurora-gpu16']:
        raise ValueError('Unexpected default boot target')
    return values[0]


def payloads(esp):
    found = []
    for directory in [esp] + [esp / name for name in RETIRED]:
        if not directory.exists():
            continue
        if directory.is_symlink():
            raise ValueError('Unexpected directory symlink')
        for path in directory.iterdir():
            if not path.is_file():
                continue
            kernel = path.name == 'Image' or path.name.startswith('vmlinuz')
            ramdisk = path.name.startswith(('initramfs', 'initrd')) and path.suffix == '.img'
            if not (kernel or ramdisk):
                continue
            if path.is_symlink() or path.stat().st_size < 1024 * 1024:
                raise ValueError('Unexpected payload: ' + str(path))
            with path.open('rb') as stream:
                head = stream.read(64)
            if kernel and head[56:60] != b'ARM\x64':
                raise ValueError('Not an ARM64 kernel Image: ' + str(path))
            if ramdisk and not head.startswith((b'\x1f\x8b', b'\x28\xb5\x2f\xfd', b'070701')):
                raise ValueError('Unknown initramfs format: ' + str(path))
            found.append(path)
    return sorted(found)


def expected_grub(esp):
    path = esp / 'AUBS001/cleanup-receipt.json'
    if not path.exists():
        return GRUB
    receipt = json.loads(path.read_text())
    if receipt['grub_before_sha256'] != GRUB or set(receipt['kept_ids']) != KEEP_IDS:
        raise ValueError('Unexpected cleanup receipt')
    for relative, digest in receipt['preserved_payloads'].items():
        if Path(relative).is_absolute() or '..' in Path(relative).parts or sha(esp / relative) != digest:
            raise ValueError('Preserved boot payload differs')
    default((esp / 'grub/grub.cfg').read_text())
    return receipt['grub_after_sha256']


def main(esp, apply):
    spec = importlib.util.spec_from_file_location('direct_stage', PROJECT / 'experiments/aurora-direct/stage.py')
    direct = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(direct)
    direct.validate_esp(esp)
    grub = esp / 'grub/grub.cfg'
    original = grub.read_text()
    default(original)
    if sha(grub) != GRUB:
        raise ValueError('GRUB differs from the reviewed original; do not repeat cleanup')
    entries = list(re.finditer(r'(?ms)^menuentry [^\n]*\{\n.*?^\}\n', original))
    chunks, previous, kept, removed = [], 0, [], []
    for entry in entries:
        chunks.append(original[previous:entry.start()])
        match = re.search(r' --id ([\w-]+) \{', entry[0].splitlines()[0])
        identity = match[1] if match else None
        if identity in KEEP_IDS:
            chunks.append(entry[0])
            kept.append(identity)
        else:
            removed.append(entry[0].splitlines()[0])
        previous = entry.end()
    chunks.append(original[previous:])
    cleaned = re.sub(r'\n{3,}', '\n\n', ''.join(chunks))
    if set(kept) != KEEP_IDS or len(kept) != len(KEEP_IDS):
        raise ValueError('Expected all five current/fallback entries')
    deleting = payloads(esp)
    deletion_set = set(deleting)
    refs = set(re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)', cleaned))
    preserve = {}
    for reference in refs:
        if not reference.startswith('/') or '..' in Path(reference).parts:
            raise ValueError('Unexpected GRUB file reference')
        path = esp / reference.lstrip('/')
        if path in deletion_set:
            raise ValueError('Attempt to remove a retained menu payload')
        preserve[reference.lstrip('/')] = sha(path)
    before = shutil.disk_usage(esp).free
    plan = {'removed_payloads': [{'path': str(p.relative_to(esp)), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in deleting],
            'payload_bytes': sum(p.stat().st_size for p in deleting), 'removed_entries': removed,
            'kept_ids': kept, 'preserved_payloads': preserve, 'default': default(cleaned),
            'grub_before_sha256': sha(grub), 'boot_bin_sha256': sha(esp / 'boot.bin'),
            'free_bytes_before': before}
    if not apply:
        print(json.dumps(plan, indent=2))
        return
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = PROJECT / 'out/esp-kernel-cleanup' / stamp
    backup.mkdir(parents=True)
    (backup / 'plan.json').write_bytes(json_bytes(plan))
    (backup / 'grub.before.cfg').write_text(original)
    for path in deleting:
        dest = backup / 'payloads' / path.relative_to(esp)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        if sha(path) != sha(dest):
            raise ValueError('Archive readback differs: ' + str(path))
    # Remove dangling menu choices before retiring their payloads. On an
    # interrupted cleanup the retained current/fallback entries remain usable.
    write(grub, cleaned.encode())
    for path, item in zip(deleting, plan['removed_payloads']):
        if sha(path) != item['sha256']:
            raise ValueError('Payload changed before removal: ' + str(path))
        path.unlink()
    for relative, digest in preserve.items():
        if sha(esp / relative) != digest:
            raise ValueError('Retained boot payload changed')
    if sha(esp / 'boot.bin') != plan['boot_bin_sha256']:
        raise ValueError('Bootloader changed during cleanup')
    plan.update(phase='complete', archive=str(backup), grub_after_sha256=sha(grub),
                free_bytes_after=shutil.disk_usage(esp).free)
    write(backup / 'receipt.json', json_bytes(plan))
    write(esp / 'AUBS001/cleanup-receipt.json', json_bytes(plan))
    if expected_grub(esp) != sha(grub):
        raise ValueError('Cleanup verification differs')
    print(json.dumps({k: plan[k] for k in ['phase', 'payload_bytes', 'free_bytes_before', 'free_bytes_after', 'archive', 'default']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--esp', type=Path, default=Path('/Volumes/M4RCHESP'))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    main(args.esp, args.apply)
