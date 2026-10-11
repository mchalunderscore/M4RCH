#!/usr/bin/env python3
"""Bind native event conversion and retained command-buffer completion metadata.

Offline stage transformation only. Numeric native sources are documented in the
receipt; no hardware completion or firmware-lifetime assertion is manufactured.
"""
import argparse,hashlib,json,shutil
from pathlib import Path
KIT=Path(__file__).resolve().parent
def pin(p):
 b=p.read_bytes();return dict(path=str(p.resolve()),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def stage(base,out):
 src=base/'source/linux/drivers/gpu/drm/asahi';dst=out/'source/linux/drivers/gpu/drm/asahi'
 out.mkdir(parents=True,exist_ok=False);shutil.copytree(src,dst)
 shutil.copyfile(KIT/'g16_t6040_event_timeline_v9.rs',dst/'g16_t6040_event_timeline_v9.rs')
 p=dst/'g16_runtime.rs';s=p.read_text()
 def replace(a,b):
  nonlocal s
  assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
 replace('''        // Real per-Work notifier storage is initialized without reusing donor
        // command bytes. The 94 count is conservative until FW clears it.
        let mut notifier_bytes=[0u8;0x100];notifier_bytes[..8].copy_from_slice(&a.event_count_array.to_le_bytes());
        notifier_bytes[8..12].copy_from_slice(&(a.fragment_stamp as u32).to_le_bytes());
        notifier_bytes[0x10..0x14].copy_from_slice(&0x50u32.to_le_bytes());
        notifier_bytes[0x24..0x28].copy_from_slice(&(a.context_id as u32).to_le_bytes());
        notifier_bytes[0x94..0x98].copy_from_slice(&2u32.to_le_bytes());
        fw.write_live(notifier,&notifier_bytes)?;fw.write_live(a.event_count_array,&2u32.to_le_bytes())?;''','''        // AGXCommandBuffer::nextCommandBufferState: one owned 0x100-byte
        // completion record, +0 counter FW alias, +8 queue-local ticket,
        // +0x10 configured numeric limit. Native initialization clears all counts;
        // firmware owns +0x94 and the external event counter after publication.
        // Linux selects a fresh record per Work; native default limit0x50 follows
        // allocation policy, not the source-derived record representation.
        let submitted_ordinal=queue.render_count.checked_sub(*crate::module_parameters::fw_counter_start.value()).ok_or(EINVAL)?;
        let ticket=submitted_ordinal.wrapping_add(1) as u32;
        let mut notifier_bytes=[0u8;0x100];
        notifier_bytes[..8].copy_from_slice(&a.event_count_array.to_le_bytes());
        notifier_bytes[8..12].copy_from_slice(&ticket.to_le_bytes());
        notifier_bytes[0x10..0x14].copy_from_slice(&0x50u32.to_le_bytes());
        fw.write_live(notifier,&notifier_bytes)?;fw.write_live(a.event_count_array,&0u32.to_le_bytes())?;''')
 replace('''        // LINUX_NATIVE_NOTIFIER_BINDING: actual retained allocations and queue
        // stamps, but initialized completion-field policy remains experimental.''','''        // Native metadata remains owned by this Work through firmware counts,
        // both driver stamps and transport retirement. Event and KSM identity
        // were checked above against the same retained queue's current state.
        let submitted_ordinal=queue.render_count.checked_sub(*crate::module_parameters::fw_counter_start.value()).ok_or(EINVAL)?;
        let ticket=submitted_ordinal.wrapping_add(1) as u32;
        let completion_payload=submitted_ordinal as u8;
        let completion_timeline=native_event.timeline | (u64::from(completion_payload)<<40);''')
 replace('''        putq(desc,if index==0{0xe30}else{0xab0},stage.shared_state_fw+0x100);''','''        if index==0 {
            // AGX3DWorkQueue::submitCommand binds two converted event stamps.
            // e30 and 14e8 are timestamp/payload words, never RAM pointers.
            putq(desc,0xe30,completion_timeline);putq(desc,0x14e8,completion_timeline);
        }else{
            // AGX3DCommandDescriptor::init clears both profiling slots. No
            // direct native producer was observed replacing these on this path.
            putq(desc,0xab0,0);putq(desc,0xab8,0);
        }''')
 replace('''completion_firmware:status_fw,x26:stage.driver_stamp_fw,w21:stamp,w22:event,''','''completion_firmware:status_fw,x26:stage.driver_stamp_fw,w21:stamp,w22:ticket,''')
 replace('''w21:stamp,w22:event,firmware_translations:pm::translations(v),''','''w21:stamp,w22:ticket,firmware_translations:pm::translations(v),''')
 replace('''                // LINUX_NATIVE_EVENT_EPOCHS starts both event banks at1;
                // driver event-machine initialization remains to be integrated.
                completion_firmware:status_fw,epochs:[1,1],capacity:state.capacity,''','''                // The active event bank's retained epoch feeds the native
                // converter. Its result equals the KSM submitted identity.
                completion_firmware:status_fw,epochs:[native_event.epoch;2],capacity:state.capacity,''')
 replace('''        // LINUX_NATIVE_EVENT_POLICY retains existing Gravity public-event stamp
        // progression until Apple notifier/event initialization is connected.''','''        // Retained event owner starts at stamp0x100 after native zero-init,
        // advances by0x100, and tracks rollover in the selected event bank.''')
 replace('''        // Native notifier gets its own uncached subrange, separate from native
        // command scratch at Work+200. Binding remains named Linux experiment.''','''        // One retained native command-buffer completion record plus its own
        // uncached event counter. Gravity owns allocation; native owns format.''')
 p.write_text(s)
 j=dict(schema='native-completion-stage-v10',base=str(base.resolve()),stage=str(out.resolve()),
  source_bindings=[dict(symbol='AGX3DWorkQueue::submitCommand',address='0xfffffe0008a2c518',writes={'0x14e8':'converted completion timeline plus channel payload<<40','0xe30':'converted TA event timeline plus channel payload<<40'}),
   dict(symbol='AGX3DChannel::getSKSMCompletionScratchRegPayload',address='0xfffffe00089d5a54',source='low byte of channel command counter204'),
   dict(symbol='AGXEventMachine::init',address='0xfffffe000899f664',record_stride=24,record_count=128,initial_stamp=0,positive_epoch=0,negative_epoch=-1),
   dict(symbol='AGXEventMachine::writeStamp',address='0xfffffe000899f564',stamp_step=256,epoch_update='increment selected bank on bit31 transition'),
   dict(symbol='AGXCommandBuffer::init',address='0xfffffe00089885c4',resource_bytes=0x2400,record_bytes=0x100,record_count=36,initial='all backing zero; per-record firstq retained event-counter firmware alias'),
   dict(symbol='AGXCommandDescriptor::loadCommandBufferData',address='0xfffffe0008987018',descriptor_188='command-buffer FW record3a0 indexed by state28',descriptor_190='CPU record280 indexed by state28'),
   dict(symbol='AGXCommandBuffer::nextCommandBufferState',address='0xfffffe0008987584',record_initial={'0':'event-counter firmware alias','8':'command-buffer queue-local ticket','0x10':'native default numeric limit0x50, accelerator718, no override','0x18':0,'0x94':0},counter_initial=0),
   dict(symbol='AGXAcceleratorG16::configureDevice',address='0xfffffe00089d9c08',accelerator_718_default=0x50,record_10_policy='f528 override or718; clamp bynonzerof530'),
   dict(symbol='AGXTAChannelG16::encodeTACommandSKUStream',address='0xfffffe00089e7394',w22='metadata CPU+8 ticket'),
   dict(symbol='AGX3DChannelG16::encode3DCommandSKUStream',address='0xfffffe00089d540c',w22='metadata CPU+8 ticket'),
   dict(symbol='AGX3DCommandDescriptor::init',address='0xfffffe000895dbc4',ab0_ab8='zero profiling slots; no fabricated FW state pointer')],
  linux_policy={'metadata_allocation':'one 0x100 record per retained Work instead of rotating36-slot command-buffer arena','ticket':'retained queue render_count minus initial plus1','initial_scheduler_counter':'requested fw_counter_start, equivalence to Apple accelerator ee48 unproved'},
  remaining=['Native positive/negative stamp bank initialization arithmetic is bound; kernel event progression is Linux owned','Native notifier FW list/accounting still requires hardware validation after whole integration','PM geometry/QoS/coremask policy remains separate source-integration work','No hardware operations performed'],source_files=[pin(q) for q in sorted(dst.rglob('*')) if q.is_file()])
 (out/'completion-stage-receipt.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(dict(stage=str(out),source_count=len(j['source_files']))))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();stage(a.base.resolve(),a.out.resolve())
