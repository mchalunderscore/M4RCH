#!/usr/bin/env python3
"""Install AUDP001 revision 2 while preserving the original known-working rollback."""
import argparse
import datetime
import hashlib
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
    previous=OUTPUT/'revision-1'
    old=json.loads((previous/'manifest.json').read_text())
    new=json.loads((OUTPUT/'manifest.json').read_text())
    assert old['revision']==1 and new['revision']==2
    for name,item in new['files'].items(): assert sha(OUTPUT/name)==item['sha256'],name
    for name,item in new['kit_sources'].items(): assert sha(PROJECT/name)==item,name
    assert sha(esp/'AUDP001/manifest.json')==sha(previous/'manifest.json')
    for source,target in [('Image','AUDP001/vmlinuz'),('initramfs.img','AUDP001/initramfs.img'),('boot.bin','boot.bin'),('profile.json','AUDP001/profile.json')]:
        assert sha(esp/target)==old['files'][source]['sha256'],target
    prior_receipt=json.loads((previous/'stage-receipt.json').read_text())
    assert sha(esp/'grub/grub.cfg')==prior_receipt['grub_sha256']
    assert sha(esp/'AUDP001/stage-receipt.json')==sha(previous/'stage-receipt.json')
    cleanup=json.loads((esp/'AUBS001/cleanup-receipt.json').read_text())
    for name,digest in cleanup['preserved_payloads'].items(): assert sha(esp/name)==digest,name
    rollback=json.loads((esp/'AUDP001/rollback.json').read_text())
    for name,item in rollback.items():
        assert sha(esp/'AUDP001'/item['backup'])==item['before_sha256'],name
        assert sha(esp/name)==item['candidate_sha256'],name
    original=(esp/'grub/grub.cfg').read_text()
    assert original.count("set default='m4rch-aurora-dcp001'")==1
    entry=re.search(r'(?ms)^menuentry [^\n]+ --id m4rch-aurora-dcp001 \{\n.*?^\}\n',original)
    assert entry and '/AUDP001/vmlinuz' in entry[0] and '/AUDP001/initramfs.img' in entry[0]
    replacement=entry[0].replace('(AUDP001; speakers disabled)','(AUDP001 r2; speakers disabled)')
    replacement=replacement.replace('/AUDP001/vmlinuz','/AUDP001/r2/vmlinuz').replace('/AUDP001/initramfs.img','/AUDP001/r2/initramfs.img')
    updated=original[:entry.start()]+replacement+original[entry.end():]
    assert len(re.findall(r'^menuentry ',updated,re.M))==6
    (OUTPUT/'grub.cfg').write_text(updated)
    target=esp/'AUDP001/r2'; assert not target.exists(), 'Inspect the existing revision-2 directory instead of overwriting'
    needed=sum((OUTPUT/name).stat().st_size for name in ['Image','initramfs.img','boot.bin'])+16*1024*1024
    assert shutil.disk_usage(esp).free>needed+64*1024*1024
    plan={'test':'AUDP001','revision':2,'kernel_release':'7.3.0-m4rch-dcp002',
          'default':'m4rch-aurora-dcp001','esp':str(esp),'payload_directory':'AUDP001/r2',
          'fallback_entries':5,'native_boot_tested':False,'reboot_performed':False,
          'upstream_prs':[429,427,433],'boot_sha256':sha(OUTPUT/'boot.bin')}
    if not args.apply:
        print(json.dumps(plan,indent=2)); return
    target.mkdir()
    for name,label in [('boot.bin','previous.candidate.boot.bin'),('grub/grub.cfg','previous.candidate.grub.cfg'),('AUDP001/stage-receipt.json','previous.stage-receipt.json'),('AUDP001/rollback.json','previous.rollback.json')]:
        direct.atomic_write(target/label,(esp/name).read_bytes())
    for source,destination in [('Image','vmlinuz'),('initramfs.img','initramfs.img'),('profile.json','profile.json'),('manifest.json','manifest.json'),('upstream-manifest.json','upstream-manifest.json')]:
        direct.atomic_write(target/destination,(OUTPUT/source).read_bytes())
    # Keep the original pre-DCP native loader/GRUB backups. Only the accepted
    # candidate hashes change; restoration still returns to the proven setup.
    # Register both old/new states before replacing either active file so a
    # stopped refresh remains restorable at every boundary.
    for name,item in rollback.items():
        item['previous_candidate_sha256']=[item['candidate_sha256']]
    rollback['boot.bin']['candidate_sha256']=sha(OUTPUT/'boot.bin')
    rollback['grub/grub.cfg']['candidate_sha256']=hashlib.sha256(updated.encode()).hexdigest()
    direct.atomic_write(esp/'AUDP001/restore.py',(PROJECT/'experiments/aurora-dcp/restore.py').read_bytes())
    direct.atomic_write(esp/'AUDP001/rollback.json',(json.dumps(rollback,indent=2)+'\n').encode())
    direct.atomic_write(esp/'boot.bin',(OUTPUT/'boot.bin').read_bytes())
    direct.atomic_write(esp/'grub/grub.cfg',updated.encode())
    for source,destination in [('Image','vmlinuz'),('initramfs.img','initramfs.img'),('profile.json','profile.json')]:
        assert sha(target/destination)==new['files'][source]['sha256']
    for name,digest in cleanup['preserved_payloads'].items(): assert sha(esp/name)==digest,name
    assert sha(esp/'boot.bin')==new['files']['boot.bin']['sha256']
    for path in re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)',updated): assert (esp/path.lstrip('/')).is_file(),path
    plan.update({'phase':'staged-awaiting-manual-boot','installed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'grub_sha256':sha(esp/'grub/grub.cfg'),'rollback':'python3 /Volumes/M4RCHESP/AUDP001/restore.py'})
    data=(json.dumps(plan,indent=2)+'\n').encode()
    direct.atomic_write(target/'stage-receipt.json',data)
    direct.atomic_write(esp/'AUDP001/stage-receipt.json',data)
    (OUTPUT/'stage-receipt.json').write_bytes(data)
    subprocess.run(['sync'],check=True)
    print(data.decode())

if __name__=='__main__': main()
