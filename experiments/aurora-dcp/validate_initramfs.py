#!/usr/bin/env python3
"""Read the packed CPIO directly; check payload identities and boot-critical modes."""
import gzip
import hashlib
import io
from pathlib import Path
import tarfile

PROJECT=Path(__file__).resolve().parents[2]
OUTPUT=PROJECT/'out/aurora-dcp'

def entries(path):
    data=gzip.decompress(path.read_bytes()); offset=0; result={}
    while True:
        assert data[offset:offset+6]==b'070701'
        fields=[int(data[offset+6+i*8:offset+14+i*8],16) for i in range(13)]
        mode,size,namesize=fields[1],fields[6],fields[11]
        name=data[offset+110:offset+110+namesize-1].decode()
        start=(offset+110+namesize+3)&~3
        body=data[start:start+size]; assert len(body)==size
        offset=(start+size+3)&~3
        if name=='TRAILER!!!': break
        result[name.removeprefix('./')]=(mode,body)
    return result

def main():
    old=entries(OUTPUT/'inputs/initramfs.gpu16.img'); new=entries(OUTPUT/'initramfs.img')
    for name in ['mesa.tar.gz','ucm.tar.gz','aurora-with-mesa','gpu16-discovery.sh']:
        assert new[name]==old[name],name
    assert new['init'][0]&0o111
    release=(OUTPUT/'kernel.release').read_text().strip()
    assert ("KERNEL_RELEASE='"+release+"'").encode() in new['etc/nvme-root.conf'][1]
    assert new['modules.tar.gz'][1]==(OUTPUT/'modules.tar.gz').read_bytes()
    for name,source in [('gpu16-recorder.sh','recorder.sh'),('collect-display.sh','collect-display.sh')]:
        assert new[name][1]==(PROJECT/'experiments/aurora-dcp'/source).read_bytes()
    assert b'modprobe_test appledrm j614s_modeset=1' in new['aurora-runtime.sh'][1]
    assert b'appledrm.j614s_modeset=1' in new['aurora-runtime.sh'][1]
    assert b'AllowSuspend=no' in new['init'][1]
    with tarfile.open(fileobj=io.BytesIO(new['modules.tar.gz'][1])) as archive:
        for suffix in ['/appledrm.ko','/asahi.ko']:
            name=next(n for n in archive.getnames() if n.endswith(suffix))
            assert ('vermagic='+release+' ').encode() in archive.extractfile(name).read()
    print('Packed initramfs PASS: executable init, matching kernel/modules, identical working Mesa/UCM/discovery, DCP runtime and sleep masks')

if __name__=='__main__': main()
