#!/usr/bin/env python3
"""Stage the tested NVMe boot files on the internal ESP, with Mac-local backup.

Does not repartition, flash, or enroll Apple boot policy. Root and ESP are
resolved by UUID and every protected GPT entry is rechecked before writes.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import uuid

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('migration', PROJECT/'scripts/migrate-nvme-macos.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
require = m.require
ESP_UUID = '5fdb35c6-3a66-416d-8358-6555fd99fcc5'
ROOT_PART = 'e80ee324-c4c5-4f3e-81b7-464adb71d41a'
ROOT_UUID = '7568fe83-378f-5b78-ab12-ccc36ff09a90'


def retarget_efi(blob, old, new):
    require(re.fullmatch(r'[0-9A-F]{4}-[0-9A-F]{4}', new), 'Invalid FAT UUID')
    require(blob[:2] == b'MZ' and len(blob) > 256, 'Not a PE executable')
    pe = struct.unpack_from('<I', blob, 60)[0]
    require(blob[pe:pe+4] == b'PE\0\0' and struct.unpack_from('<H',blob,pe+4)[0] == 0xaa64, 'Not ARM64 EFI')
    require(blob.count(old.encode()) == 1, 'Ambiguous embedded GRUB filesystem UUID')
    require(struct.unpack_from('<H',blob,pe+24)[0] == 0x20b, 'Not PE32+')
    # Authenticode signatures would be invalidated: refuse signed input.
    cert_offset, cert_size = struct.unpack_from('<II',blob,pe+24+112+8*4)
    require(not cert_offset and not cert_size, 'Cannot retarget a signed EFI application')
    result = bytearray(blob.replace(old.encode(),new.encode()))
    checksum_at = pe+24+64
    struct.pack_into('<I',result,checksum_at,0)
    total = 0
    for offset in range(0,len(result),2):
        total += int.from_bytes(result[offset:offset+2],'little')
        total = (total & 0xffff) + (total >> 16)
    total = (total & 0xffff) + (total >> 16)
    struct.pack_into('<I',result,checksum_at,total+len(result))
    return bytes(result)


def mount(part):
    value = m.resolve_part(part)
    if not value.get('MountPoint'):
        m.run('/usr/sbin/diskutil','mount',value['DeviceIdentifier'])
        value = m.resolve_part(part)
    path = Path(value.get('MountPoint',''))
    require(str(path).startswith('/Volumes/') and path.is_dir() and not path.is_symlink(), 'No usable verified ESP mount')
    return value,path



def read_fat_sector(value):
    """macOS refuses buffered opens of a mounted FAT partition (EBUSY).

    Unmount only this verified ESP, never the whole internal SSD. Restore its
    original mounted state even if the read or identity check fails.
    """
    was_mounted = bool(value.get('Mounted') or value.get('MountPoint'))
    device = value['DeviceIdentifier']
    if was_mounted:
        m.run('/usr/sbin/diskutil', 'unmount', device)
    try:
        fresh = m.info(device)
        require(not fresh.get('Mounted') and not fresh.get('MountPoint'),
                'Internal ESP is still mounted; cannot read its FAT serial')
        for key in ('DeviceIdentifier', 'DeviceNode', 'DiskUUID', 'ParentWholeDisk', 'Size'):
            require(fresh.get(key) == value.get(key), 'ESP identity changed before raw read')
        with open(fresh['DeviceNode'], 'rb') as stream:
            sector = stream.read(4096)
        require(len(sector) == 4096, 'Short FAT boot-sector read')
        return sector
    finally:
        if was_mounted:
            m.run('/usr/sbin/diskutil', 'mount', device)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review',action='store_true')
    args=parser.parse_args()
    require(os.geteuid()==0,'Run sudo make internal-esp-review or sudo make internal-esp')
    sdinfo,sd=mount('969c748a-4de0-59db-a81c-3bb8fa6862fa')
    espinfo,esp=mount(ESP_UUID)
    rootinfo=m.resolve_part(ROOT_PART)
    require(espinfo.get('ParentWholeDisk')==rootinfo.get('ParentWholeDisk')=='disk0','Unexpected internal SSD')
    disk=m.info('disk0')
    _,parts,*_=m.preflight.read_gpt('/dev/rdisk0',disk['DeviceBlockSize'],disk['TotalSize'])
    receipt=json.loads((sd/'NVME0002/migration.json').read_text())
    by_uuid={p['uuid']:p for p in parts}
    stable=lambda p:{k:v for k,v in p.items() if k!='number'}
    for saved in receipt['protected']:
        require(stable(by_uuid.get(saved['uuid'],{}))==stable(saved),'Protected GPT entry changed')
    for key,kind in (('esp',m.ESP_TYPE),('root',m.ROOT_TYPE)):
        expected={**receipt[key],'type':kind}
        require(stable(by_uuid.get(expected['uuid'],{}))==stable(expected),'Internal ESP/root bounds or type changed')
    require(len(parts)==len(receipt['protected'])+2,'Unexpected extra internal partition')
    sector=read_fat_sector(espinfo)
    espinfo,esp=mount(ESP_UUID)
    require(sector[82:90]==b'FAT32   ' and sector[510:512]==b'\x55\xaa','Not FAT32 ESP')
    serial=struct.unpack_from('<I',sector,67)[0]
    fat=f'{serial:08X}';fat=fat[:4]+'-'+fat[4:]
    initrd=(sd/'NVME0002/initramfs.img').read_bytes()
    init=m.initramfs_members(initrd)
    require(('ROOT_UUID=\''+ROOT_UUID+'\'').encode() in init['etc/nvme-root.conf'][1],'Wrong tested NVMe root')
    kernel=(sd/'NVME0002/vmlinuz').read_bytes()
    entry=next(line.strip() for line in (sd/'grub/grub.cfg').read_text().splitlines() if line.strip().startswith('linux /NVME0002/vmlinuz '))
    require('root=UUID='+ROOT_UUID in entry,'Unexpected NVMe GRUB entry')
    entry=entry.replace('/NVME0002/vmlinuz','/vmlinuz-linux-m4rch',1)
    menu=f"set timeout=3\nset default=0\nmenuentry 'M4RCH' {{\n    search --no-floppy --fs-uuid --set=root {fat}\n    {entry}\n    initrd /initramfs-linux-m4rch.img\n}}\n"
    files={'vmlinuz-linux-m4rch':kernel,'initramfs-linux-m4rch.img':initrd,
           'dtbs/board.dtbo':(sd/'dtbs/board.dtbo').read_bytes(),'grub/grub.cfg':menu.encode(),
           'internal-boot/HANDOVER.md':(PROJECT/'HANDOVER.md').read_text().split('\n---\n',1)[0].encode(),
           'EFI/BOOT/BOOTAA64.EFI':retarget_efi((sd/'EFI/BOOT/BOOTAA64.EFI').read_bytes(),'969C-748A',fat)}
    rootdev=rootinfo['DeviceNode']
    require(not rootinfo.get('Mounted') and not rootinfo.get('MountPoint'),'NVMe root must be unmounted')
    with open(rootdev,'rb') as stream:
        stream.seek(1024); superblock=stream.read(1024)
    require(superblock[56:58]==b'\x53\xef' and str(uuid.UUID(bytes=superblock[104:120]))==ROOT_UUID,'NVMe filesystem identity changed')
    fstab=m.root_text(rootdev,'/etc/fstab')
    require(any('UUID='+ROOT_UUID in l and l.split()[1]=='/' for l in fstab.splitlines() if l.strip() and not l.startswith('#')),'Unexpected root fstab')
    old='PARTUUID=969c748a-4de0-59db-a81c-3bb8fa6862fa'
    lines=fstab.splitlines();boots=[i for i,l in enumerate(lines) if l.strip() and not l.startswith('#') and l.split()[1]=='/boot']
    require(len(boots)==1 and (old.lower() in lines[boots[0]].lower() or 'PARTUUID='+ESP_UUID in lines[boots[0]]),'Unexpected /boot fstab')
    lines[boots[0]]=f'PARTUUID={ESP_UUID} /boot vfat defaults,umask=022 0 2'
    newfstab='\n'.join(lines)+'\n'
    conf=m.root_text(rootdev,'/etc/arch-m4/boot.conf')
    # Retain expansion settings for the old image, but explicitly select NVMe.
    for key,value in {'STORAGE_MODE':'nvme','ROOT_UUID':ROOT_UUID,'ROOT_PARTITION_UUID':ROOT_PART,'BOOT_PARTITION_UUID':ESP_UUID,
                      'ROOT_OFFSET':str(receipt['root']['offset']),'ROOT_BYTES':str(receipt['root']['bytes'])}.items():
        conf=re.sub(r'(?m)^'+key+r'=.*\n?','',conf)+f"{key}='{value}'\n"
    root_files={'/etc/fstab':newfstab.encode(),'/etc/arch-m4/boot.conf':conf.encode(),
                '/usr/lib/m4rch/init-nvme':(PROJECT/'tools/nvme/init').read_bytes(),
                '/usr/lib/initcpio/install/m4rch-root':(PROJECT/'packages/legacy/config-m4rch/mkinitcpio-install').read_bytes(),
                '/usr/bin/m4rch-boot-update':(PROJECT/'packages/legacy/config-m4rch/m4rch-boot-update').read_bytes()}
    sys.path.insert(0,str(PROJECT/'lib'))
    import internal_layout
    from card_disk import DiskUtil
    import internal_boot
    stub=internal_boot.read_state(PROJECT)
    extension=internal_layout.extend(DiskUtil(),stub['partition'])
    print(f'Internal ESP: {esp} ({ESP_UUID}, FAT {fat}). NVMe root: {rootdev}.')
    print('Copy the tested kernel/initramfs/overlay and retarget GRUB. Change only NVMe /boot and boot-update configuration.')
    print('Backups remain on this Mac. No SD writes, GPT edits, or Apple enrollment changes.')
    if args.review:return
    require(shutil.disk_usage(esp).free>sum(map(len,files.values()))+1024**2,'Insufficient ESP space')
    require(input('Type INTERNAL ESP: ')=='INTERNAL ESP','Cancelled')
    backup=PROJECT/'out/internal-esp-backup'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup.mkdir(parents=True,mode=0o700)
    for name in files:
        target=esp/name
        require(not target.is_symlink() and all(not q.is_symlink() for q in target.parents),'Symlink in ESP destination')
        if target.exists():
            dst=backup/'esp'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(target,dst)
    for name in root_files:
        # Save exact prior content before any writes; a missing init-nvme is expected.
        dst=backup/'root'/name.lstrip('/');dst.parent.mkdir(parents=True,exist_ok=True)
        try:
            old_data=m.root_text(rootdev,name)
        except ValueError:
            if name != '/usr/lib/m4rch/init-nvme': raise
            (dst.with_name(dst.name+'.absent')).write_text('Not present before internal ESP migration\n')
        else:
            dst.write_text(old_data)
    (backup/'migration.json').write_text(json.dumps(receipt,indent=2)+'\n')
    for name in ('grub/grub.cfg','EFI/BOOT/BOOTAA64.EFI'):
        dst=backup/'sd'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(sd/name,dst)
    m.run(m.TOOLS/'e2fsck/e2fsck','-f','-n',rootdev)
    for name,data in files.items():
        target=esp/name;target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_name(target.name+'.m4rch-stage');temporary.write_bytes(data)
        require(temporary.read_bytes()==data,'ESP verification failed');temporary.replace(target)
    for index,(name,data) in enumerate(root_files.items()):
        staged=backup/f'new-root-{index}';staged.write_bytes(data)
        m.run(m.TOOLS/'debugfs/debugfs','-w','-R','rm '+name,rootdev)
        m.run(m.TOOLS/'debugfs/debugfs','-w','-R','write '+str(staged)+' '+name,rootdev)
        mode='0100755' if name.startswith('/usr/') else '0100644'
        m.run(m.TOOLS/'debugfs/debugfs','-w','-R','set_inode_field '+name+' mode '+mode,rootdev)
        require(m.root_text(rootdev,name).encode()==data,'NVMe configuration verification failed')
    m.run(m.TOOLS/'e2fsck/e2fsck','-f','-n',rootdev);m.run('sync')
    extension_path=PROJECT/'out/internal-layout-extension.json'
    temporary=extension_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(extension,indent=2)+'\n');temporary.chmod(0o600);temporary.replace(extension_path)
    print('Internal ESP staged. Backup:',backup)
    print('Keep SD inserted until the internal U-Boot bridge is enrolled; copying files alone does not change the enrolled loader.')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.CalledProcessError) as error:raise SystemExit('m4rch: '+str(error))
