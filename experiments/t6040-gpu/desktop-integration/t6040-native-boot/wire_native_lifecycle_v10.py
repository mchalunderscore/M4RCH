#!/usr/bin/env python3
"""Compose native lifecycle into the Gravity caller. No device operations.

Owns managed RTKit adapters and retained runtime-PM provider integration.
"""
from pathlib import Path

def wiring(files):
    module='g16_t6040_lifecycle_v10'
    files[module+'.rs']=(Path(__file__).parent/(module+'.rs')).read_text()
    s=files['asahi_m4.rs']
    marker='mod g16_vm;'
    assert s.count(marker)==1 and module not in s
    files['asahi_m4.rs']=s.replace(marker,'#[allow(dead_code)] mod '+module+';\n'+marker)
    s=files['g16.rs']
    def replace(a,b):
        nonlocal s
        assert s.count(a)==1,(a,s.count(a))
        s=s.replace(a,b)
    replace('    transport: crate::g16_transport::Transport,',
            '    transport: crate::g16_transport::Transport,\n    native_lifecycle: crate::'+module+'::Lifecycle,\n    native_lifecycle_history: KVec<crate::'+module+'::Lifecycle>,\n    native_cold_data: Option<NativeColdData>,\n    native_recovery_event_packets: KVec<[u32;18]>,\n    native_recovery_allocator_reply_pending: bool,')
    replace('            _sgx: sgx, transport,',
            '            _sgx: sgx, transport,\n            native_lifecycle: crate::'+module+'::Lifecycle::new(),\n            native_lifecycle_history: KVec::new(), native_cold_data,\n            native_recovery_event_packets: KVec::new(), native_recovery_allocator_reply_pending:false,')
    replace('        let shutdown = self._rtkit.as_mut().shutdown();',
            '''        // Native shutdown is source-bound202/NMI/CPU/Fender/PMGR, not
        // the donor RTKit SLEEP path. No new power operation runs from Drop.
        let shutdown = if self.transport.native_t6040 {
            self.native_lifecycle.quarantine(); Err(ENOTSUPP)
        } else { self._rtkit.as_mut().shutdown() };''')
    replace('            core::mem::forget(core::mem::replace(&mut self.tvb_pools, KVec::new()));',
            '''            core::mem::forget(core::mem::replace(&mut self.tvb_pools, KVec::new()));
            // These are separate native owners, not contained in donor TVB.
            // Their Drop would release scene/frame mappings and retained
            // client address spaces even when flights were already empty.
            core::mem::forget(core::mem::replace(&mut self.native_pm_pools, KVec::new()));
            core::mem::forget(core::mem::replace(&mut self.native_pm_owners, KVec::new()));''')
    marker='impl Bootstrap {\n'
    # Insert a real caller hook, under the existing exclusive frontend owner.
    assert s.count(marker)==1
    s=s.replace(marker,marker+'''
    pub(crate) fn native_restart(&mut self)->Result {
        if !self.transport.native_t6040{return Err(ENOTSUPP);}
        if self.native_lifecycle.restart_attempted{return Err(EBUSY);}
        self.native_lifecycle_history.reserve(1,GFP_KERNEL)?;
        let mut provider=self.native_pm_session.take().ok_or(EIO)?;
        let mut lifecycle=core::mem::replace(&mut self.native_lifecycle,
            crate::g16_t6040_lifecycle_v10::Lifecycle::new());
        self.native_lifecycle.quarantine();
        self.render_failed=true;
        let recovery_generation=lifecycle.recovery_generation;
        if !self.flights.is_empty(){lifecycle.recovery_request_attempted=true;}
        let mut adapter=NativeLifecycleAdapter{bootstrap:self,provider:&mut provider,
            recovery_generation,stopped:false,ack:false,off:None};
        let result=lifecycle.restart(&mut adapter);
        self.native_pm_session=Some(provider);
        dev_info!(self.dev.as_ref(),"G16: retained lifecycle phase={:?} recovery_error={:?} teardown_error={:?} off={:?}\\n",
            lifecycle.phase,lifecycle.recovery_error,lifecycle.teardown_error,lifecycle.off);
        if result.is_ok() {
            let generation=lifecycle.generation;
            self.native_lifecycle_history.push(lifecycle,GFP_KERNEL)?;
            self.native_lifecycle=crate::g16_t6040_lifecycle_v10::Lifecycle::new();
            self.native_lifecycle.generation=generation;
        } else {self.native_lifecycle=lifecycle;}
        result
    }
''',1)
    marker='        let mut rtkit = KBox::pin('
    assert s.count(marker)==1
    s=s.replace(marker,'        let native_cold_data=if native_t6040 {Some(NativeColdData::capture(dev)?)}else{None};\n'+marker)
    marker='        rtkit.as_mut().set_early_crashlog();'
    assert s.count(marker)==1
    s=s.replace(marker,marker+'\n        if transport.native_t6040 {rtkit.as_mut().g16_own_retained()?;}')
    s+='\n'+(Path(__file__).parent/'native_lifecycle_caller_v10.rs.inc').read_text()
    files['g16.rs']=s
    s=files['g16_runtime.rs']
    marker='''    pub(crate) fn poison(&mut self) {
        self.render_failed = true;
    }'''
    assert s.count(marker)==1
    s=s.replace(marker,'''    pub(crate) fn poison(&mut self) {
        self.render_failed = true;
        if self.transport.native_t6040 {self.native_lifecycle.quarantine();}
    }''')
    marker='''    ) -> Result<Receipt> {
        let mut queue = queues.lock();'''
    # Both render and compute admission may have the same common prefix.
    count=s.count(marker)
    assert count>=1
    s=s.replace(marker,'''    ) -> Result<Receipt> {
        if self.transport.native_t6040 && !self.native_lifecycle.submission_allowed() {
            return Err(EBUSY);
        }
        let mut queue = queues.lock();''')
    marker='    fn service_flights(&mut self) -> Result {'
    assert s.count(marker)==1
    s=s.replace(marker,"""    /// Recovery consumes a copied event before dispatch, like Apple's
    /// RingValidator. This never acknowledges allocator requests, retires
    /// jobs, writes successful stamps, or returns credits.
    pub(super) fn native_recovery_drain(&mut self)->Result {
        if !self.transport.native_t6040{return Err(ENOTSUPP);}
        self.native_recovery_event_packets.reserve(256,GFP_KERNEL)?;
        let state=self.transport.event.state;let ring=self.transport.event.ring;
        for _ in 0..256 {
            let fw=self._firmware_space.as_mut().ok_or(EIO)?;
            let cursor=fw.read_u32(state)?;let producer=fw.read_u32(state+0x20)?;
            if cursor>=256 || producer>=256{return Err(EIO);}
            if cursor==producer{break;}
            let mut packet=[0u32;18];let base=ring+u64::from(cursor)*0x48;
            for (index,word) in packet.iter_mut().enumerate(){*word=fw.read_u32(base+index as u64*4)?;}
            // Copy/retain precedes the only consumer publication. Ring bytes
            // remain useful after the firmware overwrites a consumed slot.
            self.native_recovery_event_packets.push(packet,GFP_KERNEL)?;
            // Native AGXFirmware event-validator mask comes from qword
            // 0x712dd60 loaded at89ad150:0x2000ffd3, capacity256.
            // Preserve invalid bytes, but do not bypass its kind validation.
            if packet[0]>=64 || (0x2000_ffd3u64>>packet[0])&1==0{return Err(EPROTO);}
            if matches!(packet[0],6|7){self.native_recovery_allocator_reply_pending=true;}
            fw.write_live(state,&((cursor+1)&255).to_le_bytes())?;
            crate::mem::sync();
        }
        self.drain_trace_rx()
    }

"""+marker)
    files['g16_runtime.rs']=s
