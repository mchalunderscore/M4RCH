// SPDX-License-Identifier: GPL-2.0-only
//! Metadata-only profiles. These do not qualify firmware objects or MCC writes.
#[derive(Debug, PartialEq, Eq)]
pub(crate) enum Variant { G, S }
#[derive(Debug)]
pub(crate) struct Profile {
    pub chip: u32,
    pub variant: Variant,
    pub slots_per_cluster: u8,
    pub masks: &'static [u32],
    pub register_bytes: u64,
    pub normal_startup_implemented: bool,
}
pub(crate) const T8132: Profile = Profile { chip: 0x8132, variant: Variant::G,
    slots_per_cluster: 10, masks: &[0x3ff], register_bytes: 0x4000000,
    normal_startup_implemented: true };
// Observed board masks; other fuse configurations require their own capture.
pub(crate) const T6040: Profile = Profile { chip: 0x6040, variant: Variant::S,
    slots_per_cluster: 10, masks: &[0x3db, 0x3db], register_bytes: 0x3758000,
    normal_startup_implemented: false };
pub(crate) fn profile(chip: u32) -> Option<&'static Profile> {
    match chip { 0x8132 => Some(&T8132), 0x6040 => Some(&T6040), _ => None }
}
impl Profile {
    pub(crate) fn enabled_cores(&self) -> Option<u32> {
        let valid = (1u32.checked_shl(self.slots_per_cluster.into())?).checked_sub(1)?;
        if self.masks.is_empty() || self.masks.iter().any(|m| *m == 0 || *m & !valid != 0) { return None; }
        Some(self.masks.iter().map(|m| m.count_ones()).sum())
    }
}
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Step { pub low_mhz: u32, pub high_mhz: u32,
    pub low_index: usize, pub high_index: usize, pub core_voltage: u32, pub sram_voltage: u32 }
/// Decode one cluster independently; caller supplies storage, with no power estimate.
pub(crate) fn ladder(core: &[(u32,u32)], sram: &[(u32,u32)], out: &mut [Step]) -> Option<usize> {
    if core.is_empty() || core.len() != sram.len() { return None; }
    let mut first=0; let mut used=0;
    while first<core.len() {
        let mut last=first;
        while last+1<core.len() && core[last+1].1==core[first].1 {last+=1;}
        if used==out.len() || (first>0 && core[first].1<=core[first-1].1) {return None;}
        let mut low=first; let mut high=first;
        for i in first..=last {
            if core[i].0!=sram[i].0 || core[i].0%1_000_000!=0 || sram[i].1!=sram[first].1 {return None;}
            if core[i].0<core[low].0 {low=i;}
            if core[i].0>core[high].0 {high=i;}
        }
        out[used]=Step {low_mhz:core[low].0/1_000_000,high_mhz:core[high].0/1_000_000,
            low_index:low,high_index:high,core_voltage:core[first].1,sram_voltage:sram[first].1};
        used+=1;first=last+1;
    }
    Some(used)
}
