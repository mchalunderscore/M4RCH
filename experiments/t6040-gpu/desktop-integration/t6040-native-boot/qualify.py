#!/usr/bin/env python3
"""Exercise the actual native Rust component against saved numeric evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
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
    expected = bytearray([0xa5] * 0x2580)
    for slot, *fields in regs:
        struct.pack_into("<QQIIQI", expected, 0x640 + slot * 40, *fields)
    for cluster, groups in enumerate(contract["cluster_ladders"]):
        for state, group in enumerate(groups):
            struct.pack_into("<I", expected, 0x1008 + state * 0x40 + cluster * 4, group["core_voltage_raw"])
            struct.pack_into("<I", expected, 0x1408 + state * 0x40 + cluster * 4, group["sram_voltage_raw"])
    struct.pack_into("<I", expected, 0xe90, 0x6040)
    struct.pack_into("<QQ", expected, 0x2560, 0x3db | 0x3db << 10, 0)
    expected_steps = "[" + ",".join("[" + ",".join(
        "native::Step { low_mhz:%d, high_mhz:%d, low_index:%d, high_index:%d, core_voltage:%d, sram_voltage:%d }" %
        (g["frequency_low_mhz"], g["frequency_high_mhz"], g["index_low"], g["index_high"], g["core_voltage_raw"], g["sram_voltage_raw"])
        for g in groups) + "]" for groups in contract["cluster_ladders"]) + "]"
    tests = '''#[path = %s] mod native;
fn main() {
    let core = %s; let sram = %s;
    let hardware = native::Hardware::from_adt([0x3db,0x3db], core, sram).unwrap();
    assert_eq!(hardware.steps, %s);
    let mut out = [0xa5u8;0x2580]; hardware.write(&mut out).unwrap();
    assert_eq!(out.as_slice(), %s);
    assert_eq!(native::registers().len(), 17);
    for slot in native::UNRESOLVED_SLOTS { assert!(!native::registers().iter().any(|r|r.slot==*slot)); }
    let mut pages = std::collections::BTreeMap::new();
    native::pages(|page| -> Result<(),()> {
        assert_eq!(page.virtual_address & 0x3fff,0); assert_eq!(page.physical & 0x3fff,0);
        assert!(page.virtual_address < 0xfffffc2181400000);
        assert!(pages.insert(page.virtual_address,page).is_none()); Ok(())
    }).unwrap();
    assert_eq!(pages.len(),97); assert_eq!(pages.values().filter(|p|p.writable).count(),37);
    for instance in 0..4u64 { for page in 0..16u64 {
        let p=pages[&(0xfffffc2181000000+instance*0x40000+page*0x4000)];
        assert_eq!(p.physical,0x28b000000+instance*0x200000+page*0x4000);
        assert_eq!(p.writable,page%%4==0);
    }}
    for r in native::registers() { if r.relative!=0 {
        assert_eq!(r.address-r.relative,native::SGX_VIRTUAL);
        assert_eq!(r.physical-r.relative,native::SGX_PHYSICAL);
    }}
    assert!(native::Hardware::from_adt([0,0x3db],core,sram).is_none());
    assert!(native::Hardware::from_adt([0x400,0x3db],core,sram).is_none());
    assert!(native::Hardware::from_adt([0x3db,0x3db],&core[..248],sram).is_none());
    let mut bad=core.to_vec(); bad[8]=1;
    assert!(native::Hardware::from_adt([0x3db,0x3db],&bad,sram).is_none());
    let mut changed=core.to_vec(); changed[140..144].copy_from_slice(&606u32.to_le_bytes());
    let changed=native::Hardware::from_adt([0x3db,0x3db],&changed,sram).unwrap();
    assert_eq!(changed.steps[0][1].core_voltage,610);
    assert_eq!(changed.steps[1][1].core_voltage,606);
    assert!(hardware.write(&mut [0u8;0x256f]).is_none());
    println!("native component: saved full bytes/22 cluster steps/17 descriptors/97 pages and seven independent input/guard checks passed");
}
''' % (json.dumps(str(source / "g16_t6040.rs")), array(core), array(sram), expected_steps, array(expected))
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
    assert power_text.count("if self.native_hardware.is_some() { return Err(ENOTSUPP); }") == 2
    assert "if self.native_hardware.is_some() { return Err(ENOTSUPP); }" in platform_text
    assert "normal_startup_implemented: false" in (source / "g16_profile.rs").read_text()
    report = {"schema": "m4rch.gravity-native-t6040-components.qualification.v1",
              "complete": True, "commands": commands,
              "inputs": [pin(p) for p in [pio_path, platform_path, afr_path, contract_path,
                  source / "g16_t6040.rs", source / "g16_platform.rs", source / "g16_power.rs",
                  source / "g16.rs", rust, KIT / "qualify.py"]],
              "native_descriptors": 17, "page_plan_pages": 97, "writable_pages": 37,
              "independent_cluster_steps": 22, "whole_output_bytes_compared": len(expected),
              "normal_startup_enabled": False, "full_module_compiled": False,
              "hardware_actions": [],
              "limitations": ["Descriptor flags/PTE permissions are explicit experimental selections from earlier consumers, not a complete native policy.",
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
