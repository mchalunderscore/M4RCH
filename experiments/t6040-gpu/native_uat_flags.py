"""Checked native UAT PTE bit encoding; API option translation unqualified."""
DPRR=(0,0,0,0,4,1,0,0,5,0,2,0,6,7,0,3)
def encode(aperture,flags):
    if aperture not in (0,1):raise ValueError('Native aperture guard')
    if flags<0 or flags>0xffffffff or flags&~0x30f:raise ValueError('Native flag mask guard')
    if flags&12==12:raise ValueError('Native memory attribute guard')
    lookup=DPRR[((flags&3)<<2)|(flags>>8)]
    memattr=4 if flags&4 else flags&8
    low=(((lookup<<4)&0xc0)|(aperture<<11))^0xc02
    return low|((lookup&1)<<53)|(((lookup>>1)&1)<<54)|memattr|(1<<55)|1


def legacy_g16(flags):
    """Actual legacy G16 Gart encoder; only inputbit0 contributes."""
    return 0x00a0000000000c03 | (((2-(flags&1))>>1)<<54)
