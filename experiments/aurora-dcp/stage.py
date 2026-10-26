#!/usr/bin/env python3
"""Stage the validated AUDP001 candidate and make its GRUB entry default."""
import argparse
import datetime
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

from package import PROJECT,OUTPUT,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--esp',type=Path,default=Path('/Volumes/M4RCHESP'))
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args(); esp=args.esp
    spec=importlib.util.spec_from_file_location('direct_stage',PROJECT/'experiments/aurora-direct/stage.py')
    direct=importlib.util.module_from_spec(spec); spec.loader.exec_module(direct)
    direct.validate_esp(esp)
    manifest=json.loads((OUTPUT/'manifest.json').read_text())
    for name,item in manifest['files'].items():
        assert sha(OUTPUT/name)==item['sha256'],name
    assert sha(esp/'boot.bin')=='7005593ebd056d31cb440573ce8f84ee00447a84e81e1ee89f65b0e52ff37738', 'Current loader differs from native AUBS001 rev2'
    cleanup=json.loads((esp/'AUBS001/cleanup-receipt.json').read_text())
    assert sha(esp/'grub/grub.cfg')==cleanup['grub_after_sha256']
    for name,digest in cleanup['preserved_payloads'].items(): assert sha(esp/name)==digest,name
    original=(esp/'grub/grub.cfg').read_text()
    assert original.count("set default='m4rch-aurora-gpu16'")==1
    assert 'm4rch-aurora-dcp001' not in original
    working=re.search(r"(?ms)^menuentry [^\n]+ --id m4rch-aurora-gpu16 \{\n(.*?)^\}\n",original)
    assert working
    body=working[1].replace('/AURG016/vmlinuz','/AUDP001/vmlinuz').replace('/AURG016/initramfs.img','/AUDP001/initramfs.img')
    body=re.sub(r'(?m)^(    linux .*)$',r'\1 m4rch.dcp=1 apple_dart.j713_dcp=1 apple_dart.j713_display=1 drm.debug=0x1e',body)
    entry="menuentry 'Aurora DCP internal panel + GPU (AUDP001; speakers disabled)' --id m4rch-aurora-dcp001 {\n"+body+'}\n\n'
    updated=original.replace("set default='m4rch-aurora-gpu16'","set default='m4rch-aurora-dcp001'")
    first=updated.index('menuentry '); updated=updated[:first]+entry+updated[first:]
    assert len(re.findall(r'^menuentry ',updated,re.M))==6
    (OUTPUT/'grub.cfg').write_text(updated)
    needed=sum((OUTPUT/name).stat().st_size for name in ['Image','initramfs.img','boot.bin'])+32*1024*1024
    assert shutil.disk_usage(esp).free>needed+64*1024*1024
    assert not (esp/'AUDP001').exists(), 'Candidate directory already exists; inspect instead of overwriting'
    plan={'test':'AUDP001','default':'m4rch-aurora-dcp001','native_boot_tested':False,'reboot_performed':False,
          'esp':str(esp),'bytes_required':needed,'fallback_entries':5,'boot_sha256':sha(OUTPUT/'boot.bin')}
    (OUTPUT/'stage-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    if not args.apply: print(json.dumps(plan,indent=2)); return
    target=esp/'AUDP001'; target.mkdir()
    backup=OUTPUT/'staged-backup'; backup.mkdir(exist_ok=False)
    rollback={}
    for name,label,candidate in [('boot.bin','previous.boot.bin',OUTPUT/'boot.bin'),('grub/grub.cfg','previous.grub.cfg',OUTPUT/'grub.cfg')]:
        data=(esp/name).read_bytes()
        direct.atomic_write(target/label,data); direct.atomic_write(backup/label,data)
        rollback[name]={'backup':label,'before_sha256':sha(esp/name),'candidate_sha256':sha(candidate)}
    direct.atomic_write(target/'rollback.json',(json.dumps(rollback,indent=2)+'\n').encode())
    direct.atomic_write(target/'restore.py',(PROJECT/'experiments/aurora-dcp/restore.py').read_bytes())
    for source,dest in [('Image','vmlinuz'),('initramfs.img','initramfs.img'),('profile.json','profile.json'),('manifest.json','manifest.json')]:
        direct.atomic_write(target/dest,(OUTPUT/source).read_bytes())
    direct.atomic_write(esp/'boot.bin',(OUTPUT/'boot.bin').read_bytes())
    direct.atomic_write(esp/'grub/grub.cfg',updated.encode())
    for name,item in rollback.items(): assert sha(esp/name)==item['candidate_sha256']
    for name,digest in cleanup['preserved_payloads'].items(): assert sha(esp/name)==digest
    plan.update({'phase':'staged-awaiting-manual-boot','installed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 'grub_sha256':sha(esp/'grub/grub.cfg'),'rollback':'python3 /Volumes/M4RCHESP/AUDP001/restore.py'})
    data=(json.dumps(plan,indent=2)+'\n').encode()
    direct.atomic_write(target/'stage-receipt.json',data); (OUTPUT/'stage-receipt.json').write_bytes(data)
    subprocess.run(['sync'],check=True)
    print(data.decode())

if __name__=='__main__': main()
