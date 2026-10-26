// SPDX-License-Identifier: GPL-2.0-only
//! Native 25G83 G16X shared-allocation geometry and bounded MainConfig fields.
//! Child descriptors are aligned to 64 bytes within one zeroed allocation.
//! Power contents, complete hardware/Root/Region C, remaining MainConfig fields
//! and channel ownership are required before a complete bundle can be returned.

pub(crate) const LOGICAL_BYTES: usize = 0x225c0;
pub(crate) const BACKING_BYTES: usize = 0x24000;
pub(crate) const MAIN_OFFSET: usize = 0x1e100;
pub(crate) const MAIN_BYTES: usize = 0x4c0;
pub(crate) const BUNDLE_COMPLETE: bool = false;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct Child {
    pub cpu_owner: u32,
    pub mapping_owner: u32,
    pub offset: usize,
    pub bytes: usize,
}

/// CPU and mapping owner fields are offsets in the native AGXFirmware object.
/// The zero-sized BRN table is intentional: selected G16X slot f80 returns zero.
/// Its initial pointer aliases the next child; it is not a separately mapped page.
pub(crate) const CHILDREN: [Child; 23] = [
    Child { cpu_owner: 0x2b8, mapping_owner: 0x300, offset: 0, bytes: 0x2718 },
    Child { cpu_owner: 0x2c0, mapping_owner: 0x308, offset: 0x2740, bytes: 0xc18 },
    Child { cpu_owner: 0x2c8, mapping_owner: 0x310, offset: 0x3380, bytes: 0x1048 },
    Child { cpu_owner: 0x2d0, mapping_owner: 0x318, offset: 0x4400, bytes: 0xe10 },
    Child { cpu_owner: 0x2d8, mapping_owner: 0x320, offset: 0x5240, bytes: 0x6578 },
    Child { cpu_owner: 0x2e0, mapping_owner: 0x328, offset: 0xb7c0, bytes: 0x68 },
    Child { cpu_owner: 0x2e8, mapping_owner: 0x330, offset: 0xb840, bytes: 0x800 },
    Child { cpu_owner: 0x2f0, mapping_owner: 0x338, offset: 0xc040, bytes: 0 },
    Child { cpu_owner: 0x2f8, mapping_owner: 0x340, offset: 0xc040, bytes: 0x88 },
    Child { cpu_owner: 0x440, mapping_owner: 0x448, offset: 0xc100, bytes: 0x1800 },
    Child { cpu_owner: 0x418, mapping_owner: 0x420, offset: 0xd900, bytes: 0x1800 },
    Child { cpu_owner: 0x3f0, mapping_owner: 0x3f8, offset: 0xf100, bytes: 0x1800 },
    Child { cpu_owner: 0x3c8, mapping_owner: 0x3d0, offset: 0x10900, bytes: 0x1800 },
    Child { cpu_owner: 0x4e0, mapping_owner: 0x4e8, offset: 0x12100, bytes: 0x1800 },
    Child { cpu_owner: 0x4b8, mapping_owner: 0x4c0, offset: 0x13900, bytes: 0x1800 },
    Child { cpu_owner: 0x490, mapping_owner: 0x498, offset: 0x15100, bytes: 0x1800 },
    Child { cpu_owner: 0x468, mapping_owner: 0x470, offset: 0x16900, bytes: 0x1800 },
    Child { cpu_owner: 0x580, mapping_owner: 0x588, offset: 0x18100, bytes: 0x1800 },
    Child { cpu_owner: 0x558, mapping_owner: 0x560, offset: 0x19900, bytes: 0x1800 },
    Child { cpu_owner: 0x530, mapping_owner: 0x538, offset: 0x1b100, bytes: 0x1800 },
    Child { cpu_owner: 0x508, mapping_owner: 0x510, offset: 0x1c900, bytes: 0x1800 },
    Child { cpu_owner: 0x858, mapping_owner: 0x878, offset: MAIN_OFFSET, bytes: MAIN_BYTES },
    Child { cpu_owner: 0x8b0, mapping_owner: 0x8b8, offset: 0x1e5c0, bytes: 0x4000 },
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct MainPointers {
    pub hardware: u64,
    pub repeated: u64,
    pub header: u64,
    pub shared: [u64; 5],
    pub power: u64,
}

impl MainPointers {
    /// Only stores reached in the selected native initial shared-data producer.
    /// Unknown channels, extra+240 and external+200 remain caller-owned bytes.
    pub(crate) fn write_component(&self, out: &mut [u8]) -> Option<()> {
        if out.len() < MAIN_BYTES { return None; }
        for (offset, value) in [(0, self.hardware), (8, self.repeated),
                                (0x10, self.header), (0x471, self.power)] {
            out[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
        }
        for (i, &value) in self.shared.iter().enumerate() {
            let offset = 0x254 + i * 8;
            out[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
        }
        out[0x250..0x254].copy_from_slice(&0u32.to_le_bytes());
        out[0x2f8..0x300].copy_from_slice(&0u64.to_le_bytes());
        Some(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct BundleLayout {
    base: u64,
}

impl BundleLayout {
    /// The caller supplies an owned firmware VA. This checks geometry only;
    /// it does not claim mapping permissions, publication or ownership lifetime.
    pub(crate) fn new(base: u64) -> Option<Self> {
        if base & 0x3fff != 0 || base.checked_add(BACKING_BYTES as u64).is_none() {
            return None;
        }
        Some(Self { base })
    }

    pub(crate) fn base(&self) -> u64 { self.base }

    pub(crate) fn child_gpu_address(&self, index: usize) -> Option<u64> {
        self.base.checked_add(CHILDREN.get(index)?.offset as u64)
    }

    pub(crate) fn address_for_mapping(&self, owner: u32) -> Option<u64> {
        let index = CHILDREN.iter().position(|child| child.mapping_owner == owner)?;
        self.child_gpu_address(index)
    }

    pub(crate) fn main_gpu_address(&self) -> u64 {
        self.base + MAIN_OFFSET as u64
    }

    pub(crate) fn main_pointers(&self) -> MainPointers {
        MainPointers {
            hardware: self.base,
            repeated: self.base + CHILDREN[7].offset as u64,
            header: self.base + CHILDREN[8].offset as u64,
            shared: [1, 2, 3, 5, 6].map(|index| self.base + CHILDREN[index].offset as u64),
            power: self.base + CHILDREN[4].offset as u64,
        }
    }

    pub(crate) fn write_main_component(&self, out: &mut [u8]) -> Option<()> {
        self.main_pointers().write_component(out)
    }

    /// Writes only the proved MainConfig component in the actual native block.
    /// The allocation owner zeroes initial backing separately. Unknown objects
    /// and allocation padding are preserved, never filled from donor defaults.
    pub(crate) fn write_component(&self, out: &mut [u8]) -> Option<()> {
        if out.len() < BACKING_BYTES { return None; }
        self.write_main_component(&mut out[MAIN_OFFSET..MAIN_OFFSET + MAIN_BYTES])
    }
}
