// SPDX-License-Identifier: GPL-2.0-only
// Identification skeleton derived from pinned Gravity asahi_m4.rs/platform APIs.
//! T6040 resource preflight and explicitly gated raw GPU identification.
//! No firmware, DRM, power-table or MCC builders are linked into this module.
use kernel::io::Io;
use kernel::{c_str, device::Core, devres::Devres, io::mem::IoMem, of, platform, prelude::*};
const WINDOW: usize = 0xd04020;
const BASE: u64 = 0x288000000;
const ID_VERSION: usize = 0xd04000;
const ID_COUNTS_1: usize = 0xd04010;
const ID_COUNTS_2: usize = 0xd04014;
const ID_CLUSTERS: usize = 0xd0401c;
struct Identify { _sgx: Option<Pin<KBox<Devres<IoMem<WINDOW>>>>> }
kernel::of_device_table!(OF_TABLE, MODULE_OF_TABLE,
    <Identify as platform::Driver>::IdInfo,
    [(of::DeviceId::new(c_str!("m4rch,t6040-gpu-identify")), ())]);
impl platform::Driver for Identify {
    type IdInfo = ();
    const OF_ID_TABLE: Option<of::IdTable<Self::IdInfo>> = Some(&OF_TABLE);
    fn probe(pdev: &platform::Device<Core>, _info: Option<&Self::IdInfo>) -> impl PinInit<Self, Error> {
        let dev = pdev.as_ref();
        let node = dev.of_node().ok_or(ENODEV)?;
        let resource = pdev.resource_by_name(c_str!("sgx")).ok_or(EINVAL)?;
        // The DT must expose only the reviewed ID prefix, not the entire GPU.
        if resource.start() as u64 != BASE || resource.size() as usize != WINDOW {
            return Err(EINVAL);
        }
        dev_info!(dev, "T6040 GPU ID resource validated; reads default disabled\n");
        let read_ids = *module_parameters::read_ids.value();
        if read_ids == 0 {
            return Ok(Self { _sgx: None });
        }
        if read_ids != 1 { return Err(EINVAL); }
        // This acknowledgement is a review gate, not a hardware power sensor.
        let reviewed: u32 = node.get_property(c_str!("m4rch,id-access-reviewed"))?;
        if reviewed != 1 { return Err(EPERM); }
        let request = pdev.io_request_by_name(c_str!("sgx")).ok_or(EINVAL)?;
        let sgx = KBox::pin_init(request.iomap_sized::<WINDOW>(), GFP_KERNEL)?;
        {
            let regs = sgx.try_access().ok_or(ENODEV)?;
            let version = regs.relaxed().read32(ID_VERSION);
            if version == 0 || version == u32::MAX { return Err(ENODEV); }
            dev_info!(dev, "T6040 raw GPU IDs: version={:#010x} counts={:#010x}/{:#010x} clusters={:#010x}; decoding unqualified\n",
                version, regs.relaxed().read32(ID_COUNTS_1),
                regs.relaxed().read32(ID_COUNTS_2), regs.relaxed().read32(ID_CLUSTERS));
        }
        Ok(Self { _sgx: Some(sgx) })
    }
}
kernel::module_platform_driver! {
    type: Identify,
    name: "m4rch_gpu_identify",
    authors: ["m4rch contributors"],
    description: "T6040 GPU resource preflight and opt-in raw ID reads",
    license: "GPL v2",
    params: {
        read_ids: u32 {
            default: 0,
            description: "Read raw ID registers only after power/resource review",
        },
    },
}
