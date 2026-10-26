#!/usr/bin/env python3
"""Create package revision 2 containing the tested module; no install/load."""
from pathlib import Path
import argparse,hashlib,tarfile,subprocess
p=argparse.ArgumentParser();p.add_argument('module',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
repo=Path(__file__).resolve().parents[2];original=repo/'out/gpu-gravity-contract/package/payload.tar.gz'
assert hashlib.sha256(original.read_bytes()).hexdigest()=='9320bf3b5c7ef6081772c5d1a137a84c9065440b25bf5f8b1ad5ef436daf8739'
assert hashlib.sha256(a.module.read_bytes()).hexdigest()=='53f89da02c1d4b524c934d9d44c15c4c2acb43d5484967a572721608d565533e'
assert subprocess.check_output(['modinfo','-F','vermagic',str(a.module)],text=True).startswith('7.1.13-m4rch-gpu-contract ')
out=a.output.resolve();out.mkdir();stage=out/'source';stage.mkdir()
with tarfile.open(original) as t:t.extractall(stage,filter='data')
target=stage/'payload/usr/lib/modules/7.1.13-m4rch-gpu-contract/kernel/drivers/usb/dwc3/dwc3-apple.ko';assert target.is_file();target.write_bytes(a.module.read_bytes())
init=stage/'payload/usr/lib/m4rch-gpu-contract/init-nvme';text=init.read_text()
marker='for directory in dev proc sys run; do'
assert text.count(marker)==1
init.write_text(text.replace(marker,"# Qualified USB role provider must exist before root udev PD probing.\n/sbin/modprobe dwc3_apple || stop 'Cannot load fixed-host USB role provider'\n"+marker))
hook=stage/'payload/usr/lib/initcpio/install/m4rch-gpu-contract-root';text=hook.read_text();marker='        add_module nvme_apple'
assert text.count(marker)==1
hook.write_text(text.replace(marker,marker+'\n        add_module dwc3_apple'))
with tarfile.open(out/'payload.tar.gz','w:gz') as t:t.add(stage/'payload',arcname='payload')
h=hashlib.sha256((out/'payload.tar.gz').read_bytes()).hexdigest()
(out/'PKGBUILD').write_text(f'''pkgname=linux-m4rch-gpu-contract
pkgver=7.1.13
pkgrel=2
pkgdesc='Guarded T6040 GPU framework with qualified fixed-host USB role providers'
arch=('aarch64')
license=('GPL-2.0-only')
depends=('coreutils' 'kmod' 'mkinitcpio' 'config-m4rch')
options=('!strip' '!debug' '!lto')
source=('payload.tar.gz')
sha256sums=('{h}')
package() {{ cp -a "$srcdir/payload/." "$pkgdir/"; }}
''')
subprocess.run(['makepkg','--nodeps','--noconfirm'],cwd=out,check=True)
