#!/usr/bin/env python3
"""Experimental targeted SGX mapping batch; explicit static-map provenance."""
import struct,hashlib
from pathlib import Path
import adt,contract
PAGE=0x4000
ROWS=[(17,0,0x21400),(26,0xd04000,0x8000),(27,0xd0d000,0x1000),
      (28,0xd58000,0x8000),(29,0xd10000,0x4000),(31,0xd40000,0x4000),
      (32,0xd60000,0x20000),(40,0xe1c000,0x4000),(22,0x1000000,0x8000),
      (39,0xe08000,0x8000),(41,0xe1f800,0x4000),
      (33,0xd44000,0x4000),(35,0xe00000,0x4000),
      (34,0xd4c000,0x200),(37,0xe40000,0x4000)]
WRITABLE_SLOTS={17,26,29,31,33,34,35,37,41}
WRITABLE_PAGES={0x288004000,0x288d04000,0x288d10000,0x288d40000,0x288d44000,0x288d4c000,0x288e00000,0x288e1c000,0x288e40000}
PLATFORM_ROWS=[(0,0x502414000,0xfffffc2001a00000,0x4000),
               (11,0x5003d8000,0xfffffc2001b18000,0x4000)]
AFR_BASE=0xfffffc2001c00000
AFR_PHYSICAL=(0x28b000000,0x28b200000,0x28b400000,0x28b600000)
def extend(arena,receipt,raw):
    import json
    source=Path(__file__).resolve().parents[2]/'docs/evidence/gpuc002-input/agx-pio-map.json'
    source_raw=source.read_bytes(); mapping=json.loads(source_raw)
    if mapping['apple_build']!='25G83' or mapping['firmware_hardware_record_bytes']!=40 or mapping['firmware_copied_record_bytes']!=36:raise ValueError('Static source ABI differs')
    records={r['hal_resource_id']:r for r in mapping['records']}
    for slot,relative,size in ROWS:
        if slot in (17,26,29,31,32,33,34,35,37,40):
            r=records[slot]
            if int(r['relative_offset'],16)!=relative or int(r['length'],16)!=size:raise ValueError('Qualified static row differs')
    tree=adt.parse(raw);gpu=tree['/device-tree/arm-io/sgx']
    ranges=list(struct.iter_unpack('<QQQ',tree['/device-tree/arm-io']['ranges']))
    if ranges[0]!=(0,0x200000000,0x480000000):raise ValueError('Changed bus translation')
    windows=[(pa+0x200000000,size) for pa,size in struct.iter_unpack('<QQ',gpu['reg'])]
    if windows!=[(0x288000000,0x3758000),(0x288d00000,0x16c000)]:raise ValueError('Changed SGX apertures')
    hardware=next(o for o in receipt['objects'] if o['name']=='hardware')['arena_offset']
    base=int(receipt['base'],16);mmio_base=base+0x100000;leaf_map={};descriptors=[];result=bytearray(arena)
    for slot,relative,size in ROWS:
        physical=windows[0][0]+relative;page=physical&~(PAGE-1);offset=physical&(PAGE-1)
        length=(offset+size+PAGE-1)&~(PAGE-1)
        if not any(start<=page and page+length<=start+span for start,span in windows):raise ValueError('Uncontained MMIO page span')
        address=mmio_base+relative
        # Only the qualified producer/counter banks receive write flags/device PTEs.
        struct.pack_into('<QQIIQI',result,hardware+0x640+slot*0x28,
                         physical,address,size,size,relative if slot not in (22,39,41) else 0,int(slot in WRITABLE_SLOTS))
        for off in range(0,length,PAGE):
            pa=page+off;va=mmio_base+(pa-windows[0][0])
            if not (base+len(arena)<=va and va+PAGE<=((base>>25)+1)<<25):raise ValueError('MMIO exceeds owned L2 or overlaps objects')
            readonly=pa not in WRITABLE_PAGES
            leaf={'physical':pa,'gpu_va':va,'readonly':readonly}
            if va in leaf_map and leaf_map[va]!=leaf:raise ValueError('Conflicting physical/permission alias')
            leaf_map[va]=leaf
        descriptors.append({'slot':slot,'physical':hex(physical),'gpu_va':hex(address),
                            'size':hex(size),'readonly':slot not in WRITABLE_SLOTS,'mapped_pages':length//PAGE,
                            'role_qualification':'matching25G83 static table and exact native reads; write semantics from captured firmware' if slot in WRITABLE_SLOTS else ('matching25G83 static table extent' if slot==32 else ('native configuration word supports address' if slot==26 else 'donor offset and aperture containment hypothesis'))})

    platform_source=Path(__file__).resolve().parents[2]/'docs/evidence/gpuc003-input/platform-map.json'
    platform_raw=platform_source.read_bytes();platform=json.loads(platform_raw)
    if platform['apple_build']!='25G83' or platform['agx_version']!='353.14' or platform['macho_sha256']!='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e':raise ValueError('Changed platform provenance')
    qualified={r['slot']:(int(r['physical'],16),int(r['extent'],16)) for r in platform['resources']}
    if base!=0xfffffc2000100000 or mmio_base!=0xfffffc2000200000:raise ValueError('Changed platform VA geometry')
    for slot,physical,address,size in PLATFORM_ROWS:
        if qualified.get(slot)!=(physical,size) or size!=PAGE or physical%PAGE or address%PAGE:raise ValueError('Changed platform resource')
        if address>>25!=base>>25 or address<base+len(arena) or address in leaf_map or any(v['physical']==physical for v in leaf_map.values()):raise ValueError('Platform mapping overlap/outside L2')
        struct.pack_into('<QQIIQI',result,hardware+0x640+slot*0x28,physical,address,size,size,0,1)
        leaf_map[address]={'physical':physical,'gpu_va':address,'readonly':False}
        descriptors.append({'slot':slot,'physical':hex(physical),'gpu_va':hex(address),'size':hex(size),'readonly':False,'mapped_pages':1,'mapping_class':'platform','role_qualification':'matching25G83 AGX constructor; firmware write consumers, platform ownership experimental'})
    # Four physical ranges compacted by the matching Apple createFWPIOMapping.
    # Full extents are readable, but only the 16 captured RMW pages writable.
    afr_source=Path(__file__).resolve().parents[2]/'docs/evidence/gpuc004-afr-map.json'
    afr_raw=afr_source.read_bytes();afr=json.loads(afr_raw)
    if tuple(int(x,16) for x in afr['physical_ranges'])!=AFR_PHYSICAL or afr['range_bytes']!=0x40000 or afr['instances']!=4:raise ValueError('Changed AFR provenance')
    if afr['macho_sha256']!=mapping['macho_sha256']:raise ValueError('Changed AFR binary')
    struct.pack_into('<QQIIQI',result,hardware+0x640+20*0x28,AFR_PHYSICAL[0],AFR_BASE,0x100000,0x40000,0,1)
    for index,physical in enumerate(AFR_PHYSICAL):
        for off in range(0,0x40000,PAGE):
            pa=physical+off;va=AFR_BASE+index*0x40000+off
            if va>>25!=base>>25 or va in leaf_map or not windows[0][0]<=pa<pa+PAGE<=windows[0][0]+windows[0][1]:raise ValueError('AFR overlap/outside aperture')
            leaf_map[va]={'physical':pa,'gpu_va':va,'readonly':bool(off%0x10000)}
    descriptors.append({'slot':20,'physical':hex(AFR_PHYSICAL[0]),'physical_ranges':[hex(x) for x in AFR_PHYSICAL],
                        'gpu_va':hex(AFR_BASE),'size':'0x100000','range_size':'0x40000','readonly':False,'mapped_pages':64,
                        'mapping_class':'afr-compacted','role_qualification':'matching25G83 constructor and segmented PIO mapping; 16 native firmware RMW sites, hardware experiment'})
    leaves=[leaf_map[va] for va in sorted(leaf_map)]
    for descriptor in descriptors:
        pa=int(descriptor['physical'],16);end=pa+int(descriptor['size'],16)
        descriptor['effective_writable_pages']=[hex(v['physical']) for v in leaves if not v['readonly'] and v['physical']<end and v['physical']+PAGE>pa]
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
    receipt.update(device_access=True, afr_map_sha256=hashlib.sha256(afr_raw).hexdigest(), platform_map_sha256=hashlib.sha256(platform_raw).hexdigest(), platform_mapping_class="Exact GPUC003 PA/VA pairs; no SGX-relative arithmetic for platform pages", static_map_sha256=hashlib.sha256(source_raw).hexdigest(), core_mask_input='0xf6fdb at hardware+0x2560; third word zero at+0x2568', arena_sha256=hashlib.sha256(result).hexdigest(),mmio_descriptors=descriptors,
                   mmio_leaves=leaves,mmio_virtual_base=hex(mmio_base),mapped_pages=len(arena)//PAGE+len(leaves),voltage_adt_sha256=hashlib.sha256(raw).hexdigest(),
                   voltage_input_sha256={k:hashlib.sha256(gpu[k]).hexdigest() for k in ['perf-states','perf-states-sram']},
                   voltage_assignment='Only qualified profile-A core/SRAM cluster columns populated; profile-B and frequency assignment unchanged',
                   qualification='Experimental structural graph; nine primary SGX pages, sixteen AFR pages and two exact platform pages writable; sparse coherent SGX-relative VAs; other bank hypotheses read-only. No complete hardware construction, write permissions, queue execution or rendering established.')
    return bytes(result),receipt
