// SPDX-License-Identifier: GPL-2.0-only
//! Native queue creation joins explicit Linux process/priority policy to the
//! allocator's actual pointer ring, timestamp list and scheduler slot.
//! Allocated QoS identity and owning-object byte120 are required inputs.

use crate::g16_t6040_queue::{ChannelInputs, PriorityInputs, SchedulerInputs};

pub(crate) const QOS_GPU: u64 = 0xffff_fc20_0012_c000;

/// Allocation identity is the real reserved firmware range, bound to the
/// retained Linux task and public VM/queue. IDs never come from lane numbers.
#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) struct Owner {
    pub allocation: u64,
    pub process_id: u32,
    pub vm_id: u32,
    pub queue_id: u32,
}

#[derive(Clone, Copy)]
pub(crate) struct Leases {
    pub hardware_buffer_id: u32,
    pub work_queue_id: [u32; 3],
}

/// Two native capacity-128 ID spaces. Unknown submission/teardown outcomes
/// retain every lease. A new firmware session constructs a new allocator.
pub(crate) struct LeasePool {
    hardware: [Option<Owner>; 128],
    work: [Option<Owner>; 128],
    first_owner: Option<Owner>,
}

impl LeasePool {
    pub(crate) fn new() -> Self {
        Self { hardware: [None; 128], work: [None; 128], first_owner: None }
    }

    pub(crate) fn reserve_initial_owner(&mut self, owner: Owner) -> Option<Leases> {
        // Native group-weight redistribution and ID retirement are separate
        // producers. Until bound, only one public owner may use the initial
        // single-group share ratio 8192. This is an explicit Linux policy.
        if self.first_owner.is_some_and(|first| first != owner) { return None; }
        let hardware = self.hardware.iter().position(|entry| *entry == Some(owner))
            .or_else(|| self.hardware.iter().position(Option::is_none))?;
        let mut work = [0; 3];
        let mut found = 0;
        for (index, entry) in self.work.iter().enumerate() {
            if *entry == Some(owner) { work[found] = index as u32; found += 1; }
            if found == 3 { break; }
        }
        if found == 0 {
            for (index, entry) in self.work.iter().enumerate() {
                if entry.is_none() { work[found] = index as u32; found += 1; }
                if found == 3 { break; }
            }
        }
        if found != 3 { return None; }
        self.hardware[hardware] = Some(owner);
        for &id in &work { self.work[id as usize] = Some(owner); }
        self.first_owner = Some(owner);
        Some(Leases { hardware_buffer_id: hardware as u32, work_queue_id: work })
    }
}

pub(crate) fn initial_weight(public_priority: u32) -> Option<u8> {
    match public_priority { 0 => Some(15), 1 => Some(4), _ => None }
}

/// Linux public low/normal priorities choose these explicit native policy
/// inputs. Firmware lane is derived by the native policy, never substituted
/// for its context-priority enum.
pub(crate) fn linux_policy(public_priority: u32) -> Option<PriorityInputs> {
    match public_priority {
        0 => Some(PriorityInputs { context_priority: 2, requested_subpriority: 0, qos_level: 0 }),
        1 => Some(PriorityInputs { context_priority: 1, requested_subpriority: 0, qos_level: 2 }),
        _ => None,
    }
}

pub(crate) struct Inputs {
    pub process_id: u32,
    pub public_priority: u32,
    pub pointers: u64,
    pub ring: u64,
    /// Native AGXTimeStampQueue object+28. The owned 24-byte list initializer
    /// is separate from this channel state and from the scheduler slot.
    pub timestamp_list: u64,
    pub scheduler: SchedulerInputs,
    pub capacity: u32,
    pub producer: u32,
}

pub(crate) struct Images {
    pub state: [u8; 0xc0],
    pub pointers: [u8; 0x64],
    pub scheduler: [u8; 0x40],
    pub lane: u32,
}

impl Inputs {
    pub(crate) fn images(&self) -> Option<Images> {
        if self.producer >= self.capacity { return None; }
        let priority = linux_policy(self.public_priority)?;
        let mut out = Images { state: [0; 0xc0], pointers: [0; 0x64], scheduler: [0; 0x40],
            lane: priority.firmware_lane() };
        ChannelInputs { state_pointer_00: self.pointers, state_pointer_08: self.ring,
            state_pointer_10: self.timestamp_list, channel_context: self.scheduler.firmware_slot,
            process_id: self.process_id, capacity: self.capacity, priority,
        }.write_initial(&mut out.state, &mut out.pointers)?;
        self.scheduler.write_initial(&mut out.scheduler)?;
        out.pointers[0x40..0x44].copy_from_slice(&self.producer.to_le_bytes());
        Some(out)
    }

    /// Native config15 prefix followed by the matched scheduler companions.
    /// The caller supplies the two views of the same owned KSM pointer-ring
    /// resource. Concrete graphics initKSM overloads are no-ops, so descriptor
    /// flags/identity and task callback66 are explicit Linux experiment inputs.
    pub(crate) fn configuration(&self, device_ring: u64, work_queue_id: u32,
                               descriptor_id: u32, descriptor_flags: [u8; 2],
                               task_callback_66: u32) -> Option<[u8; 0x88]> {
        if work_queue_id >= 128 || device_ring == 0 || self.ring == 0 { return None; }
        let images = self.images()?;
        let mut out = [0; 0x88];
        out[0..8].copy_from_slice(&15u64.to_le_bytes());
        out[8..0x10].copy_from_slice(&device_ring.to_le_bytes());
        out[0x10..0x18].copy_from_slice(&self.ring.to_le_bytes());
        out[0x18..0x1a].copy_from_slice(&(work_queue_id as u16).to_le_bytes());
        for (offset, value) in [(0x1a, u32::from(descriptor_flags[1] & 1)),
            (0x1e, images.lane), (0x22, 255), (0x32, descriptor_id),
            (0x46, u32::MAX), (0x62, u32::from(descriptor_flags[0] & 1)),
            (0x66, task_callback_66)] {
            out[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
        }
        // Actual 16-byte constant is eight zero followed by eight ff bytes.
        for base in [0x36, 0x6e] { out[base + 8..base + 16].fill(0xff); }
        out[0x7e..0x86].fill(0xff);
        self.scheduler.write_config_companions(&images.state, &mut out)?;
        Some(out)
    }
}
