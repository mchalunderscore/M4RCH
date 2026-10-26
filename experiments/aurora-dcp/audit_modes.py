#!/usr/bin/env python3
"""Check the mode-call ABI in the exact private T604x firmware, without running it."""
import hashlib
import json
from pathlib import Path
import struct
from audit import image_uuid, OUTPUT

b=(OUTPUT/'private/t604xdcp.macho').read_bytes()
assert image_uuid(b)=='6CC9349E-D30B-33FB-B12B-8D6D38F9F1B3'
# A413 enters the A4xx secondary dispatcher. Index 3 in its A41x table
# resolves to a signed code pointer for the 8-byte-input/4-byte-output thunk.
branch=0x1bfa34+struct.unpack_from('<i',b,0x1000+0x1c008c+3*4)[0]
assert branch==0x1bfd80
checks={0x1bfd80:'300000b0',0x1bfd84:'10923791', # thunk 0x1c4de4
        0x1c4dfc:'7f200071', # cmp w3,8 input length
        0x1c4e34:'bf100071', # cmp w5,4 output length
        0x1c4e84:'41084029', # ldp w1,w2 request: color then timing
        0x1c4e94:'114a80d2', # vtable offset 0x250
        0x1c4eac:'800200b9', # write 32-bit response
        0x236464:'e103142a',0x236468:'e203132a'}
for addr,word in checks.items(): assert b[0x1000+addr:0x1000+addr+4].hex()==word,hex(addr)
assert struct.unpack_from('<Q',b,0x7057f8)[0]&0xffffffff==0x2363c8
result={'firmware_uuid':image_uuid(b),'firmware_sha256':hashlib.sha256(b).hexdigest(),
 'method':413,'input_bytes':8,'output_bytes':4,'request_order':['color_id','timing_id'],
 'dispatch_thunk':'0x1c4de4','implementation':'0x2363c8','vtable_slot':'0x250',
 'retained_panel_acceptance_verified':False,'native_mode_switch_tested':False,
 'known_risk':'Aurora H17P retained panels have rejected A413 with 0x8000000b; this candidate deliberately attempts the T604x path',
 'timestamp_support':'Existing retained swap encoding; ProMotion timestamp requirements remain unqualified'}
(OUTPUT/'modeset-abi-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
