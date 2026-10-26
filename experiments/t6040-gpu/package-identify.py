#!/usr/bin/env python3
from pathlib import Path
import argparse,json,subprocess,shutil,hashlib,tarfile
parser=argparse.ArgumentParser(description='Package an isolated built trial; does not install it. Uses native maintained initramfs inputs.')
parser.add_argument('workspace',type=Path)
p=parser.parse_args().workspace.resolve();tree=p/'linux-build';pkg=p/'package';payload=p/'payload';release='7.1.3-m4rch-gpu-id';name='linux-m4rch-gpu-id'
if payload.exists() or pkg.exists(): raise SystemExit('Refusing existing packaging output; preserve or move it first')
repo=Path(__file__).resolve().parents[2]
inputs=json.loads((p/'identify-build-inputs-final.json').read_text())
assert inputs['build_succeeded'], 'Build must complete before packaging'
for file,expected in inputs['artifact_hashes'].items():
 assert hashlib.sha256((tree/file).read_bytes()).hexdigest()==expected,file
assert inputs['source_sha256']==hashlib.sha256((repo/'experiments/t6040-gpu/identify.rs').read_bytes()).hexdigest()
assert inputs['config_sha256']==hashlib.sha256((tree/'.config').read_bytes()).hexdigest()
assert (tree/'include/config/kernel.release').read_text().strip()==release
payload.mkdir(exist_ok=True);pkg.mkdir(exist_ok=True)
subprocess.run(['make','-C',str(tree),'LLVM=1','KERNELRELEASE='+release,'LOCALVERSION=','modules_install','INSTALL_MOD_PATH='+str(payload),'INSTALL_MOD_STRIP=1'],check=True)
m=payload/'lib/modules'/release
for link in ['build','source']:
 f=m/link
 if f.is_symlink(): f.unlink()
usr=payload/'usr/lib/modules';usr.mkdir(parents=True,exist_ok=True);shutil.move(str(m),str(usr/release));shutil.rmtree(payload/'lib')
m=usr/release;(m/'pkgbase').write_text(name+'\n');shutil.copy2(tree/'arch/arm64/boot/Image',m/'vmlinuz')
boot=payload/'boot';boot.mkdir(exist_ok=True);shutil.copy2(m/'vmlinuz',boot/('vmlinuz-'+name))
init=payload/'usr/lib/m4rch-gpu-id';init.mkdir(parents=True,exist_ok=True)
text=Path('/usr/lib/m4rch/init').read_text().replace('= linux-m4rch ]','= linux-m4rch-gpu-id ]');assert '= linux-m4rch-gpu-id ]' in text
(init/'init').write_text(text);(init/'init').chmod(0o755)
hooks=payload/'usr/lib/initcpio/install';hooks.mkdir(parents=True,exist_ok=True)
text=Path('/usr/lib/initcpio/install/m4rch-root').read_text().replace('add_file /usr/lib/m4rch/init /init 755','add_file /usr/lib/m4rch-gpu-id/init /init 755')
(hooks/'m4rch-gpu-id-root').write_text(text)
etc=payload/'etc';etc.mkdir(exist_ok=True)
(etc/'mkinitcpio.gpu-id.conf').write_text(Path('/etc/mkinitcpio.m4rch.conf').read_text().replace('HOOKS=(m4rch-root)','HOOKS=(m4rch-gpu-id-root)'))
presets=etc/'mkinitcpio.d';presets.mkdir(exist_ok=True)
(presets/(name+'.preset')).write_text("ALL_config='/etc/mkinitcpio.gpu-id.conf'\nALL_kver='/usr/lib/modules/"+release+"/vmlinuz'\nPRESETS=('default')\ndefault_image='/boot/initramfs-"+name+".img'\n")
archive=pkg/'payload.tar.gz'
with tarfile.open(archive,'w:gz') as t:t.add(payload,arcname='payload')
h=hashlib.sha256(archive.read_bytes()).hexdigest()
(pkg/'PKGBUILD').write_text("pkgname=linux-m4rch-gpu-id\npkgver=7.1.3\npkgrel=1\npkgdesc='Isolated T6040 Rust resource-preflight trial; GPU reads disabled'\narch=('aarch64')\nlicense=('GPL-2.0-only')\ndepends=('coreutils' 'kmod' 'mkinitcpio' 'config-m4rch')\noptions=('!strip' '!debug' '!lto')\nsource=('payload.tar.gz')\nsha256sums=('"+h+"')\npackage() { cp -a \"$srcdir/payload/.\" \"$pkgdir/\"; }\n")
subprocess.run(['makepkg','--force','--nodeps','--noconfirm'],cwd=pkg,check=True)
