#!/usr/bin/env python3
from pathlib import Path
import argparse,json,sys,shutil,subprocess,os
repo=Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo/'lib'))
import boot,hardware_profile
parser=argparse.ArgumentParser(description='Reconstruct maintained patch stack in disposable pinned worktrees; no installation.')
parser.add_argument('workspace',type=Path)
p=parser.parse_args().workspace.resolve();linux=p/'linux';wallace=p/'wallace';stage=p/'stage';build=p/'linux-build';lock=json.loads((repo/'sources.lock.json').read_text())
if build.exists(): raise SystemExit('Refusing an existing linux-build tree; use a fresh workspace')
for directory,key in [(linux,'linux'),(wallace,'wallace')]:
 observed=subprocess.check_output(['git','rev-parse','HEAD'],cwd=directory,text=True).strip()
 if observed != lock[key]['revision']: raise SystemExit('Source revision mismatch: '+key)
stage.mkdir(exist_ok=True)
for directory,suffix in [('patches','*.patch'),('dts','*.dts'),('dts','*.dtsi')]:
 for f in (wallace/directory).glob(suffix):shutil.copy2(f,stage/f.name)
for f in (wallace/'dts').glob('*.dts*'):shutil.copy2(f,linux/'arch/arm64/boot/dts/apple'/f.name)
harness=stage/'kbuild.sh';harness.write_text(boot.adapt_harness((wallace/'scripts/t6040-kbuild.sh').read_text(),linux,stage))
env=dict(os.environ,BUILD_DIR=str(build),BUILD_WORKTREE='1',DOCKCHANNEL='1',DOCKCHANNEL_NBCON='1',MACSMC='1',HID_TYPE_FIX='1',TRACKPAD_FW='1',TRACKPAD_RESET_CONTRACT='1',WIFI='1',PCIE='1',CPUFREQ='1',NPROC='4',LLVM='1',KBUILD_OVERWRITE='1',KBUILD_BUILD_TIMESTAMP='@'+str(lock['source_date_epoch']),KBUILD_BUILD_USER='m4rch',KBUILD_BUILD_HOST='builder',KBUILD_BUILD_VERSION='1',SOURCE_DATE_EPOCH=str(lock['source_date_epoch']))
subprocess.run(['bash',str(harness)],env=env,check=True)
boot.apply_smp_patch(build,lock['linux_smp'],repo/lock['linux_smp']['patch'])
track=boot.trackpad_inputs(lock);subprocess.run(['git','apply','--check',str(track['patch'])],cwd=build,check=True);subprocess.run(['git','apply',str(track['patch'])],cwd=build,check=True)
name='t6040-j614s-dcuart-wifi-cpufreq-sdroot';f=build/'arch/arm64/boot/dts/apple'/(name+'.dts');shutil.copy2(stage/(name+'.dts'),f)
overlay=hardware_profile.prepare(build,stage)
f.write_text(f.read_text()+'\n'+track['overlay'].read_text()+'\n'+overlay)
print('Maintained patch stack reconstructed; no compile or install yet')
