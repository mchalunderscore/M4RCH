#!/usr/bin/env python3
"""Repair parent directories and module-loader diagnostics in the SD NVMe trial."""
import gzip
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import subprocess

PROJECT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('migration',PROJECT/'scripts/migrate-nvme-macos.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def main():
    m.require(os.geteuid()==0,'Run sudo make nvme-repair-initramfs')
    bootinfo=m.resolve_part('969c748a-4de0-59db-a81c-3bb8fa6862fa')
    if not bootinfo.get('MountPoint'):
        m.run('/usr/sbin/diskutil','mount',bootinfo['DeviceIdentifier'])
        bootinfo=m.resolve_part('969c748a-4de0-59db-a81c-3bb8fa6862fa')
    boot=Path(bootinfo.get('MountPoint',''))
    m.require(str(boot).startswith('/Volumes/') and boot.is_dir() and not boot.is_symlink(),'Invalid SD mount')
    kit=boot/'NVME0002';target=kit/'initramfs.img'
    baseblob=(boot/'initramfs-linux-m4rch.img').read_bytes()
    before=target.read_bytes()
    m.require(before.startswith(baseblob),'NVMe trial is not based on current SD initramfs; inspect before repair')
    base=m.initramfs_members(baseblob);old=m.initramfs_members(before)
    m.require('etc/nvme-root.conf' in old and 'etc/nvme-modules' in old,'Missing NVMe trial configuration')
    paths=old['etc/nvme-modules'][1].decode().splitlines()
    for path in paths:
        m.require(path.startswith('/usr/lib/modules/7.1.3-m4rch/') and path.endswith('.ko'),'Unexpected module path')
        m.require(path.lstrip('/') in old,'Missing module payload')
    files=[(name,mode,data) for name,(mode,data) in old.items() if name not in base or name=='init']
    replacements={'init':(stat.S_IFREG|0o755,(PROJECT/'tools/nvme/init').read_bytes()),
                  'sbin/m4rch-insmod':(stat.S_IFREG|0o755,m.module_loader())}
    files=[(name,*replacements.get(name,(mode,data))) for name,mode,data in files]
    files=m.archive_with_parents(files,base)
    candidate=baseblob+gzip.compress(m.newc(files),mtime=0)
    parsed=m.initramfs_members(candidate)
    for path in paths:
        name=path.lstrip('/')
        m.require(parsed[name]==old[name],'Module bytes changed during repair')
        for parent in Path(name).parents:
            if str(parent)=='.':continue
            m.require(str(parent) in parsed,'Missing archive parent: '+str(parent))
    m.require(parsed['etc/nvme-root.conf']==old['etc/nvme-root.conf'],'Root identity changed')
    m.require(shutil.disk_usage(boot).free>len(candidate)+len(before)+1024**2,'Not enough space to preserve a backup and stage repair')
    backup=kit/'initramfs-before-parents.img'
    if not backup.exists():backup.write_bytes(before)
    stage=kit/'initramfs-repair.tmp';stage.write_bytes(candidate)
    m.require(hashlib.sha256(stage.read_bytes()).digest()==hashlib.sha256(candidate).digest(),'Staging verification failed')
    m.run('sync');stage.replace(target);m.run('sync')
    print('Repaired NVMe initramfs parent directories; exact modules and root UUID preserved.')
    print('No root filesystem, GPT, kernel, GRUB default or Apple enrollment changed.')

if __name__=='__main__':main()
