#!/usr/bin/env python3
"""Package a compiled isolated Gravity-based kernel; no installation or boot edits."""
from pathlib import Path
import argparse,subprocess,shutil,tarfile,hashlib,json
p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace',type=Path);p.add_argument('--maintained',action='store_true');a=p.parse_args()
w=a.workspace.resolve();t=w/'linux';release='7.1.13-m4rch-gravity';name='linux-m4rch' if a.maintained else 'linux-m4rch-gravity-trial'
assert (t/'include/config/kernel.release').read_text().strip()==release
assert (t/'arch/arm64/boot/Image').is_file() and (t/'Module.symvers').is_file()
suffix='-maintained' if a.maintained else ''
for path in ['payload'+suffix,'package'+suffix]:assert not (w/path).exists(),'Existing package output; inspect before replacing'
root=w/('payload'+suffix);pkg=w/('package'+suffix);root.mkdir();pkg.mkdir()
subprocess.run(['make','-C',str(t),'KERNELRELEASE='+release,'LOCALVERSION=','modules_install','INSTALL_MOD_PATH='+str(root),'INSTALL_MOD_STRIP=1'],check=True)
m=root/'lib/modules'/release
for x in ['build','source']:
 q=m/x
 if q.is_symlink():q.unlink()
u=root/'usr/lib/modules';u.mkdir(parents=True);shutil.move(str(m),str(u/release));shutil.rmtree(root/'lib')
m=u/release;(m/'pkgbase').write_text(name+'\n');shutil.copy2(t/'arch/arm64/boot/Image',m/'vmlinuz')
if a.maintained:
    # Retain the established loading policy and update normal boot metadata.
    for f in ['/etc/modprobe.d/m4rch-drivers.conf']:
        q=root/f.lstrip('/');q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,q)
    q=root/'usr/lib/m4rch/kernel-release';q.parent.mkdir(parents=True,exist_ok=True);q.write_text(release+'\n')
    q=root/'etc/mkinitcpio.d/linux-m4rch.preset';q.parent.mkdir(parents=True,exist_ok=True)
    q.write_text(Path('/etc/mkinitcpio.d/linux-m4rch.preset').read_text().replace('7.1.3-m4rch',release))
    q=root/'usr/share/doc/linux-m4rch/build-provenance.json';q.parent.mkdir(parents=True,exist_ok=True)
    q.write_text((Path(__file__).resolve().parent/'profile.json').read_text())
archive=pkg/'payload.tar.gz'
with tarfile.open(archive,'w:gz') as tar:tar.add(root,arcname='payload')
h=hashlib.sha256(archive.read_bytes()).hexdigest()
(pkg/'PKGBUILD').write_text(f'''pkgname={name}
pkgver=7.1.13
pkgrel={3 if a.maintained else 1}
pkgdesc='Isolated Gravity kernel baseline with maintained T6040 drivers; GPU paused'
arch=('aarch64')
license=('GPL-2.0-only')
depends=('coreutils' 'kmod' 'mkinitcpio' 'config-m4rch')
{ "provides=('linux' 'linux-t6040')\nconflicts=('linux-m4rch-gravity-trial')\nbackup=('etc/modprobe.d/m4rch-drivers.conf')" if a.maintained else "" }
options=('!strip' '!debug' '!lto')
source=('payload.tar.gz')
sha256sums=('{h}')
package() {{ cp -a "$srcdir/payload/." "$pkgdir/"; }}
''')
subprocess.run(['makepkg','--force','--nodeps','--noconfirm'],cwd=pkg,check=True)
print('Package created; no installation performed:',name)
