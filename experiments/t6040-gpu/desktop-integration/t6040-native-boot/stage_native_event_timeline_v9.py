#!/usr/bin/env python3
"""Compose native event/scheduler identity into an existing Gravity caller stage."""
import argparse,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('base',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
assert not a.output.exists();shutil.copytree(a.base,a.output)
root=a.output/'source/linux/drivers/gpu/drm/asahi';kit=Path(__file__).resolve().parent
(root/'g16_t6040_event_timeline_v9.rs').write_bytes((kit/'g16_t6040_event_timeline_v9.rs').read_bytes())
mod=root/'asahi_m4.rs';s=mod.read_text();assert 'mod g16_vm;' in s;s=s.replace('mod g16_vm;', 'mod g16_t6040_event_timeline_v9;\nmod g16_vm;');mod.write_text(s)
f=root/'g16_runtime.rs';s=f.read_text()
old='''        a.tiling_stamp=u64::from(g16_stamp::value(ordinal,0xc00));
        a.fragment_stamp=u64::from(g16_stamp::value(ordinal,0x100));'''
new='''        let native_event=crate::g16_t6040_event_timeline_v9::identity(
            *crate::module_parameters::fw_counter_start.value(),
            ordinal.checked_sub(*crate::module_parameters::fw_counter_start.value()).ok_or(EINVAL)?).ok_or(EINVAL)?;
        a.tiling_stamp=u64::from(native_event.event);
        a.fragment_stamp=u64::from(native_event.event);'''
assert s.count(old)==1;s=s.replace(old,new)
old='''            previous:state.cached_previous.unwrap_or(state.timestamp.wrapping_sub(1)&ksm::TIMESTAMP_MASK),'''
new='''            previous:state.cached_previous.unwrap_or(native_event.previous),'''
assert s.count(old)==1;s=s.replace(old,new)
# Derive from the actual retained queue ordinal before any record mutation.
needle='''        let mut scheduler=ksm::Bindings{timestamp:state.timestamp,queue_id:state.queue_id,'''
replacement='''        let native_event=crate::g16_t6040_event_timeline_v9::identity(
            *crate::module_parameters::fw_counter_start.value(),
            queue.render_count.checked_sub(*crate::module_parameters::fw_counter_start.value()).ok_or(EINVAL)?).ok_or(EINVAL)?;
        if native_event.event!=stamp || native_event.timeline!=state.timestamp {return Err(EINVAL);}
        let mut scheduler=ksm::Bindings{timestamp:state.timestamp,queue_id:state.queue_id,'''
assert s.count(needle)==1;s=s.replace(needle,replacement)
f.write_text(s)
# Composed stage intentionally awaits notifier agent's epoch/binding repair.
receipt={'schema':'m4rch.native-event-timeline-stage.v9','base':str(a.base.resolve()),'output':str(a.output.resolve()),'hardware_actions':[],
 'scope':'Both stage event ordinals and native scheduler previous/current checked; completion descriptor/envelope epoch composition required separately.',
 'files':{str(x.relative_to(root)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [f,mod,root/'g16_t6040_event_timeline_v9.rs']}}
(a.output/'event-timeline-stage.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
