// SPDX-License-Identifier: GPL-2.0-only
//! One selected firmware topology for startup and every later publication.
//! Native T6040 transport cursors belong to allocated shared RAM. Donor
//! T8132 cursors alone use SGX register aliases. A channel count is not proof
//! that an RX composite record has work/control cursor semantics.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct Channel {
    pub state: [u64; 3],
    pub ring: u64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct Rx {
    pub state: u64,
    pub ring: u64,
    pub record_bytes: usize,
    pub capacity: u32,
}

#[derive(Clone, Copy)]
pub(crate) struct Transport {
    pub native_t6040: bool,
    pub channels: [Channel; 17],
    pub event: Rx,
    pub trace: Rx,
    pub roots: crate::g16_fw::RootPointers,
}

impl Transport {
    pub(crate) fn for_platform(native_t6040: bool) -> Option<Self> {
        if native_t6040 {
            use crate::g16_t6040_shared::{NativeTopology, RxKind};
            let layout = NativeTopology::new(crate::g16_fw::BUNDLE_ADDRESS,
                0xffff_fc20_0003_0000, crate::g16_fw::ROOT_ADDRESS,
                0xffff_fc20_0010_8000, 0xffff_fc20_000f_8000)?;
            let native = layout.channels();
            let roots = layout.root_pointers();
            let event = layout.rx(RxKind::Event);
            let trace = layout.rx(RxKind::Trace);
            Some(Self {
                native_t6040,
                channels: native.map(|channel| Channel {
                    state: channel.state, ring: channel.ring }),
                roots: crate::g16_fw::RootPointers {
                    region_a: roots.region_a, main_config: roots.main_config,
                    region_c: roots.region_c, status_a: roots.status_a,
                    status_b: roots.status_b, extra_0: roots.extra_0, extra_1: roots.extra_1,
                },
                event: Rx { state: event.state, ring: event.ring,
                    record_bytes: event.record_bytes, capacity: event.capacity },
                trace: Rx { state: trace.state, ring: trace.ring,
                    record_bytes: trace.record_bytes, capacity: trace.capacity },
            })
        } else {
            let donor = crate::g16_fw::MainConfig::bootstrap(crate::g16_fw::BUNDLE_ADDRESS);
            Some(Self { native_t6040,
                channels: donor.channels.map(|channel| Channel { state: channel.state, ring: channel.ring }),
                roots: crate::g16_fw::RootPointers::bootstrap(),
                event: Rx { state: 0xffff_fc20_0003_f1c0, ring: 0xffff_fc20_0003_f440,
                    record_bytes: 0x48, capacity: 256 },
                trace: Rx { state: 0xffff_fc20_0003_f3c0, ring: 0xffff_fc20_000e_5c40,
                    record_bytes: 0x48, capacity: 512 },
            })
        }
    }

    /// A native cursor is a firmware VA in owned RAM. Only work0..11 and
    /// control12 admit this API; Event/Trace channels have distinct layouts.
    pub(crate) fn cursor(&self, channel: usize, ordinal: usize) -> Option<u64> {
        if channel > 12 || ordinal > 2 { return None; }
        Some(self.channels[channel].state[ordinal])
    }

    pub(crate) fn donor_sgx_cursor_offset(&self, channel: usize, ordinal: usize) -> Option<usize> {
        if self.native_t6040 { return None; }
        let cursor = self.cursor(channel, ordinal)?;
        let (base, offset) = if ordinal == 2 {
            (0xffff_fc20_0002_0000, 0xd60000)
        } else {
            (0xffff_fc20_0002_8000, 0xd64000)
        };
        let delta = usize::try_from(cursor.checked_sub(base)?).ok()?;
        if delta >= 0x4000 || delta & 3 != 0 { return None; }
        Some(offset + delta)
    }
}

/// Matched AGX353.14/native712e084 == matched firmware58850. This is the
/// device-control namespace, distinct from KSM opcodes with the same numbers.
pub(crate) fn device_control_power_class(opcode: u32) -> Option<bool> {
    const CLASSES: [u8; 56] = [
        0,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,
        1,1,1,1,1,0,0,1,1,1,1,0,1,1,1,1,
        1,1,0,1,1,1,1,1,1,1,0,1,1,1,0,1,
        1,1,1,1,1,1,1,1,
    ];
    Some(*CLASSES.get(opcode as usize)? & 1 != 0)
}
