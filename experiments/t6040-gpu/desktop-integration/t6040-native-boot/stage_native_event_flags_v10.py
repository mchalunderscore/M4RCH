#!/usr/bin/env python3
"""Replace core masks with source-derived ordinary KSM event-flag masks."""
import argparse,hashlib,json,shutil
from pathlib import Path
KIT=Path(__file__).resolve().parent
def pin(p):
 b=p.read_bytes();return dict(path=str(p.resolve()),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def stage(base,out):
 src=base/'source/linux/drivers/gpu/drm/asahi';dst=out/'source/linux/drivers/gpu/drm/asahi'
 out.mkdir(parents=True,exist_ok=False);shutil.copytree(src,dst)
 shutil.copyfile(KIT/'g16_t6040_event_flags_v10.rs',dst/'g16_t6040_event_flags_v10.rs')
 p=dst/'asahi_m4.rs';s=p.read_text();assert s.count('mod g16_vm;')==1
 s=s.replace('mod g16_vm;','#[allow(dead_code)] mod g16_t6040_event_flags_v10;\nmod g16_vm;');p.write_text(s)
 p=dst/'g16_runtime.rs';s=p.read_text()
 before='''            // LINUX_NATIVE_MASK_PLACEMENT supplies actual topology masks in
            // the first two mask words; Apple's scheduling policy is unbound.
            masks:[self.topology.core_masks[0],self.topology.core_masks[1],0,0],auxiliary:stage.shared_state_fw};'''
 after='''            // Native ordinary KSM event flags: RegionC e1c is initialized0,
            // these Parameters enable no optional descriptor owner, and the
            // accelerator PPP policy uses bit16 only (byte6d7 remains0).
            // Shader-core masks belong to topology/register programming.
            masks:crate::g16_t6040_event_flags_v10::ordinary(
                crate::g16_t6040_event_flags_v10::Inputs{firmware_e1c:0,
                    descriptor_optional_owner:false,accelerator_6d7:0}),
            auxiliary:stage.shared_state_fw};'''
 assert s.count(before)==1;s=s.replace(before,after)
 s=s.replace('''        // LINUX_QOS_RECORD_POLICY currently selects0/16/0; real topology masks
        // come from this device's retained ADT-derived profile.''','''        // QOS still comes from this backend's requested scheduling policy;
        // event flags above derive from the serialized native configuration.''')
 p.write_text(s)
 j=dict(schema='native-event-flags-integration-v10',base=str(base.resolve()),stage=str(out.resolve()),
  native_type='AGFIKSMEventFlagMask',wire_words=['128','130','138','140'],
  source_bindings=[dict(symbol='AGX3DChannelSKSM::submitBuffer',range=['0xfffffe000895bfdc','0xfffffe000895c038'],initial=[0,0,0,0],last_word_bits={'63':'firmware380/e1c bit0','62':'descriptor470 nonnull','61':'accelerator6d7 low2 nonzero'}),
   dict(symbol='AGXTAChannelSKSM::submitBuffer',range=['0xfffffe0008a1fc5c','0xfffffe0008a1fcbc'],initial=[0,0,0,0],last_word_bits={'63':'firmware380/e1c bit0','62':'descriptorfd0 nonnull','61':'accelerator6d7 low2 nonzero'}),
   dict(symbol='AGXKSMKickQueueG16::encodeKickEntry',address='0xfffffe00089db230',argument='AGFIKSMEventFlagMask const reference copies four64bit words'),
   dict(symbol='AGXAcceleratorG16X::halSetEventFlags',address='0xfffffe00089e7f00',register_base='21108',words=4),
   dict(symbol='AGXAcceleratorG16X::halResetEventFlags',address='0xfffffe00089e7f60',register_base='21128',words=4)],
  active_providers=dict(firmware_e1c=0,firmware_e1c_source='g16_t6040_region_c_v4::INITIAL_U8_FIELDS native initializer',optional_descriptor_owner=False,optional_descriptor_owner_source='current ordinary Parameters exclude this owner',accelerator_6d7=0,accelerator_6d7_source='current serialized accelerator policy includes requiredPPPbit16; topbytezero'),
  removed='Incorrect percluster physicalshader masks in KSM eventflagwords',
  remaining=['Preserve these same provider inputs if optional command owners or firmwaree1c configuration are subsequently enabled','Hardware completion and wake flags remain unproved'],
  hardware_actions=[],source_files=[pin(q) for q in sorted(dst.rglob('*')) if q.is_file()])
 (out/'event-flags-stage-receipt.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(dict(stage=str(out),source_count=len(j['source_files']))))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();stage(a.base.resolve(),a.out.resolve())
