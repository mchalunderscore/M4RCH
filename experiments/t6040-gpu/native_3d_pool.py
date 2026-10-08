"""Native ordinary3D pool arithmetic, not Linux allocation/mapping services."""
MASK64=(1<<64)-1
STRIDE=0x2240

def reserve(occupancy,cursor,cpu_base,device_base,firmware_base,stride=STRIDE):
    if not 0<=cursor<=0xffffffff or not 0<=stride<=0xffffffff:
        raise ValueError('Native cursor/stride areu32')
    slots=bytearray(occupancy);capacity=len(slots)
    for n in range(capacity):
        index=((cursor+n)&0xffffffff)%capacity
        if slots[index]==0:
            offset=(index*stride)&0xffffffff
            slots[index]=1
            return dict(index=index,offset=offset,cpu=(cpu_base+offset)&MASK64,
                        device=(device_base+offset)&MASK64,firmware=(firmware_base+offset)&MASK64,
                        cursor=(index+1)%capacity,occupancy=bytes(slots))
    return None
