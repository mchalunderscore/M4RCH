#!/usr/bin/env python3
"""Install the qualified keyboard trial atomically; never reboot or enroll."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def atomic(path,data):
    temporary=path.with_name(path.name+'.keyboard-new')
    with temporary.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);a=p.parse_args()
    if os.geteuid()!=0:raise ValueError('Native sudo required')
    info=json.loads(subprocess.check_output(['findmnt','-J','-o','TARGET,UUID,PARTUUID,OPTIONS','/boot'],text=True))['filesystems'][0]
    if info['target']!='/boot' or info['uuid']!='33CE-1F10' or info['partuuid']!='5fdb35c6-3a66-416d-8358-6555fd99fcc5' or 'rw' not in info['options'].split(','):raise ValueError('Unexpected boot ESP or mount options')
    receipt=json.loads((a.candidate/'receipt.json').read_text());target=Path('/boot/boot.bin')
    if sha(target)!=receipt['original_bundle_sha256']:raise ValueError('Installed stage 2 changed')
    if sha(a.candidate/'boot.bin')!=receipt['new_bundle_sha256'] or sha(a.candidate/'boot-before.bin')!=receipt['original_bundle_sha256']:raise ValueError('Candidate or backup changed')
    backup=Path('/boot/keyboard-trial');backup.mkdir(exist_ok=True)
    if (backup/'boot-before.bin').exists() and sha(backup/'boot-before.bin')!=receipt['original_bundle_sha256']:raise ValueError('Different existing rollback file')
    for name in ['boot-before.bin','boot.bin','receipt.json','uboot.config','control.dtb']:
        shutil.copyfile(a.candidate/name,backup/name)
    os.sync()
    if sha(backup/'boot-before.bin')!=receipt['original_bundle_sha256']:raise ValueError('Rollback readback failed')
    try:
        atomic(target,(a.candidate/'boot.bin').read_bytes());os.sync()
        if sha(target)!=receipt['new_bundle_sha256']:raise ValueError('Installed readback mismatch')
    except Exception:
        atomic(target,(backup/'boot-before.bin').read_bytes());os.sync();raise
    receipt['installed']=True;receipt['installation_boot_id']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    (backup/'installed.json').write_text(json.dumps(receipt,indent=2)+'\n');os.sync()
    print('Installed keyboard-only stage 2:',sha(target))
    print('Rollback:',backup/'boot-before.bin')
    print('No reboot performed; keyboard behavior remains untested.')
if __name__=='__main__':main()
