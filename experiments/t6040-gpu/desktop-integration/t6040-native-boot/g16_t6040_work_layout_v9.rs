// SPDX-License-Identifier: GPL-2.0-only
//! Native render storage inside Gravity's retained 0x1c000 Work lease.
//! An address plan does not own pages: caller maps each Page pair to the same
//! physical backing and retains the whole lease until final retirement.
pub const STRIDE:u64=0x1c000;
pub const PAGE_BYTES:u64=0x4000;
pub const RCE_BYTES:u64=0x3000;
pub const SKU_CAPACITY:usize=0x2000;
const FW_ORIGIN:u64=0xffff_fc22_0000_0000;
const DEVICE_ORIGIN:u64=0x72_0000_0000;
const DEVICE_END:u64=0x73_0000_0000;
#[derive(Clone,Copy,Debug,PartialEq)]
pub struct Page { pub firmware:u64, pub device:u64 }
#[derive(Clone,Copy,Debug,PartialEq)]
pub struct Stage {
    pub command:Page,
    pub ksm:Page,
    pub dependency_fw:u64,
    pub postkick_fw:u64,
    pub sku_fw:u64,
    pub shared_state_fw:u64,
    pub driver_stamp_fw:u64,
}
#[derive(Clone,Copy,Debug,PartialEq)]
pub struct Layout {pub base:u64,pub pages:[Page;2],pub stages:[Stage;2],pub bm_fw:u64}
impl Layout {
    /// Native commands remain in two separate 16KiB pages. RCE's entire
    /// 0x3000 scratch/output extent excludes KSM and prelude records.
    /// Descriptor/context/scene CPU buffers are separately borrowed storage.
    pub fn new(base:u64)->Option<Self> {
        if base&(PAGE_BYTES-1)!=0{return None;}
        let delta=base.checked_sub(FW_ORIGIN)?;
        base.checked_add(STRIDE)?;
        let device=DEVICE_ORIGIN.checked_add(delta)?;
        if device.checked_add(2*PAGE_BYTES)?>DEVICE_END{return None;}
        let pages=[Page{firmware:base,device},Page{firmware:base+0x8000,device:device+PAGE_BYTES}];
        let stages=core::array::from_fn(|i|{
            let p=pages[i];
            Stage{command:p,ksm:Page{firmware:p.firmware+RCE_BYTES,device:p.device+RCE_BYTES},
                dependency_fw:p.firmware+0x3240,postkick_fw:p.firmware+0x32a0,sku_fw:p.firmware+PAGE_BYTES,
                shared_state_fw:base+0x10000+i as u64*PAGE_BYTES,
                driver_stamp_fw:base+0x18000+i as u64*0x40}
        });
        Some(Self{base,pages,stages,bm_fw:base+0x3200})
    }
}
