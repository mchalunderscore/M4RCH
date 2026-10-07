#!/usr/bin/env python3
"""Read macOS disk inventory and prepare a native migration kit; no disk writes."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import uuid

PROJECT = Path(__file__).resolve().parents[1]
RESERVATION = '5FDB35C6-3A66-416D-8358-6555FD99FCC5'

def info(device):
    return plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', device]))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=PROJECT / 'out/nvme-migration')
    args = parser.parse_args()
    inventory = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'list', '-plist', 'internal', 'physical']))
    found = [(disk, part) for disk in inventory['AllDisksAndPartitions'] for part in disk.get('Partitions', []) if part.get('DiskUUID') == RESERVATION]
    if len(found) != 1:
        raise ValueError('Expected exactly one authorized exFAT reservation')
    disk, reserved = found[0]
    whole, target = info(disk['DeviceIdentifier']), info(reserved['DeviceIdentifier'])
    if (whole.get('Internal') is not True or whole.get('BusProtocol') != 'Apple Fabric'
            or whole.get('DeviceBlockSize') != 4096 or whole.get('TotalSize') != 500277792768
            or target.get('FilesystemType') != 'exfat' or target.get('VolumeName') != 'M4RCH_ROOT'
            or target.get('PartitionMapPartitionOffset') != 362525229056
            or target.get('Size') != 127954583552):
        raise ValueError('Reservation or SSD geometry differs from the authorized allocation')
    parts = []
    for part in disk['Partitions']:
        live = info(part['DeviceIdentifier'])
        parts.append(dict(uuid=live['DiskUUID'].lower(), offset=live['PartitionMapPartitionOffset'], bytes=live['Size']))
    if len(parts) != 5:
        raise ValueError('Unexpected internal partition inventory')
    namespace = uuid.UUID(RESERVATION)
    plan = dict(schema=1, disk_bytes=whole['TotalSize'], sector_bytes=4096,
                reservation_uuid=RESERVATION.lower(), reservation_offset=target['PartitionMapPartitionOffset'],
                reservation_bytes=target['Size'], before=parts, esp_bytes=1024**3,
                esp_uuid=str(uuid.uuid5(namespace, 'm4rch-esp')),
                root_partition_uuid=str(uuid.uuid5(namespace, 'm4rch-root-partition')),
                root_uuid=str(uuid.uuid5(namespace, 'm4rch-root-filesystem')),
                sd_root_uuid='a0418040-b5b3-4ae8-9288-1c7c6dbda604',
                sd_boot_partition_uuid='969c748a-4de0-59db-a81c-3bb8fa6862fa')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    for name in ('migrate.py', 'init', 'mkinitcpio-install', 'HANDOVER.md'):
        (args.output / name).write_bytes((PROJECT / 'tools/nvme' / name).read_bytes())
    hashes = ''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n'
                     for p in sorted(args.output.iterdir()) if p.is_file() and p.name != 'SHA256SUMS')
    (args.output / 'SHA256SUMS').write_text(hashes)
    print(args.output)

if __name__ == '__main__':
    main()
