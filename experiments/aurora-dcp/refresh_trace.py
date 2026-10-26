#!/usr/bin/env python3
"""Stage revision 4 while retaining all existing payloads and native rollback."""
import argparse,datetime,hashlib,importlib.util,json,re,shutil,subprocess
from pathlib import Path
from package import PROJECT,OUTPUT,sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--esp',type=Path,default=Path('/Volumes/M4RCHESP'));p.add_argument('--apply',action='store_true');a=p.parse_args();esp=a.esp
    o=OUTPUT/'handoff-r4'
    spec=importlib.util.spec_from_file_location('direct',PROJECT/'experiments/aurora-direct/stage.py');direct=importlib.util.module_from_spec(spec);spec.loader.exec_module(direct)
    direct.validate_esp(esp)
    m=json.loads((o/'manifest.json').read_text());assert m['revision']==4
    for name,v in m['files'].items():assert sha(o/name)==v['sha256'],name
    for name,digest in m['kit_sources'].items():assert sha(PROJECT/name)==digest,name
    assert sha(esp/m['reused_kernel']['esp_path'])==m['reused_kernel']['sha256']
    previous=json.loads((esp/'AUDP001/stage-receipt.json').read_text());assert previous['revision']==3
    assert sha(esp/'boot.bin')==previous['boot_sha256'] and sha(esp/'grub/grub.cfg')==previous['grub_sha256']
    rollback=json.loads((esp/'AUDP001/rollback.json').read_text())
    for name,item in rollback.items():
        assert sha(esp/name)==item['candidate_sha256'],name
        assert sha(esp/'AUDP001'/item['backup'])==item['before_sha256'],name
    cleanup=json.loads((esp/'AUBS001/cleanup-receipt.json').read_text())
    for name,digest in cleanup['preserved_payloads'].items():assert sha(esp/name)==digest,name
    original=(esp/'grub/grub.cfg').read_text();assert "set default='m4rch-aurora-dcp001'" in original
    entry=re.search(r'(?ms)^menuentry [^\n]+ --id m4rch-aurora-dcp001 \{\n.*?^\}\n',original)
    assert entry and '/AUDP001/r3/initramfs.img' in entry[0]
    replacement=entry[0].replace('(AUDP001 r3 multi-mode; speakers disabled)','(AUDP001 r4 handoff + multi-mode; speakers disabled)').replace('/AUDP001/r3/initramfs.img','/AUDP001/r4/initramfs.img').replace('drm.debug=0x1e','drm.debug=0x04').replace('log_buf_len=4M','log_buf_len=8M')
    assert replacement!=entry[0] and 'appledrm.j614s_modeset=1' in replacement and '/AUDP001/r3/vmlinuz' in replacement
    updated=original[:entry.start()]+replacement+original[entry.end():]
    assert len(re.findall(r'^menuentry ',updated,re.M))==7
    assert updated[updated.index('--id m4rch-aurora-dcp002-retained'):]==original[original.index('--id m4rch-aurora-dcp002-retained'):]
    target=esp/'AUDP001/r4';assert not target.exists(),'Inspect existing r4 rather than overwrite'
    needed=(o/'initramfs.img').stat().st_size+2*(o/'boot.bin').stat().st_size+4*1024*1024
    assert shutil.disk_usage(esp).free>needed+48*1024*1024
    (o/'grub.cfg').write_text(updated)
    plan={'test':'AUDP001','revision':4,'kernel_release':'7.3.0-m4rch-dcp003','loader_revision':'DCP004',
        'default':'m4rch-aurora-dcp001','payload_directory':'AUDP001/r4','fallback_entries':6,
        'native_boot_tested':False,'reboot_performed':False,'boot_sha256':sha(o/'boot.bin'),
        'reused_kernel':m['reused_kernel'],'original_native_rollback_preserved':True}
    if not a.apply:print(json.dumps(plan,indent=2));return
    target.mkdir()
    for src,dst in [('boot.bin','previous.candidate.boot.bin'),('grub/grub.cfg','previous.candidate.grub.cfg'),('AUDP001/stage-receipt.json','previous.stage-receipt.json'),('AUDP001/rollback.json','previous.rollback.json')]:direct.atomic_write(target/dst,(esp/src).read_bytes())
    for name in ['initramfs.img','profile.json','manifest.json','m1n1-handoff-trace.patch','uboot-handoff-trace.patch']:
        direct.atomic_write(target/name,(o/name).read_bytes())
    # Recognize both states before replacing either active file.
    for name,item in rollback.items():item['previous_candidate_sha256']=list(dict.fromkeys(item.get('previous_candidate_sha256',[])+[item['candidate_sha256']]))
    rollback['boot.bin']['candidate_sha256']=sha(o/'boot.bin')
    rollback['grub/grub.cfg']['candidate_sha256']=hashlib.sha256(updated.encode()).hexdigest()
    direct.atomic_write(esp/'AUDP001/rollback.json',(json.dumps(rollback,indent=2)+'\n').encode())
    direct.atomic_write(esp/'boot.bin',(o/'boot.bin').read_bytes());direct.atomic_write(esp/'grub/grub.cfg',updated.encode())
    for name in ['initramfs.img','profile.json','manifest.json']:assert sha(target/name)==sha(o/name)
    for name,item in rollback.items():assert sha(esp/name)==item['candidate_sha256']
    for name,digest in cleanup['preserved_payloads'].items():assert sha(esp/name)==digest,name
    for f in re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)',updated):assert (esp/f.lstrip('/')).is_file(),f
    plan.update({'phase':'staged-awaiting-manual-boot','installed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'grub_sha256':sha(esp/'grub/grub.cfg'),'rollback':'python3 /Volumes/M4RCHESP/AUDP001/restore.py'})
    data=(json.dumps(plan,indent=2)+'\n').encode();direct.atomic_write(target/'stage-receipt.json',data);direct.atomic_write(esp/'AUDP001/stage-receipt.json',data);(o/'stage-receipt.json').write_bytes(data)
    subprocess.run(['sync'],check=True);print(data.decode())
if __name__=='__main__':main()
