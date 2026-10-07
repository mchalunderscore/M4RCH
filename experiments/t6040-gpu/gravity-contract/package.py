#!/usr/bin/env python3
"""Package the guarded trial with a separate NVMe initramfs; never install it."""
import argparse,hashlib,json,shutil,subprocess,tarfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace',type=Path)
w=p.parse_args().workspace.resolve();t=w/'linux';name='linux-m4rch-gpu-contract';release='7.1.13-m4rch-gpu-contract'
receipt=json.loads((w/'source-receipt.json').read_text())
assert receipt['compiled'] and not receipt['normal_t6040_startup_allowed']
for file,digest in receipt['artifacts'].items():
    assert hashlib.sha256((t/file).read_bytes()).hexdigest()==digest,file
for file,digest in receipt['protected_maintained_files'].items():
    assert hashlib.sha256((t/file).read_bytes()).hexdigest()==digest,file
assert hashlib.sha256((t/'.config').read_bytes()).hexdigest()==receipt['config_sha256']
assert (t/'include/config/kernel.release').read_text().strip()==release
config=(t/'.config').read_text()
for field in ['CONFIG_RUST=y','CONFIG_DRM_ASAHI_M4=m','CONFIG_RUST_APPLE_RTKIT=y']:
    assert field in config,field
entry=(t/'drivers/gpu/drm/asahi/asahi_m4.rs').read_text()
assert 'if !metadata.normal_startup_implemented' in entry
assert 'if chip_id == 0x6040' in entry
assert 'normal_startup_implemented: false' in (t/'drivers/gpu/drm/asahi/g16_profile.rs').read_text()
root=w/'payload';pkg=w/'package'
assert not root.exists() and not pkg.exists(),'Preserve existing output'
root.mkdir();pkg.mkdir()
subprocess.run(['make','-C',str(t),'LLVM=1','KERNELRELEASE='+release,'LOCALVERSION=','modules_install','INSTALL_MOD_PATH='+str(root),'INSTALL_MOD_STRIP=1'],check=True)
m=root/'lib/modules'/release
for f in ['build','source']:
    if (m/f).is_symlink():(m/f).unlink()
u=root/'usr/lib/modules';u.mkdir(parents=True);shutil.move(str(m),str(u/release));shutil.rmtree(root/'lib')
m=u/release;(m/'pkgbase').write_text(name+'\n');shutil.copy2(t/'arch/arm64/boot/Image',m/'vmlinuz')
def write(path,text):
    q=root/path;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(text);return q
native=Path('/usr/lib/m4rch/init-nvme').read_text()
assert '= linux-m4rch ]' in native
write('usr/lib/m4rch-gpu-contract/init-nvme',native.replace('= linux-m4rch ]','= '+name+' ]')).chmod(0o755)
hook=Path('/usr/lib/initcpio/install/m4rch-root').read_text()
assert 'add_file /usr/lib/m4rch/init-nvme /init 755' in hook
write('usr/lib/initcpio/install/m4rch-gpu-contract-root',hook.replace('add_file /usr/lib/m4rch/init-nvme /init 755','add_file /usr/lib/m4rch-gpu-contract/init-nvme /init 755'))
write('etc/mkinitcpio.gpu-contract.conf',Path('/etc/mkinitcpio.m4rch.conf').read_text().replace('HOOKS=(m4rch-root)','HOOKS=(m4rch-gpu-contract-root)'))
write('etc/mkinitcpio.d/'+name+'.preset',"ALL_config='/etc/mkinitcpio.gpu-contract.conf'\nALL_kver='/usr/lib/modules/"+release+"/vmlinuz'\nPRESETS=('default')\ndefault_image='/boot/initramfs-"+name+".img'\n")
archive=pkg/'payload.tar.gz'
with tarfile.open(archive,'w:gz') as a:a.add(root,arcname='payload')
sha=hashlib.sha256(archive.read_bytes()).hexdigest()
(pkg/'PKGBUILD').write_text(f'''pkgname={name}
pkgver=7.1.13
pkgrel=1
pkgdesc='Guarded T6040 GPU framework on maintained Gravity baseline'
arch=('aarch64')
license=('GPL-2.0-only')
depends=('coreutils' 'kmod' 'mkinitcpio' 'config-m4rch')
options=('!strip' '!debug' '!lto')
source=('payload.tar.gz')
sha256sums=('{sha}')
package() {{ cp -a "$srcdir/payload/." "$pkgdir/"; }}
''')
subprocess.run(['makepkg','--force','--nodeps','--noconfirm'],cwd=pkg,check=True)
print('Package created; normal kernel and boot selection unchanged')
