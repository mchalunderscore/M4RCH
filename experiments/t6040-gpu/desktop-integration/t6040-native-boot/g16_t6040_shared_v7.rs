// SPDX-License-Identifier: GPL-2.0-only
//! Matched 25G83 native shared ownership. All channel cursors live in allocated
//! RAM. Native callbacks supply GPU VAs; the caller owns Linux PTE policy,
//! publication, cache maintenance, synchronization and lifetime.

use crate::g16_t6040_bundle as bundle;

pub(crate) const SUPPORT_LOGICAL_BYTES: usize = 0xc3188;
pub(crate) const SUPPORT_BACKING_BYTES: usize = 0xc4000;
pub(crate) const ROOT_BYTES: usize = 0xc8;
pub(crate) const REGION_A_BACKING_BYTES: usize = 0x4000;
pub(crate) const AON_PTD_LOGICAL_BYTES: usize = 0xe4;
pub(crate) const AON_PTD_BACKING_BYTES: usize = 0x4000;
pub(crate) const ROOT_INTERFACE: u64 = 0x0c8a_a322_0396_04c0;
pub(crate) const SHARED_COMPLETE: bool = false;

/// Separate range9 allocation: outer FWc20/c28; only child CPUFWc38,
/// mappedFWc30 at offset0. Native ARM stores its GPU VA at power+6318.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct AonPtdLayout { base:u64 }
impl AonPtdLayout {
    pub(crate) fn new(base:u64)->Option<Self> {
        if base & 0x3fff != 0 || base.checked_add(AON_PTD_BACKING_BYTES as u64).is_none() { return None; }
        Some(Self { base })
    }
    pub(crate) fn base(&self)->u64 { self.base }
    pub(crate) fn gpu_address(&self)->u64 { self.base }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct SupportChild {
    pub cpu_owner: u32,
    pub mapping_owner: u32,
    pub offset: usize,
    pub bytes: usize,
}

/// Executed native descriptor producer 89ab988..bd8 and alignment 89a7c70..cf4.
pub(crate) const SUPPORT_CHILDREN: [SupportChild; 27] = [
    SupportChild { cpu_owner:0x430,mapping_owner:0x438,offset:0,bytes:0x30 },
    SupportChild { cpu_owner:0x408,mapping_owner:0x410,offset:0x40,bytes:0x30 },
    SupportChild { cpu_owner:0x3e0,mapping_owner:0x3e8,offset:0x80,bytes:0x30 },
    SupportChild { cpu_owner:0x3b8,mapping_owner:0x3c0,offset:0xc0,bytes:0x30 },
    SupportChild { cpu_owner:0x4d0,mapping_owner:0x4d8,offset:0x100,bytes:0x30 },
    SupportChild { cpu_owner:0x4a8,mapping_owner:0x4b0,offset:0x140,bytes:0x30 },
    SupportChild { cpu_owner:0x480,mapping_owner:0x488,offset:0x180,bytes:0x30 },
    SupportChild { cpu_owner:0x458,mapping_owner:0x460,offset:0x1c0,bytes:0x30 },
    SupportChild { cpu_owner:0x570,mapping_owner:0x578,offset:0x200,bytes:0x30 },
    SupportChild { cpu_owner:0x548,mapping_owner:0x550,offset:0x240,bytes:0x30 },
    SupportChild { cpu_owner:0x520,mapping_owner:0x528,offset:0x280,bytes:0x30 },
    SupportChild { cpu_owner:0x4f8,mapping_owner:0x500,offset:0x2c0,bytes:0x30 },
    SupportChild { cpu_owner:0x8a0,mapping_owner:0x8a8,offset:0x300,bytes:0x30 },
    SupportChild { cpu_owner:0x960,mapping_owner:0x970,offset:0x340,bytes:0xe440 },
    SupportChild { cpu_owner:0x968,mapping_owner:0x978,offset:0xe780,bytes:0x6a8 },
    SupportChild { cpu_owner:0x888,mapping_owner:0x890,offset:0xee40,bytes:0x20 },
    SupportChild { cpu_owner:0x8c0,mapping_owner:0x900,offset:0xee80,bytes:0x30 },
    SupportChild { cpu_owner:0x8c8,mapping_owner:0x908,offset:0xeec0,bytes:0x1b0 },
    SupportChild { cpu_owner:0x8d0,mapping_owner:0x910,offset:0xf080,bytes:0x30 },
    SupportChild { cpu_owner:0x8d8,mapping_owner:0x918,offset:0xf0c0,bytes:0x30 },
    SupportChild { cpu_owner:0x8e0,mapping_owner:0x920,offset:0xf100,bytes:0x4800 },
    SupportChild { cpu_owner:0x8e8,mapping_owner:0x928,offset:0x13900,bytes:0x28800 },
    SupportChild { cpu_owner:0x870,mapping_owner:0x880,offset:0x3c100,bytes:0x79800 },
    SupportChild { cpu_owner:0x8f0,mapping_owner:0x930,offset:0xb5900,bytes:0x9000 },
    SupportChild { cpu_owner:0x8f8,mapping_owner:0x938,offset:0xbe900,bytes:0x4800 },
    SupportChild { cpu_owner:0x390,mapping_owner:0x398,offset:0xc3100,bytes:0x60 },
    SupportChild { cpu_owner:0x3a0,mapping_owner:0x3a8,offset:0xc3180,bytes:8 },
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct SupportLayout { base: u64 }

impl SupportLayout {
    pub(crate) fn new(base:u64) -> Option<Self> {
        if base & 0x3fff != 0 || base.checked_add(SUPPORT_BACKING_BYTES as u64).is_none() {
            return None;
        }
        Some(Self { base })
    }
    pub(crate) fn base(&self) -> u64 { self.base }
    pub(crate) fn address_for_mapping(&self, owner:u32) -> Option<u64> {
        let child = SUPPORT_CHILDREN.iter().find(|c| c.mapping_owner == owner)?;
        self.base.checked_add(child.offset as u64)
    }
    /// Native writes preserve every other byte; backing starts zero at allocation.
    /// FW94c is a dynamic native power-state value, supplied explicitly by policy.
    pub(crate) fn write_component(&self, out:&mut[u8], initial_status:u32) -> Option<()> {
        if out.len() < SUPPORT_BACKING_BYTES { return None; }
        put32(out, 0xee40, initial_status);
        put32(out, 0xee44, 1);
        put32(out, 0x340, 0);
        put32(out, 0x348, 0);
        put32(out, 0x340 + 0xe434, 1);
        put64(out, 0xe780 + 0x624, 0);
        Some(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct ChannelTopology {
    /// Work/control: read, prefetch, producer. RX records are composite pointer
    /// records: use rx() for receive cursors, never treat all four as one ring.
    pub state:[u64;3],
    pub ring:u64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum RxKind { Event, Trace, Auxiliary }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct RxTopology {
    pub state:u64,
    pub ring:u64,
    pub record_bytes:usize,
    pub capacity:u32,
}

impl RxTopology {
    pub(crate) fn consumer(&self) -> u64 { self.state }
    pub(crate) fn producer(&self) -> u64 { self.state + 0x20 }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct RootPointers {
    pub region_a:u64, pub main_config:u64, pub region_c:u64,
    pub status_a:u64, pub status_b:u64, pub extra_0:u64, pub extra_1:u64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct NotificationPointers { pub state:u64, pub entries:u64 }

impl NotificationPointers {
    /// Composes the saved native 89d0eb4..89d0f5c publication proof. Pointers
    /// belong to separate owned resources FW16c0/16d0 and FW16c8/16d8.
    pub(crate) fn write_status_b(&self,out:&mut[u8])->Option<()> {
        if out.len()<0xe440 { return None; }
        put64(out,0x48e0,self.state); put64(out,0x48e8,self.entries);
        put64(out,0x48f0,0); put32(out,0x4900,0); put32(out,0x4910,0);
        Some(())
    }
    pub(crate) fn write_state(&self,out:&mut[u8])->Option<()> {
        if out.len()<0x14 { return None; }
        put32(out,0,0); put32(out,0x10,0);
        Some(())
    }
}

impl RootPointers {
    /// The 104-byte UAT payload is copied by native 89cdac4..af0 from the owned
    /// translator at accelerator+18d08, object+18. This API requires that exact
    /// input instead of reconstructing donor geometry inside the serializer.
    pub(crate) fn encode(&self, uat_payload:&[u8;104]) -> [u8;ROOT_BYTES] {
        let mut out = [0;ROOT_BYTES];
        put64(&mut out, 0, ROOT_INTERFACE);
        for (off, value) in [(8,self.region_a),(0x18,self.main_config),(0x20,self.region_c),
                            (0xa8,self.status_a),(0xb0,self.status_b),
                            (0xb8,self.extra_0),(0xc0,self.extra_1)] { put64(&mut out,off,value); }
        put64(&mut out,0x28,0x1_0000_0000);
        out[0x30..0x98].copy_from_slice(uat_payload);
        out
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct NativeTopology {
    pub bundle:bundle::BundleLayout,
    pub support:SupportLayout,
    pub root:u64,
    pub region_a:u64,
    pub region_c:u64,
}

impl NativeTopology {
    /// Firmware VA placement is allocator policy. Validate the owned extents;
    /// Root/A/Region C each have one selected 16 KiB ASC backing page.
    pub(crate) fn new(bundle_base:u64,support_base:u64,root:u64,region_a:u64,region_c:u64)
        -> Option<Self> {
        let bundle = bundle::BundleLayout::new(bundle_base)?;
        let support = SupportLayout::new(support_base)?;
        let extents = [(bundle_base,bundle::BACKING_BYTES),(support_base,SUPPORT_BACKING_BYTES),
                       (root,0x4000),(region_a,REGION_A_BACKING_BYTES),(region_c,0x4000)];
        for (i,&(base,size)) in extents.iter().enumerate() {
            if base & 0x3fff != 0 { return None; }
            let end = base.checked_add(size as u64)?;
            for &(other,other_size) in &extents[..i] {
                if base < other.checked_add(other_size as u64)? && other < end { return None; }
            }
        }
        Some(Self { bundle,support,root,region_a,region_c })
    }
    pub(crate) fn root_pointers(&self) -> RootPointers {
        RootPointers { region_a:self.region_a,main_config:self.bundle.main_gpu_address(),
            region_c:self.region_c,status_a:self.support.base+0xee40,
            status_b:self.support.base+0x340,extra_0:self.support.base+0xe780,
            extra_1:self.support.base+0xc3100 }
    }
    pub(crate) fn channels(&self) -> [ChannelTopology;17] {
        core::array::from_fn(|index| {
            if index < 12 {
                let priority = index / 3;
                let engine = index % 3;
                let state_owner = [0x3c0,0x460,0x500][engine] + (priority as u32)*0x28;
                let ring_owner = [0x3d0,0x470,0x510][engine] + (priority as u32)*0x28;
                let state = self.support.address_for_mapping(state_owner).unwrap();
                ChannelTopology { state:[state,state+0x10,state+0x20],
                    ring:self.bundle.address_for_mapping(ring_owner).unwrap() }
            } else {
                let s = self.support.base;
                match index {
                    12 => ChannelTopology { state:[s+0x300,s+0x310,s+0x320],
                        ring:self.bundle.base()+0x1e5c0 },
                    13 => ChannelTopology { state:[s+0xee80,s+0xf100,s+0xeec0],ring:s+0x13900 },
                    14 => ChannelTopology { state:[s+0xf080,s+0xb5900,s+0xf0c0],ring:s+0xbe900 },
                    15 => ChannelTopology { state:[s+0x3c100,0,0],ring:0 },
                    _ => ChannelTopology { state:[0;3],ring:0 },
                }
            }
        })
    }
    pub(crate) fn rx(&self,kind:RxKind) -> RxTopology {
        let (state,ring,record_bytes,capacity) = match kind {
            RxKind::Event => (0xee80,0xf100,0x48,256),
            RxKind::Trace => (0xf080,0xb5900,0x48,512),
            RxKind::Auxiliary => (0xf0c0,0xbe900,0x48,256),
        };
        RxTopology { state:self.support.base+state,ring:self.support.base+ring,record_bytes,capacity }
    }
    pub(crate) fn write_bundle_component(&self,out:&mut[u8]) -> Option<()> {
        if out.len() < bundle::BACKING_BYTES { return None; }
        self.bundle.write_component(out)?;
        let main = &mut out[bundle::MAIN_OFFSET..bundle::MAIN_OFFSET+bundle::MAIN_BYTES];
        for (i,channel) in self.channels()[..15].iter().enumerate() {
            let off=0x20+i*0x20;
            for (j,value) in channel.state.iter().enumerate() { put64(main,off+j*8,*value); }
            put64(main,off+24,channel.ring);
        }
        put64(main,0x200,self.support.base+0x3c100);
        // Native shared-data initialization, not donor sentinels/header constants.
        for &i in &[1usize,2,3,5,6,8] {
            let child=bundle::CHILDREN[i];
            out[child.offset..child.offset+child.bytes].fill(0);
        }
        put32(out,bundle::CHILDREN[2].offset+0xa18,0xffff_ffff);
        put32(out,bundle::CHILDREN[2].offset+0xa30,0xffff_ffff);
        Some(())
    }
    pub(crate) fn write_support_component(&self,out:&mut[u8],initial_status:u32)->Option<()> {
        self.support.write_component(out,initial_status)
    }
    pub(crate) fn write_notifications(&self,out:&mut[u8],pointers:NotificationPointers)->Option<()> {
        if out.len()<SUPPORT_BACKING_BYTES { return None; }
        pointers.write_status_b(&mut out[0x340..0x340+0xe440])
    }
}

/// Selected G16X accelerator virtual+a88 is an executed no-op. Native boot
/// resets FW1710 then writes a 24-byte terminator with only its first20 cleared.
/// Keep trailing padding intact, as native prepareFirmwareForBoot does.
pub(crate) fn write_region_a_component(out:&mut[u8]) -> Option<usize> {
    if out.len() < REGION_A_BACKING_BYTES { return None; }
    out[..20].fill(0);
    Some(24)
}

fn put32(out:&mut[u8],off:usize,value:u32) { out[off..off+4].copy_from_slice(&value.to_le_bytes()); }
fn put64(out:&mut[u8],off:usize,value:u64) { out[off..off+8].copy_from_slice(&value.to_le_bytes()); }
