#!/usr/bin/env python3
"""Read-only native audio prerequisites; no driver loads, bus scans or playback."""
import json,subprocess,tempfile,os
from pathlib import Path

def command(args):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=20)
        return {'command':args,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    except (OSError,subprocess.TimeoutExpired) as e:return {'command':args,'error':str(e)}

def main():
    out=Path(tempfile.mkdtemp(prefix='m4rch-audio-preflight-',dir='/var/tmp'))
    report={'uname':os.uname().release,'scope':'Read-only; no modprobe, I2C scan, MMIO, recording or playback','modules':{name:command(['modinfo',name]) for name in ('snd-soc-cs42l84','apple-admac','snd-soc-apple-mca','snd-soc-macaudio')},'alsa':{},'i2c':[],'device_tree':[]}
    for file in ('cards','pcm','devices'):
        p=Path('/proc/asound')/file
        if p.exists():report['alsa'][file]=p.read_text()
    for p in sorted(Path('/sys/bus/i2c/devices').glob('*')):
        row={'path':str(p),'driver':str((p/'driver').resolve()) if (p/'driver').exists() else None}
        for key in ('name','modalias'):
            if (p/key).is_file():row[key]=(p/key).read_text()
        report['i2c'].append(row)
    base=Path('/sys/firmware/devicetree/base')
    for p in sorted(base.rglob('compatible')):
        raw=p.read_bytes()
        if any(key in raw.lower() for key in (b'audio',b'cs42',b'mca',b'admac',b'aop')):
            row={'path':str(p.parent.relative_to(base)),'compatible':raw.rstrip(b'\0').decode(errors='replace').split('\0')}
            for key in ('reg','status','interrupts','clocks','power-domains','iommus','dmas'):
                q=p.parent/key
                if q.is_file():row[key]={'hex':q.read_bytes()[:512].hex()}
            report['device_tree'].append(row)
    (out/'preflight.json').write_text(json.dumps(report,indent=2)+'\n')
    if os.geteuid()==0:subprocess.run(['chown','-R',os.environ.get('SUDO_UID','0')+':'+os.environ.get('SUDO_GID','0'),str(out)])
    print(out)
if __name__=='__main__':main()
