#!/usr/bin/env python3
"""Capture GPU boot contracts from Linux; no driver load, MMIO or firmware start."""
import argparse,hashlib,json,os,re,subprocess,time
from pathlib import Path

LIMIT=16*1024*1024

def command(args):
    try:
        r=subprocess.run(args,capture_output=True,timeout=20)
        return {'command':args,'status':r.returncode,'stdout':r.stdout[:1024*1024].decode(errors='replace'),'stderr':r.stderr[:65536].decode(errors='replace')}
    except (OSError,subprocess.TimeoutExpired) as e:return {'command':args,'error':str(e)}

def read(path,limit=LIMIT):
    with path.open('rb') as f:data=f.read(limit+1)
    if len(data)>limit:raise ValueError('Read limit exceeded: '+str(path))
    return data

def capture(out):
    out.mkdir(exist_ok=False,parents=False)
    context={'schema':'m4rch.gpu-native.v1','uname':list(os.uname()),'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'hardware_actions':[]}
    for name,args in {'journal':['journalctl','-b','-k','--no-pager'],'modules':['lsmod'],'packages':['pacman','-Q'], 'mtd':['cat','/proc/mtd'],'dtc-version':['dtc','--version']}.items():
        (out/(name+'.json')).write_text(json.dumps(command(args),indent=2)+'\n')
    for path,name in [(Path('/sys/firmware/fdt'),'boot.dtb'),(Path('/sys/kernel/notes'),'kernel-notes.bin'),(Path('/proc/config.gz'),'config.gz')]:
        if path.exists():(out/name).write_bytes(read(path))
    tree=Path('/proc/device-tree');selected={}
    if tree.is_dir():
        for parent,dirs,files in os.walk(tree,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(parent)/d).is_symlink()]
            rel=Path(parent).relative_to(tree);name=rel.as_posix()
            if not (str(rel)=='.' or name=='chosen' or name.startswith('reserved-memory') or re.search(r'(gpu|sgx|agx|uat|mcc)',name,re.I)):continue
            props={}
            for fn in files:
                p=Path(parent)/fn
                if p.is_symlink():continue
                if name=='chosen' and not any(word in fn for word in ('firmware','bootargs','asahi','model')):continue
                try:props[fn]=read(p,65536).hex()
                except (OSError,ValueError) as e:props[fn]={'error':str(e)}
            selected[name]=props
    (out/'gpu-device-tree.json').write_text(json.dumps(selected,indent=2)+'\n')
    mtds=Path('/sys/class/mtd')
    if mtds.is_dir():
        for mtd in mtds.glob('mtd*'):
            if not re.fullmatch(r'mtd[0-9]+',mtd.name):continue
            try:
                if (mtd/'name').read_text().strip()!='adt':continue
                size=int((mtd/'size').read_text());assert 0<size<=LIMIT
                # Read only an already exposed phram ADT device, never /dev/mem.
                (out/'linux-boot.adt').write_bytes(read(Path('/dev')/mtd.name,size))
            except (OSError,ValueError,AssertionError) as e:context['adt_error']=str(e)
    context['render_nodes']=[p.name for p in Path('/dev/dri').glob('*')] if Path('/dev/dri').exists() else []
    context['platform_devices']=[p.name for p in Path('/sys/bus/platform/devices').glob('*') if re.search(r'gpu|sgx|agx|uat',p.name,re.I)]
    (out/'context.json').write_text(json.dumps(context,indent=2)+'\n')
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if os.geteuid()!=0 or os.uname().sysname!='Linux':raise SystemExit('Run with sudo in Linux')
    capture(a.output);print(a.output)
if __name__=='__main__':main()
