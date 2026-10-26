#!/usr/bin/env python3
"""Prepare an initramfs-only microphone candidate on the proven DCP r10 kernel."""
from pathlib import Path
import gzip, hashlib, io, json, re, sys, tarfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/aurora-dcp'))
from validate_initramfs import entries
from package_bootfb import repack_cpio
BASE=ROOT/'out/aurora-dcp/j616-r10'; OUT=ROOT/'out/aurora-audio/r11'; KIT=Path(__file__).resolve().parent

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    before=entries(BASE/'initramfs.img')
    init=before['init'][1].decode()
    anchor='mkdir -p /run/aurora-modules /run/aurora-userspace /run/aurora-direct'
    assert init.count(anchor)==1
    # Existing explicit module loading uses this isolated configuration.
    anchor2='echo "Aurora CPUs:'
    pos=init.index(anchor2)
    init=init[:pos]+"printf '\\noptions snd_soc_aop mic_check_123=1\\n' >>/run/aurora-direct/modprobe.conf\n"+init[pos:]
    graph=(KIT/'upstream/j616-mic.json').read_text().replace('J616','J614').replace('j616','j614')
    graph=graph.replace('alsa_input.platform-sound.RawMics','alsa_input.m4rch.j614.RawMics')
    # Upstream mic.json is SPA JSON, with legal trailing commas.
    args=json.loads(re.sub(r',\s*([}\]])',r'\1',graph))
    pw='context.modules = [ { name = libpipewire-module-filter-chain\nargs = '+json.dumps(args,indent=2)+'\n} ]\n'
    wp='''monitor.alsa.rules = [
  { matches = [ { api.alsa.path = "hw:AppleJ614HPAI,0" } ]
    actions = { update-props = {
      node.name = "alsa_input.m4rch.j614.RawMics"
      node.description = "Built-in three-channel microphone array"
      node.hidden = true
      priority.session = 100
    } }
  }
]
'''
    for name,body in [('pipewire',pw),('wireplumber',wp)]:
        (OUT/(name+'-microphone.conf')).write_text(body)
    # RAM-only overlays are prepared before PipeWire/WirePlumber start.
    overlay='\n# AUMI001: preserve installed settings and overlay capture-only configuration in RAM.\n'
    for name,body in [('pipewire',pw),('wireplumber',wp)]:
        overlay+=f'''mkdir -p /newroot/etc/{name}/{name}.conf.d /run/aurora-userspace/{name}-mic
cp -a /newroot/etc/{name}/{name}.conf.d/. /run/aurora-userspace/{name}-mic/ || stop 'Cannot preserve {name} settings'
cat >/run/aurora-userspace/{name}-mic/99-m4rch-microphone.conf <<'AUMI001_CONFIG'
{body}AUMI001_CONFIG
mount --bind /run/aurora-userspace/{name}-mic /newroot/etc/{name}/{name}.conf.d || stop 'Cannot bind {name} capture configuration'
'''
    marker='cp /aurora-runtime.sh /run/aurora-direct/runtime.sh'
    assert init.count(marker)==1;init=init.replace(marker,overlay+'\n'+marker)
    runtime=before['aurora-runtime.sh'][1].decode()
    runtime=runtime.replace('AUDP001 r10 merged J616s stack and standard T6041 DMA; speakers excluded','AUMI001 r11 AOP microphone capture; proven DCP010 kernel; speakers excluded')
    assert 'AUMI001 r11' in runtime
    # Same module tree and exact same display/GPU userspace as native-tested r10.
    ucm=io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(before['ucm.tar.gz'][1]),mode='r:gz') as src, tarfile.open(fileobj=ucm,mode='w') as dst:
        for item in src:
            dst.addfile(item,src.extractfile(item) if item.isfile() else None)
        name='ucm2/conf.d/aop_audio/MacBook Pro J614 High-Power Audio Interface.conf'
        body=b'Syntax 7\nSectionUseCase."HiFi" {\n Comment "Default"\n File "/conf.d/aop_audio/3chan/HiFi.conf"\n}\n'
        item=tarfile.TarInfo(name);item.size=len(body);item.mode=0o644;dst.addfile(item,io.BytesIO(body))
    profile=json.loads(before['gpu16-profile.json'][1]);profile.update({
        'revision':11,'test':'AUMI001','native_boot_tested':False,'native_takeover_tested':False,
        'baseline_native_validated':{'revision':10,'dcp_120hz':True,'gpu_acceleration':True,'evidence':'user report; r10 return bundle'},
        'microphone':{'card':'AppleJ614HPAI','channels':3,'rate':48000,'source':'effect_output.j614-mic',
        'aop_memory':'__ETEXT + __OS_LOG; nCal=0; __EDATA may be SRAM',
        'graph_source':'aurora-silicon/asahi-audio@68b496e2f668c210c3e3a3ac1dd5de3ef9142023/firs/j616/mic.json',
        'graph_adaptation':'J614 identity and unique raw target; unchanged mixer, gain and highpass',
        'status':'prepared for native validation'},'loader_revision':'AUMI001',
        'limitations':['Microphone capture needs native validation','Built-in speaker cards and amplifiers remain disabled',
                        'DCP suspend remains inhibited; VRR and external displays remain disabled']})
    changes={'init':init.encode(),'aurora-runtime.sh':runtime.encode(),'ucm.tar.gz':gzip.compress(ucm.getvalue(),mtime=0),
             'gpu16-profile.json':(json.dumps(profile,indent=2)+'\n').encode()}
    result=repack_cpio(BASE/'initramfs.img',changes);(OUT/'initramfs.img').write_bytes(result)
    after=entries(OUT/'initramfs.img');assert before.keys()==after.keys()
    assert sorted(n for n in before if before[n]!=after[n])==sorted(changes)
    for n in ['modules.tar.gz','mesa.tar.gz','etc/nvme-root.conf']:
        assert before[n]==after[n]
    prefix=(OUT/'m1n1.bin').read_bytes();control=(OUT/'control.dtb').read_bytes();uboot=(OUT/'u-boot-nodtb.bin').read_bytes()
    assert (OUT/'template.dtb').read_bytes() in uboot
    boot=prefix+control+gzip.compress(uboot,compresslevel=9,mtime=0)
    stage1=ROOT/'out/aurora-bootstrap/stage1.bin'
    assert stage1.stat().st_size-len(boot)>=32768
    (OUT/'boot.bin').write_bytes(boot)
    (OUT/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    files={n:{'sha256':sha((OUT/n).read_bytes()),'bytes':(OUT/n).stat().st_size} for n in ['boot.bin','initramfs.img','template.dtb','control.dtb','u-boot-nodtb.bin']}
    manifest={'test':'AUMI001','revision':11,'kernel_release':'7.3.0-m4rch-dcp010','kernel_sha256':sha((BASE/'Image').read_bytes()),
              'files':files,'stage2_window_remaining':stage1.stat().st_size-len(boot),'changed_cpio_entries':list(changes),'speakers_disabled':True}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n'); print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
