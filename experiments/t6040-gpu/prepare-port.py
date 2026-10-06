#!/usr/bin/env python3
"""Prepare a guarded M4 compile trial in a separate maintained kernel tree.

No boot files, device tree nodes, or hardware state are changed.
"""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, sys
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'lib'))
import hardware_profile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('tree',type=Path);p.add_argument('--donor',type=Path,required=True)
p.add_argument('--config',type=Path,required=True)
p.add_argument('--build',action='store_true');p.add_argument('--jobs',type=int,default=4);a=p.parse_args()
if a.jobs < 1:p.error('--jobs must be positive')
tree=a.tree.resolve();donor=a.donor.resolve()
lock=json.loads((REPO/'sources.lock.json').read_text())
pins=json.loads((REPO/'experiments/t6040-gpu/sources.json').read_text())
for root,revision in [(tree,lock['linux']['revision']),(donor,pins['repositories']['linux']['revision'])]:
 if subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()!=revision:raise SystemExit('Source revision mismatch: '+str(root))
if tree == (REPO/'out/gpu-maintained/linux-build').resolve():
 raise SystemExit('Refusing to modify the running trial build')
protected={x['source']:x['result_source_sha256'] for x in [*hardware_profile.USB_CABLE_FIXES,hardware_profile.FRAMEBUFFER_FIX,hardware_profile.CPUFREQ_SNAPSHOT,hardware_profile.EARLY_FAULT,hardware_profile.MAINTAINED_WFI]}
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
for f,h in protected.items():
 if sha(tree/f)!=h:raise SystemExit('Maintained source mismatch: '+f)
entry=(donor/'drivers/gpu/drm/asahi/asahi_m4.rs').read_text()
if 'if !metadata.normal_startup_implemented' not in entry or 'if chip_id == 0x6040' not in entry:
 raise SystemExit('Required T6040 startup and probe guards missing')
files=['rust/kernel/drm/file.rs','rust/kernel/drm/gem/shmem.rs','rust/kernel/io/mem.rs','rust/kernel/soc/apple/rtkit.rs','drivers/soc/apple/rtkit.c','drivers/soc/apple/rtkit-internal.h','include/linux/soc/apple/rtkit.h','include/uapi/drm/asahi_drm.h']
for f in (donor/'drivers/gpu/drm/asahi').rglob('*'):
 if f.is_file() and (f.suffix=='.rs' or f.name in ['Kconfig','Makefile']):files.append(str(f.relative_to(donor)))
receipt={}
for f in files:
 src=donor/f;dst=tree/f;dst.parent.mkdir(parents=True,exist_ok=True)
 receipt[f]={'before':sha(dst) if dst.exists() else None,'after':sha(src)}
 shutil.copyfile(src,dst)
parent=tree/'drivers/gpu/drm/Makefile';s=parent.read_text();line='obj-$(CONFIG_DRM_ASAHI_M4) += asahi/'
if line not in s:parent.write_text(s+'\n'+line+'\n')
shutil.copyfile(a.config,tree/'.config')
subprocess.run([str(tree/'scripts/config'),'--file',str(tree/'.config'),'-e','RUST','-m','DRM_ASAHI_M4','-d','DRM_ASAHI','-d','M4RCH_GPU_IDENTIFY','-d','APPLE_PMP','--set-str','LOCALVERSION','','-d','LOCALVERSION_AUTO'],check=True)
subprocess.run(['make','-C',str(tree),'LLVM=1','KERNELRELEASE=7.1.3-m4rch-gpu-port','LOCALVERSION=','olddefconfig'],check=True)
config=(tree/'.config').read_text()
for v in ['CONFIG_RUST=y','CONFIG_DRM_ASAHI_M4=m','CONFIG_RUST_APPLE_RTKIT=y']:
 if v not in config:raise SystemExit('Missing required config: '+v)
for v in ['CONFIG_DRM_ASAHI=y','CONFIG_DRM_ASAHI=m','CONFIG_APPLE_PMP=y','CONFIG_APPLE_PMP=m']:
 if v in config:raise SystemExit('Unexpected hardware driver: '+v)
for f,h in protected.items():
 if sha(tree/f)!=h:raise SystemExit('Protected driver changed: '+f)
(tree.parent/'port-source.json').write_text(json.dumps({'files':receipt,'protected':protected,'release':'7.1.3-m4rch-gpu-port','compiled':False,'gpu_node_installed':False,'t6040_firmware_startup_allowed':False},indent=2)+'\n')

if a.build:
 subprocess.run(['make','-C',str(tree),'LLVM=1','KERNELRELEASE=7.1.3-m4rch-gpu-port','LOCALVERSION=','-j'+str(a.jobs),'Image','modules'],check=True)
 result=json.loads((tree.parent/'port-source.json').read_text())
 result.update(compiled=True,config_sha256=sha(tree/'.config'),artifact_hashes={f:sha(tree/f) for f in ['arch/arm64/boot/Image','drivers/gpu/drm/asahi/asahi_m4.ko']})
 (tree.parent/'port-source.json').write_text(json.dumps(result,indent=2)+'\n')
