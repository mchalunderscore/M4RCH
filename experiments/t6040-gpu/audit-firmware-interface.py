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
              0x537c:0xf9426394,0x5380:0x91095289,0x5384:0xf9400d36}
    assert all(word(k)==v for k,v in expected.items())
    report['qualified_sample_findings']={
        'root_interface':'Root first u64 loaded at 2f250; compared with reconstructed G16S identifier at 2f264; mismatch branches at 2f268.',
        'root_copy_extent':'Root copied through final u64 at +c0 (2f2a4), consistent with c8 bytes.',
        'main_pointer_provenance':'Copied root+18 supplies x19; stored at firmware global 18e4c0 (2f2f8).',
        'main_power_pointer':'3734 loads that main pointer;3738 adds471;373c dereferences u64.',
        'main_shared_object_block':'537c loads main pointer;5380 adds254;5384 dereferences block+18 (main26c).'}
    report['instruction_checks']={hex(k):hex(v) for k,v in expected.items()}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
