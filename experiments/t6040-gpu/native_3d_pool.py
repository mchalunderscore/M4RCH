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


def backing_contract(requested,page_shift,resource_flags):
    """Checked createBacking size and service arguments; no physical allocation."""
    if isinstance(requested,bool) or not isinstance(requested,int) or not 1<=requested<=256:
        raise ValueError('Qualified positive pool request counts1..256')
    if isinstance(page_shift,bool) or page_shift not in (12,14,16):
        raise ValueError('Qualified page shifts12/14/16')
    if isinstance(resource_flags,bool) or not isinstance(resource_flags,int) or not 0<=resource_flags<=0xffffffff:
        raise ValueError('Resource flags requireu32')
    alignment=1<<page_shift
    size=(requested*STRIDE+alignment-1)&-alignment
    return dict(stride=STRIDE,requested=requested,page_shift=page_shift,allocation_bytes=size,
                capacity=size//STRIDE,resource_init_flags=resource_flags|0x23,
                device_map_flags=0x600000085,firmware_map_flags=0x20900000084,
                submission_ready=False)
