#!/usr/bin/env python3
"""Stage AUMI001 r12 while retaining native-tested r10 and original rollbacks."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/aurora-direct'))
from stage import atomic_write, sha, validate_esp
OUT=ROOT/'out/aurora-audio/r12'
R10_BOOT='fd6b285ae494be1fde907c35e508d30b553dcac658346868da25383026b39217'

def main():
    p=argparse.ArgumentParser();p.add_argument('--esp',type=Path,default=Path('/Volumes/M4RCHESP'));p.add_argument('--apply',action='store_true');a=p.parse_args();esp=a.esp
    validate_esp(esp);manifest=json.loads((OUT/'manifest.json').read_text())
    if a.apply: assert json.loads((OUT/'validation.json').read_text())['passed']
    for name,info in manifest['files'].items():assert sha(OUT/name)==info['sha256']
    assert sha(esp/'boot.bin')==R10_BOOT
    assert sha(esp/'AUDP001/r10/vmlinuz')=='1cf0f143747197c44becc75202369b35879bf153c852b06a045a1a1dcaa4ed68'
    original=(esp/'grub/grub.cfg').read_text()
    entries=re.findall(r'(?ms)^menuentry [^\n]+\{\n.*?^\}\n',original)
    current=next(e for e in entries if '--id m4rch-aurora-dcp001 {' in e)
    obsolete=next(e for e in entries if '--id m4rch-aurora-dcp008-previous {' in e)
    assert '/AUDP001/r10/vmlinuz' in current and '/AUDP001/r10/initramfs.img' in current
    cleaned=original.replace(obsolete,'')
    new=re.sub(r'^menuentry .*?\{',"menuentry 'Aurora DCP 120 Hz + GPU + microphone (AUMI001 r12; speakers disabled)' --id m4rch-aurora-dcp001 {",current,count=1)
    new=new.replace('/AUDP001/r10/initramfs.img','/AUDP001/r12/initramfs.img').replace('/AUDP001/r10/vmlinuz','/AUDP001/r12/vmlinuz')
    fallback=re.sub(r'^menuentry .*?\{',"menuentry 'Native-tested r10 DCP + GPU (speakers disabled)' --id m4rch-aurora-dcp010-previous {",current,count=1)
    updated=cleaned.replace(current,new+'\n'+fallback)
    assert updated.count("set default='m4rch-aurora-dcp001'")==1
    retired=esp/'AUDP001/r8/initramfs.img'
    # Retire only an obsolete DCP test initrd, archiving it first.
    original_rollback=json.loads((esp/'AUDP001/rollback.json').read_text())
    for item in original_rollback.values(): assert sha(esp/'AUDP001'/item['backup'])==item['before_sha256']
    original_grub=(esp/'AUDP001'/original_rollback['grub/grub.cfg']['backup']).read_text()
    assert '/AUDP001/r8/initramfs.img' not in updated+original_grub
    refs=set(re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)',updated+original_grub))
    protected={n:sha(esp/n.lstrip('/')) for n in refs if n not in ['/AUDP001/r12/initramfs.img','/AUDP001/r12/vmlinuz']}
    target=esp/'AUDP001/r12';assert not target.exists()
    needed=(OUT/'Image').stat().st_size+(OUT/'initramfs.img').stat().st_size+4*(OUT/'boot.bin').stat().st_size+4*1024**2
    assert shutil.disk_usage(esp).free+retired.stat().st_size>needed+32*1024**2
    plan={'test':'AUMI001','revision':12,'default':'m4rch-aurora-dcp001','kernel':'/AUDP001/r12/vmlinuz',
          'kernel_sha256':manifest['kernel_sha256'],'boot_sha256':sha(OUT/'boot.bin'),
          'retire':'AUDP001/r8/initramfs.img','retired_sha256':sha(retired),'preserved_payloads':protected,
          'native_microphone_tested':False,'reboot_performed':False,'speakers_disabled':True}
    (OUT/'stage-plan.json').write_text(json.dumps(plan,indent=2)+'\n');(OUT/'grub.cfg').write_text(updated)
    if not a.apply:print(json.dumps(plan,indent=2));return
    archive=OUT/'retired-r8.initramfs.img'
    if not archive.exists():shutil.copyfile(retired,archive)
    assert sha(archive)==plan['retired_sha256']
    previous_boot=(esp/'boot.bin').read_bytes()
    # Keep the original pre-DCP rollback valid for r10, this candidate and
    # the cleaned r10 GRUB used by the per-candidate rollback.
    import copy
    receipt=copy.deepcopy(original_rollback)
    for name,candidate in [('boot.bin',sha(OUT/'boot.bin')),('grub/grub.cfg',hashlib.sha256(updated.encode()).hexdigest())]:
        item=receipt[name]
        allowed=item.get('previous_candidate_sha256',[])+[item['candidate_sha256']]
        if name=='grub/grub.cfg':allowed.append(hashlib.sha256(cleaned.encode()).hexdigest())
        item['previous_candidate_sha256']=sorted(set(allowed))
        item['candidate_sha256']=candidate
    atomic_write(OUT/'previous.rollback.json',(json.dumps(original_rollback,indent=2)+'\n').encode())
    atomic_write(esp/'AUDP001/rollback.json',(json.dumps(receipt,indent=2)+'\n').encode())
    # First remove the retired entry, so an interrupted copy still boots r10.
    atomic_write(esp/'grub/grub.cfg',cleaned.encode());retired.unlink()
    target.mkdir()
    atomic_write(target/'previous.boot.bin',previous_boot)
    atomic_write(target/'previous.grub.cfg',cleaned.encode())
    atomic_write(OUT/'previous.boot.bin',previous_boot)
    atomic_write(OUT/'previous.grub.cfg',cleaned.encode())
    atomic_write(target/'vmlinuz',(OUT/'Image').read_bytes())
    for name in ['initramfs.img','profile.json','manifest.json']:
        atomic_write(target/name,(OUT/name).read_bytes())
    try:
        atomic_write(esp/'boot.bin',(OUT/'boot.bin').read_bytes())
        atomic_write(esp/'grub/grub.cfg',updated.encode())
        for name,digest in protected.items():assert sha(esp/name.lstrip('/'))==digest
        for rel in re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)',updated):assert (esp/rel.lstrip('/')).is_file()
        assert sha(esp/'boot.bin')==sha(OUT/'boot.bin')
        assert sha(target/'vmlinuz')==manifest['kernel_sha256']
        assert sha(target/'initramfs.img')==sha(OUT/'initramfs.img')
        assert shutil.disk_usage(esp).free>32*1024**2
    except BaseException:
        atomic_write(esp/'boot.bin',previous_boot);atomic_write(esp/'grub/grub.cfg',cleaned.encode());raise
    rollback='''#!/usr/bin/env python3
from pathlib import Path
import hashlib, os, plistlib, subprocess
here=Path(__file__).resolve().parent;esp=here.parent.parent
info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist',str(esp)]))
assert info['DiskUUID']=='5FDB35C6-3A66-416D-8358-6555FD99FCC5'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(esp/'boot.bin')=='CANDIDATE_SHA'
assert sha(here/'previous.boot.bin')=='PREVIOUS_SHA'
assert sha(esp/'grub/grub.cfg')=='CANDIDATE_GRUB'
assert sha(here/'previous.grub.cfg')=='PREVIOUS_GRUB'
for target,source in [('grub/grub.cfg','previous.grub.cfg'),('boot.bin','previous.boot.bin')]:
 data=(here/source).read_bytes();path=esp/target;tmp=path.with_name(path.name+'.revert-tmp')
 with tmp.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 assert tmp.read_bytes()==data;os.replace(tmp,path)
print('Restored native-tested r10 loader and default GRUB entry. No reboot performed.')
'''.replace('CANDIDATE_SHA',sha(OUT/'boot.bin')).replace('PREVIOUS_SHA',R10_BOOT).replace('CANDIDATE_GRUB',hashlib.sha256(updated.encode()).hexdigest()).replace('PREVIOUS_GRUB',hashlib.sha256(cleaned.encode()).hexdigest())
    atomic_write(target/'revert.py',rollback.encode());atomic_write(OUT/'revert.py',rollback.encode())
    plan.update({'status':'staged-awaiting-native-microphone-test','free_bytes':shutil.disk_usage(esp).free,
                 'initramfs_sha256':sha(target/'initramfs.img'),'grub_sha256':sha(esp/'grub/grub.cfg'),
                 'rollback':str(target/'revert.py')})
    data=(json.dumps(plan,indent=2)+'\n').encode()
    atomic_write(target/'stage-receipt.json',data);atomic_write(OUT/'stage-receipt.json',data)
    atomic_write(esp/'AUDP001/stage-receipt.json',data)
    import subprocess;subprocess.run(['sync'],check=True)
    print(json.dumps(plan,indent=2))
if __name__=='__main__':main()
