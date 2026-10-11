#!/usr/bin/env python3
"""Compare compiled v7 shared bytes against the new native RAM producer evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def pin(path):
    b=path.read_bytes()
    return {'path':str(path.resolve()),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}


def qualify(evidence, output):
    report=json.loads(evidence.read_text())
    if report['schema'] != 'm4rch.native-t6040-shared-v7.source.v1':
        raise ValueError('Unexpected new shared source evidence')
    fixture=report['native_main_fixture']
    here=Path(__file__).resolve().parent
    output.mkdir(parents=True,exist_ok=False)
    rust=output/'probe.rs'
    rust.write_text('''#![allow(dead_code)]
#[path = "BUNDLE_PATH"] mod g16_t6040_bundle;
#[path = "SHARED_PATH"] mod shared;
use shared::*;
fn hex(b:&[u8])->String { use std::fmt::Write; let mut s=String::new(); for x in b { write!(&mut s,"{:02x}",x).unwrap(); } s }
fn main() {
 let top=NativeTopology::new(0x50000000,0x51000000,0x53000000,0x53004000,0x53008000).unwrap();
 let mut bundle=vec![0;g16_t6040_bundle::BACKING_BYTES];
 top.write_bundle_component(&mut bundle).unwrap();
 println!("main:{}",hex(&bundle[g16_t6040_bundle::MAIN_OFFSET..g16_t6040_bundle::MAIN_OFFSET+g16_t6040_bundle::MAIN_BYTES]));
 let mut support=vec![0;SUPPORT_BACKING_BYTES];
 top.write_support_component(&mut support,7).unwrap();
 println!("support:{}",hex(&support));
 for (i,c) in top.channels().iter().enumerate() { println!("channel:{}:{:x}:{:x}:{:x}:{:x}",i,c.state[0],c.state[1],c.state[2],c.ring); }
 for kind in [RxKind::Event,RxKind::Trace,RxKind::Auxiliary] {
  let r=top.rx(kind); println!("rx:{:x}:{:x}:{:x}:{:x}:{:x}:{:x}",r.state,r.ring,r.record_bytes,r.capacity,r.consumer(),r.producer());
 }
 let mut a=vec![0xa5;REGION_A_BACKING_BYTES];
 assert_eq!(write_region_a_component(&mut a),Some(24));
 assert!(a[..20].iter().all(|&x|x==0)); assert!(a[20..].iter().all(|&x|x==0xa5));
 println!("region_a:{}",hex(&a));
 let mut short_a=[0xa5;24]; assert_eq!(write_region_a_component(&mut short_a),None); assert_eq!(short_a,[0xa5;24]);
 let mut short_main=[0xa5;0x4c0]; assert_eq!(top.write_bundle_component(&mut short_main),None); assert_eq!(short_main,[0xa5;0x4c0]);
 let mut short_support=[0xa5;0x20]; assert_eq!(top.write_support_component(&mut short_support,7),None); assert_eq!(short_support,[0xa5;0x20]);
 for bad in [0x50000001, u64::MAX-0x3fff] { assert!(NativeTopology::new(bad,0x51000000,0x53000000,0x53004000,0x53008000).is_none()); }
 assert!(NativeTopology::new(0x50000000,0x51000000,0x51000000,0x53004000,0x53008000).is_none());
 let uat=core::array::from_fn(|i| (i as u8).wrapping_mul(37)); let root=top.root_pointers().encode(&uat);
 assert_eq!(&root[0x30..0x98],&uat); assert_eq!(u64::from_le_bytes(root[0xb0..0xb8].try_into().unwrap()),0x51000340);
 println!("root:{}",hex(&root));
 let n=NotificationPointers{state:0x56000000,entries:0x56004000};
 let mut nstate=[0xa5;0x20]; n.write_state(&mut nstate).unwrap();
 assert_eq!(&nstate[4..0x10],&[0xa5;12]); assert_eq!(&nstate[0x14..],&[0xa5;12]);
 top.write_notifications(&mut support,n).unwrap();
 assert_eq!(u64::from_le_bytes(support[0x340+0x48e0..0x340+0x48e8].try_into().unwrap()),0x56000000);
 assert_eq!(u64::from_le_bytes(support[0x340+0x48e8..0x340+0x48f0].try_into().unwrap()),0x56004000);
 println!("notifications_composed:true");
 assert_eq!(AonPtdLayout::new(0x56008000).unwrap().gpu_address(),0x56008000);
 assert_eq!(AON_PTD_LOGICAL_BYTES,0xe4); assert_eq!(AON_PTD_BACKING_BYTES,0x4000);
 println!("boundary_cases:6");
}
'''.replace('BUNDLE_PATH',str(here/'g16_t6040_bundle_v5.rs')).replace('SHARED_PATH',str(here/'g16_t6040_shared_v7.rs')))
    binary=output/'probe'
    built=subprocess.run(['rustc','--edition=2021','-D','warnings',str(rust),'-o',str(binary)],text=True,capture_output=True)
    if built.returncode: raise RuntimeError(built.stderr)
    ran=subprocess.run([str(binary)],text=True,capture_output=True,check=True)
    rows=[line.split(':') for line in ran.stdout.splitlines()]
    main=bytes.fromhex(next(row[1] for row in rows if row[0]=='main'))
    support=bytes.fromhex(next(row[1] for row in rows if row[0]=='support'))
    if main.hex()!=fixture['main_hex']: raise ValueError('Compiled Main differs from actual native RAM producer')
    if hashlib.sha256(support).hexdigest()!=fixture['support_sha256']:
        raise ValueError('Compiled support initialization differs from actual native RAM producer')
    channels=[[int(v,16) for v in row[2:]] for row in rows if row[0]=='channel']
    if channels!=fixture['channels']: raise ValueError('Compiled selected topology differs')
    region_a=bytes.fromhex(next(row[1] for row in rows if row[0]=='region_a'))
    if hashlib.sha256(region_a).hexdigest()!=report['region_a_fixture']['sha256']:
        raise ValueError('Compiled Region A differs from complete native prepareFirmwareForBoot')
    root=bytes.fromhex(next(row[1] for row in rows if row[0]=='root'))
    if root[0x28:0x98].hex()!=report['root_fixture']['copied_root_28_98_hex']:
        raise ValueError('Compiled Root differs from actual native UAT payload copy')
    rx=[[int(v,16) for v in row[1:]] for row in rows if row[0]=='rx']
    validators={r['host_owner']:r for r in fixture['RX_validators']}
    for own,values in zip(('0x800','0x7a0','0x7d0'),rx):
        src=validators[own]
        expected=[src['state'],src['ring'],src['record_bytes'],src['capacity'],src['state'],src['state']+32]
        if values!=expected: raise ValueError('Compiled RX topology differs from actual native constructor')
    results={'schema':'m4rch.native-t6040-shared-v7.qualification.v1',
        'source_evidence':pin(evidence),'component':pin(here/'g16_t6040_shared_v7.rs'),
        'composed_frozen_bundle':pin(here/'g16_t6040_bundle_v5.rs'),
        'compiled_main_equal_actual_native':True,'main_bytes':len(main),
        'compiled_support_equal_actual_native':True,'support_bytes':len(support),
        'selected_channels_equal_actual_native':17,'rx_validators_equal_actual_native':3,
        'boundary_cases':6,'region_a_terminator_padding_preserved':True,
        'compiled_region_a_equal_actual_native':True,
        'compiled_root_UAT_copy_equal_actual_native':True,
        'saved_notification_proof':pin(Path('docs/evidence/2026-10-08-native-notify-root.json')),
        'native_AONPTD_geometry_equal':report['AONPTD_allocation']['logical_bytes']==0xe4 and report['AONPTD_allocation']['backing_bytes']==0x4000,
        'root_UAT_payload_preserved':104,'root_UAT_constructor_executed':False,
        'native_services':fixture['services'],'hardware_actions':[],
        'private_instruction_bytes_exported':False,'normal_startup_qualified':False,
        'required_closure':['native UAT payload producer binding','Linux page-table permissions',
            'live publication and synchronization','complete native Main dynamic fields',
            'firmware boot acknowledgement and actual command execution']}
    (output/'qualification.json').write_text(json.dumps(results,indent=2)+'\n')
    return results


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('source_evidence',type=Path)
    cli.add_argument('output',type=Path)
    args=cli.parse_args()
    result=qualify(args.source_evidence,args.output)
    print(json.dumps({k:v for k,v in result.items() if k.endswith('actual_native') or k in ('boundary_cases','hardware_actions')}))
