#!/usr/bin/env python3
"""Restore the pre-AUDP001 boot.bin and GRUB pair; never reboot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):
    temp=path.with_name(path.name+'.dcp-restore-tmp')
    with temp.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    assert temp.read_bytes()==data
    os.replace(temp,path); assert path.read_bytes()==data

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--esp',type=Path,default=Path('/Volumes/M4RCHESP'))
    args=parser.parse_args(); esp=args.esp
    info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist',str(esp)]))
    assert info.get('DiskUUID')=='5FDB35C6-3A66-416D-8358-6555FD99FCC5' and info.get('MountPoint')==str(esp)
    receipt=json.loads((esp/'AUDP001/rollback.json').read_text())
    for name in ['boot.bin','grub/grub.cfg']:
        item=receipt[name]; backup=esp/'AUDP001'/item['backup']
        assert sha(backup)==item['before_sha256']
        allowed=[item['before_sha256'],item['candidate_sha256']]+item.get('previous_candidate_sha256',[])
        assert sha(esp/name) in allowed, 'Current file changed; refusing overwrite: '+name
    for name in ['grub/grub.cfg','boot.bin']:
        item=receipt[name]; write(esp/name,(esp/'AUDP001'/item['backup']).read_bytes())
    subprocess.run(['sync'],check=True)
    print('Restored previous native-working loader and default GPU16 GRUB entry. No reboot performed.')

if __name__=='__main__': main()
