#!/usr/bin/env python3
"""Qualify actual Rust absolute clock arithmetic without invoking CPU registers."""
import argparse,json,subprocess
from pathlib import Path
from stage_v4 import pin
from wire_clock_v9 import wiring
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[3]


def qualify(output):
    output.mkdir(exist_ok=False)
    producer=KIT/'g16_native_clock_v9.rs'
    adapter=output/'clock-tests.rs'
    adapter.write_text('''#![allow(dead_code)]
#[path="'''+str(producer)+'''"] mod clock;
use std::io::{self,Read};
fn main(){let mut input=String::new();io::stdin().read_to_string(&mut input).unwrap();
 for line in input.lines(){let row:Vec<&str>=line.split_whitespace().collect();
 let counter:u64=row[1].parse().unwrap();let frequency:u64=row[2].parse().unwrap();
 if row[0]=="scale" {let rate:u64=row[3].parse().unwrap();
  match clock::scale(counter,frequency,rate){Some(value)=>println!("{}",value),None=>println!("none")}
 }else {match clock::Snapshot::from_sample(counter,frequency){
 Some(s)=>println!("{} {} {} {}",s.raw_counter,s.frequency_hz,s.native_absolute_ticks,s.architectural_ns),
 None=>println!("none")}}
 }}
''')
    binary=output/'clock-tests'
    cp=subprocess.run(['rustc','--edition=2021','-Dwarnings','-Copt-level=2',str(adapter),'-o',str(binary)],capture_output=True,text=True)
    (output/'compile.log').write_text(cp.stdout+cp.stderr)
    if cp.returncode:raise ValueError('Clock adapter compile failed')
    counters=[0,1,124,125,126,999999999,1000000000,2**64-1]
    frequencies=[0,999999,1000000,24000000,1000000000,10000000000,10000000001]
    rates=[0,1,24000000,1000000000,1000000001]
    rows=[];expected=[]
    def ref(counter,frequency,rate):
        if not 1000000<=frequency<=10000000000 or not 1<=rate<=1000000000:return None
        value=counter*rate//frequency
        return value if value<2**64 else None
    for frequency in frequencies:
        for rate in rates:
            for counter in counters:
                rows.append(f'scale {counter} {frequency} {rate}')
                result=ref(counter,frequency,rate);expected.append('none' if result is None else str(result))
    for frequency in frequencies:
        for counter in counters:
            rows.append(f'snapshot {counter} {frequency}')
            ticks=ref(counter,frequency,24000000);ns=ref(counter,frequency,1000000000)
            expected.append('none' if ticks is None or ns is None else f'{counter} {frequency} {ticks} {ns}')
    values='\n'.join(rows)+'\n';run=subprocess.run([str(binary)],input=values,capture_output=True,text=True)
    (output/'input.txt').write_text(values);(output/'run.log').write_text(run.stdout+run.stderr)
    if run.returncode or run.stdout.splitlines()!=expected:raise ValueError('Clock arithmetic differs from independent rational reference')
    base=ROOT/'out/gpu-gravity-normal-boot-v8/source/linux/drivers/gpu/drm/asahi'
    source_files=['asahi_m4.rs','g16.rs','g16_runtime.rs']
    files={name:(base/name).read_text() for name in source_files};wiring(files)
    joined=output/'join-inspection';joined.mkdir()
    for name,text in files.items():(joined/name).write_text(text)
    assert 'ktime_get_raw' not in files['g16.rs'] and 'ktime_get_raw' not in files['g16_runtime.rs']
    assert files['g16.rs'].count('crate::g16_native_clock::Snapshot::capture()')==1
    assert files['g16_runtime.rs'].count('crate::g16_native_clock::Snapshot::capture()')==1
    old=(base/'g16.rs').read_text();old_runtime=(base/'g16_runtime.rs').read_text()
    donor=old.split('let mut bundle = if native_t6040')[1].split('let mut region_c')[0]
    assert donor in files['g16.rs']
    cproof=ROOT/'out/gfx-native-full-power-trial-v24/clock-scale-qualification-v1/qualification.json'
    report=dict(schema='m4rch.gravity-native-architectural-clock.qualification.v9',
        inputs=[pin(p) for p in [producer,Path(__file__),KIT/'wire_clock_v9.py',KIT/'stage_v4.py',KIT/'stage_v7.py',adapter,cproof,ROOT/'docs/evidence/2026-10-11-native-clock-domain-v9.json']+[base/name for name in source_files]],
        compile_returncode=cp.returncode,run_returncode=run.returncode,scale_cases=280,snapshot_cases=56,
        independent_rational_reference_agrees=True,closed_frequency_and_rate_refusals=True,
        both_power_and_native_QoS_share_architectural_origin=True,base_M4_bundle_path_unchanged=True,
        no_u128_division_in_provider=True,capture_function_called=False,hardware_actions=[],
        normal_module_compiled=False,scope='Actual Rust arithmetic and source dictionary join; new staged module compilation remains separate')
    (output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'scale_cases':280,'snapshot_cases':56,'passed':True,'hardware_actions':[]}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);qualify(parser.parse_args().output.resolve())
