#!/usr/bin/env python3
"""Native migration to a macOS-reserved NVMe span; SD boot files remain fallback."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

KIT = Path(__file__).resolve().parent
ESP_TYPE = 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'
ROOT_TYPE = '0fc63daf-8483-4772-8e79-3d69d8477de4'
BASIC_TYPE = 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
TARGET = Path('/mnt/m4rch-nvme-root')

def run(*args, capture=False):
    print('+', ' '.join(map(str, args)), flush=True)
    return subprocess.check_output(list(map(str, args)), text=True).strip() if capture else subprocess.run(list(map(str, args)), check=True)

def require(condition, message):
    if not condition:
        raise ValueError(message)

def table(disk):
    value = json.loads(run('sfdisk', '--json', disk, capture=True))['partitiontable']
    require(value['label'] == 'gpt' and value['unit'] == 'sectors' and value['sectorsize'] == 4096,
            'Expected 4096-byte-sector GPT')
    return value

def number(part):
    return int(re.fullmatch(r'/dev/nvme\d+n\d+p(\d+)', part['node'])[1])

def identity(part):
    return {k: v for k, v in part.items() if k != 'node'}

def proposed(plan, before):
    parts = before['partitions']
    old = [p for p in parts if p['uuid'].lower() == plan['reservation_uuid']]
    require(len(old) == 1 and old[0]['type'].lower() == BASIC_TYPE, 'Missing reserved Basic Data partition')
    part = old[0]
    require(part['start'] * 4096 == plan['reservation_offset'] and part['size'] * 4096 == plan['reservation_bytes'], 'Reservation bounds changed')
    require({p['uuid'].lower(): (p['start'] * 4096, p['size'] * 4096) for p in parts}
            == {p['uuid']: (p['offset'], p['bytes']) for p in plan['before']}, 'Protected partition inventory changed')
    occupied = {number(p) for p in parts}
    free = next((n for n in range(1, 129) if n not in occupied), None)
    require(free is not None, 'No unused GPT slot')
    span = plan['esp_bytes'] // 4096
    require(0 < span < part['size'], 'Invalid split size')
    return part, free, span

def verify_split(plan, before, after):
    part, free, span = proposed(plan, before)
    require({k: v for k, v in before.items() if k != 'partitions'} ==
            {k: v for k, v in after.items() if k != 'partitions'}, 'GPT disk/header identity changed')
    old = {p['uuid'].lower(): identity(p) for p in before['partitions'] if p['uuid'].lower() != plan['reservation_uuid']}
    actual = {p['uuid'].lower(): p for p in after['partitions']}
    require(len(actual) == len(old) + 2, 'Unexpected partitions after split')
    for key, value in old.items():
        require(key in actual and identity(actual[key]) == value, 'Protected partition changed')
    results = []
    for guid, start, size, kind, slot in (
            (plan['esp_uuid'], part['start'], span, ESP_TYPE, number(part)),
            (plan['root_partition_uuid'], part['start'] + span, part['size'] - span, ROOT_TYPE, free)):
        require(guid in actual, 'Missing planned new partition')
        p = actual[guid]
        require((p['start'], p['size'], p['type'].lower(), number(p)) == (start, size, kind, slot), 'New partition differs from plan')
        results.append(p['node'])
    return results

def source_guard(plan):
    require(os.geteuid() == 0, 'Run in native Linux as root')
    require(b'apple,j614s' in Path('/proc/device-tree/compatible').read_bytes(), 'Wrong machine')
    release = run('uname', '-r', capture=True)
    modules = Path('/usr/lib/modules') / release
    require((modules / 'pkgbase').read_text().strip() == 'linux-m4rch', 'Unexpected kernel package')
    builtin = (modules / 'modules.builtin').read_text()
    require('drivers/nvme/host/apple.ko' in builtin and 'fs/ext4/ext4.ko' in builtin, 'Built-in Apple NVMe and ext4 are required before migration')
    root = run('findmnt', '-n', '-o', 'SOURCE', '/', capture=True)
    require(re.fullmatch(r'/dev/mmcblk\d+p2', root) is not None, 'Migration must run from the SD root')
    require(run('blkid', '-s', 'UUID', '-o', 'value', root, capture=True) == plan['sd_root_uuid'], 'Wrong SD root UUID')
    require(run('findmnt', '-n', '-o', 'FSTYPE', '/', capture=True) == 'ext4', 'SD root is not ext4')
    boot = run('findmnt', '-n', '-o', 'SOURCE', '/boot', capture=True)
    require(run('blkid', '-s', 'PARTUUID', '-o', 'value', boot, capture=True).lower() == plan['sd_boot_partition_uuid'], 'Mount the real SD ESP at /boot')
    require(run('findmnt', '-n', '-o', 'FSTYPE', '/boot', capture=True) == 'vfat', 'Boot mount is not FAT')
    # Root-only kit on SD, not a stale mount or another filesystem.
    require(KIT.parent == Path('/boot') and KIT.name == 'NVME0001' and not KIT.is_symlink(), 'Run the staged /boot/NVME0001 kit')
    return root

def disk_guard(disk, plan):
    require(re.fullmatch(r'/dev/nvme\d+n\d+', disk) is not None, 'Expected whole NVMe namespace')
    require(run('blockdev', '--getsize64', disk, capture=True) == str(plan['disk_bytes']), 'Wrong SSD size')
    require(run('blockdev', '--getss', disk, capture=True) == str(plan['sector_bytes']), 'Wrong sector size')

def unmounted(disk):
    nodes = json.loads(run('lsblk', '-J', '-o', 'NAME,MOUNTPOINTS', disk, capture=True))['blockdevices']
    def walk(node):
        require(not any(node.get('mountpoints') or []), 'Unmount all internal SSD filesystems before partitioning/formatting')
        for child in node.get('children', []): walk(child)
    for node in nodes: walk(node)
    swaps = Path('/proc/swaps').read_text()
    require(disk not in swaps, 'Internal SSD swap is active')

def mounted_target(rootdev):
    TARGET.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(['mountpoint', '-q', str(TARGET)])
    if result.returncode:
        require(not any(TARGET.iterdir()), 'Target directory is not empty')
        run('mount', '-t', 'ext4', rootdev, TARGET)
    require(run('findmnt', '-n', '-o', 'SOURCE', '--target', TARGET, capture=True) == rootdev, 'Wrong target mount')

def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    run('sync')
    temp.replace(path)
    run('sync')

def copy_root(final):
    require(not Path('/var/lib/pacman/db.lck').exists(), 'A package transaction is active')
    if final:
        require(subprocess.run(['systemctl', 'is-active', '--quiet', 'sddm']).returncode != 0, 'Stop SDDM and user sessions before final copy')
        sessions = run('loginctl', 'list-sessions', '--no-legend', capture=True)
        require(not sessions, 'Final copy requires no user sessions; use the systemd maintenance job in HANDOVER.md')
    excludes = ['dev/*', 'proc/*', 'sys/*', 'run/*', 'tmp/*', 'mnt/*', 'media/*', 'boot/*', 'lost+found', 'var/tmp/*', 'swapfile']
    run('rsync', '-aHAXSx', '--numeric-ids', '--delete', '--info=progress2',
        *['--exclude=/' + p for p in excludes], '/', str(TARGET) + '/')


def boot_trial(plan):
    release = run('uname', '-r', capture=True)
    modules = Path('/usr/lib/modules') / release
    require((modules / 'pkgbase').read_text().strip() == 'linux-m4rch', 'Unexpected kernel package')
    builtin = (modules / 'modules.builtin').read_text()
    require('drivers/nvme/host/apple.ko' in builtin, 'This kit requires built-in Apple NVMe; do not use a modular kernel')
    require((modules / 'vmlinuz').is_file(), 'Missing running kernel image')
    config = TARGET / 'etc/m4rch-nvme'
    config.mkdir(exist_ok=True)
    shutil.copyfile(KIT / 'init', config / 'init')
    config.joinpath('root.conf').write_text(
        f"ROOT_UUID='{plan['root_uuid']}'\nROOT_PARTITION_UUID='{plan['root_partition_uuid']}'\n"
        f"ROOT_OFFSET='{plan['reservation_offset'] + plan['esp_bytes']}'\n"
        f"ROOT_BYTES='{plan['reservation_bytes'] - plan['esp_bytes']}'\n")
    shutil.copyfile(KIT / 'mkinitcpio-install', TARGET / 'usr/lib/initcpio/install/m4rch-nvme')
    config.joinpath('mkinitcpio.conf').write_text('MODULES=()\nBINARIES=()\nFILES=()\nHOOKS=(m4rch-nvme)\nCOMPRESSION=gzip\n')
    # Existing package hooks fail their root UUID guard on NVMe. Do not silently
    # enable the SD updater on NVMe: it would replace the known-good SD fallback.
    fstab = TARGET / 'etc/fstab'
    lines = fstab.read_text().splitlines()
    require(sum(1 for line in lines if line.split() and not line.lstrip().startswith('#') and len(line.split()) > 1 and line.split()[1] == '/') == 1, 'Ambiguous root fstab')
    fstab.write_text('\n'.join(
        f"UUID={plan['root_uuid']} / ext4 defaults,noatime 0 1" if len(line.split()) > 1 and not line.lstrip().startswith('#') and line.split()[1] == '/' else line
        for line in lines) + '\n')
    # Keep /boot pointing at SD; the empty NVMe ESP is deliberately unmounted.
    require(any('PARTUUID=' + plan['sd_boot_partition_uuid'] in line and '/boot' in line for line in lines), 'Unexpected /boot fstab')
    for name in ('dev', 'proc', 'sys'):
        run('mount', '--rbind', '/' + name, TARGET / name)
        run('mount', '--make-rslave', TARGET / name)
    try:
        run('chroot', TARGET, 'mkinitcpio', '-c', '/etc/m4rch-nvme/mkinitcpio.conf', '-k', release, '-g', '/tmp/nvme-initramfs.img')
    finally:
        for name in ('sys', 'proc', 'dev'):
            run('umount', '-R', TARGET / name)
    shutil.copyfile(TARGET / 'tmp/nvme-initramfs.img', KIT / 'initramfs.img')
    (TARGET / 'tmp/nvme-initramfs.img').unlink()
    shutil.copyfile(modules / 'vmlinuz', KIT / 'vmlinuz')
    grub = Path('/boot/grub/grub.cfg')
    original = grub.read_text()
    require('M4RCH NVMe root trial' not in original, 'NVMe trial already staged; inspect the saved config before replacing it')
    # Reuse the running installation's flags, not a generic Apple cmdline.
    linux = next(line.strip() for line in original.splitlines() if line.strip().startswith('linux '))
    require('root=UUID=' + plan['sd_root_uuid'] in linux, 'SD menu root differs')
    linux = linux.replace('root=UUID=' + plan['sd_root_uuid'], 'root=UUID=' + plan['root_uuid'])
    linux = re.sub(r'^linux\s+\S+', 'linux /NVME0001/vmlinuz', linux)
    search = next(line.strip() for line in original.splitlines() if line.strip().startswith('search '))
    require(any(line.strip().startswith('set default=') for line in original.splitlines()), 'No explicit GRUB default')
    (KIT / 'grub-before.cfg').write_text(original)
    trial = "\nmenuentry 'M4RCH NVMe root trial' --id=m4rch-nvme {\n    " + search + '\n    ' + linux + '\n    initrd /NVME0001/initramfs.img\n}\n'
    # Publish artifacts, then the config. Never replace existing SD kernel/initrd.
    run('sync')
    staged = KIT / 'grub-nvme.cfg'
    staged.write_text(re.sub(r'(?m)^\s*set default=.*$', 'set default=m4rch-nvme', original) + trial)
    run('sync')
    shutil.copyfile(staged, grub.with_suffix('.nvme.tmp'))
    grub.with_suffix('.nvme.tmp').replace(grub)
    run('sync')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'partition', 'format', 'seed', 'final', 'boot'))
    parser.add_argument('--disk', required=True)
    args = parser.parse_args()
    plan = json.loads((KIT / 'plan.json').read_text())
    source_guard(plan)
    disk_guard(args.disk, plan)
    receipt = KIT / 'partition-receipt.json'
    if args.action in ('inspect', 'partition'):
        before = table(args.disk)
        part, free, span = proposed(plan, before)
        print(json.dumps(dict(reservation=part, esp_number=number(part), root_number=free, esp_sectors=span), indent=2))
        if args.action == 'inspect': return
        unmounted(args.disk)
        require(not receipt.exists(), 'Partition receipt already exists; do not repeat a completed split')
        require(run('blkid', '-s', 'TYPE', '-o', 'value', part['node'], capture=True) == 'exfat', 'Reservation is no longer exFAT')
        require(input('Type SPLIT ' + plan['reservation_uuid'] + ': ') == 'SPLIT ' + plan['reservation_uuid'], 'Not confirmed')
        require(not (KIT / 'gpt-before.bin').exists(), 'A prior split backup exists; inspect before retrying')
        run('sgdisk', '--backup=' + str(KIT / 'gpt-before.bin'), args.disk)
        save(KIT / 'gpt-before.json', before)
        end = part['start'] + part['size'] - 1
        run('sgdisk', '--set-alignment=1', f'--delete={number(part)}',
            f'--new={number(part)}:{part["start"]}:{part["start"] + span - 1}', f'--typecode={number(part)}:ef00',
            f'--partition-guid={number(part)}:{plan["esp_uuid"]}', f'--change-name={number(part)}:M4RCH ESP',
            f'--new={free}:{part["start"] + span}:{end}', f'--typecode={free}:8300',
            f'--partition-guid={free}:{plan["root_partition_uuid"]}', f'--change-name={free}:M4RCH ROOT', args.disk)
        run('blockdev', '--rereadpt', args.disk)
        after = table(args.disk)
        verify_split(plan, before, after)
        save(receipt, dict(before=before, phase='partitioned'))
        return
    state = json.loads(receipt.read_text())
    esp, root = verify_split(plan, state['before'], table(args.disk))
    if args.action == 'format':
        require(state['phase'] == 'partitioned', 'Formatting requires a fresh split; never reformat a copied root')
        unmounted(args.disk)
        require(input('Type FORMAT ' + plan['root_partition_uuid'] + ': ') == 'FORMAT ' + plan['root_partition_uuid'], 'Not confirmed')
        # Mark first: interruption must be reviewed, never automatically reformatted.
        state['phase'] = 'formatting'; save(receipt, state)
        for device in (esp, root): run('wipefs', '--all', device)
        run('mkfs.fat', '-F', '32', '-S', '4096', '-n', 'M4RCHESP', '-i', plan['esp_uuid'].replace('-', '')[:8], esp)
        run('mkfs.ext4', '-L', 'M4RCH_ROOT', '-U', plan['root_uuid'], root)
        state['phase'] = 'formatted'; save(receipt, state)
        return
    require(state['phase'] in ('formatted', 'seeded', 'copied', 'boot-staged'), 'Filesystems not ready')
    require(run('blkid', '-s', 'TYPE', '-o', 'value', esp, capture=True) == 'vfat', 'ESP is not FAT')
    require(run('blkid', '-s', 'UUID', '-o', 'value', root, capture=True) == plan['root_uuid'], 'Wrong ext4 UUID')
    mounted_target(root)
    if args.action in ('seed', 'final'):
        require(state['phase'] != 'boot-staged', 'Trial already staged; do not overwrite its root')
        copy_root(args.action == 'final')
        state['phase'] = 'copied' if args.action == 'final' else 'seeded'
    else:
        require(state['phase'] == 'copied', 'Complete the quiescent final copy before staging boot')
        boot_trial(plan)
        state['phase'] = 'boot-staged'
    run('sync'); save(receipt, state)
    print('Completed:', state['phase'], '; NVMe ESP remains empty.')

if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print('m4rch NVMe:', error, file=sys.stderr)
        sys.exit(1)
