// SPDX-License-Identifier: GPL-2.0-only
//! Candidate 25G83 G16S wire codecs from the owner-supplied standalone ABI note.
//! These do not allocate firmware objects or authorize GPU startup.
pub const INTERFACE: u64 = 0x0c8aa322039604c0;
pub const MAIN_POINTERS: usize = 0x254;
pub const MAIN_POWER: usize = 0x471;
pub const STATUS_NOTIFY: [usize; 2] = [0x48e0, 0x48e8];
pub const OBJECT_EXTENTS: [usize; 5] = [0xc18, 0x1048, 0xe10, 0x68, 0x800];

/// Patch only the published pointer fields; caller owns all remaining bytes.
/// This is deliberately not a complete main-object constructor.
pub fn main_pointers(out: &mut [u8], pointers: [u64; 5], power: u64) -> Option<()> {
    if out.len() < MAIN_POWER + 8 { return None; }
    for (i, pointer) in pointers.iter().enumerate() { put64(out, MAIN_POINTERS + i * 8, *pointer); }
    put64(out, MAIN_POWER, power);
    Some(())
}

fn put32(out: &mut [u8], offset: usize, value: u32) {
    out[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
}
fn put64(out: &mut [u8], offset: usize, value: u64) {
    out[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
}
fn get32(input: &[u8], offset: usize) -> u32 {
    u32::from_le_bytes(input[offset..offset + 4].try_into().unwrap())
}

/// Separate from the queue-pointer record: firmware owns cursor words 18/1c/20.
pub struct ChannelState(pub [u8; 0xc0]);
impl ChannelState {
    pub fn new(context: u64, uuid: u32, priority: [u32; 2], mask: u64,
               ranges: [u32; 2]) -> Self {
        let mut out = [0; 0xc0];
        put64(&mut out, 0x9c, context);
        put32(&mut out, 0x48, uuid);
        put32(&mut out, 0x28, priority[0]);
        put32(&mut out, 0x2c, priority[1]);
        put64(&mut out, 0x30, mask);
        put32(&mut out, 0x38, ranges[0]);
        put32(&mut out, 0x40, ranges[1]);
        Self(out)
    }
}
/// Only the documented prefix: full allocation extent is not qualified.
pub struct QueuePointers(pub [u8; 0x64]);
impl QueuePointers {
    pub fn new(capacity: u32) -> Option<Self> {
        if capacity == 0 { return None; }
        let mut out = [0; 0x64];
        put32(&mut out, 0x60, capacity);
        Some(Self(out))
    }
    pub fn publish(&mut self, producer: u32) -> Option<()> {
        if producer >= get32(&self.0, 0x60) { return None; }
        put32(&mut self.0, 0x50, producer);
        Some(())
    }
    pub fn completed(&self) -> u32 { get32(&self.0, 0) }
    pub fn prefetched(&self) -> u32 { get32(&self.0, 0x30) }
}

/// Ordinary tiling-to-fragment dependency. Never use for an init barrier.
pub fn dependency(stamp: u64, timestamp: u64, queue: u32, wait: u32,
                  event: u32, consumer: u32, uuid: u64) -> Option<[u8; 0x48]> {
    if timestamp >= (1u64 << 40) || queue >= 128 { return None; }
    let mut out = [0; 0x48];
    put32(&mut out, 0, 4);
    put64(&mut out, 4, stamp);
    put64(&mut out, 0xc, timestamp);
    put32(&mut out, 0x14, queue);
    put32(&mut out, 0x18, wait);
    put32(&mut out, 0x24, event);
    put32(&mut out, 0x28, consumer);
    put64(&mut out, 0x2c, uuid);
    put32(&mut out, 0x34, 1);
    Some(out)
}
pub fn manager_init(context: u32, slot: u32, manager: u64, stamp: u32) -> [u8; 0x18] {
    let mut out = [0; 0x18];
    put32(&mut out, 0, 5);
    put32(&mut out, 4, context);
    put32(&mut out, 8, slot);
    put64(&mut out, 0xc, manager);
    put32(&mut out, 0x14, stamp);
    out
}
pub fn scheduler_header(timestamp: u64, queue: u8, priority: u8) -> Option<u64> {
    if timestamp >= (1u64 << 40) || queue >= 128 || priority >= 4 { return None; }
    Some((timestamp << 2) | ((queue as u64) << 42) | ((priority as u64) << 59))
}
pub fn register_list(address: u64, count: u32) -> Option<u64> {
    // Descriptor carries the low 48 address bits; accept zero or sign-extended
    // representations, never truncate an unrelated upper address field.
    if address >> 48 != 0 && address >> 48 != 0xffff { return None; }
    let address = address & 0x0000_ffff_ffff_ffff;
    if address & 31 != 0 || count >= (1 << 21) {
        return None;
    }
    Some((address >> 5) | ((count as u64) << 43))
}
/// Eleven candidate groups in16-slot storage; only columns zero/one hold data.
/// Hash-pinned profile-A consumer reads all16 slots; remaining rows are zero.
/// Assignment of decoded groups to the two frequency profiles is still unknown.
pub fn voltages(clusters: &[[u32; 11]; 2]) -> [u8; 16 * 0x40] {
    let mut out = [0; 16 * 0x40];
    for row in 0..11 {
        for cluster in 0..2 { put32(&mut out, row * 0x40 + cluster * 4, clusters[cluster][row]); }
    }
    out
}

/// Patch only candidate profile voltage arrays. Caller supplies every profile
/// and retains responsibility for the remaining hardware-data contents.
/// Low/high frequency to profile A/B assignment is not established here.
pub fn hardware_voltages(out: &mut [u8], core: &[[[u32; 11]; 2]; 2],
                         sram: &[[[u32; 11]; 2]; 2]) -> Option<()> {
    const CORE: [usize; 2] = [0x1008, 0x1d1c];
    const SRAM: [usize; 2] = [0x1408, 0x211c];
    const BYTES: usize = 16 * 0x40;
    if out.len() < SRAM[1] + BYTES { return None; }
    for profile in 0..2 {
        out[CORE[profile]..CORE[profile]+BYTES].copy_from_slice(&voltages(&core[profile]));
        out[SRAM[profile]..SRAM[profile]+BYTES].copy_from_slice(&voltages(&sram[profile]));
    }
    Some(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn prefetch_is_not_completion() {
        let mut q = QueuePointers::new(16).unwrap();
        put32(&mut q.0, 0, 2); put32(&mut q.0, 0x30, 9);
        assert_eq!(q.completed(), 2); assert_eq!(q.prefetched(), 9);
        assert_eq!(q.publish(15), Some(())); assert_eq!(q.publish(16), None);
        assert_eq!(&q.0[0x50..0x54], &[15, 0, 0, 0]);
    }
    #[test]
    fn channel_context_does_not_replace_firmware_cursors() {
        let c = ChannelState::new(0x1122334455667788, 9, [2, 3], 4, [5, 6]);
        assert_eq!(&c.0[0x18..0x24], &[0; 12]);
        assert_eq!(&c.0[0x9c..0xa4], &[0x88,0x77,0x66,0x55,0x44,0x33,0x22,0x11]);
        assert_eq!(&c.0[0x30..0x38], &[4,0,0,0,0,0,0,0]);
    }
    #[test]
    fn dependency_preserves_unaligned_uuid_and_type() {
        let d = dependency(1, 2, 3, 4, 5, 6, 0x1122334455667788).unwrap();
        assert_eq!(&d[0x2c..0x34], &[0x88,0x77,0x66,0x55,0x44,0x33,0x22,0x11]);
        assert_eq!(&d[0x34..0x38], &[1,0,0,0]);
        assert_eq!(dependency(0,1 << 40,0,0,0,0,0), None);
        assert_eq!(dependency(0,0,128,0,0,0,0), None);
    }
    #[test]
    fn manager_pointer_is_not_inline_block_count() {
        let m = manager_init(2,3,0x1122334455667788,4);
        assert_eq!(&m[0xc..0x14], &[0x88,0x77,0x66,0x55,0x44,0x33,0x22,0x11]);
        assert_eq!(&m[0x14..], &[4,0,0,0]);
    }
    #[test]
    fn packed_scheduler_boundaries_do_not_overlap() {
        let h = scheduler_header((1 << 40)-1, 127, 3).unwrap();
        assert_eq!((h >> 2) & ((1 << 40)-1), (1 << 40)-1);
        assert_eq!((h >> 42) & 127, 127); assert_eq!((h >> 59) & 3, 3);
        assert_eq!(scheduler_header(1 << 40,0,0), None);
        assert_eq!(register_list(33,1), None);
        let r = register_list(0xfffffc2000100000, 17).unwrap();
        assert_eq!(r >> 43, 17);
        assert_eq!(r & ((1 << 43)-1), 0xfc2000100000 >> 5);
        assert_eq!(register_list(0x1234000000000000, 1), None);
    }
    #[test]
    fn voltage_columns_remain_distinct_and_unused_columns_zero() {
        let table = voltages(&[[700; 11], [800; 11]]);
        assert_eq!(table.len(),0x400);
        assert!(table[11*0x40..].iter().all(|b| *b==0));
        for row in table[..11*0x40].chunks_exact(0x40) {
            assert_eq!(&row[..8], &[0xbc,2,0,0,0x20,3,0,0]);
            assert!(row[8..].iter().all(|v| *v == 0));
        }
    }
    #[test]
    fn main_patch_preserves_unknown_fields_and_unaligned_power_pointer() {
        let mut main = [0xa5; 0x500];
        assert_eq!(main_pointers(&mut main, [1,2,3,4,5], 0x1122334455667788), Some(()));
        assert_eq!(&main[0x240..0x254], &[0xa5; 0x14]);
        assert_eq!(&main[0x471..0x479], &[0x88,0x77,0x66,0x55,0x44,0x33,0x22,0x11]);
        assert_eq!(&main[0x469..0x471], &[0xa5; 8]);
        let mut short = [0xa5; 0x478];
        assert_eq!(main_pointers(&mut short, [0; 5], 0), None);
        assert!(short.iter().all(|b| *b == 0xa5));
    }
    #[test]
    fn voltage_patch_keeps_profiles_clusters_and_unknown_bytes_distinct() {
        let mut out = [0xa5; 0x3db4];
        let core = [[[610;11],[605;11]], [[1025;11],[1040;11]]];
        let sram = [[[810;11],[815;11]], [[1025;11],[1040;11]]];
        assert_eq!(hardware_voltages(&mut out,&core,&sram),Some(()));
        assert_eq!(get32(&out,0x1008),610); assert_eq!(get32(&out,0x100c),605);
        assert_eq!(get32(&out,0x1d1c),1025); assert_eq!(get32(&out,0x1d20),1040);
        assert_eq!(get32(&out,0x1408),810); assert_eq!(get32(&out,0x140c),815);
        for offset in [0x1008,0x1408,0x1d1c,0x211c] {
            for row in out[offset..offset+11*0x40].chunks_exact(0x40) {
                assert!(row[8..].iter().all(|byte| *byte==0));
            }
        }
        // Tail rows read by the profile-A consumer must not inherit opaque
        // template bytes. Candidate profile-B arrays use the same geometry.
        for offset in [0x1008,0x1408,0x1d1c,0x211c] {
            assert!(out[offset+11*0x40..offset+16*0x40].iter().all(|b| *b==0));
        }
        assert_eq!(&out[0x251c..0x26b8], &[0xa5;0x19c]);
        assert_eq!(&out[0x26b8..0x26c0], &[0xa5;8]);
        let mut short = [0xa5;0x251b];
        assert_eq!(hardware_voltages(&mut short,&core,&sram),None);
        assert!(short.iter().all(|byte| *byte==0xa5));
    }

}
