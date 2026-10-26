// SPDX-License-Identifier: GPL-2.0-only
//! Native QoS firmware resource and willSubmit publication fields.
//! The runtime owns ID leases, task association, clocks and cache publication.

pub(crate) const RESOURCE_BYTES: usize = 0xe40;
pub(crate) const ID_CAPACITY: usize = 128;

fn word(out: &mut [u8], off: usize, value: u32) {
    out[off..off + 4].copy_from_slice(&value.to_le_bytes());
}
fn long(out: &mut [u8], off: usize, value: u64) {
    out[off..off + 8].copy_from_slice(&value.to_le_bytes());
}
fn read_word(out: &[u8], off: usize) -> u32 {
    u32::from_le_bytes(out[off..off + 4].try_into().unwrap())
}
fn read_long(out: &[u8], off: usize) -> u64 {
    u64::from_le_bytes(out[off..off + 8].try_into().unwrap())
}

#[derive(Clone, Copy)]
pub(crate) struct SubmissionInputs {
    pub hardware_buffer_id: u32,
    pub work_queue_id: u32,
    pub data_master: u32,
    pub scheduler_slot: u64,
    /// Native registerQueue supplies these two values. Linux may choose its
    /// own explicit policy; this encoder does not derive them from lane IDs.
    pub weight: u8,
    pub share_ratio: u32,
    pub native_ticks: u64,
}

pub(crate) struct QueueState {
    initialized: bool,
    binding: Option<(u32, u64, u8, u32)>,
    published: [u64; 2],
}

pub(crate) struct ManagerState {
    /// Native manager's host c48/c50/c58 mirrors, updated by completion.
    pub observed_dm_counts: [u64; 3],
    pub submission_count: u64,
}

impl QueueState {
    pub(crate) fn new() -> Self {
        Self { initialized: false, binding: None, published: [0; 2] }
    }

    /// Update the same owned resource before command publication. All input
    /// refusals occur before any byte or host state changes. Duplicate queue
    /// submissions are allowed, as native willSubmit increments their count.
    pub(crate) fn write_submission(&mut self, manager: &mut ManagerState,
                                  resource: &mut [u8], input: SubmissionInputs)
        -> Option<()>
    {
        if resource.len() < RESOURCE_BYTES || input.hardware_buffer_id >= ID_CAPACITY as u32
            || input.work_queue_id >= ID_CAPACITY as u32 || input.data_master >= 3 {
            return None;
        }
        let binding = (input.hardware_buffer_id, input.scheduler_slot,
                       input.weight, input.share_ratio);
        if self.binding.is_some_and(|old| old != binding) { return None; }
        let id = input.hardware_buffer_id as usize;
        let queue = input.work_queue_id as usize;
        let dm = input.data_master as usize;
        if !self.initialized {
            word(resource, 0xc00 + id * 4, input.share_ratio);
            long(resource, 0x800 + id * 8, input.scheduler_slot);
            self.binding = Some(binding);
            self.initialized = true;
        }
        let bit = 1u64 << (queue & 63);
        if self.published[queue / 64] & bit == 0 {
            resource[queue * 8] = id as u8;
            resource[queue * 8 + 1] = input.weight;
            self.published[queue / 64] |= bit;
        }
        let offset = 0x400 + queue * 4;
        word(resource, offset, read_word(resource, offset).wrapping_add(1));
        let offset = 0x600 + id * 4;
        word(resource, offset, read_word(resource, offset).wrapping_add(1));
        let offset = 0xe20 + dm * 8;
        let count = read_long(resource, offset);
        if count == manager.observed_dm_counts[dm] {
            long(resource, 0xe08 + dm * 8, input.native_ticks);
            long(resource, 0xe00, read_long(resource, 0xe00).wrapping_add(1));
        }
        long(resource, offset, count.wrapping_add(1));
        manager.submission_count = manager.submission_count.wrapping_add(1);
        Some(())
    }
}

impl ManagerState {
    pub(crate) fn new() -> Self {
        Self { observed_dm_counts: [0; 3], submission_count: 0 }
    }
}

/// Native init clears exactly e40 bytes. The caller owns page allocation and
/// publishes the resource GPU VA at hardware child0+26b8 before firmware boot.
pub(crate) fn write_initial(resource: &mut [u8]) -> Option<()> {
    if resource.len() < RESOURCE_BYTES { return None; }
    resource[..RESOURCE_BYTES].fill(0);
    Some(())
}
