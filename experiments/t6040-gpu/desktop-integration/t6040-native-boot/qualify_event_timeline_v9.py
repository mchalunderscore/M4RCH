#!/usr/bin/env python3
"""Offline integration check for source-native event-to-scheduler arithmetic."""
from pathlib import Path
import hashlib,json,subprocess,tempfile
kit=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='m4rch-event-timeline-') as t:
 p=Path(t)/'main.rs'
 p.write_text('#[path="'+str(kit/'g16_t6040_ksm_work_v8.rs')+'"] mod g16_t6040_ksm_work_v8;\n#[path="'+str(kit/'g16_t6040_event_timeline_v9.rs')+'"] mod event;\n'+'fn main(){let mut cases=0;for initial in [0u64,1,255,256,0xfffffeff]{for ordinal in [0u64,1,2,254,255,256,257,0x7ffffe,0x7fffff,0x800000,0xfffffe,0xffffff,0x1000000,0x1ffffff]{let x=event::identity(initial,ordinal).unwrap();assert_eq!(x.timeline,(initial+ordinal)&((1u64<<40)-1));assert_eq!(x.previous,x.timeline.wrapping_sub(1)&((1u64<<40)-1));assert_eq!(x.event,((ordinal+1)as u32).wrapping_shl(8));cases+=1;}let mut ts=initial;for ordinal in 0..1024{let x=event::identity(initial,ordinal).unwrap();assert_eq!(x.timeline,ts);ts=g16_t6040_ksm_work_v8::convert_timestamp(x.epoch,x.event.wrapping_add(256),256,initial).unwrap();cases+=1;}}assert!(event::identity(0,u64::MAX).is_none());println!("{cases} native converter/timeline cases passed");}\n')
 subprocess.run(['rustc','--edition=2021','-Awarnings',str(p),'-o',str(Path(t)/'check')],check=True)
 r=subprocess.run([str(Path(t)/'check')],check=True,capture_output=True,text=True)
 report={'schema':'m4rch.native-event-timeline-check.v9','cases':5190,'result':r.stdout.strip(),'hardware_actions':[],
 'scope':'Actual Rust converter and joined identity compared against independently closed-form one-entry/ordinal policy at sign/rollover boundaries; no event callback or hardware completion proof.',
 'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in [kit/'g16_t6040_ksm_work_v8.rs',kit/'g16_t6040_event_timeline_v9.rs']}}
 output=kit.parents[3]/'docs/evidence/2026-10-11-native-event-timeline-v9.json'
 output.write_text(json.dumps(report,indent=2)+'\n');print(output)
