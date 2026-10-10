// Compile against the actual staged pure kernel profile, not a copied model.
use profile::*;

#[test]
fn observed_j614_topology() {
    let t = T6040.topology(&[0x3db, 0x3db]).unwrap();
    assert_eq!((t.chip, t.generation, t.variant, t.dies), (0x6040, 16, b'S' as u32, 1));
    assert_eq!((t.clusters, t.slots_per_cluster, t.enabled_cores()), (2, 10, 16));
    assert_eq!(t.core_masks, [0x3db, 0x3db]);
    assert!(T6040.initialization().is_none());
    println!("BIND,{},{},{},{},{},{},{},{},{}", t.generation, t.chip,
        t.variant, t.dies, t.clusters, t.slots_per_cluster,
        t.enabled_cores(), t.core_masks[0], t.core_masks[1]);
}

#[test]
fn device_masks_are_not_replaced_by_capture() {
    let t = T6040.topology(&[0x3ff, 0x155]).unwrap();
    assert_eq!(t.core_masks, [0x3ff, 0x155]);
    assert_eq!(t.enabled_cores(), 15);
    let g = T8132.topology(&[0x1ff]).unwrap();
    assert_eq!(g.core_masks, [0x1ff, 0]);
    assert_eq!(g.enabled_cores(), 9);
    assert_eq!(g.variant, b'G' as u32);
    assert_eq!(T8132.initialization(), Some(Initialization::T8132));
}

#[test]
fn missing_extra_empty_or_high_masks_are_rejected() {
    for masks in [&[][..], &[0x3db][..], &[0, 0x3db][..], &[0x400, 0x3db][..], &[0x3db, u32::MAX][..], &[1, 1, 1][..]] {
        assert!(T6040.topology(masks).is_none());
    }
    assert!(T8132.topology(&[0]).is_none());
    assert!(T8132.topology(&[1, 1]).is_none());
}

#[test]
fn a_metadata_flag_cannot_authorize_the_donor_builder() {
    let fake = Profile { normal_startup_implemented: true, ..T6040 };
    assert!(fake.initialization().is_none());
    let fake = Profile { chip: 0x6040, ..T8132 };
    assert!(fake.initialization().is_none());
    assert!(fake.topology(&[0x3ff]).is_none());
    let fake = Profile { register_bytes: 0x3758000, ..T8132 };
    assert!(fake.initialization().is_none());
}

#[test]
fn every_valid_single_cluster_mask_remains_truthful() {
    for mask in 1u32..=0x3ff {
        let t = T8132.topology(&[mask]).unwrap();
        assert_eq!(t.core_masks, [u64::from(mask), 0]);
        assert_eq!(t.enabled_cores(), mask.count_ones());
    }
}

#[test]
fn captured_probe_metadata_and_ladders_remain_independent() {
    assert_eq!(T6040.enabled_cores(), Some(16));
    assert!(profile(0x9999).is_none());
    let mut out = [Step::default(); 3];
    assert_eq!(ladder(&[(0, 125), (338_000_000, 610)], &[(0, 810), (338_000_000, 810)], &mut out), Some(2));
    assert_eq!(out[1].high_mhz, 338);
    assert_eq!(ladder(&[(1, 125)], &[(1, 810)], &mut out), None);
}
