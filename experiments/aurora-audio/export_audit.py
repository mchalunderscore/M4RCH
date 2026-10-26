#!/usr/bin/env python3
"""Export exact rebuild patches and audit candidate state inside the build VM."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path('/project');OUT=ROOT/'out/aurora-audio/r12';LINUX=Path('/work/linux');UBOOT=Path('/work/uboot')
def sha(data):return hashlib.sha256(data).hexdigest()
def export(root,name):
 patch=subprocess.check_output(['git','diff','--binary','HEAD'],cwd=root)
 for name2 in subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=root,text=True).splitlines():
  p=subprocess.run(['git','diff','--no-index','--binary','/dev/null',name2],cwd=root,stdout=subprocess.PIPE);assert p.returncode==1;patch+=p.stdout
 (OUT/name).write_bytes(patch)
export(LINUX,'kernel-combined.patch');export(UBOOT,'uboot-j614s.patch')
upstream=subprocess.check_output(['git','show','HEAD:drivers/iommu/apple-dart.c'],cwd=LINUX)
assert upstream==(LINUX/'drivers/iommu/apple-dart.c').read_bytes()
config=(LINUX/'.config').read_text()
for setting in ['CONFIG_RUST=y','CONFIG_APPLE_J614S_DCP_BOOT=y','CONFIG_APPLE_T6041_DISPLAY_GATE=y']:
 assert setting+'\n' in config,setting
checks={}
for name in ['control.dtb','template.dtb']:
 dt=OUT/name
 def get(node,prop):return subprocess.check_output(['fdtget',str(dt),node,prop],text=True).strip()
 assert get('/aop@510600000/audio','apple,chassis-name')=='J614'
 assert get('/aop@510600000/audio','dma-names')=='dma cout cin'
 def nodes(parent):
  yield parent
  for child in subprocess.check_output(['fdtget','-l',str(dt),parent],text=True).splitlines():yield from nodes(parent.rstrip('/')+'/'+child)
 amps=[]
 for node in nodes('/'):
  props=subprocess.check_output(['fdtget','-p',str(dt),node],text=True).splitlines()
  if 'compatible' not in props:continue
  compat=get(node,'compatible').split()
  if set(compat)&{'apple,j616-macaudio','ti,tas2764','ti,tas2770','ti,sn012776'}:
   assert get(node,'status')=='disabled';amps.append(node)
 assert amps
 for node in ['/iommu@402300000','/iommu@402340000','/mailbox@402e08000','/dcp@402e00000','/dcp@402e00000/piodma','/display-subsystem']:
  assert get(node,'status')=='disabled'
 checks[name]={'speaker_nodes_disabled':amps,'aop_streams':'dma cout cin','chassis':'J614'}
report={'linux_pin':subprocess.check_output(['git','rev-parse','HEAD'],cwd=LINUX,text=True).strip(),
 'dart_byte_identical_to_upstream':True,'dart_sha256':sha(upstream),'templates':checks,
 'speaker_streams_absent':True,'gpu16_opt_in_preserved':'t6040_16core' in (LINUX/'drivers/gpu/drm/asahi/g17/mod.rs').read_text(),
 'loaded_firmware_identity_included':True,'native_boot_tested':False}
assert report['gpu16_opt_in_preserved']
(OUT/'source-audit.json').write_text(json.dumps(report,indent=2)+'\n')
