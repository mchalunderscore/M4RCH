#!/usr/bin/env python3
import pathlib,subprocess,json,datetime,time,os,hashlib,plistlib
root=pathlib.Path(__file__).resolve().parents[1]
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
timeline=[]
def event(name,**extra):
 timeline.append({'utc':now(),'event':name,**extra});write(root/'timeline.json',timeline)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
bootfiles=['boot.bin','grub/grub.cfg','EFI/BOOT/BOOTAA64.EFI']
before={p:sha(pathlib.Path('/Volumes/M4RCHESP')/p) for p in bootfiles}
write(root/'boot-files-before.json',before)
commands={
'macos-version.txt':['/usr/bin/sw_vers'],
'kernel-version.txt':['/usr/bin/uname','-a'],
'boot-time.txt':['/usr/sbin/sysctl','kern.boottime'],
'ioservice.plist':['/usr/sbin/ioreg','-a','-l','-p','IOService'],
'devicetree.plist':['/usr/sbin/ioreg','-a','-l','-p','IODeviceTree'],
'hardware-displays.plist':['/usr/sbin/system_profiler','-xml','SPHardwareDataType','SPDisplaysDataType'],
'power-settings.txt':['/usr/bin/pmset','-g','custom'],
'power-source.txt':['/usr/bin/pmset','-g','batt'],
'display-modes.json':[str(root/'display-modes')],
}
allstatus={}
def capture(phase):
 d=root/'captures'/phase;d.mkdir(parents=True,exist_ok=False);event('capture-start',phase=phase);status=[]
 for name,args in commands.items():
  start=now()
  with (d/name).open('wb') as out,(d/(name+'.stderr')).open('wb') as err:
   try:r=subprocess.run(args,stdout=out,stderr=err,timeout=70);code=r.returncode
   except subprocess.TimeoutExpired:code=124
  item={'file':name,'command':args,'started_utc':start,'ended_utc':now(),'exit_code':code,'bytes':(d/name).stat().st_size}
  if name.endswith('.plist') and code==0:
   try:
    with (d/name).open('rb') as f:plistlib.load(f)
    item['plist_parsed']=True
   except Exception as e:item['plist_parsed']=False;item['parse_error']=str(e)
  status.append(item)
 write(d/'status.json',status);allstatus[phase]=status;event('capture-end',phase=phase)
 print('Captured',phase,flush=True)
 return d
capture('idle')
(root/'render').mkdir()
log=(root/'render/workload.stdout').open('wb');err=(root/'render/workload.stderr').open('wb')
env=dict(os.environ,MTL_CAPTURE_ENABLED='1')
event('triangle-launch',maximum_seconds=240)
p=subprocess.Popen([str(root/'triangle'),str(root/'render'),str(root/'source/triangle.metal')],stdout=log,stderr=err,env=env)
try:
 deadline=time.monotonic()+40
 while not (root/'render/ready').exists():
  if p.poll() is not None:raise RuntimeError('Workload exited before ready; inspect render/failure.json')
  if time.monotonic()>deadline:raise RuntimeError('Workload ready timeout')
  time.sleep(.25)
 event('triangle-ready',pid=p.pid,verification=json.loads((root/'render/verification.json').read_text()))
 time.sleep(3)
 d=root/'captures/workload'
 progress_before=json.loads((root/'render/progress.json').read_text())
 capture('workload');write(d/'progress-before.json',progress_before)
 progress_after=json.loads((root/'render/progress.json').read_text());write(d/'progress-after.json',progress_after)
 if p.poll() is not None or not progress_after['running'] or progress_after['draws_completed']<=progress_before['draws_completed']:raise RuntimeError('Workload did not remain active across registry captures')
 event('triangle-stop-request');(root/'render/stop').touch();code=p.wait(timeout=30)
 event('triangle-exited',exit_code=code)
 if code!=0:raise RuntimeError('Workload failed')
finally:
 if p.poll() is None:
  (root/'render/stop').touch()
  try:p.wait(timeout=35)
  except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=10)
 log.close();err.close()
time.sleep(10)
capture('post-idle')
tools=root/'tools';tools.mkdir()
for name,args in {'swift-version.txt':['/usr/bin/xcrun','swiftc','--version'],'xcode-version.txt':['/usr/bin/xcodebuild','-version'],'instruments-templates.txt':['/usr/bin/xcrun','xctrace','list','templates'],'sdk-version.txt':['/usr/bin/xcrun','--sdk','macosx','--show-sdk-version']}.items():
 with (tools/name).open('wb') as out,(tools/(name+'.stderr')).open('wb') as err:
  r=subprocess.run(args,stdout=out,stderr=err,timeout=30)
 write(tools/(name+'.status.json'),{'command':args,'exit_code':r.returncode})
after={p:sha(pathlib.Path('/Volumes/M4RCHESP')/p) for p in bootfiles};write(root/'boot-files-after.json',after)
assert before==after,'Boot files changed during capture'
boots=[(root/'captures'/phase/'boot-time.txt').read_text() for phase in allstatus]
assert len(set(boots))==1,'Boot identity changed'
required=['ioservice.plist','devicetree.plist','hardware-displays.plist','display-modes.json']
assert all(s['exit_code']==0 and s.get('plist_parsed',True) for status in allstatus.values() for s in status if s['file'] in required),'Required capture failed'
event('collection-complete',boot_files_unchanged=True)
write(root/'collection-summary.json',{'complete':True,'phases':list(allstatus),'boot_files_unchanged':True,'boot_time_unchanged':True,'workload_exited':p.poll()==0,'note':'Idle means this test workload is absent. Other applications were not stopped. No sleep/wake, driver reset, MMIO or firmware memory access was performed.'})
print('Collection complete',root,flush=True)
