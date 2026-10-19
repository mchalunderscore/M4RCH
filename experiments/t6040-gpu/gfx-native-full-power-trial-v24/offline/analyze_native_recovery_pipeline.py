#!/usr/bin/env python3
"""Offline private source numeric pins, no hardware or full disassembly export."""
from pathlib import Path
import hashlib,json,re,struct
root=Path(__file__).resolve().parents[4]
image=Path('/boot/GPUC003/private-apple/com.apple.AGXG16X').read_bytes()
assert hashlib.sha256(image).hexdigest()=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
segments=[];off=32
for i in range(struct.unpack_from('<I',image,16)[0]):
 cmd,size=struct.unpack_from('<II',image,off)
 if cmd==25:
  vm,vs,fo,fs=struct.unpack_from('<QQQQ',image,off+24);segments.append((vm,vm+fs,fo))
 off+=size
def read(va,size):
 for lo,hi,fo in segments:
  if lo<=va and va+size<=hi:return image[fo+va-lo:fo+va-lo+size]
 raise ValueError(hex(va))
def virtual(slot,target):
 va=0xfffffe0007ea8678+slot;raw=struct.unpack('<Q',read(va,8))[0]
 decoded=0xfffffe0007004000+(raw&0xffffffff);assert decoded==target
 return dict(slot=slot,entry=va,raw=raw,target=target)
def pin(a,b):return dict(start=a,end=b,bytes=b-a,sha256=hashlib.sha256(read(a,b-a)).hexdigest())
base=0xfffffe0000000000
validator_mask,validator_capacity=struct.unpack('<QQ',read(base+0x712dd60,16))
assert (validator_mask,validator_capacity)==(0x2000ffd3,256)
report=dict(event_validator=dict(mask=validator_mask,capacity=validator_capacity,record_bytes=72,constant=base+0x712dd60,consumer_publish=base+0x89b7468,copy_before_dispatch=True,allocator_reply_kinds=[6,7]),schema='m4rch.native-recovery-pipeline.v10',hardware_actions=[],
 source_image_sha256=hashlib.sha256(image).hexdigest(),
 virtual_bindings=[virtual(s,base+t) for s,t in [(0x308,0x89c8a68),(0x1a8,0x89ca56c),(0x468,0x89c28b8),(0x480,0x89c27e8),(0x488,0x89c27c8),(0x470,0x89c2828),(0x208,0x89c9fb4),(0x210,0x89c9d9c)]],
 source_ranges=[pin(base+a,base+b) for a,b in [(0x8a0f9c0,0x8a0fa38),(0x8a11220,0x8a112a0),(0x89c8a68,0x89c8b70),(0x89b7360,0x89b747c),(0x89ad140,0x89ad168),(0x89a2ad4,0x89a2be8),(0x8963f74,0x8966ce0),(0x89c2778,0x89c2954),(0x89c9d9c,0x89ca29c),(0x89d1650,0x89d1658)]],
 shared_owner=dict(cpu_owner=0x960,gpu_owner=0x970,root_pointer_offset=0xb0,gravity_name='status_b',bytes=58432),
 ingress85=dict(packet=0x0085000000000000,ring_object_offset=0x16c0,consumer_offset=0,producer_offset=0x10,source_callers=[dict(call=base+0x8a0fa34,method='AGXSecureGart::unmapFromThisGart'),dict(call=base+0x8a1129c,method='AGXSecureGart::unmapWithAddress')],not_observed_before86_in_inspected_restart_caller=True),
 recovery_records=dict(offset=0x40b8,count=256,stride=8,valid_bit=0,stamp_index_shift=4,stamp_index_bits=7,stamp_value_offset=4,ta_match_mask=9),
 recovery_protocol=dict(offset=0x4900,pre_stopped=1,host_resume_pre=2,post_stopped=3,host_resume_post=0),
 caller_steps=[dict(call=base+a,slot=s,meaning=m) for a,s,m in [(0x8964010,0x1a8,'stop_for_host_inspection86'),(0x896664c,0x468,'resume_pre_recovery'),(0x8966690,0x488,'wait_post_recovery_stopped'),(0x89666f8,0x210,'process_TA_recovery_records'),(0x8966730,0x208,'process_firmware_recovery_records_when_enabled'),(0x8966bfc,0x470,'resume_post_recovery')]],
 recovery_failure_branch=dict(instruction=base+0x8964014,cleanup_target=base+0x8966ca0,apple_caller_recovery_aborts=True,linux_retained_shutdown='independent RTBuddy shutdown once; missing job recovery never admits fresh graph; crashed/nonrunningRTKit remains refused'),
 caller_generation_increment=base+0x8966534,
 firmware_reset_method_is_noop=True,
 conclusions=['86/getters alone are inspection, not the complete Apple recovery handshake',
 'The inspected restartWorkQueue path resumes existing firmware/shared graph through 1->2->3->0; it is not evidence that fresh CPU boot alone retires fixed VAs',
 'No explicit PMGR RESET31 call established in this function; indirect external vtable calls remain unresolved',
 'Recovery record job/error/fence processing remains necessary before claiming cancellation or completion',
 'TA flags9 restoration supports continuing existing Apple allocator backing; new Linux generation retains old backing and rejects same-generation reuse rather than pretending resource restoration',
 '85 ingress barrier is called after notifyNewUnmapping; it is not an established mandatory pre86 step in inspected restartWorkQueue caller'],
 integrated_candidate=dict(kernel_rtkit_managed_api=True,retained_cookie_and_native_drop=True,owned_pm_adapter=True,cold_DATA_restore='Linux hypothesis; not Apple source parity',pre_post_protocol_implemented=True),
 unresolved=['External recovery callback objects and queue/job record identities', 'Whether separate device-reset provider is called by a deeper power/recovery path', 'Retirement witness sufficient for fresh fixed-VA graph'])
out=root/'docs/evidence/2026-10-11-native-recovery-pipeline-v10.json';out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(report=str(out),virtual_bindings=len(report['virtual_bindings']),hardware_actions=[])))
