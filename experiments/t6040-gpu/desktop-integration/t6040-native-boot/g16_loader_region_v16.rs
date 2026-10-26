// SPDX-License-Identifier: GPL-2.0-only
//! Loader-owned G16 RAM spans, including descriptive live OF overlay nodes.
use kernel::{bindings,c_str,of,prelude::*};
use kernel::io::resource::Resource;

/// Physical loader reservation; does not allocate RAM or reserve new pages.
struct LoaderSpan { start:u64,size:u64 }
impl LoaderSpan {
    fn checked(start:u64,size:u64)->Result<Self> {
        let _end=start.checked_add(size).ok_or(EINVAL)?;
        if start==0||size<0x4000||(start|size)&0x3fff!=0 {return Err(EINVAL);}
        let bytes:usize=size.try_into()?;
        // SAFETY: Read-only resource-tree query; reject both intersecting and
        // mixed ranges, because live OF no-map cannot remove Linux-owned RAM.
        let intersection=unsafe {bindings::region_intersects(start,bytes,
            bindings::IORESOURCE_SYSTEM_RAM as _,bindings::IORES_DESC_NONE as _)};
        if intersection!=bindings::REGION_DISJOINT as i32 {return Err(EBUSY);}
        Ok(Self{start,size})
    }
    fn resource(self)->Resource {
        let raw=bindings::resource {start:self.start,end:self.start+self.size-1,
            flags:bindings::IORESOURCE_MEM as _,..Default::default()};
        // SAFETY: Resource is repr(transparent) over Opaque<bindings::resource>;
        // its documented invariant is a valid C resource. This is a checked
        // physical memory extent with an inclusive end and IORESOURCE_MEM.
        // Null name and tree links describe an unattached value, as returned by
        // the static reserved-memory API. No resource-tree ownership is claimed.
        // transmute enforces identical size at compile time; Opaque has the C
        // payload's alignment. Mem::try_new consumes it without tree insertion.
        unsafe {core::mem::transmute::<bindings::resource,Resource>(raw)}
    }
}
fn raw_u64(node:&of::Node,name:&CStr)->Result<u64> {
    let bytes:KVec<u8>=node.get_property(name)?;
    if bytes.len()!=8 {return Err(EINVAL);}
    Ok(u64::from_le_bytes(bytes.as_slice().try_into().map_err(|_|EINVAL)?))
}
pub(crate) fn resource(node:&of::Node,name:&CStr)->Result<Resource> {
    // Other generations retain their original static reserved-memory lookup,
    // even if their loader also publishes raw SGX aliases. Only T6040 is
    // admitted to this fixed five-region profile; its aliases are mandatory.
    let compatible:KVec<u8>=node.get_property(c_str!("compatible"))?;
    if !compatible.as_slice().split(|b|*b==0).any(|value|value==b"apple,agx-t6040") {
        return node.reserved_mem_region_to_resource_byname(name);
    }
    let (index,base_name,size_name)=match name.to_bytes() {
        b"ttbs"=>(0,c_str!("apple,sgx-gpu-region-base"),c_str!("apple,sgx-gpu-region-size")),
        b"pagetables"=>(1,c_str!("apple,sgx-gfx-shared-region-base"),c_str!("apple,sgx-gfx-shared-region-size")),
        b"l2"=>(2,c_str!("apple,sgx-gfx-shared-l2-region-base"),c_str!("apple,sgx-gfx-shared-l2-region-size")),
        b"handoff"=>(3,c_str!("apple,sgx-gfx-handoff-base"),c_str!("apple,sgx-gfx-handoff-size")),
        b"firmware"=>(4,c_str!("apple,sgx-gfx-data-base"),c_str!("apple,sgx-gfx-data-size")),
        _=>return Err(EINVAL),
    };
    let original=LoaderSpan::checked(raw_u64(node,base_name)?,raw_u64(node,size_name)?)?;
    let names:KVec<u8>=node.get_property(c_str!("memory-region-names"))?;
    if names.as_slice()!=b"ttbs\0pagetables\0l2\0handoff\0firmware\0" {return Err(EINVAL);}
    let region=node.parse_phandle(c_str!("memory-region"),index).ok_or(EINVAL)?;
    let no_map:KVec<u8>=region.get_property(c_str!("no-map"))?;
    if !no_map.is_empty() {return Err(EINVAL);}
    let reg:KVec<u8>=region.get_property(c_str!("reg"))?;
    if reg.len()!=16 {return Err(EINVAL);}
    let described=LoaderSpan::checked(
        u64::from_be_bytes(reg.as_slice()[0..8].try_into().map_err(|_|EINVAL)?),
        u64::from_be_bytes(reg.as_slice()[8..16].try_into().map_err(|_|EINVAL)?))?;
    if described.start!=original.start||described.size!=original.size {return Err(EINVAL);}
    if let Ok(static_resource)=node.reserved_mem_region_to_resource_byname(name) {
        if static_resource.start()!=original.start||static_resource.size()!=original.size {
            return Err(EINVAL);
        }
        return Ok(static_resource);
    }
    Ok(original.resource())
}
