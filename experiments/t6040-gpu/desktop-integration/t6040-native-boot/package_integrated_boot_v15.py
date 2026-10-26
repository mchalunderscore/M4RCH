#!/usr/bin/env python3
"""Build an isolated boot payload in workspace; never installs or starts GPU."""
import argparse,gzip,hashlib,json,shutil,stat,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OLD='7.1.13-m4rch-gpu-native-reset'
PKG='linux-m4rch-gpu-native-integrated'

def pin(p):
 p=Path(p);b=p.read_bytes();return dict(path=str(p.resolve()),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def parse(data):
 result={};pos=0
 while pos+110<=len(data):
  assert data[pos:pos+6] in [b'070701',b'070702']
  h=[int(data[pos+6+i*8:pos+14+i*8],16)for i in range(13)];pos+=110
  name=data[pos:pos+h[11]-1].decode();pos=(pos+h[11]+3)&~3
  payload=data[pos:pos+h[6]];pos=(pos+h[6]+3)&~3
  if name=='TRAILER!!!':break
  assert not name.startswith('/') and '..' not in Path(name).parts and name not in result
  result[name]=(h,payload)
 return result

def archive(entries):
 out=bytearray()
 for index,(name,(header,data)) in enumerate(list(entries.items())+[('TRAILER!!!',([0]*13,b''))],1):
  h=list(header);h[0]=index;h[6]=len(data);h[11]=len(name.encode())+1;h[12]=0
  out.extend(b'070701'+''.join(f'{x:08x}' for x in h).encode());out.extend(name.encode()+b'\0')
  out.extend(b'\0'*(-len(out)%4));out.extend(data);out.extend(b'\0'*(-len(out)%4))
 out.extend(b'\0'*(-len(out)%512));return bytes(out)

def stage(kernel,driver,output,launcher=None):
 output=output.resolve();output.relative_to(ROOT/'out');assert not output.exists()
 release=(kernel/'include/config/kernel.release').read_text().strip()
 assert release=='7.1.13-m4rch-gpu-native-integrated+',release
 receipt=json.loads((driver.parent.parent/'integrated-build-receipt.json').read_text())
 assert receipt['returncode']==0 and receipt['module']['sha256']==pin(driver)['sha256']
 assert subprocess.check_output(['modinfo','-F','vermagic',str(driver)],text=True).split()[0]==release
 output.mkdir(parents=True);boot=output/'boot'/'NATI001';boot.mkdir(parents=True)
 modules=output/'rootfs';modules.mkdir()
 subprocess.run(['make','-C',str(kernel),'LLVM=1','INSTALL_MOD_PATH='+str(modules),'modules_install'],check=True,stdout=(output/'modules-install.log').open('w'),stderr=subprocess.STDOUT)
 directory=modules/'lib/modules'/release
 assert directory.is_dir();dest=directory/'kernel/drivers/gpu/drm/asahi/asahi_m4.ko'
 # Replace baseline by the reviewed external whole-driver artifact. Any other
 # copy could win modprobe's name/alias lookup, so remove all duplicates first.
 for p in directory.rglob('asahi_m4.ko*'):p.unlink()
 dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(driver,dest)
 for name in ['build','source']:
  p=directory/name
  if p.is_symlink():p.unlink()
 (directory/'pkgbase').write_text(PKG+'\n')
 subprocess.run(['depmod','-b',str(modules),release],check=True,stdout=subprocess.PIPE,stderr=(output/'depmod.log').open('w'))
 # Arch host uses usr/lib/modules. Use only the new release's isolated tree.
 target=modules/'usr/lib/modules';target.mkdir(parents=True);directory.rename(target/release)
 directory=target/release
 image=Path('/boot/GFXN001/initramfs.img').read_bytes();cut=image.find(b'\x1f\x8b')
 assert cut==10240
 old=parse(gzip.decompress(image[cut:]));entries={}
 assert not any(stat.S_ISREG(h[1]) and h[4]>1 for h,data in old.values()),'cpio hardlinks require preserved inode groups'
 kept={};early_modules=[]
 for name,(h,data) in old.items():
  if name.startswith('usr/lib/modules/'):
   if name.endswith('.ko'):
    relative=Path(name).relative_to('usr/lib/modules/'+OLD)
    source=directory/relative;assert source.is_file(),source
    assert subprocess.check_output(['modinfo','-F','vermagic',str(source)],text=True).split()[0]==release
    entries['usr/lib/modules/'+release+'/'+str(relative)]=(h,source.read_bytes());early_modules.append(str(relative))
   elif stat.S_ISDIR(h[1]):entries[name.replace(OLD,release)]=(h,data)
   continue
  if name=='etc/nvme-root.conf':data=data.replace(OLD.encode(),release.encode())
  elif name=='init':
   data=data.replace(b'linux-m4rch-gpu-native-reset',PKG.encode())
   anchor=b'mount -t tmpfs tmpfs /run\n';assert data.count(anchor)==1
   data=data.replace(anchor,anchor+b'mkdir -p /run/modprobe.d\n'+b"printf 'blacklist asahi_m4\\ninstall asahi_m4 /bin/false\\n' >/run/modprobe.d/m4rch-native-trial.conf\n")
  else:kept[name]=hashlib.sha256(data).hexdigest()
  entries[name]=(h,data)
 scratch=output/'initramfs-depmod';small=scratch/'lib/modules'/release;small.mkdir(parents=True)
 for relative in early_modules:
  p=small/relative;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(directory/relative,p)
 for p in directory.glob('modules.builtin*'):shutil.copy2(p,small/p.name)
 subprocess.run(['depmod','-b',str(scratch),release],check=True,stdout=subprocess.PIPE,stderr=(output/'initramfs-depmod.log').open('w'))
 header=[0,stat.S_IFREG|0o644,0,0,1,0,0,0,0,0,0,0,0]
 for p in sorted(small.glob('modules.*')):entries['usr/lib/modules/'+release+'/'+p.name]=(header,p.read_bytes())
 rebuilt=archive(entries);decoded=parse(rebuilt)
 assert all(hashlib.sha256(decoded[n][1]).hexdigest()==sha for n,sha in kept.items())
 (boot/'initramfs.img').write_bytes(image[:cut]+gzip.compress(rebuilt,mtime=0))
 shutil.copy2(kernel/'arch/arm64/boot/Image',boot/'vmlinuz')
 # Alias blacklist keeps the driver under the launcher owner. It does not
 # forbid the launcher's explicit insmod with chosen trial parameters.
 # /run/modprobe.d is created by init before root udev and moved into newroot.
 fragment=f"""menuentry '{release} (NATI001 integrated GPU trial)' {{
    search --no-floppy --fs-uuid --set=root 33CE-1F10
    linux /NATI001/vmlinuz root=UUID=7568fe83-378f-5b78-ab12-ccc36ff09a90 rw console=ttydc0 console=tty0 rdinit=/init idle=nop arm64.nowfxt pd_ignore_unused clk_ignore_unused modprobe.blacklist=asahi_m4 asahi_m4.probe_only=1
    initrd /NATI001/initramfs.img
}}
"""
 (output/'grub-entry.cfg').write_text(fragment)
 if launcher:
  assert launcher.is_dir();shutil.copytree(launcher,output/'launcher')
 result=dict(schema='m4rch.integrated-boot-package.v15',release=release,package_name=PKG,inputs=[pin(driver),pin(kernel/'arch/arm64/boot/Image'),pin(Path('/boot/GFXN001/initramfs.img'))],boot_files=[pin(p)for p in boot.iterdir()],module=pin(dest if dest.exists() else directory/'kernel/drivers/gpu/drm/asahi/asahi_m4.ko'),module_root=str(directory),early_modules=early_modules,non_module_initramfs_entries_preserved=len(kept),early_cpio_preserved=True,blacklist_before_root_udev=True,explicit_insmod_required=True,hardware_actions=[],installed=False,grub_modified=False,default_changed=False,launcher_supplied=bool(launcher),DT_activation_ready=False,trial_ready=False,DT_requirements=['Retain original loader FDT as boot input; do not pass stale saved reserved-address DTB in GRUB','Launcher must create/enable native GPU/mailbox and fresh five loader reservation bindings, preserving aliases/PM/resources','Only explicit integrated driver with probe_only=0 native_t6040_experiment=1 may start firmware','No old helper replay or baseline asahi_m4 autoload'])
 (output/'boot-package-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(dict(package=str(output),release=release,installed=False,trial_ready=False)))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--driver',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--launcher',type=Path);a=p.parse_args();stage(a.kernel.resolve(),a.driver.resolve(),a.out,a.launcher)
