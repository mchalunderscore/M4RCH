"""Native generic UAT leaf-update arithmetic; not a live GPU mapping API."""
from native_uat_flags import encode
PA_MASK=((1<<40)-1)&~((1<<14)-1)
def leaf_update(va,pa,flags):
    if not 0<=va<1<<64:raise ValueError('VA must be uint64')
    if pa<0 or pa&~PA_MASK:raise ValueError('Native physical address guard')
    aperture=(va>>42)&1
    return dict(aperture=aperture,metadata_offset=aperture*0x90,
                root_index=(va>>36)&63,middle_index=(va>>25)&2047,
                leaf_index=(va>>14)&2047,pte=pa|encode(aperture,flags))
