#!/usr/bin/env python3
"""Capture private, read-only stub-upgrade evidence; mount existing roles only."""
import datetime
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'sdboot'), str(ROOT/'lib')]
import enrollment
import stub_upgrade
from card_disk import DiskUtil
from common import sha256
import card


def capture(output, name, command, timeout=60):
    try:
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
        data=result.stdout
        status=result.returncode
    except subprocess.TimeoutExpired as error:
        data=(error.stdout or b'')+b'\nCapture timed out.\n';status='timeout'
    (output/name).write_bytes(data)
    return {'command':command,'status':status}


def main_preboot(dutil, main):
    containers=[c for c in dutil.apfs()['Containers']
                if c.get('APFSContainerUUID','').upper()==main['container_uuid'].upper()]
    if len(containers)!=1:raise ValueError('Primary macOS container absent or ambiguous')
    volumes=[v for v in containers[0]['Volumes'] if v.get('Roles')==['Preboot']]
    if len(volumes)!=1:raise ValueError('Primary macOS Preboot absent or ambiguous')
    volume=volumes[0]
    info=dutil.info(volume['DeviceIdentifier'])
    if not info.get('MountPoint'):
        dutil.run('mount',volume['DeviceIdentifier'])
        info=dutil.info(volume['DeviceIdentifier'])
    mount=Path(info.get('MountPoint',''))
    if (not mount.is_absolute() or mount.is_symlink()
            or not (str(mount).startswith('/Volumes/') or mount==Path('/System/Volumes/Preboot'))):
        raise ValueError('Unexpected primary macOS Preboot mount')
    check=dutil.info(str(mount))
    expected=volume['APFSVolumeUUID'].upper()
    if any(item.get('VolumeUUID','').upper()!=expected or
           item.get('DeviceIdentifier')!=volume['DeviceIdentifier'] for item in (info,check)):
        raise ValueError('Primary macOS Preboot mount identity changed')
    return card.checked_path(mount,main['vgid']+'/var/db/AdminUserRecoveryInfo.plist')


def main():
    card.require_macos()
    if os.geteuid()!=0:
        raise SystemExit('Run with sudo to read protected policy and rollback receipts.')
    parent=ROOT/'out/stub-diagnostics';parent.mkdir(exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=parent))
    output.chmod(0o700)
    # Keep captures private but readable by the user invoking sudo.
    sudo_uid=os.environ.get('SUDO_UID')
    sudo_gid=os.environ.get('SUDO_GID')
    if sudo_uid is not None and sudo_gid is not None:
        os.chown(output,int(sudo_uid),int(sudo_gid))
    print('Private capture:',output,flush=True)
    dutil=DiskUtil()
    old,identity,roles=enrollment._resolve(ROOT,dutil)
    mounts=stub_upgrade.destinations(dutil,identity,roles)
    record=json.loads((ROOT/'out/sdboot'/stub_upgrade.STATE).read_text())
    backup=Path(record['backup'])
    summary={'identity':identity,'phase':record['phase'],'backup':str(backup),'commands':{}}
    # Hash owner data, never copy credentials or the owner plist itself.
    owner=mounts['Preboot']/'var/db/AdminUserRecoveryInfo.plist'
    source=main_preboot(dutil,old['partition']['plan']['main'])
    sources=[source] if source.is_file() and not source.is_symlink() else []
    summary['owner_metadata']={'stub_sha256':sha256(owner),'source_candidates':[{'path':str(p),'sha256':sha256(p),'matches_stub':sha256(p)==sha256(owner)} for p in sources]}
    summary['loader_sha256']=sha256(mounts['System']/card.RESOURCES/'boot.bin')
    summary['loader_matches_transaction']=summary['loader_sha256']==record['boot_sha256']
    summary['system_version']=plistlib.loads((mounts['System']/'System/Library/CoreServices/SystemVersion.plist').read_bytes())
    candidate=Path(record['candidate'])
    mismatches=[]
    for role,names in record['replacements'].items():
        for name in names:
            source=candidate/'payload'/role/name
            target=card.checked_path(mounts[role],name,leaf_symlink=source.is_symlink())
            if source.is_symlink():
                valid=target.is_symlink() and os.readlink(target)==os.readlink(source)
            else:
                valid=target.is_file() and not target.is_symlink() and sha256(target)==sha256(source)
            if not valid:mismatches.append(role+'/'+name)
    summary['payload_mismatches']=mismatches
    # Full saved-tree verification, including original immutable flags receipt.
    stub_upgrade.validate_backup(backup,record)
    summary['backup_verified']=True
    for name,command,timeout in (
        ('macos-version.txt',['/usr/bin/sw_vers'],10),
        ('policy.txt',['/usr/bin/bputil','-d','-v',identity['vgid']],30),
        ('bputil-help.txt',['/usr/bin/bputil','-h'],10),
        ('apfs.plist',['/usr/sbin/diskutil','apfs','list','-plist'],30),
        ('boot-policy-log.txt',['/usr/bin/log','show','--last','4h','--style','compact','--predicate','process == "bless" OR process == "bootpolicy" OR process == "BootabilityService" OR eventMessage CONTAINS "AP boot mode"'],60),
    ):
        summary['commands'][name]=capture(output,name,command,timeout)
    summary['launcher']=stub_upgrade.recovery_launcher.inspect(mounts['System'],ROOT/'out/sdboot',identity)
    (output/'summary.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
    (output/'transaction.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
    print('Capture complete:',output,flush=True)
    print('No firmware, owner metadata or boot policy was changed. Existing APFS volumes may have been mounted.')

if __name__=='__main__':main()
