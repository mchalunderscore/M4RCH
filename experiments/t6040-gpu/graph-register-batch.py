#!/usr/bin/env python3
"""Experimental read-only SGX mapping batch; explicit candidate roles."""
import struct,hashlib
from pathlib import Path
import adt,contract
PAGE=0x4000
ROWS=[(17,0,0x20000),(26,0xd04000,0x8000),(27,0xd0d000,0x1000),
      (28,0xd58000,0x8000),(29,0xd10000,0x4000),(31,0xd40000,0x4000),
      (32,0xd60000,0x8000),(40,0xe1c000,0x4000),(22,0x1000000,0x8000),
      (39,0xe08000,0x8000),(41,0xe1f800,0x4000)]
def extend(arena,receipt,raw):
    tree=adt.parse(raw);gpu=tree['/device-tree/arm-io/sgx']
    ranges=list(struct.iter_unpack('<QQQ',tree['/device-tree/arm-io']['ranges']))
    if ranges[0]!=(0,0x200000000,0x480000000):raise ValueError('Changed bus translation')
    windows=[(pa+0x200000000,size) for pa,size in struct.iter_unpack('<QQ',gpu['reg'])]
    if windows!=[(0x288000000,0x3758000),(0x288d00000,0x16c000)]:raise ValueError('Changed SGX apertures')
    hardware=next(o for o in receipt['objects'] if o['name']=='hardware')['arena_offset']
    base=int(receipt['base'],16);cursor=len(arena);leaves=[];descriptors=[];result=bytearray(arena)
    for slot,relative,size in ROWS:
        physical=windows[0][0]+relative;page=physical&~(PAGE-1);offset=physical&(PAGE-1)
        length=(offset+size+PAGE-1)&~(PAGE-1)
        if not any(start<=page and page+length<=start+span for start,span in windows):raise ValueError('Uncontained MMIO page span')
        address=base+cursor+offset
        # Descriptor flags0 and read-only device PTEs: no firmware write grant.
        struct.pack_into('<QQIIQI',result,hardware+0x640+slot*0x28,
                         physical,address,size,size,relative if slot not in (22,39,41) else 0,0)
        for off in range(0,length,PAGE):
            leaves.append({'physical':page+off,'gpu_va':base+cursor+off,'readonly':True})
        descriptors.append({'slot':slot,'physical':hex(physical),'gpu_va':hex(address),
                            'size':hex(size),'readonly':True,'mapped_pages':length//PAGE,
                            'role_qualification':'native configuration word supports address' if slot==26 else 'donor offset and aperture containment hypothesis'})
        cursor+=length
    count=int.from_bytes(gpu['perf-state-count'],'little');clusters=int.from_bytes(gpu['perf-state-table-count'],'little')
    if count!=16 or clusters!=2:raise ValueError('Changed voltage geometry')
    core=contract.tables(gpu['perf-states'],count,clusters);sram=contract.tables(gpu['perf-states-sram'],count,clusters)
    groups=[contract.ladder(c,s) for c,s in zip(core,sram)]
    if any(len(x)!=11 for x in groups):raise ValueError('Changed voltage groups')
    for row in range(11):
        for cluster in range(2):
            struct.pack_into('<I',result,hardware+0x1008+row*0x40+cluster*4,groups[cluster][row]['core_voltage_raw'])
            struct.pack_into('<I',result,hardware+0x1408+row*0x40+cluster*4,groups[cluster][row]['sram_voltage_raw'])
    for obj in receipt['objects']:
        start=obj['arena_offset'];receipt_bytes=result[start:start+obj['input_bytes']]
        obj['input_sha256']=hashlib.sha256(receipt_bytes).hexdigest()
    receipt.update(device_access=True, arena_sha256=hashlib.sha256(result).hexdigest(),mmio_descriptors=descriptors,
                   mmio_leaves=leaves,mapped_pages=cursor//PAGE,voltage_adt_sha256=hashlib.sha256(raw).hexdigest(),
                   voltage_input_sha256={k:hashlib.sha256(gpu[k]).hexdigest() for k in ['perf-states','perf-states-sram']},
                   voltage_assignment='Only qualified profile-A core/SRAM cluster columns populated; profile-B and frequency assignment unchanged',
                   qualification='Experimental structural graph and read-only register-bank hypotheses. No complete hardware construction, write permissions, queue execution or rendering established.')
    return bytes(result),receipt
