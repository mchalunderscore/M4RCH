#!/usr/bin/env python3
"""Audit captured firmware register slots and ADT containment; no MMIO access."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import adt
from firmware_text_contract import qualify

TABLE = 0x87108
TABLE_BYTES = 0x2e0
TABLE_SHA = '1cd874115d385cab17f2eba6ae57d8f7692b8f93c527178ea5000f6c5851844a'
CHECKS = {0x32ec0:0xd2800008,0x32ec4:0x90000ae9,0x32ec8:0xf9426129,
          0x32ecc:0xf940012a,0x32ed0:0x9119014a,0x32ed4:0xb00002ab,
          0x32ed8:0x9104216b,0x32edc:0x5280050c,0x32ee0:0x90000aed,
          0x32ee4:0x9139e1ad,0x32ee8:0x14000004,0x32eec:0x91004108,
          0x32ef0:0xf10b811f,0x32ef4:0x54000280,0x32ef8:0xb868696e,
          0x32efc:0x9bac7dcf,0x32f00:0xf86f694f,0x32f04:0xb4ffff4f,
          0x32f08:0xf940012f,0x32f0c:0x8b0e09ce,0x32f10:0xd37df1ce,
          0x32f14:0x8b0e01ef,0x32f18:0x8b0e01ae,0x32f1c:0x9116a1d0,
          0x32f20:0xfd4329e0,0x32f28:0xb94661f1,0x32f30:0xf9432df1,
          0x32f38:0x3dc191e0,0x32f40:0x17ffffeb}


def translate(base,size,ranges):
    matches = [parent+base-child for child,parent,span in ranges
               if child<=base and size<=span and base-child<=span-size]
    if len(matches)!=1:
        raise ValueError('Missing or ambiguous complete bus window')
    return matches[0]


def audit(text,data,raw_adt):
    text_contract = qualify(text)
    if len(data)!=0x138000:
        raise ValueError('Wrong DATA capture extent')
    for pc, expected in CHECKS.items():
        if struct.unpack_from('<I',text,pc)[0]!=expected:
            raise ValueError(f'Instruction mismatch at{pc:x}')
    table = data[TABLE-0x60000:TABLE-0x60000+TABLE_BYTES]
    if hashlib.sha256(table).hexdigest()!=TABLE_SHA:
        raise ValueError('Static register table differs from qualified captures')
    slots = []
    for slot,reserved,name_address,raw_flags in struct.iter_unpack('<4I',table):
        if reserved or not 0<=name_address<len(text):
            raise ValueError('Invalid slot row')
        end = text.find(b'\0',name_address,min(len(text),name_address+256))
        if end<0:
            raise ValueError('Unbounded slot name')
        name = text[name_address:end].decode('ascii')
        slots.append(dict(slot=slot,name=name,name_text_offset=hex(name_address),
                          raw_table_word_3=hex(raw_flags),
                          hardware_record_offset=hex(0x640+slot*0x28),
                          firmware_cached_record=hex(0x18ee78+0x5a8+slot*0x28)))
    if len(slots)!=46 or len({s['slot'] for s in slots})!=46:
        raise ValueError('Duplicate/missing slot records')
    tree = adt.parse(raw_adt)
    gpu = tree['/device-tree/arm-io/sgx']
    mcc = tree['/device-tree/arm-io/mcc']
    ranges = list(struct.iter_unpack('<QQQ',tree['/device-tree/arm-io']['ranges']))
    pairs = list(struct.iter_unpack('<QQ',mcc['reg']))
    first = int.from_bytes(mcc['amcc-reg-idx'],'little')
    count = int.from_bytes(mcc['amcc-count'],'little')
    mask = int.from_bytes(gpu['active-mcc-bit-vector'],'little')
    if not count or first+count>len(pairs) or not mask or mask>>count:
        raise ValueError('MCC metadata inconsistent')
    candidates = []
    for bit in range(count):
        if not mask&(1<<bit):
            continue
        base,size = pairs[first+bit]
        physical = translate(base,size,ranges)
        # This offset/extent comes from the donor; containment is checked,
        # firmware register semantics are deliberately NOT inferred from it.
        offset,span = 0x1c4000,0x18000
        if offset+span>size:
            raise ValueError('Donor MCC subrange exceeds selected ADT window')
        candidates.append(dict(active_bit=bit,adt_reg_index=first+bit,
                               parent_physical=hex(physical),parent_bytes=hex(size),
                               candidate_physical=hex(physical+offset),candidate_bytes=hex(span),
                               role_qualified=False))
    irq = gpu['meta-sw-interrupt']
    if len(irq)!=20:
        raise ValueError('Unexpected interrupt metadata geometry')
    return dict(text_contract=text_contract,data_sha256=hashlib.sha256(data).hexdigest(),
                adt_sha256=hashlib.sha256(raw_adt).hexdigest(),register_table_sha256=TABLE_SHA,
                instruction_checks={hex(k):hex(v) for k,v in CHECKS.items()},
                hardware_record_base=hex(0x640),hardware_record_stride=hex(0x28),
                copied_record_bytes=0x24,zero_physical_skips_record=True,
                fields=dict(offset_0='u64 gate/copy; donor calls physical address',
                            offset_8='u64 copied; donor calls firmware virtual address',
                            offset_10='u64 copied; donor packs size/stride here',
                            offset_18='u64 copied; donor calls relative offset',
                            offset_20='u32 copied; flags semantics unqualified'),
                slots=slots,active_mcc_mask=hex(mask),mcc_candidates=candidates,
                meta_sw_interrupt=dict(addresses=[hex(v) for v in struct.unpack_from('<QQ',irq)],
                                       raw_word=hex(struct.unpack_from('<I',irq,16)[0]),
                                       semantics_qualified=False),
                qualification='Static firmware descriptor-copy geometry and slot names qualified; table unchanged across two captures. Candidate MCC subranges are derived from ADT parent windows plus donor offsets. Containment alone does not authorize register accesses or prove correct T6040 register roles. No hardware reads/writes, mappings or publication performed.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    r = audit((a.capture/'text.bin').read_bytes(),(a.capture/'data-before.bin').read_bytes(),(a.capture/'boot.adt').read_bytes())
    a.output.write_text(json.dumps(r,indent=2)+'\n')
    print(f'{len(r["slots"])} firmware-named slots; descriptor base640/stride28 confirmed; {len(r["mcc_candidates"])} MCC subranges contained, roles unqualified')


if __name__=='__main__':
    main()
