#!/usr/bin/env python3
"""Reproduce numeric MainConfig and scheduler owner bindings, read-only."""
import hashlib,json,struct
from pathlib import Path
root=Path(__file__).resolve().parents[4]
src=Path('/boot/GPUC003/private-apple/com.apple.AGXG16X')
r=src.read_bytes();sha=lambda x:hashlib.sha256(x).hexdigest()
assert sha(r)=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments=[];p=32
for _ in range(struct.unpack_from('<I',r,16)[0]):
    cmd,n=struct.unpack_from('<II',r,p)
    if cmd==25:segments.append(struct.unpack_from('<QQQQ',r,p+24))
    p+=n
def read(a,n):
    for v,_,o,l in segments:
        if v<=a and a+n<=v+l:return r[o+a-v:o+a-v+n]
    raise ValueError(hex(a))
ap=0xfffffe0007eae398
provider=0xfffffe0007004000+(struct.unpack('<Q',read(ap+0x10d0,8))[0]&0xffffffff)
assert provider==0xfffffe00089d7060
assert read(provider+4,4)==bytes.fromhex('80008052')
ranges=[(0x8967348,0x8967350),(0x8967758,0x896777c),(0x8967970,0x89679d4),
        (0x8972714,0x8972724),(0x89aa434,0x89aa44c),
        (0x89cd2dc,0x89cd41c),(0x89cd4bc,0x89cd50c),(0x8987718,0x8987744),
        (0x89d9c08,0x89d9c14)]
report={'schema':'m4rch.native-main-defaults.v10','hardware_actions':[],
        'driver_sha256':sha(r),'vtable_address_point':hex(ap),
        'default_usc_tgmem_provider':hex(provider),'main_300_default':4,
        'main_304':'accelerator ed94 active-GTP override absent, fresh typed zero',
        'main_479_489':'accelerator ecf0 explicitly zeroed at89679d0',
        'main_3e0':255,'main_3e1_471':'unconditional native clear144bytes',
        'main_2d8_2f8':'optional f928/f930 services absent; fresh zero service pointers',
        'hardware_scheduler':{'2614':'same owned initial timestamp as every KSM queue/event converter',
                              '261c':'same owned capacity as every KSM queue/event converter',
                              'linux_capacity':256,'apple_seed_numeric_origin':'not claimed'},
        'notifier':{'record_limit':'f528 override or718, clamped bynonzero f530',
                    'default_limit':80,'command_buffer_rotating_slots':36,
                    'linux_record_policy':'fresh retained0x100 record per Work'},
        'bounded_first_triangle_admission':{
            'identified_source_gaps_closed_by':['wire_native_scheduler_policy_v10.py',
                                                'wire_native_main_defaults_v10.py'],
            'recommended_gate':'existing explicit native_t6040_experiment plus fallible owned providers and extents, POWER_COMPLETE and no-growth restrictions',
            'historical_gate':'BUNDLE_COMPLETE=false predates composed ownership and would reject before construction',
            'broad_completeness_booleans':'leave false; they describe broader native completeness',
            'excluded_source_branches':['f928/f930 optional service providers','active-GTP override',
                                       'growth recovery allocators6/7','Apple debug initial-seed policy'],
            'hardware_validation_remaining':['firmware admission','scheduler fetch/execution',
                                             'completion retirement','nonzero triangle pixels']},
        'ranges':[{'start':hex(0xfffffe0000000000+s),'end':hex(0xfffffe0000000000+e),
                   'sha256':sha(read(0xfffffe0000000000+s,e-s))}for s,e in ranges],
        'limitations':['Source owner propagation, not hardware execution proof',
                       'Optional service and active-GTP overrides deliberately absent',
                       'Full native bundle completeness remains a separate historical claim']}
out=root/'docs/evidence/2026-10-11-native-main-defaults-v10.json'
out.write_text(json.dumps(report,indent=2)+'\n');print(out)
