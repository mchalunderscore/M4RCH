// SPDX-License-Identifier: GPL-2.0-only
//! Matched T6040 channel reset, priority and command-pointer transport.
//! Mapping, process association and QoS ID ownership are caller obligations.
//! This component does not encode Work or establish safe resource retirement.

pub(crate) const STATE_BYTES: usize = 0xc0;
pub(crate) const POINTER_MIN_BYTES: usize = 0x64;
pub(crate) const SCHEDULER_BYTES: usize = 0x40;
pub(crate) const QUEUE_COMPLETE: bool = false;

fn word(out: &mut [u8], offset: usize, value: u32) {
    out[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
}
fn long(out: &mut [u8], offset: usize, value: u64) {
    out[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
}
fn read_word(input: &[u8], offset: usize) -> u32 {
    u32::from_le_bytes(input[offset..offset + 4].try_into().unwrap())
}

/// Raw native policy inputs to AGXArmFirmware::setChannelPriority. Firmware
/// lane numbers are outputs of this policy, not its context-priority input.
#[derive(Clone, Copy)]
pub(crate) struct PriorityInputs {
    pub context_priority: u32,
    pub requested_subpriority: u32,
    pub qos_level: u32,
}

impl PriorityInputs {
    /// Native mapped priority, mask, scheduling word38 and getter word40.
    /// Native comparisons are signed; unknown enum values take native fallbacks.
    fn fields(self) -> (u32, u64, u32, u32) {
        match self.context_priority {
            0 => (0, 0xffff_ffff_ffff_0000, 1, 1),
            5 => (0, 0xffff_ffff_ffff_0000, 1, 0),
            2 => (3, 0, 0, 0),
            1 => match self.qos_level {
                0 => (2, 0xffff_ffff_0000_0000, 0, 0),
                1 => (2, 0xffff_0000_0000_0000, 0, 1),
                2 => (2, 0xffff_0000_0000_0000, 0, 2),
                4 => (3, 0, 0, 4),
                _ => (2, 0xffff_0000_0000_0000, 0, 3),
            },
            _ => (1, 0xffff_ffff_0000_0000, 0, 0),
        }
    }

    pub(crate) fn firmware_lane(self) -> u32 { self.fields().0 }

    /// Only the six exact native priority fields are changed. This is initial
    /// creation; later live changes also need the native host synchronization.
    pub(crate) fn write_initial(self, state: &mut [u8]) -> Option<()> {
        if state.len() < STATE_BYTES { return None; }
        let (lane, mask, first, last) = self.fields();
        word(state, 0x28, lane);
        word(state, 0x2c, lane);
        long(state, 0x30, mask);
        word(state, 0x38, first);
        word(state, 0x3c, self.requested_subpriority);
        word(state, 0x40, last);
        Some(())
    }
}

#[derive(Clone, Copy)]
pub(crate) struct ChannelInputs {
    /// Exact native channel+88/+90/+98 source values. Their mapping and roles
    /// must be supplied by the allocator; no donor pointer is reconstructed.
    pub state_pointer_00: u64,
    pub state_pointer_08: u64,
    pub state_pointer_10: u64,
    pub channel_context: u64,
    pub process_id: u32,
    pub capacity: u32,
    pub priority: PriorityInputs,
}

impl ChannelInputs {
    /// Native clears exactly c0 state bytes and resets six separated queue
    /// words; all other queue bytes and bytes outside c0 remain untouched.
    /// The Linux capacity bound admits a 16-bit submitted next-write index.
    pub(crate) fn write_initial(self, state: &mut [u8], pointers: &mut [u8]) -> Option<()> {
        if state.len() < STATE_BYTES || pointers.len() < POINTER_MIN_BYTES
            || self.capacity < 2 || self.capacity > 0x10000 { return None; }
        state[..STATE_BYTES].fill(0);
        long(state, 0, self.state_pointer_00);
        long(state, 8, self.state_pointer_08);
        long(state, 0x10, self.state_pointer_10);
        word(state, 0x24, u32::MAX);
        word(state, 0x28, 4);
        word(state, 0x44, u32::MAX);
        word(state, 0x48, self.process_id);
        long(state, 0x9c, self.channel_context);
        for offset in [0, 0x10, 0x20, 0x30, 0x40] { word(pointers, offset, 0); }
        word(pointers, 0x50, u32::MAX);
        word(pointers, 0x60, self.capacity);
        self.priority.write_initial(state)
    }
}

/// Supplied native pool/task and HardwareBufferIDManager associations.
/// A zero hardware-buffer ID is permitted only as a caller-owned allocated ID.
#[derive(Clone, Copy)]
pub(crate) struct SchedulerInputs {
    pub firmware_slot: u64,
    pub hardware_buffer_id: u32,
    pub owner_byte_120: u8,
}

impl SchedulerInputs {
    /// Native initializes 38 bytes in a 40-byte slot, preserving its last eight.
    pub(crate) fn write_initial(self, out: &mut [u8]) -> Option<()> {
        if out.len() < SCHEDULER_BYTES { return None; }
        out[..0x38].fill(0);
        out[..2].copy_from_slice(&u16::MAX.to_le_bytes());
        out[5] = 1;
        out[0x26] = self.owner_byte_120;
        out[0x33] = 0xff;
        Some(())
    }

    /// Join native config companions to the same channel's actual getters.
    /// Does not build the remainder of the scheduler configuration command.
    pub(crate) fn write_config_companions(self, state: &[u8], config: &mut [u8]) -> Option<()> {
        if state.len() < STATE_BYTES || config.len() < 0x62 { return None; }
        long(config, 0x4a, self.firmware_slot);
        word(config, 0x56, self.hardware_buffer_id);
        word(config, 0x5a, read_word(state, 0x48));
        word(config, 0x5e, read_word(state, 0x40));
        Some(())
    }
}

/// A validated plan, not an MMIO/cache/DMA publication. The caller writes the
/// pointer at ring_byte_offset, publishes that record with a barrier, and only
/// then publishes next_write to queue+40. None is allowed for a full queue.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct PointerPublication {
    pub ring_byte_offset: usize,
    pub next_write: u32,
}

pub(crate) fn pointer_publication(pointers: &[u8], ring_bytes: usize) -> Option<PointerPublication> {
    if pointers.len() < POINTER_MIN_BYTES { return None; }
    let capacity = read_word(pointers, 0x60);
    let read = read_word(pointers, 0);
    let write = read_word(pointers, 0x40);
    if !(2..=0x10000).contains(&capacity) || read >= capacity || write >= capacity
        || ring_bytes != capacity as usize * 8 { return None; }
    let next_write = (write + 1) % capacity;
    if next_write == read { return None; }
    Some(PointerPublication { ring_byte_offset: write as usize * 8, next_write })
}
