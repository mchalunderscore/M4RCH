// SPDX-License-Identifier: GPL-2.0-only
//! AGX memory-map address domains. Slot 0x160 is the user/aperture view,
//! not a firmware-root alias. The caller retains the same mapped resource.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Aperture {
    /// Native map flag +0x58 bit zero is clear.
    Absolute,
    /// Region 1 obtains this base from the owning allocator's slot 0x200.
    Allocator { base: u64 },
    /// Other regions obtain this base from their selected aperture table row.
    Region { index: u16, base: u64 },
}
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Address { pub device: u64, pub user: u64 }
impl Address {
    /// The native getter performs a wrapping subtraction. Retaining this
    /// exact encoding does not establish mapping coverage or resource lifetime.
    pub const fn from_mapping(device: u64, aperture: Aperture) -> Self {
        let user = match aperture {
            Aperture::Absolute => device,
            Aperture::Allocator { base } | Aperture::Region { base, .. } => device.wrapping_sub(base),
        };
        Self { device, user }
    }
}
