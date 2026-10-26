#!/usr/bin/env python3
"""Install r6 runtime, retaining the tested r5 loader/kernel and all fallbacks."""
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
    p.add_argument('--esp',type=Path,default=Path('/Volumes/M4RCHESP'));p.add_argument('--apply',action='store_true')
    a=p.parse_args();esp=a.esp;out=OUTPUT/'bootfb-r6'
    spec=importlib.util.spec_from_file_location('direct',PROJECT/'experiments/aurora-direct/stage.py')
    direct=importlib.util.module_from_spec(spec);spec.loader.exec_module(direct);direct.validate_esp(esp)
    manifest=json.loads((out/'manifest.json').read_text());assert manifest['revision']==6
    for n,item in manifest['files'].items():assert sha(out/n)==item['sha256'],n
    for n,digest in manifest['kit_sources'].items():assert sha(PROJECT/n)==digest,n
    previous=json.loads((esp/'AUDP001/stage-receipt.json').read_text());assert previous['revision']==5
    assert sha(esp/'boot.bin')==previous['boot_sha256']==sha(OUTPUT/'desktop-r5/boot.bin')
    assert sha(esp/'grub/grub.cfg')==previous['grub_sha256']
    assert sha(esp/'AUDP001/r5/vmlinuz')==sha(OUTPUT/'desktop-r5/Image')
    rollback=json.loads((esp/'AUDP001/rollback.json').read_text())
    for n,item in rollback.items():
        assert sha(esp/n)==item['candidate_sha256']
        assert sha(esp/'AUDP001'/item['backup'])==item['before_sha256']
    original=(esp/'grub/grub.cfg').read_text()
    assert "set default='m4rch-aurora-dcp001'" in original
    entry=re.search(r'(?ms)^menuentry [^\n]+ --id m4rch-aurora-dcp001 \{\n.*?^\}\n',original)
    assert entry and '/AUDP001/r5/vmlinuz' in entry[0] and '/AUDP001/r5/initramfs.img' in entry[0]
    assert len(re.findall(r'^menuentry ',original,re.M))==8
    new=entry[0].replace('AUDP001 r5;','AUDP001 r6;').replace('/AUDP001/r5/initramfs.img','/AUDP001/r6/initramfs.img')
    old=entry[0].replace('--id m4rch-aurora-dcp001 {','--id m4rch-aurora-dcp005-previous {')
    old=re.sub(r"^menuentry '[^']+'","menuentry 'Previous DCP r5 candidate (speakers disabled)'",old)
    updated=original[:entry.start()]+new+'\n'+old+original[entry.end():]
    rollback_grub=(esp/'AUDP001'/rollback['grub/grub.cfg']['backup']).read_text()
    protected={n:sha(esp/n.lstrip('/')) for n in set(re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)',original))}
    retire='AUDP001/r3/initramfs.img';archive=out/'retired-r3-initramfs.img'
    assert '/'+retire not in original+updated+rollback_grub
    expected=sha(OUTPUT/'initramfs.img')
    present=(esp/retire).exists();assert sha(esp/retire if present else archive)==expected
    retire_bytes=(esp/retire if present else archive).stat().st_size
    target=esp/'AUDP001/r6';assert not target.exists()
    free=shutil.disk_usage(esp).free
    needed=(out/'initramfs.img').stat().st_size+4*1024**2
    assert free+(retire_bytes if present else 0)>needed+32*1024**2
    plan={'test':'AUDP001','revision':6,'kernel_release':'7.3.0-m4rch-dcp005','loader_revision':'DCP005',
        'default':'m4rch-aurora-dcp001','payload_directory':'AUDP001/r6','fallback_entries':8,
        'kernel_reused':'/AUDP001/r5/vmlinuz','boot_sha256':sha(esp/'boot.bin'),
        'grub_sha256':hashlib.sha256(updated.encode()).hexdigest(),'protected_payloads':protected,
        'retired_unreferenced_payload':{'path':retire,'sha256':expected,'archive':str(archive),'bytes':retire_bytes},
        'native_boot_tested':False,'reboot_performed':False,'speakers_enabled':False,'free_before':free,
        'rollback':'python3 /Volumes/M4RCHESP/AUDP001/restore.py'}
    (out/'grub.cfg').write_text(updated);(out/'stage-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    if not a.apply:print(json.dumps(plan,indent=2));return
    if not archive.exists():archive.write_bytes((esp/retire).read_bytes())
    assert sha(archive)==expected
    if present:(esp/retire).unlink()
    subprocess.run(['sync'],check=True);assert shutil.disk_usage(esp).free>needed+32*1024**2
    target.mkdir()
    for src,dst in [('grub/grub.cfg','previous.candidate.grub.cfg'),('AUDP001/stage-receipt.json','previous.stage-receipt.json'),('AUDP001/rollback.json','previous.rollback.json')]:
        direct.atomic_write(target/dst,(esp/src).read_bytes())
    for name in ['initramfs.img','profile.json','manifest.json','validation.json','kernel-bootfb.patch']:
        direct.atomic_write(target/name,(out/name).read_bytes());assert sha(target/name)==sha(out/name)
    item=rollback['grub/grub.cfg']
    item['previous_candidate_sha256']=list(dict.fromkeys(item.get('previous_candidate_sha256',[])+[item['candidate_sha256']]))
    item['candidate_sha256']=plan['grub_sha256']
    direct.atomic_write(esp/'AUDP001/rollback.json',(json.dumps(rollback,indent=2)+'\n').encode())
    direct.atomic_write(esp/'grub/grub.cfg',updated.encode())
    for n,digest in protected.items():assert sha(esp/n.lstrip('/'))==digest,n
    for n,item in rollback.items():
        assert sha(esp/n)==item['candidate_sha256']
        assert sha(esp/'AUDP001'/item['backup'])==item['before_sha256']
    for n in re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)',updated):assert (esp/n.lstrip('/')).is_file(),n
    assert len(re.findall(r'^menuentry ',updated,re.M))==9
    plan.update({'phase':'staged-awaiting-manual-boot','installed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'free_after':shutil.disk_usage(esp).free})
    data=(json.dumps(plan,indent=2)+'\n').encode()
    direct.atomic_write(target/'stage-receipt.json',data);direct.atomic_write(esp/'AUDP001/stage-receipt.json',data)
    (out/'stage-receipt.json').write_bytes(data);subprocess.run(['sync'],check=True)
    print(data.decode())


if __name__=='__main__':main()
