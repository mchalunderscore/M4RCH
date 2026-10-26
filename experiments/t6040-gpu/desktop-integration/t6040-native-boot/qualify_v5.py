#!/usr/bin/env python3
"""Exercise native shared allocation, MainConfig and actual Platform methods offline."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import re
import subprocess

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[3]

def pin(path):
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

def array(data):
    return "&[" + ",".join(str(v) for v in data) + "]"

def qualify(staging, output):
    output.mkdir(exist_ok=False, parents=True)
    source = staging / "source/linux/drivers/gpu/drm/asahi"
    pio_path = ROOT / "docs/evidence/gpuc002-input/agx-pio-map.json"
    platform_path = ROOT / "docs/evidence/gpuc003-input/platform-map.json"
    afr_path = ROOT / "docs/evidence/gpuc004-afr-map.json"
    contract_path = ROOT / "docs/evidence/2026-10-06-gpu-contract.json"
    pio = json.loads(pio_path.read_text())
    platform = json.loads(platform_path.read_text())
    afr = json.loads(afr_path.read_text())
    contract = json.loads(contract_path.read_text())
    expected_sha = "3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e"
    assert pio["macho_sha256"] == platform["macho_sha256"] == afr["macho_sha256"] == expected_sha
    assert contract["performance_rows_per_table"] == 16 and contract["performance_table_count"] == 2
    core = b"".join(struct.pack("<II", r["frequency_hz"], r["voltage_raw"])
                    for cluster in contract["core_tables"] for r in cluster)
    sram = b"".join(struct.pack("<II", r["frequency_hz"], r["voltage_raw"])
                    for cluster in contract["sram_tables"] for r in cluster)
    sgx_base = int(pio["sgx_physical_base"], 16)
    sgx_va = 0xfffffc2180000000
    regs = []
    for item in pio["records"]:
        if int(item["relative_offset"], 16) == 0xffffffff:
            continue
        slot = item["hal_resource_id"]
        relative = int(item["relative_offset"], 16)
        size = int(item["length"], 16)
        flags = int(slot in {17, 26, 29, 31, 32, 33, 34, 35, 37})
        regs.append((slot, sgx_base + relative, sgx_va + relative, size, size, relative, flags))
    native_platform = {item["slot"]: int(item["physical"], 16)
                       for item in platform["resources"] + platform["adjacent_resources"]}
    for i, slot in enumerate([0, 9, 10, 11]):
        regs.append((slot, native_platform[slot], 0xfffffc2181200000 + i * 0x4000,
                     0x4000, 0x4000, 0, int(slot != 10)))
    regs.append((afr["slot"], int(afr["physical_ranges"][0], 16), 0xfffffc2181000000,
                 afr["virtual_extent_bytes"], afr["range_bytes"], 0, 1))
    followup_path = ROOT / "out/gpu-gravity-normal-boot-v1/native-resource-followup.json"
    assert pin(followup_path)["sha256"] == "ec6e967d66f57d225c66f64924664888ffdaced39e1501ddec8f8aea90646275"
    followup = json.loads(followup_path.read_text())
    resources = {r["slot"]: r for r in followup["resources"]}
    flags_path = ROOT / 'out/gpu-gravity-normal-boot-v3-source-evidence/native-descriptor-flags.json'
    flags = json.loads(flags_path.read_text())['native_hardware_flags']
    assert flags == {'3': 2, '22': 2, '39': 2, '41': 2}
    mcc = resources[3]
    mcc_mask = mcc["active_mcc_mask"]
    mcc_ranges = [int(pa, 16) for pa in mcc["physical_ranges"]]
    mcc_stride = int(mcc["native_per_range_bytes"], 16)
    assert mcc_ranges == [0x2201c4000 + (bit << 25) for bit in range(32) if mcc_mask & (1 << bit)]
    assert mcc_stride == (0x4000 + 0x1407b) & ~0x3fff
    regs.extend([(3, mcc_ranges[0], 0xfffffc2181280000, len(mcc_ranges) * mcc_stride, mcc_stride, 0, flags['3']),
                 (22, int(resources[22]["physical"], 16), 0xfffffc2181240000,
                  int(resources[22]["native_per_range_bytes"], 16), int(resources[22]["native_per_range_bytes"], 16), 0, flags['22']),
                 (39, int(resources[39]["physical"], 16), 0xfffffc2181250000,
                  int(resources[39]["native_per_range_bytes"], 16), int(resources[39]["native_per_range_bytes"], 16), 0, flags['39'])])
    counter_path = ROOT / 'out/gpu-gravity-normal-boot-v3-source-evidence/native-counter.json'
    absent_path = ROOT / 'out/gpu-gravity-normal-boot-v3-source-evidence/native-slot27-absent.json'
    counter = json.loads(counter_path.read_text())
    absent = json.loads(absent_path.read_text())
    assert counter['macho']['sha256'] == expected_sha
    assert counter['slot'] == 41 and counter['instances'] == 1
    counter_pa = int(counter['physical'], 16)
    counter_bytes = counter['size']
    assert counter_pa == sgx_base + 0xe1f000 + 0x800
    assert counter_bytes == (0x4000 + 0x49b) & ~0x3fff
    assert absent['slot'] == 27 and absent['hardware_descriptor'] == {
        'physical': 0, 'virtual': 0, 'size': 0, 'stride': 0, 'relative': 0, 'flags': 2}
    regs.extend([(41, counter_pa, sgx_va + counter_pa - sgx_base,
                  counter_bytes, counter_bytes, 0, flags['41']),
                 (27, 0, 0, 0, 0, 0, 2)])
    assert len(regs) == 22 and len({r[0] for r in regs}) == len(regs)
    interface_path = ROOT / "docs/evidence/2026-10-07-gravity-gpu-firmware-interface-current.json"
    interface = json.loads(interface_path.read_text())
    assert interface["text_contract"]["normalized_sha256"] == "190cef1946a23dfbde180592629631c3b28d0509a17eb76108b7c9a52accd9ac"
    native_identifier = int(interface["g16s_identifier_sequences"][0]["identifier"], 16)
    assert native_identifier == 0x0c8aa322039604c0
    # Exercise the actual RootPointers implementation as well as its selected
    # identifier helper. Other root fields here are caller-supplied test values;
    # passing this serialization check does not qualify production bindings.
    fw_text = (source / "g16_fw.rs").read_text()
    root_impl = fw_text[fw_text.index("fn put64(out:"):]
    constants = "\n".join(re.findall(r"pub\(crate\) const [A-Z_]+:.*?;", fw_text))
    root_context = "mod native_root {\n" + constants + "\n" + root_impl + "\n}\n"
    region_path = ROOT / 'out/gpu-gravity-normal-boot-v4-source-evidence/native-region-c.json'
    region = json.loads(region_path.read_text())
    assert region['logical_bytes'] == 0xe58 and region['backing_bytes'] == 0x4000
    assert not region['region_c_complete'] and not region['hardware_actions']
    expected_region = bytearray([0xa5] * region['backing_bytes'])
    for item in region['initial_u32_fields']:
        struct.pack_into('<I', expected_region, int(item['offset'],16), item['value'])
    for item in region['initial_u8_fields']:
        expected_region[int(item['offset'],16)] = item['value']
    for item in region['idle_default_fields'].values():
        struct.pack_into('<I', expected_region, int(item['offset'],16), item['value'])
    expected_zero_region = bytearray(region['backing_bytes'])
    for i, value in enumerate(expected_region):
        if value != 0xa5:
            expected_zero_region[i] = value
    platform_text = (source / 'g16_platform.rs').read_text()
    region_methods = platform_text[platform_text.index('    /// Native initial component in the source-proved shared allocation.'):
                                   platform_text.rfind('\n}')]
    # Compile the actual Platform helper and rejection method with a small
    # property/allocation adapter. This adapter supplies inputs only; the
    # production methods, raw-input decoding and byte writer are unmodified.
    power_text = (source / 'g16_power.rs').read_text()
    bundle_methods = power_text[power_text.index('    /// Native zeroed shared allocation'):
                                power_text.index('    pub(crate) fn power_data')]
    platform_context = '''mod actual_platform {
type KVec<T> = std::vec::Vec<T>;
type Result<T> = std::result::Result<T,i32>;
pub const EINVAL:i32=22;pub const ENOENT:i32=2;pub const ENOTSUPP:i32=95;
const PAGE:u64=0x4000;
macro_rules! c_str { ($v:literal) => { $v }; }
pub struct Node {pub gpu:Option<KVec<u8>>,pub fender:Option<KVec<u8>>,
    pub gpu_error:Option<i32>,pub fender_error:Option<i32>}
impl Node {
    pub fn empty() -> Self {Self {gpu:None,fender:None,gpu_error:None,fender_error:None}}
    fn get_property(&self,name:&str)->Result<KVec<u8>> {
        let (value,error)=match name {
            "apple,sgx-gpu-idle-off-delay-ms"=>(&self.gpu,self.gpu_error),
            "apple,sgx-gpu-fender-idle-off-delay-ms"=>(&self.fender,self.fender_error),
            _=>panic!("Unexpected property adapter input")};
        if let Some(error)=error {return Err(error);}
        value.clone().ok_or(ENOENT)
    }
}
pub struct Platform {pub native_hardware:Option<crate::native::Hardware>,pub node:Node,pub maximum_power:u32}
fn zeroed(size:usize)->Result<KVec<u8>> {Ok(vec![0;size])}
fn put32(out:&mut[u8],offset:usize,value:u32){out[offset..offset+4].copy_from_slice(&value.to_le_bytes());}
fn put64(out:&mut[u8],offset:usize,value:u64){out[offset..offset+8].copy_from_slice(&value.to_le_bytes());}
impl Platform {
    fn hwdata(&self)->Result<KVec<u8>> {panic!("Donor hardware path must not execute in native qualification")}
    fn power_data(&self,_out:&mut[u8])->Result<()> {panic!("Donor power path must not execute in native qualification")}
''' + region_methods + bundle_methods + '\n}\n}\n'
    root_values = [0xfffffc2000080000 + i * 0x4000 for i in range(7)]
    expected_root = bytearray(0xc8)
    struct.pack_into("<Q", expected_root, 0, native_identifier)
    for offset, value in zip([8, 0x18, 0x20, 0xa8, 0xb0, 0xb8, 0xc0], root_values):
        struct.pack_into("<Q", expected_root, offset, value)
    struct.pack_into("<IHBB", expected_root, 0x2c, 1, 0x4000, 14, 3)
    for i, (shift, entries) in enumerate([(36,64), (25,2048), (14,2048)]):
        off = 0x34 + i * 0x20
        expected_root[off:off+4] = bytes([8,14,14,shift])
        struct.pack_into("<HHQQQ", expected_root, off+4, entries, 0x4000, 1,
                         0x3ffffffc000, (entries-1) << shift)
    expected = bytearray([0xa5] * 0x2580)
    for slot, *fields in regs:
        struct.pack_into("<QQIIQI", expected, 0x640 + slot * 40, *fields)
    for cluster, groups in enumerate(contract["cluster_ladders"]):
        for state, group in enumerate(groups):
            struct.pack_into("<I", expected, 0x1008 + state * 0x40 + cluster * 4, group["core_voltage_raw"])
            struct.pack_into("<I", expected, 0x1408 + state * 0x40 + cluster * 4, group["sram_voltage_raw"])
    struct.pack_into("<I", expected, 0xe90, 0x6040)
    struct.pack_into("<I", expected, 0xea0, 1)
    struct.pack_into("<QQ", expected, 0x2560, 0x3db | 0x3db << 10, 0)
    bundle_path = ROOT / 'out/gpu-gravity-normal-boot-v5-source-evidence/native-bundle.json'
    assert pin(bundle_path)['sha256'] == '14f6f91b6a9827819a61303e6fcb163942477e95bc48d323f7f212805ef9a7fe'
    bundle = json.loads(bundle_path.read_text())
    assert bundle['macho']['sha256'] == expected_sha
    assert not bundle['bundle_complete'] and not bundle['hardware_actions']
    assert len(bundle['children']) == 23
    assert bundle['logical_bytes'] == 0x225c0 and bundle['backing_bytes'] == 0x24000
    assert bundle['main_bytes'] == 0x4c0 and int(bundle['main_offset'], 16) == 0x1e100
    base = int(re.search(r'BUNDLE_ADDRESS: u64 = ([^;]+);', fw_text)[1].replace('_',''),16)
    children = bundle['children']
    expected_children = '&[' + ','.join(
        'native_bundle::Child {cpu_owner:%d,mapping_owner:%d,offset:%d,bytes:%d}' %
        (int(c['cpu_owner'],16),int(c['mapping_owner'],16),int(c['offset'],16),c['bytes'])
        for c in children) + ']'
    main_offset = int(bundle['main_offset'],16)
    expected_main = bytearray([0xa5] * bundle['main_bytes'])
    main_ranges = []
    for field in bundle['main_pointer_fields']:
        child = children[field['child_index']]
        assert child['mapping_owner'] == field['mapping_owner'] and field['width'] == 8
        offset = int(field['offset'],16)
        struct.pack_into('<Q',expected_main,offset,base + int(child['offset'],16))
        main_ranges.append((offset,8))
    for field in bundle['main_literal_fields']:
        offset,width = int(field['offset'],16),field['width']
        expected_main[offset:offset+width] = field['value'].to_bytes(width,'little')
        main_ranges.append((offset,width))
    expected_preserved_bundle = bytearray([0xa5] * bundle['backing_bytes'])
    expected_preserved_bundle[main_offset:main_offset+len(expected_main)] = expected_main
    expected_zero_bundle = bytearray(bundle['backing_bytes'])
    hardware_ranges = [(0x640 + slot * 40,36) for slot,*fields in regs]
    for cluster,groups in enumerate(contract['cluster_ladders']):
        for state,group in enumerate(groups):
            hardware_ranges.extend([(0x1008+state*0x40+cluster*4,4),
                                    (0x1408+state*0x40+cluster*4,4)])
    hardware_ranges.extend([(0xe90,4),(0xea0,4),(0x2560,16)])
    for offset,width in hardware_ranges:
        expected_zero_bundle[offset:offset+width] = expected[offset:offset+width]
    for offset,width in main_ranges:
        expected_zero_bundle[main_offset+offset:main_offset+offset+width] = expected_main[offset:offset+width]
    # Numeric expected children and all output bytes derive from the frozen
    # native report; the test never calls the producer to create its expected data.
    bundle_tests = '''
    assert_eq!(native_bundle::CHILDREN.as_slice(),EXPECTED_CHILDREN);
    assert_eq!(native_bundle::LOGICAL_BYTES,0x225c0);
    assert_eq!(native_bundle::BACKING_BYTES,0x24000);
    assert_eq!(native_bundle::MAIN_OFFSET,0x1e100);
    assert_eq!(native_bundle::MAIN_BYTES,0x4c0);
    assert!(!native_bundle::BUNDLE_COMPLETE);
    let base=BASEu64;
    let layout=native_bundle::BundleLayout::new(base).unwrap();
    assert_eq!(layout.base(),base);
    for (index,child) in native_bundle::CHILDREN.iter().enumerate() {
        assert_eq!(layout.child_gpu_address(index),Some(base+child.offset as u64));
        assert_eq!(layout.address_for_mapping(child.mapping_owner),Some(base+child.offset as u64));
        assert_eq!(child.offset&63,0);
    }
    assert_eq!(layout.child_gpu_address(23),None);
    assert_eq!(layout.address_for_mapping(0xdead),None);
    assert_eq!(native_bundle::CHILDREN[7].bytes,0);
    assert_eq!(layout.child_gpu_address(7),layout.child_gpu_address(8));
    assert_eq!(layout.main_pointers().repeated,layout.main_pointers().header);
    assert_eq!(layout.main_gpu_address(),base+0x1e100);
    assert!(native_bundle::BundleLayout::new(base+1).is_none());
    assert!(native_bundle::BundleLayout::new(u64::MAX&!0x3fff).is_none());
    assert!(native_bundle::BundleLayout::new((u64::MAX&!0x3fff)-0x20000).is_none());
    let mut main=vec![0xa5;0x4c0];layout.write_main_component(&mut main).unwrap();
    assert_eq!(main.as_slice(),EXPECTED_MAIN);
    assert!(layout.write_main_component(&mut vec![0;0x4bf]).is_none());
    let mut main_extended=vec![0xa5;0x4c8];
    layout.main_pointers().write_component(&mut main_extended).unwrap();
    assert_eq!(&main_extended[0x4c0..],&[0xa5;8]);
    assert_eq!(&main[0x200..0x208],&[0xa5;8]);
    assert_eq!(&main[0x240..0x248],&[0xa5;8]);
    let mut whole=vec![0xa5;0x24000];layout.write_component(&mut whole).unwrap();
    assert_eq!(whole.as_slice(),EXPECTED_PRESERVED_BUNDLE);
    assert!(layout.write_component(&mut vec![0;0x23fff]).is_none());
    let mut extended=vec![0xa5;0x24008];layout.write_component(&mut extended).unwrap();
    assert_eq!(&extended[0x24000..],&[0xa5;8]);
    let native_root=native_root::RootPointers::bootstrap_for_platform(true).unwrap();
    let donor_root=native_root::RootPointers::bootstrap_for_platform(false).unwrap();
    assert_eq!(native_root.main_config,base+0x1e100);
    assert_eq!(donor_root.main_config,base+0x1da40);
    assert_eq!(native_root.region_a,donor_root.region_a);
    assert_eq!(native_root.region_c,donor_root.region_c);
    assert_eq!(native_root.status_a,donor_root.status_a);
    assert_eq!(native_root.status_b,donor_root.status_b);
    assert_eq!(&native_root.encode(true)[0x18..0x20],&(base+0x1e100).to_le_bytes());
    assert_eq!(&donor_root.encode(false)[0x18..0x20],&(base+0x1da40).to_le_bytes());
    assert_eq!(native_root::bundle_backing_bytes(true),0x24000);
    assert_eq!(native_root::bundle_backing_bytes(false),0x24000);
    platform.native_hardware=Some(native::Hardware::from_adt([0x3db,0x3db],15,true,core,sram).unwrap());
    let produced=platform.native_bundle_component().unwrap();
    assert_eq!(produced.as_slice(),EXPECTED_ZERO_BUNDLE);
    assert_eq!(&produced[0x28..0x30],&[0;8]);
    for entropy in [0,0x12345678,u32::MAX] {
        assert_eq!(platform.bundle(entropy),Err(actual_platform::ENOTSUPP));
    }
    platform.native_hardware=None;
    assert_eq!(platform.native_bundle_component(),Err(actual_platform::EINVAL));
'''
    replacements = {'EXPECTED_CHILDREN':expected_children,'BASE':str(base),
                    'EXPECTED_MAIN':array(expected_main),
                    'EXPECTED_PRESERVED_BUNDLE':array(expected_preserved_bundle),
                    'EXPECTED_ZERO_BUNDLE':array(expected_zero_bundle)}
    for name,value in replacements.items():
        bundle_tests = bundle_tests.replace(name,value)
    expected_steps = "[" + ",".join("[" + ",".join(
        "native::Step { low_mhz:%d, high_mhz:%d, low_index:%d, high_index:%d, core_voltage:%d, sram_voltage:%d }" %
        (g["frequency_low_mhz"], g["frequency_high_mhz"], g["index_low"], g["index_high"], g["core_voltage_raw"], g["sram_voltage_raw"])
        for g in groups) + "]" for groups in contract["cluster_ladders"]) + "]"
    tests = '''#[path = %s] mod native;
use native as g16_t6040;
#[path = %s] mod native_region_c;
use native_region_c as g16_t6040_region_c;
#[path = %s] mod native_bundle;
use native_bundle as g16_t6040_bundle;
%s
use native_root as g16_fw;
%s
fn main() {
    let core = %s; let sram = %s;
    let hardware = native::Hardware::from_adt([0x3db,0x3db], 15, true, core, sram).unwrap();
    assert_eq!(hardware.steps, %s);
    let mut out = [0xa5u8;0x2580]; hardware.write(&mut out).unwrap();
    assert_eq!(out.as_slice(), %s);
    assert_eq!(native::registers().len(), 22);
    for slot in native::UNRESOLVED_SLOTS { assert!(!native::registers().iter().any(|r|r.slot==*slot)); }
    assert_eq!(native::NATIVE_ABSENT_SLOTS, &[27]);
    let absent=native::registers().into_iter().find(|r|r.slot==27).unwrap();
    assert_eq!(absent,native::Register { slot:27,flags:2,..Default::default() });
    assert_eq!(&out[0xa78..0xa9c], &[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
        0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2,0,0,0]);
    let mut pages = std::collections::BTreeMap::new();
    native::pages(|page| -> Result<(),()> {
        assert_eq!(page.virtual_address & 0x3fff,0); assert_eq!(page.physical & 0x3fff,0);
        assert!(page.virtual_address < 0xfffffc2181400000);
        assert!(pages.insert(page.virtual_address,page).is_none()); Ok(())
    }).unwrap();
    assert_eq!(pages.len(),126); assert_eq!(pages.values().filter(|p|p.writable).count(),38);
    assert_eq!(pages[&(native::SGX_VIRTUAL+0xe1c000)].physical,native::SGX_PHYSICAL+0xe1c000);
    assert!(pages[&(native::SGX_VIRTUAL+0xe1c000)].writable);
    assert_eq!(pages[&(native::SGX_VIRTUAL+0xe20000)].physical,native::SGX_PHYSICAL+0xe20000);
    assert!(!pages[&(native::SGX_VIRTUAL+0xe20000)].writable);
    let counter=native::registers().into_iter().find(|r|r.slot==41).unwrap();
    let covered=(counter.address&!0x3fff)..((counter.address+u64::from(counter.size)+0x3fff)&!0x3fff);
    assert_eq!(covered.end-covered.start,0x8000);
    for address in covered.step_by(0x4000) { assert!(pages.contains_key(&address)); }
    assert!(!pages.values().any(|p|p.physical==native::SGX_PHYSICAL+0xd0c000));
    assert_eq!(native::MCC_STRIDE,0x18000);
    let mcc_ranges: [u64;4] = %s;
    for (i,physical) in mcc_ranges.iter().enumerate() { for page in 0..6u64 {
        let p=pages[&(0xfffffc2181280000+i as u64*0x18000+page*0x4000)];
        assert_eq!(p.physical,*physical+page*0x4000); assert!(!p.writable);
    }}
    for (base,pa) in [(0xfffffc2181240000u64,0x289000000u64),
                      (0xfffffc2181250000,0x288e08000)] { for page in 0..2u64 {
        let p=pages[&(base+page*0x4000)]; assert_eq!(p.physical,pa+page*0x4000);
        assert_eq!(p.writable,base==0xfffffc2181240000 && page==1);
    }}
    let mut emitted=0;
    assert_eq!(native::pages(|_| { emitted+=1; Err(73u8) }),Err(73));
    assert_eq!(emitted,1);
    for instance in 0..4u64 { for page in 0..16u64 {
        let p=pages[&(0xfffffc2181000000+instance*0x40000+page*0x4000)];
        assert_eq!(p.physical,0x28b000000+instance*0x200000+page*0x4000);
        assert_eq!(p.writable,page%%4==0);
    }}
    for r in native::registers() { if r.relative!=0 {
        assert_eq!(r.address-r.relative,native::SGX_VIRTUAL);
        assert_eq!(r.physical-r.relative,native::SGX_PHYSICAL);
    }}
    assert!(native::Hardware::from_adt([0,0x3db],15,true,core,sram).is_none());
    assert!(native::Hardware::from_adt([0x400,0x3db],15,true,core,sram).is_none());
    assert!(native::Hardware::from_adt([0x3db,0x3db],15,true,&core[..248],sram).is_none());
    let mut bad=core.to_vec(); bad[8]=1;
    assert!(native::Hardware::from_adt([0x3db,0x3db],15,true,&bad,sram).is_none());
    let mut changed=core.to_vec(); changed[140..144].copy_from_slice(&606u32.to_le_bytes());
    let changed=native::Hardware::from_adt([0x3db,0x3db],15,true,&changed,sram).unwrap();
    assert_eq!(changed.steps[0][1].core_voltage,610);
    assert_eq!(changed.steps[1][1].core_voltage,606);
    assert!(hardware.write(&mut [0u8;0x256f]).is_none());
    for mask in [0,3,16,255] { assert!(native::Hardware::from_adt([0x3db,0x3db],mask,true,core,sram).is_none()); }
    let off=native::Hardware::from_adt([0x3db,0x3db],15,false,core,sram).unwrap();
    let mut off_bytes=[0xa5u8;0x2580];off.write(&mut off_bytes).unwrap();
    out[0xea0..0xea4].fill(0); assert_eq!(out,off_bytes);
    let root=native_root::RootPointers { region_a:%s,main_config:%s,region_c:%s,
        status_a:%s,status_b:%s,extra_0:%s,extra_1:%s };
    let encoded=root.encode(true); assert_eq!(encoded.as_slice(),%s);
    let mut donor=encoded;donor[..8].copy_from_slice(&0x0c89c357839204b8u64.to_le_bytes());
    assert_eq!(root.encode(false),donor);
    assert!(native::write_root_interface(&mut [0u8;7],true).is_none());
    let mut isolated=[0xa5u8;16];native::write_root_interface(&mut isolated,true).unwrap();
    assert_eq!(&isolated[..8],&encoded[..8]);assert_eq!(&isolated[8..],&[0xa5;8]);
    assert_eq!(native_region_c::LOGICAL_BYTES,0xe58);
    assert_eq!(native_region_c::BACKING_BYTES,0x4000);
    assert!(!native_region_c::REGION_C_COMPLETE);
    let defaults=native_region_c::RegionC::from_adt(None,None).unwrap();
    assert_eq!(defaults,native_region_c::RegionC::native_defaults());
    let mut region=[0xa5u8;0x4000];defaults.write_component(&mut region).unwrap();
    assert_eq!(region.as_slice(),%s);
    assert!(defaults.write_component(&mut [0u8;0xe57]).is_none());
    defaults.write_component(&mut [0u8;0xe58]).unwrap();
    let mut extended=[0xa5u8;0x4008];defaults.write_component(&mut extended).unwrap();
    assert_eq!(&extended[0x4000..],&[0xa5;8]);
    for length in [0,1,3,5,8] {
        let bytes=vec![0;length];
        assert!(native_region_c::RegionC::from_adt(Some(&bytes),None).is_none());
        assert!(native_region_c::RegionC::from_adt(None,Some(&bytes)).is_none());
    }
    let gpu=0x01020304u32.to_le_bytes();let fender=u32::MAX.to_le_bytes();
    let overrides=native_region_c::RegionC::from_adt(Some(&gpu),Some(&fender)).unwrap();
    assert_eq!(overrides.gpu_idle_off_ms,0x01020304);assert_eq!(overrides.fender_idle_off_ms,u32::MAX);
    let mut override_bytes=[0xa5u8;0x4000];overrides.write_component(&mut override_bytes).unwrap();
    region[0x9b8..0x9bc].copy_from_slice(&gpu);region[0x9bc..0x9c0].copy_from_slice(&fender);
    assert_eq!(override_bytes,region);
    let mut platform=actual_platform::Platform {native_hardware:Some(
        native::Hardware::from_adt([0x3db,0x3db],15,true,core,sram).unwrap()),
        node:actual_platform::Node::empty(),maximum_power:12345};
    assert_eq!(platform.native_region_c_component().unwrap().as_slice(),%s);
    assert_eq!(platform.region_c(),Err(actual_platform::ENOTSUPP));
    platform.node.gpu=Some(gpu.to_vec());platform.node.fender=Some(fender.to_vec());
    let produced=platform.native_region_c_component().unwrap();
    assert_eq!(&produced[0x9b8..0x9bc],&gpu);assert_eq!(&produced[0x9bc..0x9c0],&fender);
    platform.node.gpu=Some(vec![0;3]);assert_eq!(platform.region_c(),Err(actual_platform::EINVAL));
    platform.node.gpu_error=Some(73);assert_eq!(platform.region_c(),Err(73));
    platform.node.gpu_error=None;platform.node.gpu=None;platform.node.fender_error=Some(74);
    assert_eq!(platform.region_c(),Err(74));
    platform.native_hardware=None;assert_eq!(platform.native_region_c_component(),Err(actual_platform::EINVAL));
    BUNDLE_TESTS
    println!("native v5: native 23-child allocation/Main pointers, whole component bytes, actual Platform producers/full-object rejection, selected native/donor root and allocation extents passed");
}
''' % (json.dumps(str(source / "g16_t6040.rs")),
       json.dumps(str(source / 'g16_t6040_region_c.rs')),
       json.dumps(str(source / 'g16_t6040_bundle.rs')),root_context, platform_context,
       array(core), array(sram), expected_steps,
       array(expected), "[" + ",".join(str(v) + "u64" for v in mcc_ranges) + "]",
       *(str(v) + "u64" for v in root_values), array(expected_root),
       array(expected_region), array(expected_zero_region))
    tests = tests.replace('    BUNDLE_TESTS', bundle_tests)
    rust = output / "native-tests.rs"
    rust.write_text(tests)
    commands = []
    for command in [["rustc", "--edition=2021", str(rust), "-o", str(output / "native-tests")],
                    [str(output / "native-tests")]]:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        commands.append({"command": command, "returncode": result.returncode,
                         "stdout": result.stdout, "stderr": result.stderr})
        (output / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        if result.returncode:
            raise RuntimeError("Native qualification failed; evidence preserved")
    platform_text = (source / "g16_platform.rs").read_text()
    power_text = (source / "g16_power.rs").read_text()
    runtime_text = (source / "g16.rs").read_text()
    assert "return Self::new_t6040(dev, profile)" in platform_text
    assert "native.write(&mut out).ok_or(EINVAL)?" in platform_text
    assert "crate::g16_t6040::pages(|page|" in runtime_text
    assert power_text.count("if self.native_hardware.is_some() { return Err(ENOTSUPP); }") == 1
    assert 'let out = self.native_bundle_component()?;' in power_text
    assert 'if !crate::g16_t6040_bundle::BUNDLE_COMPLETE { return Err(ENOTSUPP); }' in power_text
    assert "let out = self.native_region_c_component()?;" in platform_text
    assert "if !crate::g16_t6040_region_c::REGION_C_COMPLETE { return Err(ENOTSUPP); }" in platform_text
    assert "mod g16_t6040_region_c;" in (source / 'asahi_m4.rs').read_text()
    assert "apple,sgx-active-mcc-bit-vector" in platform_text
    assert "masks, active_mcc_mask, gpc, &core, &sram" in platform_text
    assert '&pointers.encode(native_t6040)' in runtime_text
    assert 'crate::g16_fw::bundle_backing_bytes(native_t6040)' in runtime_text
    assert 'let pointers = crate::g16_fw::RootPointers::bootstrap_for_platform(native_t6040)' in runtime_text
    assert 'if !native_t6040 {\n            bundle[0x28..0x30]' in runtime_text
    assert "write_root_interface(&mut out, native_t6040)" in (source / "g16_fw.rs").read_text()
    assert "normal_startup_implemented: false" in (source / "g16_profile.rs").read_text()
    report = {"schema": "m4rch.gravity-native-t6040-components.qualification.v5",
              "complete": True, "commands": commands,
              "inputs": [pin(p) for p in [pio_path, platform_path, afr_path, contract_path,
                  source / "g16_t6040.rs", source / "g16_platform.rs", source / "g16_power.rs",
                  source / "g16.rs", source / "g16_fw.rs", followup_path, interface_path,
                  counter_path, absent_path, flags_path, staging / 'stage-receipt.json',
                  KIT / 'stage_v5.py', source / 'g16_t6040_region_c.rs', source / 'asahi_m4.rs',
                  source / 'g16_t6040_bundle.rs', bundle_path,
                  region_path, rust, KIT / "qualify_v5.py"]],
              "native_descriptors": 22, "page_plan_pages": 126, "writable_pages": 38,
              "actual_root_bytes_compared": len(expected_root),
              "new_geometry_slots": [3,22,39,41], "native_absent_slots": [27], "unresolved_slots": [],
              "native_descriptor_flag_slots": [3,22,27,39,41],
              "native_region_c_logical_bytes": region['logical_bytes'],
              "native_region_c_backing_bytes_compared": len(expected_region),
              "actual_platform_native_region_c_methods_exercised": True,
              "region_c_complete": False, "of_input_bridge_installed": False,
              "bundle_complete": False,
              "native_bundle_logical_bytes": bundle['logical_bytes'],
              "native_bundle_backing_bytes_compared": bundle['backing_bytes'],
              "native_child_count": len(bundle['children']),
              "native_main_bytes_compared": bundle['main_bytes'],
              "native_zero_brn_header_alias_exercised": True,
              "actual_platform_native_bundle_methods_exercised": True,
              "actual_root_native_main_selection_exercised": True,
              "actual_firmware_allocation_size_selection_exercised": True,
              "donor_inline_timestamp_store_selected_for_native": False,
              "independent_cluster_steps": 22, "whole_output_bytes_compared": len(expected),
              "normal_startup_enabled": False, "full_module_compiled": False,
              "hardware_actions": [],
              "limitations": ["Native shared allocation and bounded Main pointer/literal fields are source-backed. Full bundle still rejects ENOTSUPP; complete hardware, power/channel/callback fields, native timestamp header production and Linux mapping-policy translation remain unqualified.",
                  "Region C allocation and bounded initial fields are native bindings. Full Region C still rejects ENOTSUPP; native power/controller/callback fields and Linux mapping-policy translation remain unqualified.",
                  "Optional raw idle-property OF bridge is specified but not installed into a device tree.",
                  "Slot27 absence and descriptor flags for slots3/22/27/39/41 are native producer bindings. Other descriptor flags and Linux PTE permissions are explicit experimental selections from earlier consumers; MCC/MTR and the counter's second page remain read-only until native policy is bound.",
                  "Partial native hardware-data fields only; full bundle, root/channel/work-cursor/power providers still unimplemented and reject T6040.",
                  "No GPU memory publication, reset, queue execution or pixels."]}
    (output / "qualification.json").write_text(json.dumps(report, indent=2) + "\n")
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("staging", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    report = qualify(arguments.staging.resolve(), arguments.output.resolve())
    print(json.dumps({"complete": report["complete"], "pages": report["page_plan_pages"]}))
