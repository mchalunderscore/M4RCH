#!/usr/bin/env python3
"""Inspect a captured firmware TEXT image offline; never execute firmware."""
import argparse,hashlib,json,struct
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('text',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();data=a.text.read_bytes()
def word(offset):return struct.unpack_from('<I',data,offset)[0]
matches=[]
for offset in range(0,len(data)-20,4):
    op=word(offset)
    if op&0xff800000!=0xd2800000:continue
    reg=op&31;value=((op>>5)&0xffff)<<(((op>>21)&3)*16)
    for n in range(1,5):
        op=word(offset+n*4)
        if op&0xff800000!=0xf2800000 or op&31!=reg:break
        shift=((op>>21)&3)*16;value=(value&~(0xffff<<shift))|(((op>>5)&0xffff)<<shift)
        if value==0x0c8aa322039604c0:
            matches.append({'offset':hex(offset),'register':reg,'identifier':hex(value),'instructions':[hex(word(offset+k*4)) for k in range(n+1)]})
report={'text_sha256':hashlib.sha256(data).hexdigest(),'g16s_identifier_sequences':matches,'qualification':'Static instruction evidence only; does not establish successful firmware initialization.'}
if report['text_sha256']=='f09648aa1dee7d1d1783649bc8d8321d31e5f2fb84240b588b45381932e93600':
    expected={0x2f250:0xf9400109,0x2f264:0xeb0a013f,0x2f268:0x54003d61,0x2f2a4:0xf940610a,
              0x2f2f8:0xf9026293,0x3734:0xf9426108,0x3738:0x9111c508,0x373c:0xf9400108,
              0x537c:0xf9426394,0x5380:0x91095289,0x5384:0xf9400d36,
              0x2f300:0xf903a52a,0x3888:0xd0000c9b,0x388c:0xf943a768,
              0x3890:0x91394508,0x3894:0xb940011c,
              0xfcec:0xf0000be8,0xfcf0:0xf9426108,0xfcf4:0xf9400108,
              0xfcf8:0xf9535d09,0xfd04:0xf947012b,
              0x14d20:0xf9426288,0x14d24:0xf9400108,0x14d28:0xf9535d08,
              0x14d48:0xf9471108}
    assert all(word(k)==v for k,v in expected.items())
    report['qualified_sample_findings']={
        'root_interface':'Root first u64 loaded at 2f250; compared with reconstructed G16S identifier at 2f264; mismatch branches at 2f268.',
        'root_copy_extent':'Root copied through final u64 at +c0 (2f2a4), consistent with c8 bytes.',
        'main_pointer_provenance':'Copied root+18 supplies x19; stored at firmware global 18e4c0 (2f2f8).',
        'main_power_pointer':'3734 loads that main pointer;3738 adds471;373c dereferences u64.',
        'main_shared_object_block':'537c loads main pointer;5380 adds254;5384 dereferences block+18 (main26c).',
        'hardware_nested_object':'fcec/fcf0 load main from global18e4c0;fcf4 dereferences main+0 (hardware data);fcf8 dereferences hardware+26b8. fd04 reads nested+e00 as u64. Independent chain14d20/24/28 reaches the same object;14d48 reads indexed nested+e20. This corroborates the pointer and counter-like use, not full e40 extent or all semantics.',
        'region_c_packed_word':'2f2c8 supplies root+20 as x10;2f300 stores it at global195748.3888/388c load that global;3890 adds e51;3894 reads a 32-bit word. This confirms parent, offset and width, not host-write protocol.',
        'unknown_main_240':'Unresolved. Matches15aa0/15b80/382c4/38380 refer to global146240 rather than the main object; they are not evidence for its extra field.'}
    report['instruction_checks']={hex(k):hex(v) for k,v in expected.items()}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
