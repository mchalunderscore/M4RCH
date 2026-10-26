#!/usr/bin/env python3
"""Stage AUDP001 r3 multi-mode trial, retaining r2 and the proven rollback."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
from package import PROJECT, OUTPUT, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--esp',type=Path,default=Path('/Volumes/M4RCHESP'))
    p.add_argument('--apply',action='store_true');a=p.parse_args();esp=a.esp
    spec=importlib.util.spec_from_file_location('direct_stage',PROJECT/'experiments/aurora-direct/stage.py')
    direct=importlib.util.module_from_spec(spec);spec.loader.exec_module(direct)
    direct.validate_esp(esp)
    old=json.loads((OUTPUT/'revision-2/manifest.json').read_text())
    new=json.loads((OUTPUT/'manifest.json').read_text())
    assert old['revision']==2 and new['revision']==3
    for name,item in new['files'].items():assert sha(OUTPUT/name)==item['sha256'],name
    for name,digest in new['kit_sources'].items():assert sha(PROJECT/name)==digest,name
    assert sha(esp/'AUDP001/r2/manifest.json')==sha(OUTPUT/'revision-2/manifest.json')
    for src,dst in [('Image','vmlinuz'),('initramfs.img','initramfs.img'),('profile.json','profile.json')]:
        assert sha(esp/'AUDP001/r2'/dst)==old['files'][src]['sha256'],dst
    receipt=json.loads((OUTPUT/'revision-2/stage-receipt.json').read_text())
    assert sha(esp/'boot.bin')==receipt['boot_sha256']
    assert sha(esp/'grub/grub.cfg')==receipt['grub_sha256']
    assert sha(esp/'AUDP001/stage-receipt.json')==sha(OUTPUT/'revision-2/stage-receipt.json')
    rollback=json.loads((esp/'AUDP001/rollback.json').read_text())
    for name,item in rollback.items():
        assert sha(esp/'AUDP001'/item['backup'])==item['before_sha256'],name
        assert sha(esp/name)==item['candidate_sha256'],name
    cleanup=json.loads((esp/'AUBS001/cleanup-receipt.json').read_text())
    for name,digest in cleanup['preserved_payloads'].items():assert sha(esp/name)==digest,name
    original=(esp/'grub/grub.cfg').read_text()
    assert original.count("set default='m4rch-aurora-dcp001'")==1
    entry=re.search(r'(?ms)^menuentry [^\n]+ --id m4rch-aurora-dcp001 \{\n.*?^\}\n',original)
    assert entry and '/AUDP001/r2/vmlinuz' in entry[0]
    replacement=entry[0].replace('(AUDP001 r2; speakers disabled)','(AUDP001 r3 multi-mode; speakers disabled)')
    replacement=replacement.replace('/AUDP001/r2/','/AUDP001/r3/').replace('m4rch.dcp=1','m4rch.dcp=1 appledrm.j614s_modeset=1')
    assert replacement.count('appledrm.j614s_modeset=1')==1
    fallback=entry[0].replace('--id m4rch-aurora-dcp001','--id m4rch-aurora-dcp002-retained')
    fallback=fallback.replace('Aurora DCP internal panel + GPU','Aurora DCP revision 2 retained mode + GPU')
    updated=original[:entry.start()]+replacement+fallback+original[entry.end():]
    assert len(re.findall(r'^menuentry ',original,re.M))==6
    assert len(re.findall(r'^menuentry ',updated,re.M))==7
    assert 'appledrm.j614s_modeset=1' not in fallback
    (OUTPUT/'grub.cfg').write_text(updated)
    target=esp/'AUDP001/r3';assert not target.exists(),'Inspect existing r3 rather than overwrite'
    needed=sum((OUTPUT/n).stat().st_size for n in ['Image','initramfs.img','boot.bin'])+16*1024*1024
    assert shutil.disk_usage(esp).free>needed+64*1024*1024
    plan={'test':'AUDP001','revision':3,'kernel_release':'7.3.0-m4rch-dcp003',
          'default':'m4rch-aurora-dcp001','esp':str(esp),'payload_directory':'AUDP001/r3',
          'fallback_entries':6,'native_boot_tested':False,'reboot_performed':False,
          'modes':'firmware-advertised physical SDR timings; highest refresh preferred up to 120 Hz',
          'experimental_modeset':True,'boot_sha256':sha(OUTPUT/'boot.bin')}
    if not a.apply:print(json.dumps(plan,indent=2));return
    target.mkdir()
    for name,label in [('boot.bin','previous.candidate.boot.bin'),('grub/grub.cfg','previous.candidate.grub.cfg'),('AUDP001/stage-receipt.json','previous.stage-receipt.json'),('AUDP001/rollback.json','previous.rollback.json')]:
        direct.atomic_write(target/label,(esp/name).read_bytes())
    for src,dst in [('Image','vmlinuz'),('initramfs.img','initramfs.img'),('profile.json','profile.json'),('manifest.json','manifest.json'),('upstream-manifest.json','upstream-manifest.json'),('modeset-abi-audit.json','modeset-abi-audit.json')]:
        direct.atomic_write(target/dst,(OUTPUT/src).read_bytes())
    for name,item in rollback.items():
        item['previous_candidate_sha256']=list(dict.fromkeys(item.get('previous_candidate_sha256',[])+[item['candidate_sha256']]))
    rollback['boot.bin']['candidate_sha256']=sha(OUTPUT/'boot.bin')
    rollback['grub/grub.cfg']['candidate_sha256']=hashlib.sha256(updated.encode()).hexdigest()
    direct.atomic_write(esp/'AUDP001/rollback.json',(json.dumps(rollback,indent=2)+'\n').encode())
    direct.atomic_write(esp/'boot.bin',(OUTPUT/'boot.bin').read_bytes())
    direct.atomic_write(esp/'grub/grub.cfg',updated.encode())
    for src,dst in [('Image','vmlinuz'),('initramfs.img','initramfs.img'),('profile.json','profile.json')]:
        assert sha(target/dst)==new['files'][src]['sha256']
    for name,digest in cleanup['preserved_payloads'].items():assert sha(esp/name)==digest,name
    for path in re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)',updated):assert (esp/path.lstrip('/')).is_file(),path
    for name,item in rollback.items():assert sha(esp/name)==item['candidate_sha256'],name
    plan.update({'phase':'staged-awaiting-manual-boot','installed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'grub_sha256':sha(esp/'grub/grub.cfg'),'rollback':'python3 /Volumes/M4RCHESP/AUDP001/restore.py'})
    data=(json.dumps(plan,indent=2)+'\n').encode()
    direct.atomic_write(target/'stage-receipt.json',data)
    direct.atomic_write(esp/'AUDP001/stage-receipt.json',data)
    (OUTPUT/'stage-receipt.json').write_bytes(data)
    subprocess.run(['sync'],check=True);print(data.decode())

if __name__=='__main__':main()
