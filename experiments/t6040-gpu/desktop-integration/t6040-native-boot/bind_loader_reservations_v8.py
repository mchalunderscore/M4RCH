#!/usr/bin/env python3
"""Bind original loader SGX reservations into disabled prepared native DT.

This copies loader-owned inputs; never allocate/initialize firmware tables or
access hardware. Current boot's saved addresses require verification against
fresh boot ADT before using an enabled candidate.
"""
import argparse,importlib.util,json,struct
from pathlib import Path
import libfdt
from native_adt_bridge_v7 import node_properties,pin
from prepare_dt_v7 import reg,GPU
KIT=Path(__file__).resolve().parent
ROOT=KIT.parents[3]
SOURCES={'ttbs':'gpu-region','pagetables':'gfx-shared-region',
         'l2':'gfx-shared-l2-region','handoff':'gfx-handoff','firmware':'gfx-data'}

def bind(adt_path,dt_path,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('loader_adt',ROOT/'experiments/t6040-gpu/adt.py')
    parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
    tree=parser.parse(Path(adt_path).read_bytes());sgx=tree['/device-tree/arm-io/sgx']
    raw=Path(dt_path).read_bytes();before=node_properties(raw)
    assert before[GPU]['status']==b'disabled\0'
    def u64(key):
        value=sgx[key];assert len(value)==8;return struct.unpack('<Q',value)[0]
    private=(u64('rtkit-private-vm-region-base'),u64('rtkit-private-vm-region-size'))
    assert private==(0xfffffc0000000000,0x2000000000)
    assert before[GPU]['apple,rtkit-private-vm-region']==reg(*private)
    banks=[]
    for props in before.values():
        if props.get('device_type')==b'memory\0':
            data=props['reg'];assert len(data)%16==0
            banks.extend(struct.unpack_from('>QQ',data,i) for i in range(0,len(data),16))
    assert banks
    reservations={}
    for name,prefix in SOURCES.items():
        base,size=u64(prefix+'-base'),u64(prefix+'-size')
        assert base and size>=0x4000 and not((base|size)&0x3fff)
        assert all(base+size<=b or b+n<=base for b,n in banks),(name,'intersects Linux RAM')
        assert all(base+size<=b or b+n<=base for b,n in reservations.values())
        reservations[name]=(base,size)
    # Firmware TEXT has a separate native mapping, although crash-buffer offers
    # are bounded by the DATA reservation consumed by BootOps::shmem_map.
    names=tree['/device-tree/arm-io/gfx-asc']['segment-names'].split(b'\0')[0].split(b';')
    ranges=tree['/device-tree/arm-io/gfx-asc']['segment-ranges']
    assert len(ranges)==len(names)*32
    segments=[]
    for i,name in enumerate(names):
        cpu,va,pa,encoded=struct.unpack_from('<4Q',ranges,i*32)
        size=encoded&0xffffffff; flags=encoded>>32
        assert cpu==pa and not((pa|size)&0x3fff)
        assert all(pa+size<=b or b+n<=pa for b,n in banks)
        segments.append(dict(name=name.decode(),physical=hex(pa),virtual=hex(va),bytes=size,segment_flags=flags))
    assert next((int(x['physical'],16),x['bytes']) for x in segments if x['name']=='__DATA')==reservations['firmware']
    fdt=libfdt.Fdt(raw);fdt.resize(fdt.totalsize()+4096)
    for name,span in reservations.items():
        off=fdt.path_offset('/reserved-memory/gpu-'+name)
        fdt.setprop(off,'reg',reg(*span));fdt.setprop(off,'status',b'okay\0')
    fdt.pack();result=bytes(fdt.as_bytearray());after=node_properties(result)
    assert after[GPU]==before[GPU]
    for path,props in before.items():
        if path not in ['/reserved-memory/gpu-'+name for name in SOURCES]:assert after[path]==props
    target=output/'native-loader-reservations-disabled.dtb';target.write_bytes(result)
    report=dict(schema='m4rch.native-loader-reservations.v8',
        inputs=[pin(adt_path),pin(dt_path),pin(__file__)],output=pin(target),
        regions={k:dict(source=SOURCES[k],physical=hex(b),bytes=n) for k,(b,n) in reservations.items()},
        firmware_segments=segments,linux_memory_banks=[dict(physical=hex(b),bytes=n) for b,n in banks],
        firmware_root_retained=True,all_regions_disjoint_from_linux_allocator=True,
        GPU_disabled=True,hardware_actions=[],fresh_boot_addresses_verified=False,
        next_steps=['On fresh boot capture loader ADT and require all five regions/privateVM/segments match candidate; if relocated construct DT from that boot loader ADT before driver probing.',
                    'Enable the prepared GPU/mailbox/provider DT only together with qualified complete power module and bounded triangle launcher.',
                    'Reuse the existing firmware root; no zeroing borrowed page tables or loading a second firmware image.'])
    (output/'loader-reservations.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adt',required=True,type=Path);p.add_argument('--dtb',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();print(json.dumps(bind(a.adt,a.dtb,a.output)['regions']))
