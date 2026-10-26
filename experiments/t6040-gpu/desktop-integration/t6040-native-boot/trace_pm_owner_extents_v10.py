#!/usr/bin/env python3
"""Pin native PM resource extent, fresh scalar, and capacity ownership offline."""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
AGX=Path('/boot/GPUC003/private-apple/com.apple.AGXG16X')
IOGPU=ROOT/'out/private-apple/com.apple.iokit.IOGPUFamily.fileset-macho'
KERNEL=ROOT/'out/private-apple/kernelcache.decoded'
def segments(raw,header=0):
    p=header+32;out=[]
    for _ in range(struct.unpack_from('<I',raw,header+16)[0]):
        c,n=struct.unpack_from('<II',raw,p)
        if c==25:out.append(struct.unpack_from('<QQQQ',raw,p+24))
        p+=n
    return out
def read(raw,segs,a,n):
    for v,_,o,l in segs:
        if v<=a and a+n<=v+l:return raw[o+a-v:o+a-v+n]
    raise ValueError(hex(a))
def main():
    agx=AGX.read_bytes();io=IOGPU.read_bytes();kr=KERNEL.read_bytes()
    digest=lambda b:hashlib.sha256(b).hexdigest()
    assert digest(agx)=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
    e=next(x for x in json.loads((KERNEL.parent/'fileset-index.json').read_text())['entries'] if x['name']=='com.apple.kernel')
    owners=[('agx',AGX,agx,segments(agx),[(0x89fc794,0x89fc7b0),(0x89e8188,0x89e8204),(0x89fd440,0x89fd474),(0x89fb83c,0x89fb848),(0x89fb8dc,0x89fb8e8),(0x89e9f04,0x89e9f38),(0x89ff4e0,0x89ff544)]),
      ('iogpu',IOGPU,io,segments(io),[(0xa7d7bc0,0xa7d7c08),(0xa7d7dd4,0xa7d7de0),(0xa7d7e38,0xa7d7e7c),(0xa7d7f44,0xa7d7f54)]),
      ('kernel',KERNEL,kr,segments(kr,e['offset']),[(0xbeb2ca0,0xbeb2d00)])]
    spans=[]
    for name,path,raw,segs,ranges in owners:
        for s,t in ranges:
            a=0xfffffe0000000000+s;z=0xfffffe0000000000+t
            spans.append({'owner':name,'start':hex(a),'end':hex(z),'sha256':digest(read(raw,segs,a,z-a))})
    report={'schema':'m4rch.native-pm-owner-extents.v10','hardware_actions':[],
      'source_pins':[{'path':str(p),'sha256':digest(r)}for _,p,r,_,_ in owners],
      'source_spans':spans,
      'resource_extent':{'request':'AGX newKernelResource x2=PM148*DevicePMConfig[0]*4 bytes at89fd440..470',
        'resource_constructor':'8a0d524 forwards requested length through x3 toIOGPU newResourcea7d7bc0',
        'rounding':'newResourceWithOptions computes (requested+page_size-1)&-page_size at a7d7dd4..ddc/a7d7e3c; stores sp10 at a7d7e74',
        'assignment':'IOGPU resource78 receives rounded length fromsp10 at a7d7f44..50',
        'hardware_copy':'AGX reset89fb83c..844 resource78low32 toHWstate30',
        'linux_binding':'plan.roles[6].mapped_bytes is correct; logical_bytes is incorrect for this field'},
      'PM1d4':{'value':0,'scope':'fresh native object',
        'constructor':'G16X vtablebc0→89e9f04→AGXParameterManagementVirtual metaclass; alloc89ff4f8 invokes kernel OSObject_typed_operator_new atbeb2ca0',
        'allocation_flags':'small allocation flag4; large allocation0x41004. Both retain zero allocation flag4',
        'initialization':'ordinary PMinit89fc624 copiesDevicePMConfig to1d8 and does not write1d4; no ordinary PM setter found',
        'consumer':'reset89fb8dc..e4 copiesPM1d4 toHWstate10',
        'limitation':'Scalar semantic name remains unassigned; zero is fresh allocation provenance, not a proved persistent/reset identity'},
      'capacity':{'native':'PMinit89fc794..ac calls accelerator virtual1028→halGetDefaultParameterBufferSizeMax89e8188, then shifts result17; no +1 sentinel added',
        'native_provider':'rounds independent global/device memory budgets to multiples of129*0x20000, then selectsmaximum',
        'linux_policy':'capacity=max_blocks+1 remains explicit Linux retained allocation choice. It is not claimed to duplicate native global memory budgeting; CFGmaximum/maxPB count remainsmax_blocks.',
        'triangle_scope':'First render growth disabled, populated initial blocks11 below both configured max and retained capacity'},
      'qualification':'Static source owner chain only; no component execution, kernel build or hardware probe performed by this audit.'}
    out=ROOT/'docs/evidence/2026-10-11-native-pm-owner-extents-v10.json';out.write_text(json.dumps(report,indent=2)+'\n');print(out)
if __name__=='__main__':main()
