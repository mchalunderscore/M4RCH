// SPDX-License-Identifier: GPL-2.0-only
//! T6040 hardware-data components from the matched 25G83 AGX producer.
//! This is not a complete boot bundle. Unresolved resources are absent, and
//! no T8132 power policy, work cursors, scheduler roots or boot objects appear.

pub(crate) const PAGE: u64 = 0x4000;
pub(crate) const SGX_PHYSICAL: u64 = 0x288000000;
pub(crate) const SGX_BYTES: u64 = 0x3758000;
pub(crate) const SGX_VIRTUAL: u64 = 0xffff_fc21_8000_0000;
const AFR_VIRTUAL: u64 = 0xffff_fc21_8100_0000;
const PLATFORM_VIRTUAL: u64 = 0xffff_fc21_8120_0000;
/// Minimum backing for the fields this component writes, not native sizeof.
pub(crate) const COMPONENT_BYTES: usize = 0x2570;
pub(crate) const UNRESOLVED_SLOTS: &[usize] = &[3, 22, 27, 39, 41];

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Register {
    pub slot: usize,
    pub physical: u64,
    pub address: u64,
    pub size: u32,
    pub stride: u32,
    pub relative: u64,
    pub flags: u32,
}

// Native PIO table has thirteen rows; slot44 has no primary mapping and is
// intentionally not turned into an inferred GMGIF/MTR/counter window.
const SGX: &[(usize, u64, u32, u32)] = &[
    (17, 0, 0x21400, 1), (26, 0xd04000, 0x8000, 1),
    (29, 0xd10000, 0x4000, 1), (31, 0xd40000, 0x4000, 1),
    (33, 0xd44000, 0x4000, 1), (34, 0xd4c000, 0x200, 1),
    (28, 0xd58000, 0x8000, 0), (32, 0xd60000, 0x20000, 1),
    (35, 0xe00000, 0x4000, 1), (40, 0xe1c000, 0x4000, 0),
    (37, 0xe40000, 0x4000, 1), (43, 0xe60000, 0x58, 0),
];
const PLATFORM: &[(usize, u64, u32)] = &[
    (0, 0x502414000, 1), (9, 0x5003d0000, 1),
    (10, 0x5003c0000, 0), (11, 0x5003d8000, 1),
];
pub(crate) const REGISTER_COUNT: usize = 17;

