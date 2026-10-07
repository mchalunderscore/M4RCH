#!/usr/bin/env python3
"""Set only the reserved ESP/root GPT types after booting the migrated NVMe root."""
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import uuid
import zlib

ESP='c12a7328-f81f-11d2-ba4b-00a0c93ec93b'
ROOT='0fc63daf-8483-4772-8e79-3d69d8477de4'
BASIC='ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'

def require(condition,message):
    if not condition: raise ValueError(message)

def output(*args):return subprocess.check_output(args,text=True).strip()

def parts(disk):
    with open(disk,'rb',buffering=0) as stream:
        stream.seek(4096);header=stream.read(4096)
        require(header[:8]==b'EFI PART','Invalid GPT')
        size,crc=struct.unpack_from('<II',header,12)
        require(92<=size<=4096,'Invalid header size')
        checked=bytearray(header[:size]);checked[16:20]=bytes(4)
        require(zlib.crc32(checked)==crc,'Invalid header checksum')
        start,count,width,checksum=struct.unpack_from('<QIII',header,72)
        require(width>=128 and width%128==0 and 0<count<=4096 and count*width<=4*1024**2,'Invalid table bounds')
        stream.seek(start*4096);data=stream.read(count*width)
        require(len(data)==count*width and zlib.crc32(data)==checksum,'Invalid table checksum')
    result=[]
    for i in range(count):
        entry=data[i*width:(i+1)*width]
        if entry[:16]==bytes(16):continue
        first,last,attributes=struct.unpack_from('<QQQ',entry,32)
        result.append(dict(number=i+1,uuid=str(uuid.UUID(bytes_le=entry[16:32])),type=str(uuid.UUID(bytes_le=entry[:16])),offset=first*4096,bytes=(last-first+1)*4096,attributes=attributes))
    return result

def main():
    require(os.geteuid()==0,'Run sudo in native Linux')
    kit=Path(__file__).resolve().parent
    receipt=json.loads((kit/'migration.json').read_text())
    rootdev=output('findmnt','-n','-o','SOURCE','/')
    match=re.fullmatch(r'(/dev/nvme\d+n\d+)p\d+',rootdev)
    require(match is not None,'Boot the migrated NVMe root first')
    require(output('blkid','-s','UUID','-o','value',rootdev)==receipt['root_uuid'],'Wrong root UUID')
    disk=match[1]
    require(output('blockdev','--getss',disk)=='4096','Wrong sector size')
    before=parts(disk)
    current={p['uuid']:p for p in before}
    stable=lambda p:{k:v for k,v in p.items() if k!='number'}
    require(len(current)==len(receipt['protected'])+2,'Unexpected partition count')
    for old in receipt['protected']:
        require(old['uuid'] in current and stable(current[old['uuid']])==stable(old),'Protected partition changed')
    targets=[]
    for name,kind in [('esp',ESP),('root',ROOT)]:
        old=receipt[name];p=current.get(old['uuid'])
        require(p is not None and all(p[k]==old[k] for k in ('uuid','offset','bytes','attributes')),'Reserved partition changed')
        require(p['type'] in (BASIC,kind),'Unexpected existing type')
        if p['type']!=kind:targets.append((p['number'],kind))
    if targets:
        subprocess.run(['sgdisk',*[f'--typecode={n}:{kind}' for n,kind in targets],disk],check=True)
    after=parts(disk)
    expected={p['uuid']:dict(p) for p in before}
    expected[receipt['esp']['uuid']]['type']=ESP;expected[receipt['root']['uuid']]['type']=ROOT
    require({p['uuid']:p for p in after}==expected,'Unexpected change after GPT typing')
    subprocess.run(['sync'],check=True)
    print('EFI ESP and Linux root GPT types verified; partition UUIDs, bounds and filesystems preserved.')

if __name__=='__main__':main()
