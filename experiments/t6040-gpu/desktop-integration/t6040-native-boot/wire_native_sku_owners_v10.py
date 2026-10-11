#!/usr/bin/env python3
"""Bind native SKU startup fields to ordinary Gart policy and notifier ticket.

AGXGartG16 vtable +0x1e0 -> 0xfffffe00089dc65c returns +0x2c9 bit0,
AGXGart::isHWSoftFaultEnabled. TA 0x89e7394..739c and 3D
0x89d540c..5414 load descriptor+0x190 metadata+8 as the second u32.
The retained Linux owner installs resident pages and no hardware-soft-fault
service, so the former input is false. The latter is the actual owned ticket.
"""
def wiring(files):
    for name in ('g16_t6040_ta_sku_v9.rs','g16_t6040_fragment_sku_v9.rs'):
        s=files[name]
        s=s.replace('pub resource_type:u32','pub hardware_soft_fault_enabled:bool')
        s=s.replace('pub context_id:u32','pub notifier_ticket:u32')
        s=s.replace('b.resource_type','u32::from(b.hardware_soft_fault_enabled)')
        s=s.replace('b.context_id','b.notifier_ticket')
        if name=='g16_t6040_ta_sku_v9.rs':
            s=s.replace('pub state:u64, pub counter:u64,','pub state:u64,')
            s=s.replace('b.counter','u64::from(w(command,0x8ce))')
        files[name]=s
    name='g16_runtime.rs';s=files[name]
    before='resource_type:0,context_id:a.context_id as u32,resource_map:status,'
    after='hardware_soft_fault_enabled:false,notifier_ticket:ticket,resource_map:status,'
    assert s.count(before)==1;s=s.replace(before,after)
    before='resource_type:0,resource_map:status,context_id:a.context_id as u32,'
    after='hardware_soft_fault_enabled:false,resource_map:status,notifier_ticket:ticket,'
    assert s.count(before)==1;s=s.replace(before,after)
    before='state:stage.shared_state_fw+0x100,counter:v.counter_firmware,'
    after='state:stage.shared_state_fw+0x100,'
    assert s.count(before)==1;s=s.replace(before,after)
    before='context:envelope_context,serial:self.render_publication,counter:queue.render_count as u32,'
    after='context:envelope_context,serial:self.render_publication,counter:submitted_ordinal as u32,'
    assert s.count(before)==1;s=s.replace(before,after)
    event_binding="""        let native_event=crate::g16_t6040_event_timeline_v9::identity(
            *crate::module_parameters::fw_counter_start.value(),
            queue.render_count.checked_sub(*crate::module_parameters::fw_counter_start.value()).ok_or(EINVAL)?).ok_or(EINVAL)?;
        if native_event.event!=stamp || native_event.timeline!=state.timestamp {return Err(EINVAL);}
"""
    assert s.count(event_binding)==1
    s=s.replace(event_binding,'',1)
    marker='        // Native metadata remains owned by this Work through firmware counts,'
    assert s.count(marker)==1
    s=s.replace(marker,event_binding+marker,1)
    files[name]=s
