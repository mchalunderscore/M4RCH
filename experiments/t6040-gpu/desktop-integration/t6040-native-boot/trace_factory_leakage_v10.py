#!/usr/bin/env python3
"""Pure source-pinned factory input decoder; never accesses physical memory."""
import argparse, hashlib, json, struct
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
DRIVER = Path('/boot/GPUC003/private-apple/com.apple.AGXG16X')
def source_read(raw, address, length):
    p = 32
    for _ in range(struct.unpack_from('<I',raw,16)[0]):
        cmd,n = struct.unpack_from('<II',raw,p)
        if cmd == 25:
            v,_,o,l = struct.unpack_from('<QQQQ',raw,p+24)
            if v <= address and address+length <= v+l:
                return raw[o+address-v:o+address-v+length]
        p += n
    raise ValueError(hex(address))
def decode(words):
    c10,c1c,c20,c24,c28 = words
    fbits = lambda value: struct.unpack('<I',struct.pack('<f',value))[0]
    return {'cluster_bits':[fbits((((c10>>s)&0x3fff)+1)*1.5) for s in [1,15]],
            'core_bits':[fbits(((((c20>>24)|(c24<<8))&0x3ff)+1)*3)]*2,
            'afr_bits':fbits(((c1c>>9)&0x1fff)+1),
            'auxiliary_bits':fbits((((c28>>4)&0xfff)+1)*1.5)}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--saved-words',type=Path,help='JSON five actual u32 inputs, never a hardware path')
    p.add_argument('--output',type=Path,default=ROOT/'docs/evidence/2026-10-11-native-factory-leakage-source-v10.json')
    args=p.parse_args(); raw=DRIVER.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
    assert digest=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
    table=list(struct.unpack('<40I',source_read(raw,0xfffffe0007130518,160)))
    assert table[:10]==[0,3088,1,16383,0,0,0,0,0,1069547520]
    assert table[10:20]==[0,3088,15,16383,0,0,0,0,0,1069547520]
    assert table[20:30]==[1,3088,29,7,0,3092,0,2047,3,1069547520]
    assert table[30:]==[0,3092,11,16383,0,0,0,0,0,0]
    spans=[(0x89e9844,0x89e9d78),(0x89caf20,0x89cb0f8),(0x89d67d4,0x89d67e0),(0x89a012c,0x89a0148),(0x89a0cc4,0x89a0cd0)]
    report={'schema':'m4rch.native-factory-leakage-source.v10','driver_sha256':digest,
      'hardware_actions':[], 'fuse_physical_base':'0x508374000','mapping_bytes':4096,
      'word_offsets':['0xc10','0xc1c','0xc20','0xc24','0xc28'],
      'gpu_clusters':2,'soc_die_count':1,'numeric_table_u32':table,
      'cluster_count_provenance':{'native_store':'readChipInfo89d67d4..dc writes coreconfig64=((d04010>>8)&ff)*((d04010>>16)&f)','saved_register':'0x11020a','calculated':2,'copy':'coreconfig60 vector toacc4e0 at89a0cc4..cc8; coreconfig64 becomesacc4e4'},
      'die_count_provenance':{'initializer':'coreconfig temporarysp10; native89a0140..144 stores1 atsp7c=coreconfig6c','preservation':'G16 readChipInfo does not store coreconfig6c','copy':'same vector coreconfig6c becomesacc4ec'},
      'positive_outputs':{'cluster':'power642c,6430','core':'power64ac,64b0','afr':'power64fc','auxiliary':'power6504'},
      'fresh_zero_outputs':['power646c..64ac (no provider writes)','power64ec..64fc (native zero per die)','unused cluster/core/die slots'],
      'failure_fallback':'Native memory descriptor or mapping failure returns without writing, leaving fresh zeros. Successful mapping does not produce zero leakage.',
      'remaining_policy':['20W Linux maximum replaces separate Apple maximum provider','absent optional AON dictionary branch remains explicitly selected'],
      'source_spans':[{'start':hex(0xfffffe0000000000+s),'end':hex(0xfffffe0000000000+e),'sha256':hashlib.sha256(source_read(raw,0xfffffe0000000000+s,e-s)).hexdigest()} for s,e in spans],
      'decoder_boundary_checks':{'all_zero_words':decode([0]*5),'all_ones_words':decode([0xffffffff]*5)},
      'qualification':'Static source and pure arithmetic decoder only. No captured actual fuse values and no device execution.'}
    if args.saved_words:
        words=json.loads(args.saved_words.read_text())
        if len(words)!=5 or any(type(v)!=int or not 0<=v<=0xffffffff for v in words):raise ValueError('five u32 inputs required')
        report['saved_input_sha256']=hashlib.sha256(args.saved_words.read_bytes()).hexdigest();report['decoded_actual']=decode(words)
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(args.output)
if __name__=='__main__':main()
