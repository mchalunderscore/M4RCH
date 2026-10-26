#!/usr/bin/env python3
"""Package the reviewed Aurora kernel/loader with the capture-only audio runtime."""
from pathlib import Path
import gzip,hashlib,io,json,re,sys,tarfile
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'out/aurora-audio/r12'
sys.path.insert(0,str(ROOT/'experiments/aurora-dcp'))
from validate_initramfs import entries
from package_bootfb import repack_cpio

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 source=ROOT/'out/aurora-audio/r11/initramfs.img';before=entries(source)
 release=(OUT/'kernel.release').read_text().strip();assert release=='7.3.0-m4rch-aurora012'
 modules=(OUT/'modules.tar.gz').read_bytes()
 with tarfile.open(fileobj=io.BytesIO(modules),mode='r:gz') as tar:
  names=tar.getnames();ko=[n for n in names if n.endswith('.ko')]
  assert len(ko)>=248
  assert not any('tas2764.ko' in n or 'tas2770.ko' in n for n in names)
  for name in ko:assert ('vermagic='+release+' ').encode() in tar.extractfile(name).read(),name
  assert any(n.endswith('/snd-soc-aop.ko') for n in ko)
  assert any(n.endswith('/appledrm.ko') for n in ko)
 runtime=before['aurora-runtime.sh'][1].replace(b'AUMI001 r11 AOP microphone capture; proven DCP010 kernel; speakers excluded',b'AUMI001 r12 reviewed Aurora integration; microphone + GPU/DCP; speakers excluded')
 assert b'AUMI001 r12' in runtime
 conf=before['etc/nvme-root.conf'][1].replace(b'7.3.0-m4rch-dcp010',release.encode());assert release.encode() in conf
 profile=json.loads(before['gpu16-profile.json'][1]);profile.update({'revision':12,'kernel_release':release,
  'sources':{'linux':'ff1510ce2d2c25077948a78beba8cc32fb7068c1','m1n1':'1efafe1fe0ec134b89d55c2cc64106a66a4df2b7','uboot':'7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c'},
  'linux_prs_added':[436,437,451,453],'linux_prs_in_base':[427,428,435,448,452],
  'linux_prs_retained':[429,433],'loader_revision':'AUMI012','native_boot_tested':False,
  'changes':['AOP code/log firmware reservations; SRAM calibration-data segment no longer blocks AOP',
   'J614 HPAI UCM and Aurora J616 microphone DSP adapted to J614',
   'Independent jack registration; speaker/sense DMA streams removed from the AOP audio node',
   'Named same-boot GPU fw-text reservation for upstream loaded-image identification',
   'Reviewed Type-C fabric routing, callback bounds and USB3 lane reclaim changes',
   'IRQ-safe PMP report entries and alternate T6040 firmware identity',
   'Native-tested J614 resource layout, GPU16 opt-in and runtime Mesa retained'],
  'limitations':['Native validation of the combined kernel and microphone remains pending',
   'External display processors remain disabled pending J614 loader/DT handoff enablement',
   'DCP suspend remains inhibited and VRR disabled','Built-in speaker cards, streams and amplifier modules excluded']})
 collect=before['aurora-collect.sh'][1].decode()
 anchor='sync -f "$destination"'
 assert collect.count(anchor)==1
 collect=collect.replace(anchor,'''{
 echo 'ALSA cards and capture devices:'
 cat /proc/asound/cards /proc/asound/pcm 2>/dev/null || true
 arecord -l 2>/dev/null || true
 echo 'AOP handoff status:'
 od -An -t x1 /proc/device-tree/chosen/m4rch,aop-handoff-error 2>/dev/null || true
 if [ -S /run/user/1000/pipewire-0 ]; then
  runuser -u alice -- env XDG_RUNTIME_DIR=/run/user/1000 wpctl status 2>/dev/null || true
 fi
} >"$destination/microphone.txt"
'''+anchor)
 changes={'aurora-runtime.sh':runtime,'etc/nvme-root.conf':conf,'modules.tar.gz':modules,
          'gpu16-profile.json':(json.dumps(profile,indent=2)+'\n').encode(),'aurora-collect.sh':collect.encode()}
 (OUT/'initramfs.img').write_bytes(repack_cpio(source,changes))
 after=entries(OUT/'initramfs.img');assert before.keys()==after.keys()
 assert sorted(n for n in before if before[n]!=after[n])==sorted(changes)
 for n in ['init','mesa.tar.gz','ucm.tar.gz','aurora-with-mesa']:assert before[n]==after[n]
 for n in ['init','aurora-runtime.sh','aurora-collect.sh']:assert after[n][0]&0o111
 (OUT/'init').write_bytes(after['init'][1]);(OUT/'aurora-runtime.sh').write_bytes(runtime)
 prefix=(OUT/'m1n1.bin').read_bytes();control=(OUT/'control.dtb').read_bytes();uboot=(OUT/'u-boot-nodtb.bin').read_bytes()
 sys.path.insert(0,str(ROOT/'sdboot'));from loader import pack,validate_uboot_config
 pack(prefix,control,uboot);validate_uboot_config(OUT/'uboot.config',OUT/'serial.Makefile',internal=True)
 assert (OUT/'template.dtb').read_bytes() in uboot
 boot=prefix+control+gzip.compress(uboot,compresslevel=9,mtime=0)
 remaining=(ROOT/'out/aurora-bootstrap/stage1.bin').stat().st_size-len(boot)
 assert remaining>=32768
 (OUT/'boot.bin').write_bytes(boot);(OUT/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
 files={n:{'sha256':sha(OUT/n),'bytes':(OUT/n).stat().st_size} for n in ['Image','initramfs.img','boot.bin','modules.tar.gz','control.dtb','template.dtb','u-boot-nodtb.bin']}
 manifest={'test':'AUMI001','revision':12,'kernel_release':release,'kernel_sha256':sha(OUT/'Image'),
  'files':files,'stage2_window_remaining':remaining,'module_count':len(ko),'speakers_disabled':True,'native_boot_tested':False}
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
