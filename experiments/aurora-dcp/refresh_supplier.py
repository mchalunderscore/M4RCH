#!/usr/bin/env python3
"""Install integrated r7 and retire only the obsolete r2 test entry/payloads."""
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
from package_supplier import RELEASE


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--esp',type=Path,default=Path('/Volumes/M4RCHESP'));p.add_argument('--apply',action='store_true')
    a=p.parse_args();esp=a.esp;out=OUTPUT/'supplier-r7'
    spec=importlib.util.spec_from_file_location('direct',PROJECT/'experiments/aurora-direct/stage.py')
    direct=importlib.util.module_from_spec(spec);spec.loader.exec_module(direct);direct.validate_esp(esp)
    manifest=json.loads((out/'manifest.json').read_text());assert manifest['revision']==7 and manifest['kernel_release']==RELEASE
    for n,item in manifest['files'].items():assert sha(out/n)==item['sha256'],n
    for n,digest in manifest['kit_sources'].items():assert sha(PROJECT/n)==digest,n
    previous=json.loads((esp/'AUDP001/stage-receipt.json').read_text());assert previous['revision']==6
    assert sha(esp/'boot.bin')==previous['boot_sha256']==sha(OUTPUT/'desktop-r5/boot.bin')
    assert sha(esp/'grub/grub.cfg')==previous['grub_sha256']
    rollback=json.loads((esp/'AUDP001/rollback.json').read_text())
    for n,item in rollback.items():
        assert sha(esp/n)==item['candidate_sha256']
        assert sha(esp/'AUDP001'/item['backup'])==item['before_sha256']
    original=(esp/'grub/grub.cfg').read_text()
    assert "set default='m4rch-aurora-dcp001'" in original
    entry=re.search(r'(?ms)^menuentry [^\n]+ --id m4rch-aurora-dcp001 \{\n.*?^\}\n',original)
    obsolete=re.search(r'(?ms)^menuentry [^\n]+ --id m4rch-aurora-dcp002-retained \{\n.*?^\}\n',original)
    assert entry and obsolete and '/AUDP001/r6/initramfs.img' in entry[0]
    assert '/AUDP001/r5/vmlinuz' in entry[0] and len(re.findall(r'^menuentry ',original,re.M))==9
    assert '/AUDP001/r2/vmlinuz' in obsolete[0] and '/AUDP001/r2/initramfs.img' in obsolete[0]
    new=entry[0].replace('AUDP001 r6;','AUDP001 r7;').replace('/AUDP001/r5/vmlinuz','/AUDP001/r7/vmlinuz').replace('/AUDP001/r6/initramfs.img','/AUDP001/r7/initramfs.img')
    old=entry[0].replace('--id m4rch-aurora-dcp001 {','--id m4rch-aurora-dcp006-previous {')
    old=re.sub(r"^menuentry '[^']+'","menuentry 'Previous DCP r6 candidate (speakers disabled)'",old)
    updated=original.replace(obsolete[0],'').replace(entry[0],new+'\n'+old)
    rollback_grub=(esp/'AUDP001'/rollback['grub/grub.cfg']['backup']).read_text()
    retire=[]
    for path,source in [('AUDP001/r2/vmlinuz','Image'),('AUDP001/r2/initramfs.img','initramfs.img')]:
        assert '/'+path not in updated+rollback_grub
        expected=OUTPUT/'revision-2'/source;archive=out/'retired-r2'/Path(path).name;present=(esp/path).exists()
        assert sha(esp/path if present else archive)==sha(expected)
        retire.append({'path':path,'sha256':sha(expected),'bytes':expected.stat().st_size,'archive':str(archive),'present':present})
    retired_paths={'/'+x['path'] for x in retire}
    protected={n:sha(esp/n.lstrip('/')) for n in set(re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)',original))-retired_paths}
    target=esp/'AUDP001/r7';assert not target.exists()
    free=shutil.disk_usage(esp).free;needed=(out/'initramfs.img').stat().st_size+(out/'Image').stat().st_size+4*1024**2
    assert free+sum(x['bytes'] for x in retire if x['present'])>needed+32*1024**2
    plan={'test':'AUDP001','revision':7,'kernel_release':RELEASE,'loader_revision':'DCP005',
        'default':'m4rch-aurora-dcp001','payload_directory':'AUDP001/r7','fallback_entries':8,
        'boot_sha256':sha(esp/'boot.bin'),'grub_sha256':hashlib.sha256(updated.encode()).hexdigest(),
        'protected_payloads':protected,'retired_obsolete_test_payloads':retire,'free_before':free,
        'native_boot_tested':False,'reboot_performed':False,'speakers_enabled':False,
        'rollback':'python3 /Volumes/M4RCHESP/AUDP001/restore.py'}
    (out/'grub.cfg').write_text(updated);(out/'stage-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    if not a.apply:print(json.dumps(plan,indent=2));return
    for item in retire:
        archive=Path(item['archive']);archive.parent.mkdir(parents=True,exist_ok=True)
        if not archive.exists():archive.write_bytes((esp/item['path']).read_bytes())
        assert sha(archive)==item['sha256']
    for item in retire:
        if item['present']:(esp/item['path']).unlink()
    subprocess.run(['sync'],check=True);assert shutil.disk_usage(esp).free>needed+32*1024**2
    target.mkdir()
    for src,dst in [('grub/grub.cfg','previous.candidate.grub.cfg'),('AUDP001/stage-receipt.json','previous.stage-receipt.json'),('AUDP001/rollback.json','previous.rollback.json')]:
        direct.atomic_write(target/dst,(esp/src).read_bytes())
    for src,dst in [('Image','vmlinuz'),('initramfs.img','initramfs.img')]+[(n,n) for n in ['profile.json','manifest.json','validation.json','kernel-supplier.patch','kernel.config','kernel.release']]:
        direct.atomic_write(target/dst,(out/src).read_bytes());assert sha(target/dst)==sha(out/src)
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
