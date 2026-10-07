#!/usr/bin/env python3
"""Experimental targeted SGX mapping batch; explicit static-map provenance."""
import struct,hashlib
from pathlib import Path
import adt,contract
PAGE=0x4000
ROWS=[(17,0,0x20000),(26,0xd04000,0x8000),(27,0xd0d000,0x1000),
      (28,0xd58000,0x8000),(29,0xd10000,0x4000),(31,0xd40000,0x4000),
      (32,0xd60000,0x20000),(40,0xe1c000,0x4000),(22,0x1000000,0x8000),
      (39,0xe08000,0x8000),(41,0xe1f800,0x4000),
      (33,0xd44000,0x4000),(35,0xe00000,0x4000)]
WRITABLE_SLOTS={33,35}
def extend(arena,receipt,raw):
    import json
    source=Path(__file__).resolve().parents[2]/'docs/evidence/gpuc002-input/agx-pio-map.json'
    source_raw=source.read_bytes(); mapping=json.loads(source_raw)
    if mapping['apple_build']!='25G83' or mapping['firmware_hardware_record_bytes']!=40 or mapping['firmware_copied_record_bytes']!=36:raise ValueError('Static source ABI differs')
    records={r['hal_resource_id']:r for r in mapping['records']}
    for slot,relative,size in ROWS:
        if slot in (26,32,33,35):
            r=records[slot]
            if int(r['relative_offset'],16)!=relative or int(r['length'],16)!=size:raise ValueError('Qualified static row differs')
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
        # Only the two mandatory producer banks receive write flags/device PTEs.
        struct.pack_into('<QQIIQI',result,hardware+0x640+slot*0x28,
                         physical,address,size,size,relative if slot not in (22,39,41) else 0,int(slot in WRITABLE_SLOTS))
        for off in range(0,length,PAGE):
            leaves.append({'physical':page+off,'gpu_va':base+cursor+off,'readonly':slot not in WRITABLE_SLOTS})
        descriptors.append({'slot':slot,'physical':hex(physical),'gpu_va':hex(address),
                            'size':hex(size),'readonly':slot not in WRITABLE_SLOTS,'mapped_pages':length//PAGE,
                            'role_qualification':'matching25G83 static table and exact native reads; write semantics from captured firmware' if slot in WRITABLE_SLOTS else ('matching25G83 static table extent' if slot==32 else ('native configuration word supports address' if slot==26 else 'donor offset and aperture containment hypothesis'))})
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
    # Captured J614s masks3db/3db; verified producer offsets and packed geometry.
    struct.pack_into('<QQ',result,hardware+0x2560,0x3db|(0x3db<<10),0)
    for obj in receipt['objects']:
        start=obj['arena_offset'];receipt_bytes=result[start:start+obj['input_bytes']]
        obj['input_sha256']=hashlib.sha256(receipt_bytes).hexdigest()
    receipt.update(device_access=True, static_map_sha256=hashlib.sha256(source_raw).hexdigest(), core_mask_input='0xf6fdb at hardware+0x2560; third word zero at+0x2568', arena_sha256=hashlib.sha256(result).hexdigest(),mmio_descriptors=descriptors,
                   mmio_leaves=leaves,mapped_pages=cursor//PAGE,voltage_adt_sha256=hashlib.sha256(raw).hexdigest(),
                   voltage_input_sha256={k:hashlib.sha256(gpu[k]).hexdigest() for k in ['perf-states','perf-states-sram']},
                   voltage_assignment='Only qualified profile-A core/SRAM cluster columns populated; profile-B and frequency assignment unchanged',
                   qualification='Experimental structural graph; only slots33/35 device pages writable; other bank hypotheses read-only. No complete hardware construction, write permissions, queue execution or rendering established.')
    return bytes(result),receipt
