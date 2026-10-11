// SPDX-License-Identifier: GPL-2.0-only
//! Linux-owned native PM allocation. All physical pages belong to retained
//! FirmwareSpace; client UAT aliases map those identical pages, not donor data.
use crate::{
    g16_fw, g16_t6040_pm_v9 as native,
    g16_vm::{AddressSpace, FirmwareSpace},
    pgtable::prot,
};
use kernel::prelude::*;

pub(crate) struct NativePm {
    pub roles: native::OwnedRoles,
    pub geometry: native::Geometry,
    pub firmware_bytes: usize,
    pub client_base: u64,
    operations: u32,
    scenes: u64,
}
impl NativePm {
    /// Caller reserves firmware_base against its global firmware VA allocator.
    /// The Linux user/device views are the same private client UAT aliases;
    /// explicit FW translation maps these to retained firmware aliases.
    /// On any mapping failure, existing Bootstrap retention must retain BOTH
    /// owners; there is no partial rollback or free after device publication.
    pub(crate) fn new(
        fw: &mut FirmwareSpace,
        client: &mut AddressSpace,
        firmware_base: u64,
        geometry: native::Geometry,
    ) -> Result<Self> {
        let plan = native::AllocationPlan::new(geometry).ok_or(EINVAL)?;
        if firmware_base & 0x3fff != 0 {
            return Err(EINVAL);
        }
        let client_base = client.reserve_native_pm_alias(plan.mapped_bytes)?;
        let roles = plan
            .views(firmware_base, client_base, client_base)
            .ok_or(EINVAL)?;
        for role in plan.roles {
            // Every alias uses the same uncached memory attribute, avoiding
            // cached/uncached aliases of firmware/GPU-mutated shared resources.
            fw.alloc(
                firmware_base + role.offset as u64,
                role.mapped_bytes,
                prot::PROT_FW_SHARED_RW,
            )?;
        }
        for offset in (0..plan.mapped_bytes).step_by(0x4000) {
            let va = client_base + offset as u64;
            let pa = fw.physical(firmware_base + offset as u64)?;
            client.map_work_alias(va, pa)?;
        }
        let block_base = client
            .alloc_tvb_blocks(geometry.initial_blocks as usize)?
            .ok_or(ENOMEM)?;
        let mut blocks = KVec::new();
        for j in 0..geometry.initial_blocks {
            blocks.push(block_base + u64::from(j) * 0x28000, GFP_KERNEL)?;
        }
        let e = geometry.extents().ok_or(EINVAL)?;
        let sizes = [0xc0, 4, 0x80, e.aux, e.scenes, e.block_frames, e.page_list];
        let bytes = sizes
            .iter()
            .try_fold(0usize, |a, b| a.checked_add(*b))
            .ok_or(EINVAL)?;
        let mut backing = KVec::new();
        backing.extend_with(bytes, 0u8, GFP_KERNEL)?;
        let (hw, tail) = backing.as_mut_slice().split_at_mut(0xc0);
        let (counter, tail) = tail.split_at_mut(4);
        let (config, tail) = tail.split_at_mut(0x80);
        let (aux, tail) = tail.split_at_mut(e.aux);
        let (scenes, tail) = tail.split_at_mut(e.scenes);
        let (frames, pages) = tail.split_at_mut(e.block_frames);
        native::initialize(
            geometry,
            roles,
            blocks.as_slice(),
            &mut native::Images {
                hw_state: &mut *hw,
                counter: &mut *counter,
                config: &mut *config,
                aux: &mut *aux,
                scenes: &mut *scenes,
                block_frames: &mut *frames,
                page_list: &mut *pages,
            },
        )
        .ok_or(EINVAL)?;
        for (r, b) in [
            (roles.hw_state, &*hw),
            (roles.counter, &*counter),
            (roles.config, &*config),
            (roles.aux, &*aux),
            (roles.scenes, &*scenes),
            (roles.block_frames, &*frames),
            (roles.page_list, &*pages),
        ] {
            fw.write_live(r.firmware, b)?;
        }
        fw.sync();
        client.sync();
        Ok(Self {
            roles,
            geometry,
            firmware_bytes: plan.mapped_bytes,
            client_base,
            operations: 0,
            scenes: 0,
        })
    }
    pub(crate) fn descriptor(&self) -> Result<[u8; 16]> {
        g16_fw::parameter_buffer_descriptor(
            self.roles.page_list.device,
            self.geometry.initial_blocks * 4,
        )
        .ok_or(EINVAL)
    }
    pub(crate) fn reserve_scene(&mut self) -> Result<u32> {
        let i = (!self.scenes).trailing_zeros();
        if i >= self.geometry.scene_count {
            return Err(EBUSY);
        }
        self.scenes |= 1u64 << i;
        Ok(i)
    }
    pub(crate) fn release_scene(&mut self, i: u32) {
        if i < self.geometry.scene_count {
            self.scenes &= !(1u64 << i);
        }
    }
    /// Actual ordinary3D preproducer increments descriptor940's hostcounter.
    /// Caller orders this exactly once before its sole command publication.
    pub(crate) fn increment(&mut self, fw: &mut FirmwareSpace) -> Result {
        let next = self.operations.wrapping_add(1);
        fw.write_live(self.roles.counter.firmware, &next.to_le_bytes())?;
        self.operations = next;
        Ok(())
    }
}
