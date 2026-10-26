#!/usr/bin/env python3
"""Save numeric Apple PM defaults/provider closure; never access hardware."""
import struct,hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[4];src=Path('/boot/GPUC003/private-apple/com.apple.AGXG16X');r=src.read_bytes();sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(r)=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segs=[];pos=32
for _ in range(struct.unpack_from('<I',r,16)[0]):
 cmd,n=struct.unpack_from('<II',r,pos)
 if cmd==25:segs.append(struct.unpack_from('<QQQQ',r,pos+24))
 pos+=n
def read(a,n):
 for v,_,o,l in segs:
  if v<=a and a+n<=v+l:return r[o+a-v:o+a-v+n]
 raise ValueError(hex(a))
base=0xfffffe0007004000;ap=0xfffffe0007eae398
ptr=lambda off:base+(struct.unpack('<Q',read(ap+off,8))[0]&0xffffffff)
assert ptr(0xb90)==0xfffffe00089d8c2c and ptr(0x1078)==0xfffffe00089e80e4
constants=struct.unpack('<4Q',read(0xfffffe000712dd70,32));assert constants==(6144,8,8,16)
base_counts=struct.unpack('<4I',read(0xfffffe000712da50,16));assert base_counts==(36,36,0,0)
# Source scalar overrides and callback returns are exact pinned instructions.
assert read(0xfffffe00089d9c0c,8)==bytes.fromhex('090a8052691a07b9')
assert read(0xfffffe00089e80e8,4)==bytes.fromhex('00008052')
ranges=[(0x8967348,0x8967350),(0x89675f4,0x8967600),(0x8967648,0x896766c),(0x89678bc,0x89678c8),(0x89d9c0c,0x89d9c14),(0x89d8c2c,0x89d8c54),(0x89fc75c,0x89fc770),(0x89fd168,0x89fd180),(0x89fb880,0x89fb898),(0x89fd440,0x89fd450),(0x89fb83c,0x89fb848),(0x89ff10c,0x89ff168)]
report={'schema':'m4rch.native-pm-geometry-source.v9','driver_sha256':sha(r),'hardware_actions':[],
 'address_point':hex(ap),'provider_b90':hex(ptr(0xb90)),'provider_1078':hex(ptr(0x1078)),
 'device_config_u64':[4,4,*constants],'device_config_roles':['page_factor','registration_alignment','scene_divisor_units','scene_fixed_bytes','scene_bytes_per_unit','scene_alignment'],
 'device_config_destination':'PM1d8..207, not PM1d4',
 'scene_count':80,'state_count':36,'base_counts':list(base_counts),'group_shift':0,'group_allowance':False,'extra_scene_stride':False,
 'native_count_chain':'CFG14=ceil(initialPBbytes/20000),CFG18=ceil(maxPBbytes/20000);PM154/15c copy;HWstate80/7c multiply4',
 'support_extent_chain':'HWParamBufferManager20 is retained AGXResource. Resource allocation bytes=PM148capacity*DevicePMConfigpagefactor*4; reset resource78 low32→HWstate30. It is byte extent, not support lease count.',
 'linux_bindings':{'initial_blocks':11,'max_blocks':'tvb_max_blocks','capacity':'max_blocks+1 explicit free-slot Linux policy','registration_stride':4,'scene_stride_default_max2193':32,'hardware_support_extent':'actual mapped page-list allocation bytes','PM1d4':'explicit fresh Linux zero; no direct native setter established'},
 'ranges':[{'start':hex(0xfffffe0000000000+s),'end':hex(0xfffffe0000000000+e),'sha256':sha(read(0xfffffe0000000000+s,e-s))}for s,e in ranges],
 'qualification':'Static instruction/constant/vtable closure. Native allocator, property overrides and memory provider not replayed here. Linux requested-memory/free-slot policy remains explicit; no firmware execution or retirement proved.'}
out=root/'docs/evidence/2026-10-11-native-pm-geometry-source-v9.json';out.write_text(json.dumps(report,indent=2)+'\n');print(out)
