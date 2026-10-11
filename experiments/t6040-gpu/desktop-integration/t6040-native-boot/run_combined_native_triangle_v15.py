#!/usr/bin/env python3
"""Explicit whole next-boot trial owner. This file is never run by packaging.

One overlay, driver probe and render only. Every process capable of retaining
kernel/DRM owners is launched in a separate session and never killed on timeout.
The parent stops collecting after its deadline and leaves those owners alive.
"""
import argparse,hashlib,json,os,platform,shutil,stat,subprocess,sys,time,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
class RetainedFailure(Exception):pass
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def record(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--manifest-sha256',required=True);p.add_argument('--expected-boot',required=True)
 p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();uuid.UUID(a.expected_boot)
 manifest_path=HERE/'manifest.json'
 if digest(manifest_path)!=a.manifest_sha256:raise ValueError('Manifest pin mismatch')
 manifest=json.loads(manifest_path.read_text())
 for pin in manifest['files']:
  name=pin['path'];path=HERE/name
  if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Unsafe manifest path')
  if path.is_symlink() or not path.is_file() or path.stat().st_size!=pin['bytes'] or digest(path)!=pin['sha256']:
   raise ValueError('Packaged file pin mismatch: '+name)
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 if os.geteuid()!=0 or boot!=a.expected_boot or boot in manifest['consumed_boots']:
  raise ValueError('Root and explicitly admitted unconsumed boot required')
 if platform.release()!=manifest['release']:raise ValueError('Distinct integrated kernel required')
 compat=Path('/proc/device-tree/compatible').read_bytes().split(b'\0')
 if not all(x in compat for x in (b'apple,j614s',b'apple,t6040')):raise ValueError('J614s/T6040 required')
 for name in ('asahi_m4','asahi','m4rch_native_of_bridge_v15','m4rch_gpu_adt'):
  if (Path('/sys/module')/name).exists():raise ValueError('Prior module owner exists: '+name)
 if any(Path('/sys/firmware/devicetree/base').rglob('gpu@28a600000')):
  raise ValueError('Native GPU node already exists')
 for tool in ('insmod','modinfo','dtc','dmesg'):
  if not shutil.which(tool):raise ValueError('Missing runtime dependency: '+tool)
 # Exclusive /run claim survives launcher exits and blocks every replay this boot.
 claim=Path('/run/m4rch-native-integrated-trial');claim.mkdir(mode=0o700)
 record(claim/'owner.json',{'boot_id':boot,'manifest_sha256':a.manifest_sha256,'pid':os.getpid(),'intent':'one whole boot and render'})
 a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
 result={'schema':'m4rch.combined-native-triangle.v15','boot_id':boot,'release':platform.release(),'manifest_sha256':a.manifest_sha256,'commands':[],'retained_processes':[],'render_submissions_requested':0,'success':False}
 started=time.monotonic();deadline=started+300;transcript=None
 def capture(label):
  with (a.output/(label+'-dmesg.txt')).open('wb') as out:
   checked=subprocess.run(['dmesg','--raw'],stdout=out,stderr=subprocess.STDOUT,timeout=5,check=False)
   if checked.returncode:raise RetainedFailure('Kernel evidence capture unavailable')
  record(a.output/(label+'-owners.json'),{'modules':Path('/proc/modules').read_text(),'retained_processes':result['retained_processes']})
 def command(label,argv,limit=30,retain=True):
  available=min(limit,deadline-time.monotonic())
  if available<=0:raise RetainedFailure('Combined parent deadline expired before '+label)
  log=(a.output/(label+'.log')).open('wb')
  child=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
  log.close();item={'stage':label,'argv':[str(x) for x in argv],'pid':child.pid,'pgid':child.pid,'returncode':None}
  result['commands'].append(item);record(a.output/'trial.json',result)
  print('Combined native trial stage: '+label,flush=True)
  try:item['returncode']=child.wait(timeout=available)
  except subprocess.TimeoutExpired:
   if retain:
    item['status']='timeout; process group deliberately retained'
    result['retained_processes'].append(item.copy())
   else:
    # Only metadata userspace commands enter this branch; no driver owners.
    child.kill();child.wait();item['status']='metadata command timed out'
   record(a.output/'trial.json',result)
   raise RetainedFailure(label+' timed out')
  except KeyboardInterrupt:
   if child.poll() is None:
    item['status']='parent interrupted; process group deliberately retained'
    result['retained_processes'].append(item.copy())
   raise
  record(a.output/'trial.json',result)
  if item['returncode']:raise RetainedFailure(label+' failed with '+str(item['returncode']))
 try:
  capture('admission')
  with (a.output/'kernel-transcript.txt').open('wb') as log:
   transcript=subprocess.Popen(['dmesg','--follow','--raw'],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
  time.sleep(0.1)
  if transcript.poll() is not None:raise RetainedFailure('Continuous kernel evidence capture unavailable')
  for module in ('bridge/m4rch_native_of_bridge_v15.ko','bridge/m4rch_gpu_adt.ko','driver/asahi_m4.ko'):
   vermagic=subprocess.check_output(['modinfo','-F','vermagic',str(HERE/module)],text=True,timeout=5).split()[0]
   if vermagic!=manifest['release']:raise RetainedFailure('Module/kernel vermagic mismatch')
  command('metadata-bridge-load',['insmod',str(HERE/'bridge/m4rch_native_of_bridge_v15.ko')])
  command('loader-adt-export-load',['insmod',str(HERE/'bridge/m4rch_gpu_adt.ko')])
  adt=a.output/'current-loader.adt'
  # Capture only the loader-reserved ADT metadata export; no GPU RAM/MMIO reads.
  with Path('/sys/kernel/m4rch_gpu_adt/adt').open('rb') as src,adt.open('xb') as dst:shutil.copyfileobj(src,dst)
  live_of=a.output/'current-expanded-of.dtb'
  command('expanded-live-of',['dtc','-I','fs','-O','dtb','-o',str(live_of),'/sys/firmware/devicetree/base'],retain=False)
  overlay=a.output/'current-overlay'
  command('prepare-current-overlay',[sys.executable,str(HERE/'prepare_live_overlay_v15.py'),'--adt',str(adt),'--of',str(live_of),'--output',str(overlay),'--boot-id',boot],retain=False)
  record(a.output/'current-input-pins.json',{str(x.name):{'bytes':x.stat().st_size,'sha256':digest(x)} for x in (adt,live_of,overlay/'native-current.dtbo')})
  firmware=Path('/lib/firmware/m4rch');firmware.mkdir(parents=True,exist_ok=True)
  target=firmware/'native-current.dtbo'
  if target.is_symlink():raise RetainedFailure('Firmware destination is a symlink')
  temporary=firmware/('native-current.'+boot+'.tmp')
  with temporary.open('xb') as out:
   out.write((overlay/'native-current.dtbo').read_bytes());out.flush();os.fsync(out.fileno())
  os.replace(temporary,target)
  # The subprocess may enter provider/mailbox creation; retain on any timeout.
  command('apply-current-overlay',[sys.executable,'-c',"from pathlib import Path; Path('/sys/module/m4rch_native_of_bridge_v15/parameters/apply').write_text('m4rch/native-current.dtbo\\n')"])
  capture('binding')
  command('integrated-driver-load',['insmod',str(HERE/'driver/asahi_m4.ko'),'probe_only=0','native_t6040_experiment=1'],limit=120)
  nodes=[]
  for node in sorted(Path('/sys/class/drm').glob('renderD*')):
   module=node/'device/driver/module'
   if module.exists() and module.resolve().name=='asahi_m4':nodes.append('/dev/dri/'+node.name)
  if len(nodes)!=1:raise RetainedFailure('Require exactly one integrated render node')
  capture('before-submit')
  result['render_node']=nodes[0];result['render_submissions_requested']=1
  command('triangle-client',[sys.executable,str(HERE/'client/run-native-triangle.py'),'--render-node',nodes[0],'--expected-boot',boot,'--output',str(a.output/'triangle')],limit=90)
  attempt=json.loads((a.output/'triangle/attempt.json').read_text())
  result['success']=bool(attempt.get('client_exit')==0 and attempt.get('pixel_validation_passed'))
  if not result['success']:raise RetainedFailure('Fence/pixel validation not successful')
 except (Exception,KeyboardInterrupt) as error:
  # No signals, driver removal, resource cleanup, or second attempt here.
  result['failure']=str(error)
 finally:
  try:capture('final')
  except Exception as error:result['capture_error']=str(error)
  if transcript is not None:
   # This group owns only the read-only dmesg follower, never a GPU client.
   transcript.terminate()
   try:transcript.wait(timeout=2)
   except subprocess.TimeoutExpired:transcript.kill();transcript.wait()
  result['elapsed_seconds']=time.monotonic()-started
  result['owner_release_actions']=[]
  record(a.output/'trial.json',result)
  print(json.dumps({'evidence':str(a.output),'success':result['success'],'retained_processes':result['retained_processes'],'failure':result.get('failure')}))
 return 0 if result['success'] else 1
if __name__=='__main__':raise SystemExit(main())
