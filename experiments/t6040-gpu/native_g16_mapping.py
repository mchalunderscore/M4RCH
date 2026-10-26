"""Qualified legacy G16 Gart geometry/arithmetic, not a hardware mapping API."""
from native_uat_flags import legacy_g16
PA_MASK=0x3ffffffc000
GEOMETRY=((36,64,0x3f000000000),(25,2048,0xffe000000),(14,2048,0x1ffc000))
MIRROR_RANGES=((0xfffffc2000000000,0xfffffc2180000000),(0xfffffc2181400000,0xfffffc2185400000))
def leaf_update(va,pa,flags,previous,check_same,counter):
    if any(x<0 or x>=1<<64 for x in (va,pa,previous)):raise ValueError('uint64 required')
    pte=(pa&PA_MASK)|legacy_g16(flags)
    changed=not(check_same and previous==pte)
    return dict(indices=tuple((va&mask)>>shift for shift,_,mask in GEOMETRY),pte=pte,
                counter=(counter+int(changed))&0xffffffff,changed=changed,
                mirror=changed and any(lo<=va<hi for lo,hi in MIRROR_RANGES))
def context_root(pa,asid):
    if not 0<=pa<1<<64 or not 0<=asid<128:raise ValueError('Audited context domain')
    return ((pa&~0x3fff)|(asid<<48)|1,0)