/// Descriptor flags and PTE write permission are separate native interfaces.
/// Only pages used by captured write consumers are writable. No host access
/// or ownership is authorized by producing this mapping plan.
fn writable_sgx(relative: u64) -> bool {
    matches!(relative, 0 | 0x4000 | 0x8000 | 0xc000 | 0x10000 | 0x14000 |
        0x18000 | 0x1c000 | 0x20000 | 0xd04000 | 0xd10000 | 0xd40000 |
        0xd44000 | 0xd4c000 | 0xd60000 | 0xe00000 | 0xe1c000 | 0xe40000)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct Page {
    pub virtual_address: u64,
    pub physical: u64,
    pub writable: bool,
}

pub(crate) fn registers() -> [Register; REGISTER_COUNT] {
    let mut out = [Register::default(); REGISTER_COUNT];
    for (i, &(slot, relative, size, flags)) in SGX.iter().enumerate() {
        out[i] = Register { slot, physical: SGX_PHYSICAL + relative,
            address: SGX_VIRTUAL + relative, size, stride: size, relative, flags };
    }
    for (i, &(slot, physical, flags)) in PLATFORM.iter().enumerate() {
        out[SGX.len() + i] = Register { slot, physical,
            address: PLATFORM_VIRTUAL + i as u64 * PAGE, size: PAGE as u32,
            stride: PAGE as u32, relative: 0, flags };
    }
    out[REGISTER_COUNT - 1] = Register { slot: 20, physical: 0x28b000000,
        address: AFR_VIRTUAL, size: 0x100000, stride: 0x40000, relative: 0, flags: 1 };
    out
}

/// Emit a page-rounded plan consumed directly by Gravity FirmwareSpace.
/// Adjacent SGX descriptor aliases do not result in duplicate PTEs.
pub(crate) fn pages<E>(mut emit: impl FnMut(Page) -> Result<(), E>) -> Result<(), E> {
    for (i, &(_, relative, size, _)) in SGX.iter().enumerate() {
        let end = (relative + u64::from(size) + PAGE - 1) & !(PAGE - 1);
        let mut offset = relative & !(PAGE - 1);
        while offset < end {
            let already = SGX[..i].iter().any(|&(_, previous, bytes, _)| {
                offset >= (previous & !(PAGE - 1))
                    && offset < ((previous + u64::from(bytes) + PAGE - 1) & !(PAGE - 1))
            });
            if !already {
                emit(Page { virtual_address: SGX_VIRTUAL + offset,
                    physical: SGX_PHYSICAL + offset, writable: writable_sgx(offset) })?;
            }
            offset += PAGE;
        }
    }
    for (i, &(_, physical, flags)) in PLATFORM.iter().enumerate() {
        emit(Page { virtual_address: PLATFORM_VIRTUAL + i as u64 * PAGE,
            physical, writable: flags != 0 })?;
    }
    // Concatenated IOMemoryDescriptor: four 256 KiB physical regions spaced
    // 2 MiB apart. Their firmware VA has no 2 MiB physical gaps.
    for instance in 0..4u64 {
        for page in 0..16u64 {
            emit(Page { virtual_address: AFR_VIRTUAL + instance * 0x40000 + page * PAGE,
                physical: 0x28b000000 + instance * 0x200000 + page * PAGE,
                writable: page % 4 == 0 })?;
        }
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Step {
    pub low_mhz: u32, pub high_mhz: u32, pub low_index: u32, pub high_index: u32,
    pub core_voltage: u32, pub sram_voltage: u32,
}
pub(crate) struct Hardware {
    pub masks: [u32; 2],
    pub steps: [[Step; 11]; 2],
}

impl Hardware {
    /// The original ADT performance properties contain LE frequency/voltage
    /// pairs, sixteen rows per cluster. Decode both clusters independently.
    pub(crate) fn from_adt(masks: [u32; 2], core: &[u8], sram: &[u8]) -> Option<Self> {
        if masks.iter().any(|m| *m == 0 || *m & !0x3ff != 0)
            || core.len() != 2 * 16 * 8 || sram.len() != core.len() { return None; }
        let read = |data: &[u8], cluster: usize, row: usize, word: usize| {
            let off = (cluster * 16 + row) * 8 + word * 4;
            u32::from_le_bytes(data[off..off + 4].try_into().unwrap())
        };
        let mut steps = [[Step::default(); 11]; 2];
        for cluster in 0..2 {
            let mut first = 0; let mut used = 0;
            while first < 16 {
                if used == 11 { return None; }
                let voltage = read(core, cluster, first, 1);
                let memory = read(sram, cluster, first, 1);
                if voltage == 0 || memory == 0
                    || (first > 0 && voltage <= read(core, cluster, first - 1, 1)) { return None; }
                let mut last = first;
                while last + 1 < 16 && read(core, cluster, last + 1, 1) == voltage { last += 1; }
                let mut low = first; let mut high = first;
                for row in first..=last {
                    let frequency = read(core, cluster, row, 0);
                    if frequency % 1_000_000 != 0 || frequency != read(sram, cluster, row, 0)
                        || read(sram, cluster, row, 1) != memory { return None; }
                    if frequency < read(core, cluster, low, 0) { low = row; }
                    if frequency > read(core, cluster, high, 0) { high = row; }
                }
                steps[cluster][used] = Step { low_mhz: read(core, cluster, low, 0) / 1_000_000,
                    high_mhz: read(core, cluster, high, 0) / 1_000_000,
                    low_index: low as u32, high_index: high as u32,
                    core_voltage: voltage, sram_voltage: memory };
                used += 1; first = last + 1;
            }
            if used != 11 || steps[cluster][0].high_mhz != 0 { return None; }
        }
        Some(Self { masks, steps })
    }

    /// Populate only independently established native fields. The remaining
    /// bytes are not a default power/firmware policy and must not be booted.
    pub(crate) fn write(&self, out: &mut [u8]) -> Option<()> {
        if out.len() < COMPONENT_BYTES { return None; }
        let put32 = |out: &mut [u8], off: usize, value: u32| {
            out[off..off + 4].copy_from_slice(&value.to_le_bytes());
        };
        let put64 = |out: &mut [u8], off: usize, value: u64| {
            out[off..off + 8].copy_from_slice(&value.to_le_bytes());
        };
        for r in registers() {
            let off = 0x640 + r.slot * 40;
            put64(out, off, r.physical); put64(out, off + 8, r.address);
            put32(out, off + 16, r.size); put32(out, off + 20, r.stride);
            put64(out, off + 24, r.relative); put32(out, off + 32, r.flags);
        }
        for cluster in 0..2 {
            for state in 0..11 {
                put32(out, 0x1008 + state * 0x40 + cluster * 4, self.steps[cluster][state].core_voltage);
                put32(out, 0x1408 + state * 0x40 + cluster * 4, self.steps[cluster][state].sram_voltage);
            }
        }
        put32(out, 0xe90, 0x6040);
        put64(out, 0x2560, u64::from(self.masks[0]) | u64::from(self.masks[1]) << 10);
        put64(out, 0x2568, 0);
        Some(())
    }
}
