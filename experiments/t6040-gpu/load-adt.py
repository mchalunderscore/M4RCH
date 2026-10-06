#!/usr/bin/env python3
"""Temporarily expose the loader's reserved ADT RAM as a read-only sysfs file."""
import argparse,hashlib,json,os,struct,subprocess,sys
from pathlib import Path
KIT=Path(__file__).resolve().parent

def build_id():
    data=Path('/sys/kernel/notes').read_bytes();offset=0
    while offset+12<=len(data):
        n,d,t=struct.unpack_from('<III',data,offset);offset+=12
        name=data[offset:offset+n];offset+=(n+3)&~3;desc=data[offset:offset+d];offset+=(d+3)&~3
        if name==b'GNU\0' and t==3:return desc.hex()
    raise ValueError('Missing kernel build ID')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if os.geteuid()!=0 or os.uname().sysname!='Linux':raise ValueError('Run with sudo in native Linux')
    receipt=json.loads((KIT/'BUILD.JSN').read_text())
    if os.uname().release!=receipt['release'] or build_id()!=receipt['build_id']:raise ValueError('Wrong kernel; no module load')
    for line in (KIT/'SUMS.TXT').read_text().splitlines():
        digest,name=line.split('  ',1)
        if '/' in name or name in ('.','..'):raise ValueError('Invalid kit manifest')
        if hashlib.sha256((KIT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Kit checksum mismatch: '+name)
    if a.output.exists():raise ValueError('Use a new output directory')
    if Path('/sys/module/m4rch_gpu_adt').exists():raise ValueError('ADT helper already loaded; inspect ownership')
    subprocess.run(['insmod',str(KIT/'ADT.ko')],check=True)
    try:
        subprocess.run([sys.executable,str(KIT/'COLLECT.PY'),'--output',str(a.output)],check=True)
        source=Path('/sys/kernel/m4rch_gpu_adt/adt')
        with source.open('rb') as f:data=f.read(16*1024*1024+1)
        if len(data)>16*1024*1024:raise ValueError('ADT read limit')
        (a.output/'linux-boot.adt').write_bytes(data)
        subprocess.run([sys.executable,str(KIT/'ADT.PY'),'--input',str(a.output/'linux-boot.adt'),'--output',str(a.output/'selected-adt.json')],check=True)
        (a.output/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in sorted(a.output.iterdir()) if f.is_file() and f.name!='SHA256SUMS'))
    finally:subprocess.run(['rmmod','m4rch_gpu_adt'],check=True)
    print('Captured Linux boot ADT; temporary read-only helper unloaded:',a.output)
if __name__=='__main__':main()
