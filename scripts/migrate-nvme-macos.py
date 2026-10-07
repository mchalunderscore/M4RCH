#!/usr/bin/env python3
"""Offline SD-to-NVMe clone on macOS, confined to the authorized reservation."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
import uuid

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'scripts'))
import importlib.util
spec = importlib.util.spec_from_file_location('preflight', PROJECT / 'scripts/nvme-preflight.py')
preflight = importlib.util.module_from_spec(spec); spec.loader.exec_module(preflight)
require = preflight.require
ESP_TYPE = 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'
ROOT_TYPE = '0fc63daf-8483-4772-8e79-3d69d8477de4'
BASIC_TYPE = 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
TOOLS = preflight.TOOLS
STATE = PROJECT / 'out/nvme-macos-migration.json'


def run(*args, capture=False, allowed=(0,)):
    print('+', ' '.join(map(str,args)), flush=True)
    result = subprocess.run(list(map(str,args)), capture_output=capture, text=True)
    require(result.returncode in allowed, 'Command failed: '+str(args[0])+' (exit '+str(result.returncode)+')')
    return result.stdout if capture else None


def info(device): return preflight.plist('info','-plist',device)


def save(value):
    stage = STATE.with_suffix('.tmp')
    stage.write_text(json.dumps(value,indent=2)+'\n'); os.chmod(stage,0o600)
    with stage.open('rb') as f: os.fsync(f.fileno())
    stage.replace(STATE)
    run('sync')


def protect(before, after, reservation):
    stable = lambda p: {key:value for key,value in p.items() if key != 'number'}
    expected = {p['uuid']:stable(p) for p in before if p['uuid'] != reservation}
    actual = {p['uuid']:stable(p) for p in after}
    require(len(actual) == len(after), 'Duplicate GPT UUID')
    require(all(actual.get(key) == value for key,value in expected.items()), 'A protected GPT entry changed')
    return [p for p in after if p['uuid'] not in expected]


def validate_split(before, after, plan, types=False):
    added = protect(before,after,plan['reservation_uuid'])
    require(len(added)==2, 'Expected exactly two replacement partitions')
    added.sort(key=lambda p:p['offset']); esp,root=added
    start,size,esp_size=plan['reservation_offset'],plan['reservation_bytes'],plan['esp_bytes']
    require((esp['offset'],esp['bytes'],root['offset'],root['bytes']) ==
            (start,esp_size,start+esp_size,size-esp_size), 'Split escaped the reserved bounds')
    if types: require(esp['type']==ESP_TYPE and root['type']==ROOT_TYPE, 'Wrong ESP/root GPT types')
    return esp,root


def cpio_members(blob):
    """Parse newc archives without extracting any supplied path."""
    offset=0; result={}
    while offset<len(blob):
        if blob[offset]==0: offset+=1; continue
        header=blob[offset:offset+110]
        require(len(header)==110 and header[:6]==b'070701', 'Unsupported/truncated newc archive')
        fields=[int(header[6+i*8:14+i*8],16) for i in range(13)]
        size,namesize=fields[6],fields[11]
        require(0<namesize<=4096 and size<=256*1024**2, 'Invalid cpio member size')
        name=blob[offset+110:offset+110+namesize]
        require(len(name)==namesize and name.endswith(b'\0'), 'Invalid cpio name')
        offset=(offset+110+namesize+3)&~3
        content=blob[offset:offset+size]
        require(len(content)==size,'Truncated cpio data')
        offset=(offset+size+3)&~3
        decoded=name[:-1].decode('utf-8')
        if decoded!='TRAILER!!!': result[decoded.removeprefix('./')]=(fields[1],content)
    return result


def initramfs_members(blob):
    offset=0
    # Early uncompressed microcode archives can precede the main gzip archive.
    while blob[offset:offset+6]==b'070701':
        while True:
            header=blob[offset:offset+110]
            require(len(header)==110 and header[:6]==b'070701','Invalid early archive')
            size=int(header[54:62],16);namesize=int(header[94:102],16)
            require(0<namesize<=4096,'Invalid early name')
            name=blob[offset+110:offset+110+namesize]
            offset=(offset+110+namesize+3)&~3;offset=(offset+size+3)&~3
            require(offset<=len(blob),'Truncated early archive')
            if name==b'TRAILER!!!\0': break
        while offset<len(blob) and blob[offset]==0: offset+=1
    require(blob[offset:offset+2]==b'\x1f\x8b', 'Expected gzip main initramfs')
    return cpio_members(gzip.decompress(blob[offset:]))


def newc(files):
    output=bytearray()
    for inode,(name,mode,content) in enumerate([*files,('TRAILER!!!',0,b'')],1):
        encoded=name.encode()+b'\0'
        fields=(inode,mode,0,0,1,0,len(content),0,0,0,0,len(encoded),0)
        output+=b'070701'+''.join(f'{value:08x}' for value in fields).encode()+encoded
        output+=bytes((-len(output))%4);output+=content;output+=bytes((-len(output))%4)
    return bytes(output)


def archive_with_parents(files,existing):
    # The kernel's cpio unpacker does not recursively create missing parents.
    # Preserve existing symlinks such as /sbin -> usr/bin.
    known=set(existing);result=[]
    for name,mode,data in files:
        components=name.split('/')
        require(all(component and component not in ('.','..') for component in components),'Unsafe generated archive path')
        for length in range(1,len(components)):
            parent='/'.join(components[:length])
            if parent not in known:
                result.append((parent,stat.S_IFDIR|0o755,b''));known.add(parent)
        result.append((name,mode,data));known.add(name)
    return result


def module_order(dependencies, builtin):
    rows={}
    for line in dependencies.splitlines():
        path, separator, rest=line.partition(':')
        require(separator and re.fullmatch(r'[A-Za-z0-9_./+-]+\.ko',path),'Unsupported module dependency entry')
        rows[path]=rest.split()
    if any(path.endswith('/nvme-apple.ko') for path in builtin.splitlines()):return []
    candidates=[path for path in rows if path.endswith('/nvme-apple.ko')]
    require(len(candidates)==1,'Cannot identify exact Apple NVMe module')
    ordered=[]; visiting=set()
    def visit(path):
        require(path in rows,'Missing module dependency: '+path)
        if path in ordered:return
        require(path not in visiting,'Cyclic module dependencies')
        visiting.add(path)
        for dependency in rows[path]:visit(dependency)
        visiting.remove(path);ordered.append(path)
    visit(candidates[0]);return ordered


def module_loader():
    with tempfile.TemporaryDirectory(dir=PROJECT/'out',prefix='nvme-loader-') as directory:
        obj=Path(directory)/'insmod.o'
        run('clang','--target=aarch64-linux-gnu','-c',PROJECT/'tools/nvme/insmod.S','-o',obj)
        blob=obj.read_bytes()
        require(blob[:6]==b'\x7fELF\x02\x01','Expected little-endian ELF64 object')
        shoff=struct.unpack_from('<Q',blob,40)[0]
        shsize,shnum,strings=struct.unpack_from('<HHH',blob,58)
        sections=[struct.unpack_from('<IIQQQQIIQQ',blob,shoff+i*shsize) for i in range(shnum)]
        names=blob[sections[strings][4]:sections[strings][4]+sections[strings][5]]
        require(not any(sec[1] in (4,9) and sec[5] for sec in sections),'Loader contains unresolved relocations')
        text=[sec for sec in sections if names[sec[0]:].split(b'\0',1)[0]==b'.text']
        require(len(text)==1,'Missing loader text')
        code=blob[text[0][4]:text[0][4]+text[0][5]]
        address=0x400000;offset=128;length=offset+len(code)
        header=struct.pack('<16sHHIQQQIHHHHHH',b'\x7fELF\x02\x01\x01'+bytes(9),2,183,1,address+offset,64,0,0,64,56,1,0,0,0)
        segment=struct.pack('<IIQQQQQQ',1,5,0,address,address,length,length,4096)
        return header+segment+bytes(offset-len(header)-len(segment))+code


def storage_modules(source,release,builtin):
    require('fs/ext4/ext4.ko' in builtin,'Built-in ext4 required')
    dependencies=root_text(source,'/usr/lib/modules/'+release+'/modules.dep')
    order=module_order(dependencies,builtin)
    files=[]
    if not order:return files
    with tempfile.TemporaryDirectory(dir=PROJECT/'out',prefix='nvme-modules-') as directory:
        for index,path in enumerate(order):
            full='/usr/lib/modules/'+release+'/'+path
            destination=Path(directory)/str(index)
            run(TOOLS/'debugfs/debugfs','-R','dump '+full+' '+str(destination),source)
            blob=destination.read_bytes()
            require(blob[:4]==b'\x7fELF' and ('vermagic='+release+' ').encode() in blob,'Module release mismatch: '+path)
            files.append((full.lstrip('/'),stat.S_IFREG|0o644,blob))
    files.append(('sbin/m4rch-insmod',stat.S_IFREG|0o755,module_loader()))
    paths=''.join('/usr/lib/modules/'+release+'/'+path+'\n' for path in order).encode()
    files.append(('etc/nvme-modules',stat.S_IFREG|0o644,paths))
    print('Early NVMe modules:',', '.join(order),flush=True)
    return files


def completed_clone(state,root,esp):
    if not state or state.get('phase')!='cloning':return False
    require(re.fullmatch(r'[0-9a-f]{64}',state.get('clone_sha256','')) is not None,'Incomplete clone receipt')
    require(state.get('root')==root and state.get('esp')==esp,'Copied target partition identity changed')
    return True


def clone(source,destination,source_bytes,target_bytes):
    amount=(source_bytes+4095)//4096*4096
    require(amount<=target_bytes,'Destination is too small')
    digest=hashlib.sha256();done=0;last=time.monotonic()
    with open(source,'rb',buffering=0) as src, open(destination,'r+b',buffering=0) as dst:
        while done<source_bytes:
            expected=min(4*1024**2,source_bytes-done)
            data=src.read(expected)
            require(len(data)==expected,'Short source read')
            digest.update(data)
            padded=data+bytes((-len(data))%4096)
            view=memoryview(padded);written=0
            while written<len(view):
                count=dst.write(view[written:]);require(count and count%4096==0,'Short/unaligned destination write');written+=count
            # Read back each destination chunk before proceeding.
            dst.seek(done);check=dst.read(len(padded));require(check==padded,'Clone read-back mismatch')
            dst.seek(done+len(padded));done+=len(data)
            if time.monotonic()-last>5:
                print(f'Clone verified {done/1024**3:.1f}/{source_bytes/1024**3:.1f} GiB',flush=True);last=time.monotonic()
        os.fsync(dst.fileno())
    return digest.hexdigest()


def root_text(device,path):
    text=run(TOOLS/'debugfs/debugfs','-R','cat '+path,device,capture=True)
    require(text and 'File not found' not in text,'Missing root file: '+path)
    return text


def resolve_part(uuid_value):
    disks=preflight.plist('list','-plist','physical')['AllDisksAndPartitions']
    found=[p['DeviceIdentifier'] for d in disks for p in d.get('Partitions',[]) if p.get('DiskUUID','').lower()==uuid_value]
    require(len(found)==1,'macOS has not recognized the updated GPT; stop and inspect before continuing')
    return info(found[0])


def stage_trial(boot, root_device, root_part, plan, original, release, original_initrd,module_files,esp_part,before):
    kit=boot/'NVME0002'
    require(not kit.exists(),'NVME0002 already exists; inspect before replacing it')
    kit.mkdir()
    init=(PROJECT/'tools/nvme/init').read_bytes()
    config=(f"ROOT_UUID='{plan['root_uuid']}'\nROOT_PARTITION_UUID='{root_part['uuid']}'\n"
            f"ROOT_OFFSET='{root_part['offset']}'\nROOT_BYTES='{root_part['bytes']}'\nKERNEL_RELEASE='{release}'\n").encode()
    combined=original_initrd+gzip.compress(newc(archive_with_parents([('init',stat.S_IFREG|0o755,init),('etc/nvme-root.conf',stat.S_IFREG|0o644,config),*module_files],initramfs_members(original_initrd))),mtime=0)
    parsed=initramfs_members(combined)
    require(parsed['init'][1]==init and parsed['etc/nvme-root.conf'][1]==config,'Appended initramfs verification failed')
    (kit/'initramfs.img').write_bytes(combined)
    shutil.copyfile(boot/'vmlinuz-linux-m4rch',kit/'vmlinuz')
    (kit/'grub-before.cfg').write_text(original)
    (kit/'HANDOVER.md').write_text('''# NVMe-root trial

macOS cloned the unmounted SD root to NVMe with a new ext4 UUID, left an empty FAT32 ESP placeholder (GPT typing may still be pending) and selected this isolated SD-loaded trial. Keep the SD fallback unchanged.

Capture `findmnt / /boot`, `lsblk -o NAME,SIZE,FSTYPE,UUID,PARTUUID,MOUNTPOINTS`, and kernel ANS/NVMe logs. Verify root writes and an ordinary application package transaction. Do not bypass the old boot.conf root-UUID guard: maintained kernel/config/firmware updates still need NVMe integration.

The kernel and appended initramfs are in /boot/NVME0002; rollback restores grub-before.cfg to /boot/grub/grub.cfg from macOS. Do not run the older NVME0001 partition/migration kit. Return mount UUIDs, ANS errors and boot/shutdown results.
''')
    (kit/'migration.json').write_text(json.dumps(dict(root=root_part,esp=esp_part,protected=[p for p in before if p['uuid']!=plan['reservation_uuid']],root_uuid=plan['root_uuid'],kernel_release=release),indent=2)+'\n')
    shutil.copyfile(PROJECT/'tools/nvme/finalize-types.py',kit/'finalize-types.py')
    with (kit/'HANDOVER.md').open('a') as handover:
        handover.write('\nAfter verifying NVMe root boot, run `sudo python3 /boot/NVME0002/finalize-types.py`. It changes only the two reserved partitions to EFI/Linux GPT types after checking all protected entries. Keep the FAT32 partition without boot files.\n')
    linux=next(line.strip() for line in original.splitlines() if line.strip().startswith('linux '))
    require('root=UUID='+plan['sd_root_uuid'] in linux and 'rdinit=/init' in linux,'Unexpected SD boot entry')
    require(linux.split()[1]=='/vmlinuz-linux-m4rch','First SD boot entry is not the maintained kernel')
    linux=re.sub(r'^linux\s+\S+','linux /NVME0002/vmlinuz',linux).replace('root=UUID='+plan['sd_root_uuid'],'root=UUID='+plan['root_uuid'])
    search=next(line.strip() for line in original.splitlines() if line.strip().startswith('search '))
    require(re.search(r'(?m)^\s*set default=',original),'Missing explicit GRUB default')
    result=re.sub(r'(?m)^\s*set default=.*$','set default=m4rch-nvme-macos',original)
    result+="\nmenuentry 'M4RCH NVMe root trial' --id=m4rch-nvme-macos {\n    "+search+'\n    '+linux+'\n    initrd /NVME0002/initramfs.img\n}\n'
    stage=boot/'grub/grub-nvme.tmp';stage.write_text(result);run('sync');stage.replace(boot/'grub/grub.cfg');run('sync')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight',type=Path,required=True)
    parser.add_argument('--review',action='store_true',help='Validate inputs and show intended changes; no disk writes')
    parser.add_argument('--resume',action='store_true',help='Continue a verified completed split without splitting again')
    args=parser.parse_args()
    require(sys.platform=='darwin' and os.geteuid()==0,'Run with sudo on macOS')
    require(STATE.exists() if args.resume else not STATE.exists(),'Use the checked resume command for an existing migration state')
    pending=json.loads(STATE.read_text()) if args.resume else None
    if pending:
        require(pending['phase'] in ('splitting','partitioned','cloning'),'This phase cannot be resumed automatically')
        require(Path(pending['preflight']).resolve()==args.preflight.resolve(),'Resume requires the original preflight')
        if pending['phase']=='cloning':
            require(re.fullmatch(r'[0-9a-f]{64}',pending.get('clone_sha256','')) is not None,'Clone did not finish; automatic post-copy resume refused')
    receipt=json.loads((args.preflight/'receipt.json').read_text())
    plan=json.loads((PROJECT/'out/nvme-migration/plan.json').read_text())
    require(receipt.get('read_only') is True and receipt.get('e2fsck_exit')==0,'Preflight did not pass')
    for key,path in [('e2fsck','e2fsck/e2fsck'),('tune2fs','misc/tune2fs'),('resize2fs','resize/resize2fs'),('debugfs','debugfs/debugfs')]:
        require(hashlib.sha256((TOOLS/path).read_bytes()).hexdigest()==receipt['tools'][key],'Native tool changed since preflight')
    sd=receipt['source'].replace('/dev/rdisk','/dev/disk').rsplit('s',1)[0]
    source,_,source_part=preflight.validate_disk(sd)
    require(not source_part.get('MountPoint'),'SD root must be unmounted')
    raw=receipt['nvme_raw'];whole=raw.replace('/dev/rdisk','disk')
    whole_info=info(whole)
    require(whole_info.get('Internal') is True and whole_info.get('BusProtocol')=='Apple Fabric'
            and whole_info.get('TotalSize')==plan['disk_bytes'] and whole_info.get('DeviceBlockSize')==4096,'Wrong internal SSD')
    def current(): return preflight.read_gpt(raw,4096,plan['disk_bytes'])
    header,before,head,tail,tail_offset=current()
    if args.resume:
        require(all(header[key]==receipt['gpt'][key] for key in ('guid','first','last','count','entry_size','current','other','entry_lba')), 'GPT disk/header identity changed')
        require(pending['before']==receipt['partitions'],'Saved migration baseline differs from preflight')
        before=receipt['partitions']
        esp,root=validate_split(before,current()[1],plan)
        require(esp['type'] in (BASIC_TYPE,ESP_TYPE) and root['type'] in (BASIC_TYPE,ROOT_TYPE),'Unexpected replacement types')
        reserved_info=None
    else:
        require(header==receipt['gpt'] and before==receipt['partitions'],'GPT changed since passing preflight')
        reserved=[p for p in before if p['uuid']==plan['reservation_uuid']]
        require(len(reserved)==1 and reserved[0]['type']==BASIC_TYPE and
                (reserved[0]['offset'],reserved[0]['bytes'])==(plan['reservation_offset'],plan['reservation_bytes']),'Wrong reservation')
        reserved_info=resolve_part(plan['reservation_uuid'])
        require(reserved_info.get('FilesystemType')=='exfat' and reserved_info.get('VolumeName')=='M4RCH_ROOT','Reservation is not the authorized exFAT volume')
    boot_info=resolve_part(plan['sd_boot_partition_uuid'])
    if not boot_info.get('MountPoint'):
        require(not args.review,'Mount the SD ESP before a read-only review')
        run('/usr/sbin/diskutil','mount',boot_info['DeviceIdentifier']);boot_info=resolve_part(plan['sd_boot_partition_uuid'])
    boot=Path(boot_info.get('MountPoint',''))
    require(str(boot).startswith('/Volumes/') and boot.is_dir() and not boot.is_symlink(),'Invalid SD ESP mount')
    original=(boot/'grub/grub.cfg').read_text();original_initrd=(boot/'initramfs-linux-m4rch.img').read_bytes()
    require(shutil.disk_usage(boot).free > len(original_initrd)+(boot/'vmlinuz-linux-m4rch').stat().st_size+16*1024**2,'SD ESP needs free space for the isolated rollback-safe trial')
    members=initramfs_members(original_initrd)
    bootconf=members['etc/sdboot.conf'][1].decode()
    release_match=re.search(r"^KERNEL_RELEASE='([A-Za-z0-9._+-]+)'$",bootconf,re.M)
    require(release_match is not None and "TESTING='0'" in bootconf,'Unsupported source initramfs')
    release=release_match[1]
    require(root_text(source,'/usr/lib/modules/'+release+'/pkgbase').strip()=='linux-m4rch','SD kernel/initramfs package mismatch')
    builtin=root_text(source,'/usr/lib/modules/'+release+'/modules.builtin')
    module_files=storage_modules(source,release,builtin)
    original_fstab=root_text(source,'/etc/fstab')
    require(not (boot/'NVME0002').exists(),'NVME0002 already exists')
    require(source_part['Size']<=plan['reservation_bytes']-plan['esp_bytes'],'Destination smaller than SD root')
    print('Resume existing checked ESP/root split.' if args.resume else 'Replace only '+reserved_info['DeviceIdentifier']+' with 1 GiB empty ESP and remaining ext4 root.')
    print('Clone',source_part['Size'],'bytes from',source,'; keep SD root unchanged.')
    print('Use SD /boot; select an isolated NVMe trial. No Apple enrollment changes.')
    if args.review: print('Review complete. No disk writes.');return
    if args.resume:
        require(input('Type RESUME NVME: ')=='RESUME NVME','Not confirmed')
        validate_split(before,current()[1],plan)
        state=pending
        backup=PROJECT/'out/nvme-macos-backup'
        require((backup/'grub-before.cfg').read_text()==original,'SD GRUB changed since migration started')
        run(TOOLS/'e2fsck/e2fsck','-f','-n',source)
    else:
        require(input('Type MIGRATE '+plan['reservation_uuid']+': ')=='MIGRATE '+plan['reservation_uuid'],'Not confirmed')
        require(current()[1]==before,'GPT changed during confirmation')
        run(TOOLS/'e2fsck/e2fsck','-f','-n',source)
        backup=PROJECT/'out/nvme-macos-backup';require(not backup.exists(),'Prior migration backup exists')
        backup.mkdir(mode=0o700)
        (backup/'gpt-head.bin').write_bytes(head);(backup/'gpt-tail.bin').write_bytes(tail)
        (backup/'grub-before.cfg').write_text(original)
        state=dict(schema=1,phase='splitting',preflight=str(args.preflight.resolve()),before=before,backup_tail_offset=tail_offset)
        save(state)
        run('/usr/sbin/diskutil','splitPartition',reserved_info['DeviceIdentifier'],'2',
            'MS-DOS FAT32','M4RCHESP',str(plan['esp_bytes'])+'B','ExFAT','M4RCH_ROOT','R')
    esp,root=validate_split(before,current()[1],plan)
    # macOS can reject raw GPT edits on its active system disk. Keep the
    # checked allocation and defer the two type fields to native Linux.
    esp,root=validate_split(before,current()[1],plan)
    require(esp['type'] in (BASIC_TYPE,ESP_TYPE) and root['type'] in (BASIC_TYPE,ROOT_TYPE),'Unexpected replacement GPT type')
    state['gpt_types_pending']=esp['type']!=ESP_TYPE or root['type']!=ROOT_TYPE
    if state['gpt_types_pending']:
        print('GPT typing deferred to Linux; FAT32 is an empty ESP placeholder.',flush=True)
    copied_receipt=completed_clone(pending,root,esp)
    copied_root=pending.get('root') if copied_receipt else None
    copied_esp=pending.get('esp') if copied_receipt else None
    if not copied_receipt:
        state.update(phase='partitioned',esp=esp,root=root);save(state)
    root_info=resolve_part(root['uuid']);esp_info=resolve_part(esp['uuid'])
    for part,live in [(root,root_info),(esp,esp_info)]:
        require((live.get('PartitionMapPartitionOffset'),live.get('Size'))==(part['offset'],part['bytes']),'Cached macOS partition map differs; stop before writing filesystems')
        if live.get('MountPoint'):run('/usr/sbin/diskutil','unmount',live['DeviceIdentifier'])
    require(esp_info.get('Content') in ('EFI','Microsoft Basic Data') and esp_info.get('FilesystemType')=='msdos','Placeholder is not the expected empty FAT volume')
    raw_root='/dev/r'+root_info['DeviceIdentifier']
    # Darwin raw devices require hardware-sector-aligned I/O. e2fsprogs reads
    # the superblock at byte1024; use the buffered block node for filesystem
    # operations, reserving the raw node for the aligned clone.
    root_device='/dev/'+root_info['DeviceIdentifier']
    already_copied=copied_receipt
    if already_copied:
        require(copied_root==root and copied_esp==esp,'Copied target partition identity changed')
        with open(raw_root,'rb',buffering=0) as stream: block=stream.read(4096)
        require(len(block)==4096 and block[1080:1082]==b'\x53\xef','Copied root lacks ext4 superblock')
        require(str(uuid.UUID(bytes=block[1128:1144]))==plan['sd_root_uuid'],'Copied filesystem UUID changed before post-copy checks')
        print('Verified completed clone receipt; continuing without copying again.',flush=True)
    else:
        state['phase']='cloning';save(state)
        state['clone_sha256']=clone(source,raw_root,source_part['Size'],root['bytes']);save(state)
    run(TOOLS/'e2fsck/e2fsck','-f','-n',root_device)
    run(TOOLS/'misc/tune2fs','-U',plan['root_uuid'],root_device)
    run(TOOLS/'e2fsck/e2fsck','-f','-p',root_device,allowed=(0,1))
    run(TOOLS/'resize/resize2fs',root_device)
    run(TOOLS/'e2fsck/e2fsck','-f','-n',root_device)
    lines=original_fstab.splitlines()
    roots=[line for line in lines if len(line.split())>1 and not line.lstrip().startswith('#') and line.split()[1]=='/']
    require(len(roots)==1,'Ambiguous fstab root')
    require(any('PARTUUID='+plan['sd_boot_partition_uuid'] in line and '/boot' in line for line in lines),'Unexpected boot fstab')
    updated='\n'.join(f"UUID={plan['root_uuid']} / ext4 defaults,noatime 0 1" if line==roots[0] else line for line in lines)+'\n'
    staged=backup/'fstab-nvme';staged.write_text(updated)
    run(TOOLS/'debugfs/debugfs','-w','-R','rm /etc/fstab',root_device)
    run(TOOLS/'debugfs/debugfs','-w','-R','write '+str(staged)+' /etc/fstab',root_device)
    require(root_text(root_device,'/etc/fstab')==updated,'Copied fstab verification failed')
    run(TOOLS/'e2fsck/e2fsck','-f','-n',root_device)
    state['phase']='root-ready';save(state)
    stage_trial(boot,root_device,root,plan,original,release,original_initrd,module_files,esp,before)
    state['phase']='boot-staged';save(state)
    print('NVMe trial selected. Empty FAT32 ESP placeholder prepared; finish GPT types in Linux. SD fallback preserved; no automatic reboot.')
    print('Rollback: restore',str(boot/'NVME0002/grub-before.cfg'),'to',str(boot/'grub/grub.cfg'))

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.CalledProcessError,KeyError) as error:
        print('m4rch migration stopped:',error,file=sys.stderr);sys.exit(1)
