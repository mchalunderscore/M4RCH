"""Checked ARM firmware mapping descriptor/ring arithmetic (16KiB profile)."""
import struct

def descriptor(va,physical,writable,classification_gate=False):
    if any(x<0 or x>=1<<64 for x in (va,physical)):raise ValueError('uint64 required')
    classification=3 if 0xfffffc20c0000000<=va<0xfffffc2180000000 and not classification_gate else 1
    flags=classification|(4 if writable else 0)
    # Actual host callback truncates PPN to u32; live callers must check range.
    return struct.pack('<QIIHHI',va,(physical>>12)&0xffffffff,0,1,flags,0)

def ring_transition(head,tail):
    if not 0<=tail<256:raise ValueError('Native tail guard')
    if not 0<=head<256:raise ValueError('Native head guard')
    return dict(slot=tail,next_tail=(tail+1)&255,
                flush=((tail-head)&0xc0)==0xc0,
                wait=((tail+1)&255)==head)
