#!/usr/bin/env python3
"""Keep the native-tested r12 kernel/modules/Mesa; correct AOP handoff and option."""
from pathlib import Path
import gzip,hashlib,json,sys,subprocess
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'out/aurora-audio/r13';BASE=OUT.parent/'r12'
sys.path.insert(0,str(ROOT/'experiments/aurora-dcp'))
from validate_initramfs import entries
from package_bootfb import repack_cpio
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 before=entries(BASE/'initramfs.img');init=before['init'][1].decode()
 option=r"printf '\noptions snd_soc_aop mic_check_123=1\n'"
 assert init.count(option)==1
 actual=subprocess.check_output(['/bin/sh','-c',option]);assert actual==b'\noptions snd_soc_aop mic_check_123=1\n'
 init=init.replace('# Dedicated test initramfs:', '# AUMI013: Aurora m1n1 AOP reservation handoff; capture-only audio.\n# Dedicated test initramfs:',1)
 runtime=before['aurora-runtime.sh'][1].replace(b'AUMI001 r12 reviewed Aurora integration;',b'AUMI001 r13 upstream AOP handoff;')
 collect=before['aurora-collect.sh'][1].decode();anchor='sync -f "$destination"';assert collect.count(anchor)==1
 collect=collect.replace(anchor,'''{
 echo 'AOP same-boot segment metadata:'
 for p in /proc/device-tree/chosen/m4rch,aop-segment-*; do echo "$p"; od -An -tx1 "$p"; done
 echo 'Capture configuration and mounts:'
 cat /run/aurora-direct/modprobe.conf /etc/pipewire/pipewire.conf.d/99-m4rch-microphone.conf /etc/wireplumber/wireplumber.conf.d/99-m4rch-microphone.conf
 findmnt -rn | grep -E 'pipewire|wireplumber|ucm2' || true
 if [ -S /run/user/1000/pipewire-0 ]; then
  runuser -u alice -- env XDG_RUNTIME_DIR=/run/user/1000 pw-dump >"$destination/pipewire-nodes.json" 2>&1 || true
  runuser -u alice -- env XDG_RUNTIME_DIR=/run/user/1000 systemctl --user show pipewire.service wireplumber.service -p ExecStart -p Environment || true
 fi
} >"$destination/microphone-config.txt" 2>&1
'''+anchor)
 profile=json.loads(before['gpu16-profile.json'][1]);profile.update(revision=13,loader_revision='AUMI013',native_boot_tested=False)
 profile['microphone']['aop_memory']='Aurora m1n1 same-boot DRAM reservations, remapped to template AOP; nCal=0 code/log only'
 changes={'init':init.encode(),'aurora-runtime.sh':runtime,'aurora-collect.sh':collect.encode(),'gpu16-profile.json':(json.dumps(profile,indent=2)+'\n').encode()}
 (OUT/'initramfs.img').write_bytes(repack_cpio(BASE/'initramfs.img',changes))
 after=entries(OUT/'initramfs.img');assert before.keys()==after.keys();assert sorted(n for n in before if before[n]!=after[n])==sorted(changes)
 for n in ['modules.tar.gz','mesa.tar.gz','ucm.tar.gz','etc/nvme-root.conf']:assert before[n]==after[n]
 boot=(OUT/'m1n1.bin').read_bytes()+(OUT/'control.dtb').read_bytes()+gzip.compress((OUT/'u-boot-nodtb.bin').read_bytes(),compresslevel=9,mtime=0)
 remaining=(ROOT/'out/aurora-bootstrap/stage1.bin').stat().st_size-len(boot);assert remaining>=32768
 (OUT/'boot.bin').write_bytes(boot);(OUT/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
 files={n:{'sha256':sha((OUT/n).read_bytes()),'bytes':(OUT/n).stat().st_size} for n in ['boot.bin','initramfs.img','control.dtb','template.dtb','u-boot-nodtb.bin']}
 manifest={'test':'AUMI001','revision':13,'kernel_release':'7.3.0-m4rch-aurora012','kernel_sha256':sha((BASE/'Image').read_bytes()),'kernel_path':'/AUDP001/r12/vmlinuz','files':files,'stage2_window_remaining':remaining,'native_microphone_tested':False,'speakers_disabled':True}
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
