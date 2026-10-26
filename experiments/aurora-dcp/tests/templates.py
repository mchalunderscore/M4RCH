#!/usr/bin/env python3
"""Check the actual serialized DMA graph while preserving GPU device properties."""
from pathlib import Path
import subprocess

OUTPUT=Path(__file__).resolve().parents[3]/'out/aurora-dcp'
def get(path,node,prop,kind='x'):
    return subprocess.check_output(['fdtget','-t',kind,str(path),node,prop],text=True).strip()
def props(path,node):
    return subprocess.check_output(['fdtget','-p',str(path),node],text=True).splitlines()

def main():
    for name in ['control.dtb','template.dtb']:
        path=OUTPUT/name; before=OUTPUT/'revision-1'/name
        for node in ['/dcp@402e00000','/dcp@402e00000/piodma','/display-subsystem']:
            assert 'dma-noncoherent' in props(path,node) and 'dma-coherent' not in props(path,node),node
        for node in ['/iommu@402300000','/iommu@402340000','/mailbox@402e08000','/dcp@402e00000','/display-subsystem']:
            assert get(path,node,'status','s')=='disabled',node
        for node,dart,sid in [('/dcp@402e00000','/iommu@402340000',23),('/dcp@402e00000/piodma','/iommu@402300000',16),('/display-subsystem','/iommu@402300000',0)]:
            assert [int(x,16) for x in get(path,node,'iommus').split()]==[int(get(path,dart,'phandle'),16),sid]
        roots=subprocess.check_output(['fdtget','-l',str(path),'/'],text=True).splitlines()
        candidates=[node for node in roots if node.startswith('gpu@')]
        assert len(candidates)==1
        gpu='/'+candidates[0]
        assert set(props(path,gpu))==set(props(before,gpu))
        for prop in props(path,gpu): assert get(path,gpu,prop,'bx')==get(before,gpu,prop,'bx'),prop
        assert 'pmp' not in props(path,'/aliases')
    print('Serialized templates PASS: explicit NC on all three display devices, correct retained SIDs, disabled admission, identical GPU properties')

if __name__=='__main__': main()
