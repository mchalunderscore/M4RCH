#!/usr/bin/env python3
"""Pin and bundle the whole launcher after kernel/driver/bridge builds pass."""
import argparse,json,shutil,subprocess,uuid
from pathlib import Path
from native_adt_bridge_v7 import pin
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[3]
def prepare(kernel,driver,bridge,client,out,consumed):
 out=out.resolve();out.relative_to(ROOT/'out');out.mkdir(parents=True,exist_ok=False)
 release=(kernel/'include/config/kernel.release').read_text().strip()
 assert release=='7.1.13-m4rch-gpu-native-integrated+'
 for boot in consumed:uuid.UUID(boot)
 driver_receipt=json.loads((driver.parent.parent/'integrated-build-receipt.json').read_text())
 bridge_receipt=json.loads((bridge/'build-receipt.json').read_text())
 assert driver_receipt['returncode']==0 and driver_receipt['module']['sha256']==pin(driver)['sha256']
 assert bridge_receipt['returncode']==0 and bridge_receipt['kernel_release']==release
 for name in ('run_combined_native_triangle_v15.py','prepare_live_overlay_v15.py','native_adt_bridge_v7.py'):
  shutil.copy2(KIT/name,out/name)
 shutil.copy2(ROOT/'experiments/t6040-gpu/adt.py',out/'adt.py')
 (out/'driver').mkdir();shutil.copy2(driver,out/'driver/asahi_m4.ko')
 (out/'bridge').mkdir()
 for name in ('m4rch_native_of_bridge_v15.ko','m4rch_gpu_adt.ko'):
  module=bridge/name
  matching=[x for x in bridge_receipt['modules'] if Path(x['path']).name==name]
  assert len(matching)==1 and matching[0]['sha256']==pin(module)['sha256']
  assert subprocess.check_output(['modinfo','-F','vermagic',str(module)],text=True).split()[0]==release
  shutil.copy2(module,out/'bridge'/name)
 assert subprocess.check_output(['modinfo','-F','vermagic',str(driver)],text=True).split()[0]==release
 client_receipt=json.loads((client/'receipt.json').read_text())
 (out/'client').mkdir()
 for name,expected in client_receipt['files'].items():
  source=client/name;actual=pin(source)
  assert actual['bytes']==expected['bytes'] and actual['sha256']==expected['sha256']
  dest=out/'client'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
 shutil.copy2(client/'receipt.json',out/'client/receipt.json')
 manifest={'schema':'m4rch.combined-native-triangle-manifest.v15','release':release,'consumed_boots':consumed,'files':[dict(path=str(p.relative_to(out)),bytes=p.stat().st_size,sha256=pin(p)['sha256']) for p in sorted(out.rglob('*')) if p.is_file()],'kernel_Image':pin(kernel/'arch/arm64/boot/Image'),'hardware_actions':[],'installed':False,'submissions':1,'compute_commands':0,'retry_policy':'one exclusive /run claim per boot; no replay','failure_policy':'retain timed-out client, insmod and overlay caller process groups; no owner release/unbind/rmmod','capture_deadline_seconds':300,'requirements':['Fresh unconsumed integrated boot UUID supplied explicitly','Whole kernel and driver ABI match','Current ADT and expanded OF captured by the admitted launcher only','Current overlay bridge activation before reviewed explicit driver insmod']}
 path=out/'manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
 receipt={'schema':'m4rch.combined-native-triangle-package.v15','manifest':pin(path),'launcher':pin(out/'run_combined_native_triangle_v15.py'),'inputs':[pin(kernel/'arch/arm64/boot/Image'),pin(driver),pin(bridge/'build-receipt.json'),pin(client/'receipt.json')],'installed':False,'hardware_actions':[]}
 (out/'launcher-package-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps({'bundle':str(out),'manifest_sha256':receipt['manifest']['sha256'],'hardware_actions':[]}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--kernel',type=Path,required=True);p.add_argument('--driver',type=Path,required=True);p.add_argument('--bridge',type=Path,required=True);p.add_argument('--client',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--consumed-boot',action='append',required=True);a=p.parse_args();prepare(a.kernel,a.driver,a.bridge,a.client,a.out,a.consumed_boot)
