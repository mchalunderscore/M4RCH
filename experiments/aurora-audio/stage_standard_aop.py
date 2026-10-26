#!/usr/bin/env python3
"""Install r13, sharing r12's kernel and retaining r12/r10 plus original rollback."""
from pathlib import Path
import argparse,copy,hashlib,json,re,shutil,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/aurora-direct'))
from stage import atomic_write,sha,validate_esp
OUT=ROOT/'out/aurora-audio/r13';BASE=OUT.parent/'r12'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--esp',type=Path,default=Path('/Volumes/M4RCHESP'));args=ap.parse_args();esp=args.esp
 validate_esp(esp);m=json.loads((OUT/'manifest.json').read_text())
 for n,v in m['files'].items():assert sha(OUT/n)==v['sha256'],n
 assert sha(esp/'boot.bin')==sha(BASE/'boot.bin')
 assert sha(esp/'AUDP001/r12/vmlinuz')==m['kernel_sha256']
 assert sha(esp/'AUDP001/r12/initramfs.img')==sha(BASE/'initramfs.img')
 original=(esp/'grub/grub.cfg').read_text();blocks=re.findall(r'(?ms)^menuentry .*?^}',original)
 obsolete=[s for s in blocks if '/AUDP001/r9/initramfs.img' in s];assert len(obsolete)==1
 cleaned=original.replace(obsolete[0],'');current=[s for s in blocks if '--id m4rch-aurora-dcp001 ' in s];assert len(current)==1;current=current[0]
 candidate=re.sub(r'^menuentry .*?\{',"menuentry 'Aurora DCP 120 Hz + GPU + microphone (AUMI001 r13; speakers disabled)' --id m4rch-aurora-dcp001 {",current,count=1).replace('/AUDP001/r12/initramfs.img','/AUDP001/r13/initramfs.img')
 fallback=re.sub(r'^menuentry .*?\{',"menuentry 'Native-tested r12 GPU + DCP (no microphone)' --id m4rch-aurora012-previous {",current,count=1)
 updated=cleaned.replace(current,candidate+'\n'+fallback)
 assert updated.count("set default='m4rch-aurora-dcp001'")==1
 old_rollback=json.loads((esp/'AUDP001/rollback.json').read_text());original_grub=(esp/'AUDP001'/old_rollback['grub/grub.cfg']['backup']).read_text()
 for v in old_rollback.values():assert sha(esp/'AUDP001'/v['backup'])==v['before_sha256']
 assert '/AUDP001/r9/initramfs.img' not in updated+original_grub
 refs=set(re.findall(r'(?m)^\s*(?:linux|initrd)\s+(\S+)',updated+original_grub));protected={n:sha(esp/n.lstrip('/')) for n in refs if n!='/AUDP001/r13/initramfs.img'}
 target=esp/'AUDP001/r13';assert not target.exists()
 retired=esp/'AUDP001/r9/initramfs.img';retired_sha=sha(retired)
 assert shutil.disk_usage(esp).free+retired.stat().st_size>(OUT/'initramfs.img').stat().st_size+3*(OUT/'boot.bin').stat().st_size+32*1024**2
 plan={'revision':13,'kernel_path':m['kernel_path'],'initramfs_path':'/AUDP001/r13/initramfs.img','default':'m4rch-aurora-dcp001','retired':'AUDP001/r9/initramfs.img','retired_sha256':retired_sha,'preserved_payloads':protected,'native_microphone_tested':False,'reboot_performed':False}
 (OUT/'stage-plan.json').write_text(json.dumps(plan,indent=2)+'\n');(OUT/'grub.cfg').write_text(updated)
 if not args.apply:print(json.dumps(plan,indent=2));return
 assert json.loads((OUT/'validation.json').read_text())['passed']
 archive=OUT/'retired-r9.initramfs.img';shutil.copyfile(retired,archive);assert sha(archive)==retired_sha
 previous=(esp/'boot.bin').read_bytes();atomic_write(OUT/'previous.boot.bin',previous);atomic_write(OUT/'previous.grub.cfg',cleaned.encode());atomic_write(OUT/'previous.rollback.json',(json.dumps(old_rollback,indent=2)+'\n').encode())
 receipt=copy.deepcopy(old_rollback)
 for n,digest in [('boot.bin',sha(OUT/'boot.bin')),('grub/grub.cfg',hashlib.sha256(updated.encode()).hexdigest())]:
  v=receipt[n];allowed=v.get('previous_candidate_sha256',[])+[v['candidate_sha256']]
  if n=='grub/grub.cfg':allowed.append(hashlib.sha256(cleaned.encode()).hexdigest())
  v['previous_candidate_sha256']=sorted(set(allowed));v['candidate_sha256']=digest
 atomic_write(esp/'AUDP001/rollback.json',(json.dumps(receipt,indent=2)+'\n').encode())
 atomic_write(esp/'grub/grub.cfg',cleaned.encode());retired.unlink();target.mkdir()
 for n in ['previous.boot.bin','previous.grub.cfg','initramfs.img','profile.json','manifest.json']:atomic_write(target/n,(OUT/n).read_bytes())
 rollback='''#!/usr/bin/env python3
from pathlib import Path
import hashlib,os,plistlib,subprocess
here=Path(__file__).resolve().parent;esp=here.parent.parent
info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist',str(esp)]));assert info['DiskUUID']=='5FDB35C6-3A66-416D-8358-6555FD99FCC5'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(esp/'boot.bin')=='NEW_BOOT'
assert sha(esp/'grub/grub.cfg')=='NEW_GRUB'
assert sha(here/'previous.boot.bin')=='OLD_BOOT'
assert sha(here/'previous.grub.cfg')=='OLD_GRUB'
for target,source in [('grub/grub.cfg','previous.grub.cfg'),('boot.bin','previous.boot.bin')]:
 data=(here/source).read_bytes();path=esp/target;tmp=path.with_name(path.name+'.revert-tmp')
 with tmp.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 assert tmp.read_bytes()==data;os.replace(tmp,path)
print('Restored native-tested r12 loader and default entry. No reboot performed.')
'''
 for k,v in {'NEW_BOOT':sha(OUT/'boot.bin'),'NEW_GRUB':hashlib.sha256(updated.encode()).hexdigest(),'OLD_BOOT':sha(BASE/'boot.bin'),'OLD_GRUB':hashlib.sha256(cleaned.encode()).hexdigest()}.items():rollback=rollback.replace(k,v)
 atomic_write(target/'revert.py',rollback.encode());atomic_write(OUT/'revert.py',rollback.encode())
 try:
  atomic_write(esp/'boot.bin',(OUT/'boot.bin').read_bytes());atomic_write(esp/'grub/grub.cfg',updated.encode())
  for n,digest in protected.items():assert sha(esp/n.lstrip('/'))==digest,n
  assert sha(target/'initramfs.img')==sha(OUT/'initramfs.img')
  assert sha(esp/'boot.bin')==sha(OUT/'boot.bin')
  assert sha(esp/'grub/grub.cfg')==sha(OUT/'grub.cfg')
  assert shutil.disk_usage(esp).free>32*1024**2
 except BaseException:
  atomic_write(esp/'boot.bin',previous);atomic_write(esp/'grub/grub.cfg',cleaned.encode());raise
 plan.update(free_bytes=shutil.disk_usage(esp).free,passed=True)
 atomic_write(OUT/'installed-validation.json',(json.dumps(plan,indent=2)+'\n').encode());atomic_write(target/'stage-receipt.json',(json.dumps(plan,indent=2)+'\n').encode())
 import subprocess;subprocess.run(['sync'],check=True);print(json.dumps(plan,indent=2))
if __name__=='__main__':main()
