#!/usr/bin/env python3
"""Stage a reviewed DCP runtime manifest while preserving its kernel and loader."""
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
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',type=Path,default=OUTPUT/'shared-r8')
    p.add_argument('--esp',type=Path,default=Path('/Volumes/M4RCHESP'));p.add_argument('--apply',action='store_true')
    a=p.parse_args();out=a.candidate;esp=a.esp
    spec=importlib.util.spec_from_file_location('direct',PROJECT/'experiments/aurora-direct/stage.py')
    direct=importlib.util.module_from_spec(spec);spec.loader.exec_module(direct);direct.validate_esp(esp)
    m=json.loads((out/'manifest.json').read_text());revision=m['revision'];previous_revision=m['previous_revision']
    assert revision==previous_revision+1
    for n,item in m['files'].items():assert Path(n).name==n and sha(out/n)==item['sha256'],n
    for n,digest in m['kit_sources'].items():assert sha(PROJECT/n)==digest,n
    assert sha(esp/'AUDP001/stage-receipt.json')==m['previous_receipt_sha256']
    previous=json.loads((esp/'AUDP001/stage-receipt.json').read_text());assert previous['revision']==previous_revision
    assert sha(esp/'boot.bin')==m['loader_sha256']==previous['boot_sha256']
    assert sha(esp/m['kernel_path'])==m['kernel_sha256']
    assert sha(esp/'grub/grub.cfg')==previous['grub_sha256']
    rollback=json.loads((esp/'AUDP001/rollback.json').read_text())
    for n,item in rollback.items():
        assert sha(esp/n)==item['candidate_sha256'];assert sha(esp/'AUDP001'/item['backup'])==item['before_sha256']
    original=(esp/'grub/grub.cfg').read_text();assert "set default='m4rch-aurora-dcp001'" in original
    entry=re.search(r'(?ms)^menuentry [^\n]+ --id m4rch-aurora-dcp001 \{\n.*?^\}\n',original)
    obsolete=re.search(r'(?ms)^menuentry [^\n]+ --id '+re.escape(m['retire_entry'])+r' \{\n.*?^\}\n',original)
    assert entry and obsolete
    assert f'/AUDP001/r{previous_revision}/initramfs.img' in entry[0] and '/'+m['kernel_path'] in entry[0]
    new=entry[0].replace(f'AUDP001 r{previous_revision};',f'AUDP001 r{revision};').replace(f'/AUDP001/r{previous_revision}/initramfs.img',f'/AUDP001/r{revision}/initramfs.img')
    old=re.sub(r"^menuentry '[^']+'",f"menuentry 'Previous DCP r{previous_revision} candidate (speakers disabled)'",entry[0])
    old=old.replace('--id m4rch-aurora-dcp001 {',f'--id m4rch-aurora-dcp{previous_revision:03d}-previous {{')
    updated=original.replace(obsolete[0],'').replace(entry[0],new+'\n'+old)
    assert len(re.findall(r'^menuentry ',updated,re.M))==len(re.findall(r'^menuentry ',original,re.M))
    assert len(set(re.findall(r'--id (\S+) \{',updated)))==len(re.findall(r'^menuentry ',updated,re.M))
    old_grub=(esp/'AUDP001'/rollback['grub/grub.cfg']['backup']).read_text();retire=[]
    for n,digest in m['retire'].items():
        assert n.startswith('AUDP001/') and '..' not in Path(n).parts
        assert '/'+n in obsolete[0] and '/'+n not in updated+old_grub
        archive=out/'retired'/n.removeprefix('AUDP001/');present=(esp/n).exists()
        source=esp/n if present else archive;assert sha(source)==digest
        retire.append({'path':n,'sha256':digest,'archive':str(archive),'bytes':source.stat().st_size,'present':present})
    retired={'/'+n for n in m['retire']}
    protected={n:sha(esp/n.lstrip('/')) for n in set(re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)',original))-retired}
    target=esp/'AUDP001'/f'r{revision}';assert not target.exists()
    needed=sum((out/n).stat().st_size for n in m['payloads'])+4*1024**2;free=shutil.disk_usage(esp).free
    assert free+sum(x['bytes'] for x in retire if x['present'])>needed+32*1024**2
    plan={'test':'AUDP001','revision':revision,'kernel_release':m['kernel_release'],'loader_revision':'DCP005',
        'default':'m4rch-aurora-dcp001','payload_directory':f'AUDP001/r{revision}','kernel_reused':'/'+m['kernel_path'],
        'fallback_entries':len(re.findall(r'^menuentry ',updated,re.M))-1,
        'boot_sha256':m['loader_sha256'],'grub_sha256':hashlib.sha256(updated.encode()).hexdigest(),
        'protected_payloads':protected,'retired_obsolete_test_payloads':retire,'free_before':free,
        'native_boot_tested':False,'reboot_performed':False,'speakers_enabled':False,
        'rollback':'python3 /Volumes/M4RCHESP/AUDP001/restore.py'}
    (out/'grub.cfg').write_text(updated);(out/'stage-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    if not a.apply:print(json.dumps(plan,indent=2));return
    for x in retire:
        archive=Path(x['archive']);archive.parent.mkdir(parents=True,exist_ok=True)
        if not archive.exists():archive.write_bytes((esp/x['path']).read_bytes())
        assert sha(archive)==x['sha256']
    for x in retire:
        if x['present']:(esp/x['path']).unlink()
    subprocess.run(['sync'],check=True);assert shutil.disk_usage(esp).free>needed+32*1024**2
    target.mkdir()
    for src,dst in [('grub/grub.cfg','previous.candidate.grub.cfg'),('AUDP001/stage-receipt.json','previous.stage-receipt.json'),('AUDP001/rollback.json','previous.rollback.json')]:
        direct.atomic_write(target/dst,(esp/src).read_bytes())
    for n in m['payloads']:
        assert Path(n).name==n;direct.atomic_write(target/n,(out/n).read_bytes());assert sha(target/n)==sha(out/n)
    item=rollback['grub/grub.cfg'];item['previous_candidate_sha256']=list(dict.fromkeys(item.get('previous_candidate_sha256',[])+[item['candidate_sha256']]))
    item['candidate_sha256']=plan['grub_sha256']
    direct.atomic_write(esp/'AUDP001/rollback.json',(json.dumps(rollback,indent=2)+'\n').encode())
    direct.atomic_write(esp/'grub/grub.cfg',updated.encode())
    for n,h in protected.items():assert sha(esp/n.lstrip('/'))==h,n
    for n,item in rollback.items():
        assert sha(esp/n)==item['candidate_sha256'];assert sha(esp/'AUDP001'/item['backup'])==item['before_sha256']
    for n in re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)',updated):assert (esp/n.lstrip('/')).is_file(),n
    plan.update({'phase':'staged-awaiting-manual-boot','installed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'free_after':shutil.disk_usage(esp).free})
    data=(json.dumps(plan,indent=2)+'\n').encode();direct.atomic_write(target/'stage-receipt.json',data)
    direct.atomic_write(esp/'AUDP001/stage-receipt.json',data);(out/'stage-receipt.json').write_bytes(data)
    subprocess.run(['sync'],check=True);print(data.decode())


if __name__=='__main__':main()
