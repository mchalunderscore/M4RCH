#!/usr/bin/env python3
"""Private-derived SPM register sequence; field provenance, not draw semantics."""
import struct
from private_rce_entry import encode_entry
MASK64=(1<<64)-1

def spm_entries(accelerator, command, descriptor, phase, enabled, mapped_address=0):
    if phase not in range(4):raise ValueError('phase must be 0..3')
    q=lambda off:struct.unpack_from('<Q',descriptor,off)[0]
    d=lambda off:struct.unpack_from('<I',descriptor,off)[0]
    cq=lambda off:struct.unpack_from('<Q',command,off)[0]
    entries=[]
    def add(reg,flag,value):entries.append((reg,flag,value&MASK64))
    if enabled and phase!=1:
        add(0x14048,0,d(0xb60)|((struct.unpack_from('<Q',accelerator,0x6d0)[0]>>31)&0x200))
        add(0x14080,0,((mapped_address+d(0xb98))&0x7ffffffffc0)|1)
    if descriptor[0x897]&1:
        add(0x16020,0,0);add(0x160a8,0,0x20);add(0x16068,0,0x40000)
        return entries
    if phase!=3:
        add(0x15378,1,q(0x780));add(0x15380,1,q(0x788))
    short=phase<=1
    if short:
        control=0x10000 if q(0x678) or q(0x688) or descriptor[0x88e]&1 else 0
    else:
        add(0x15368,1,q(0x638));add(0x15370,1,q(0x640))
        control=(descriptor[0x88f]&1)<<16 if phase==3 else 0
    add(0x10038,1,(cq(0x1f58)&~0x10000)|control)
    if phase==3:
        if q(0x4e0):add(0x16060,0,q(0x4e0))
    else:
        add(0x15358,1,cq(0x1f60)|0x20)
        for reg,off in [(0x15330,0x678),(0x153c8,0x6f8),(0x15340,0x690),(0x153d8,0x720),(0x15420,0x6c8),(0x15430,0x700),(0x15428,0x6d8),(0x15438,0x728),(0x15220,0x6a8),(0x15228,0x6c0)]:add(reg,1,q(off))
    if not short:add(0x15308,1,d(0x7ac)|0x200)
    flags=q(0x648)
    if phase!=3:
        if q(0x678):flags|=0x80000
        if q(0x690):flags|=0x40000
        flags&=0xf0fffffffffffebf
        if q(0x6f8):flags|=0x40
        if q(0x720):flags|=0x100
    if not short:
        for reg,off in [(0x15328,0x678),(0x153c0,0x6f8),(0x15338,0x690),(0x153d0,0x720)]:add(reg,1,q(off))
        if q(0x668):flags|=0x8000
        if q(0x680):flags|=0x4000
    add(0x15318,1,flags)
    add(0x15348,1,q(0x650) if short else q(0x650)&~0x4040)
    return entries

def append_spm(backing,entries):
    out=bytearray(backing)
    for reg,flag,value in entries:
        count,cursor=struct.unpack_from('<HH',out,0x708)
        if cursor+12>0x708:raise ValueError('fixture cursor would overlap metadata')
        out[cursor:cursor+12]=encode_entry(out[cursor:cursor+12],reg,flag,value)
        struct.pack_into('<HH',out,0x708,(count+1)&0xffff,(cursor+12)&0xffff)
    return bytes(out)
