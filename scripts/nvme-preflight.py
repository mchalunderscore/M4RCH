#!/usr/bin/env python3
"""Read-only macOS migration preflight; saves GPT backups and SD filesystem check."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import struct
import subprocess
import sys
import tempfile
import uuid
import zlib

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'sdboot'))
from collect_sd_logs import validate_disk, validate_superblock
TOOLS = PROJECT / 'out/native-ext4-tools/e2fsprogs-1.47.4'

def plist(*args):
    return plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', *args]))

def gpt_header(block):
    require(len(block) >= 92 and block[:8] == b'EFI PART', 'Invalid GPT header')
    size, checksum = struct.unpack_from('<II', block, 12)
    require(92 <= size <= len(block), 'Invalid GPT header size')
    checked = bytearray(block[:size]); checked[16:20] = bytes(4)
    require(zlib.crc32(checked) == checksum, 'GPT header CRC mismatch')
    current, other, first, last = struct.unpack_from('<QQQQ', block, 24)
    entry_lba, count, entry_size, entry_crc = struct.unpack_from('<QIII', block, 72)
    require(128 <= entry_size <= 4096 and entry_size % 128 == 0 and 0 < count <= 4096 and count * entry_size <= 4 * 1024**2, 'Invalid GPT table bounds')
    return dict(current=current, other=other, first=first, last=last,
                guid=str(uuid.UUID(bytes_le=block[56:72])), entry_lba=entry_lba,
                count=count, entry_size=entry_size, entry_crc=entry_crc)

def require(condition, message):
    if not condition: raise ValueError(message)

def read_gpt(raw, block_size, total_bytes):
    count = total_bytes // block_size
    require(total_bytes % block_size == 0, 'Unaligned SSD size')
    with open(raw, 'rb', buffering=0) as stream:
        def read(lba, size):
            require(0 <= lba < count and lba * block_size + size <= total_bytes, 'GPT read outside disk')
            stream.seek(lba * block_size)
            value = stream.read(size)
            require(len(value) == size, 'Short GPT read')
            return value
        primary_raw, backup_raw = read(1, block_size), read(count - 1, block_size)
        primary, backup = gpt_header(primary_raw), gpt_header(backup_raw)
        require((primary['current'], primary['other'], backup['current'], backup['other']) == (1, count - 1, count - 1, 1), 'GPT header positions differ')
        for key in ('guid', 'first', 'last', 'count', 'entry_size', 'entry_crc'):
            require(primary[key] == backup[key], 'GPT headers disagree')
        length = primary['count'] * primary['entry_size']
        entries = read(primary['entry_lba'], length)
        require(entries == read(backup['entry_lba'], length), 'GPT copies disagree')
        require(zlib.crc32(entries) == primary['entry_crc'], 'GPT entry CRC mismatch')
        parts = []
        for n in range(primary['count']):
            entry = entries[n * primary['entry_size']:(n + 1) * primary['entry_size']]
            if entry[:16] == bytes(16): continue
            start, end, attributes = struct.unpack_from('<QQQ', entry, 32)
            require(primary['first'] <= start <= end <= primary['last'], 'Partition outside usable GPT range')
            parts.append(dict(number=n+1, uuid=str(uuid.UUID(bytes_le=entry[16:32])),
                              type=str(uuid.UUID(bytes_le=entry[:16])), offset=start * block_size,
                              bytes=(end-start+1) * block_size, attributes=attributes))
        ordered = sorted(parts, key=lambda p:p['offset'])
        require(all(a['offset'] + a['bytes'] <= b['offset'] for a,b in zip(ordered,ordered[1:])), 'Overlapping partitions')
        # Save raw regions covering both tables and headers, including the PMBR.
        first_data = min(p['offset'] for p in parts)
        head_size = (primary['entry_lba'] * block_size + length + block_size - 1) // block_size * block_size
        require(head_size <= first_data, 'GPT overlaps first partition')
        tail_start = backup['entry_lba'] * block_size
        require(tail_start >= max(p['offset'] + p['bytes'] for p in parts), 'Backup GPT overlaps a partition')
        return primary, parts, read(0, head_size), read(backup['entry_lba'], total_bytes-tail_start), tail_start

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', default='')
    args = parser.parse_args()
    require(sys.platform == 'darwin' and os.geteuid() == 0, 'Run sudo make nvme-preflight on macOS')
    plan = json.loads((PROJECT / 'out/nvme-migration/plan.json').read_text())
    inventory = plist('list', '-plist', 'physical')
    disks = inventory['AllDisksAndPartitions']
    sd_matches = [disk['DeviceIdentifier'] for disk in disks if any(p.get('DiskUUID', '').lower() == '5d3356d1-51e3-513c-8cff-bc034a445a99' for p in disk.get('Partitions', []))]
    require(len(sd_matches) == 1, 'Cannot find exactly one current SD root')
    sd = args.disk or '/dev/' + sd_matches[0]
    require(sd == '/dev/' + sd_matches[0], 'Selected SD differs from expected root UUID')
    source, whole, root = validate_disk(sd)
    require(not root.get('MountPoint'), 'SD ext4 root must be unmounted')
    internal = [disk for disk in disks if any(p.get('DiskUUID', '').lower() == plan['reservation_uuid'] for p in disk.get('Partitions', []))]
    require(len(internal) == 1, 'Cannot find reserved NVMe allocation')
    info = plist('info', '-plist', internal[0]['DeviceIdentifier'])
    require(info.get('Internal') is True and info.get('BusProtocol') == 'Apple Fabric'
            and info.get('DeviceBlockSize') == plan['sector_bytes'] and info.get('TotalSize') == plan['disk_bytes'], 'Wrong internal SSD')
    destination_bytes = plan['reservation_bytes'] - plan['esp_bytes']
    require(root['Size'] <= destination_bytes, 'NVMe root would be smaller than the SD partition')
    with open(source, 'rb', buffering=0) as stream: superblock = stream.read(4096)
    validate_superblock(superblock)
    internal_raw = '/dev/r' + internal[0]['DeviceIdentifier']
    header, parts, head, tail, tail_offset = read_gpt(internal_raw, plan['sector_bytes'], plan['disk_bytes'])
    require({p['uuid']:(p['offset'],p['bytes']) for p in parts} == {p['uuid']:(p['offset'],p['bytes']) for p in plan['before']}, 'GPT differs from migration plan')
    parent = PROJECT / 'out/nvme-preflight'; parent.mkdir(exist_ok=True)
    os.umask(0o077)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-')
    output = Path(tempfile.mkdtemp(prefix=stamp, dir=parent))
    (output/'gpt-head.bin').write_bytes(head); (output/'gpt-tail.bin').write_bytes(tail)
    (output/'sd-superblock.bin').write_bytes(superblock)
    tools = {name:TOOLS/path for name,path in [('e2fsck','e2fsck/e2fsck'),('tune2fs','misc/tune2fs'),('resize2fs','resize/resize2fs'),('debugfs','debugfs/debugfs')]}
    for tool in tools.values(): require(tool.is_file() and os.access(tool,os.X_OK), 'Missing native ext4 tool: '+str(tool))
    receipt = dict(read_only=True, source=source, source_bytes=root['Size'], nvme_raw=internal_raw,
                   destination_bytes=destination_bytes, gpt=header, partitions=parts,
                   backup_tail_offset=tail_offset, tools={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in tools.items()})
    print('Read-only preflight:', sd, '→ reserved NVMe allocation', flush=True)
    print('Saving to',output,flush=True)
    with (output/'e2fsck.txt').open('w') as log:
        check = subprocess.run([str(tools['e2fsck']), '-f', '-n', source], stdout=log, stderr=subprocess.STDOUT)
    receipt['e2fsck_exit'] = check.returncode
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    require(check.returncode == 0, 'Read-only SD filesystem check did not pass; inspect '+str(output/'e2fsck.txt')+' before migration')
    # Verify the GPT remained identical during the scan.
    require(read_gpt(internal_raw,plan['sector_bytes'],plan['disk_bytes'])[1] == parts, 'GPT changed during preflight')
    print('PASS. No disk writes or partition changes. Return path:',output)

if __name__ == '__main__':
    try: main()
    except (ValueError,OSError,subprocess.CalledProcessError) as error:
        print('m4rch:',error,file=sys.stderr);sys.exit(1)
