#!/usr/bin/env python3
"""Package a compiled isolated Gravity-based kernel; no installation or boot edits."""
from pathlib import Path
import argparse,subprocess,shutil,tarfile,hashlib,json
p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace',type=Path);a=p.parse_args()
w=a.workspace.resolve();t=w/'linux';release='7.1.13-m4rch-gravity';name='linux-m4rch-gravity-trial'
assert (t/'include/config/kernel.release').read_text().strip()==release
assert (t/'arch/arm64/boot/Image').is_file() and (t/'Module.symvers').is_file()
for path in ['payload','package']:assert not (w/path).exists(),'Existing package output; inspect before replacing'
root=w/'payload';pkg=w/'package';root.mkdir();pkg.mkdir()
subprocess.run(['make','-C',str(t),'KERNELRELEASE='+release,'LOCALVERSION=','modules_install','INSTALL_MOD_PATH='+str(root),'INSTALL_MOD_STRIP=1'],check=True)
m=root/'lib/modules'/release
for x in ['build','source']:
 q=m/x
 if q.is_symlink():q.unlink()
u=root/'usr/lib/modules';u.mkdir(parents=True);shutil.move(str(m),str(u/release));shutil.rmtree(root/'lib')
m=u/release;(m/'pkgbase').write_text(name+'\n');shutil.copy2(t/'arch/arm64/boot/Image',m/'vmlinuz')
archive=pkg/'payload.tar.gz'
with tarfile.open(archive,'w:gz') as tar:tar.add(root,arcname='payload')
h=hashlib.sha256(archive.read_bytes()).hexdigest()
(pkg/'PKGBUILD').write_text(f'''pkgname={name}
pkgver=7.1.13
pkgrel=1
pkgdesc='Isolated Gravity kernel baseline with maintained T6040 drivers; GPU paused'
arch=('aarch64')
license=('GPL-2.0-only')
depends=('coreutils' 'kmod' 'mkinitcpio' 'config-m4rch')
options=('!strip' '!debug' '!lto')
source=('payload.tar.gz')
sha256sums=('{h}')
package() {{ cp -a "$srcdir/payload/." "$pkgdir/"; }}
''')
subprocess.run(['makepkg','--force','--nodeps','--noconfirm'],cwd=pkg,check=True)
print('Separate trial package created. No preset, boot files or maintained kernel replaced.')
