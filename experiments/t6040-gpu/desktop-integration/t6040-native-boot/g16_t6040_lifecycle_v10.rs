// SPDX-License-Identifier: GPL-2.0-only
//! Native lifecycle caller order, separate from DMA retirement permission.
//! Hardware adapters must supply fresh observations. No BUSY-clear write exists.
use kernel::prelude::*;


#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Phase { Running, Quiescing, OffIntent, OffRetained, OnIntent, Booting, Quarantined }

#[derive(Clone, Copy, Debug)]
pub(crate) struct ProviderState { pub word:u32, pub domain_on:bool }
impl ProviderState {
    pub(crate) fn actual(self)->u32 {(self.word>>4)&15}
    pub(crate) fn target(self)->u32 {self.word&15}
    pub(crate) fn busy(self)->bool {self.word&0x800!=0}
    pub(crate) fn valid(self)->bool {self.word!=u32::MAX}
    // Gravity's provider returns success on ACTUAL alone. Require TARGET as
    // well for lifecycle admission, and expose BUSY separately without hiding
    // it or granting retirement on ordinary provider transition completion.
    pub(crate) fn provider_off(self)->bool {
        self.valid()&&!self.domain_on&&self.actual()==0&&self.target()==0
            &&self.word&0x90001400==0
    }
    pub(crate) fn strict_off(self)->bool {self.provider_off()&&!self.busy()}
    pub(crate) fn active(self)->bool {
        self.valid()&&self.domain_on&&self.actual()==15&&self.target()==15
            &&self.word&0x80001400==0
    }
}

pub(crate) struct Lifecycle {
    pub phase:Phase, pub generation:u64, pub old_owners_quarantined:bool,
    pub off:Option<ProviderState>, pub management_ack:bool,
    pub restart_attempted:bool,
    pub recovery_generation:u64, pub recovery_request_attempted:bool,
    pub recovery_error:Option<kernel::error::Error>, pub teardown_error:Option<kernel::error::Error>,
}
impl Lifecycle {
    pub(crate) const fn new()->Self {Self {phase:Phase::Running,generation:1,
        old_owners_quarantined:false,off:None,management_ack:false,restart_attempted:false,
        recovery_generation:0,recovery_request_attempted:false,recovery_error:None,teardown_error:None}}
    pub(crate) fn submission_allowed(&self)->bool {self.phase==Phase::Running&&!self.old_owners_quarantined}
    pub(crate) fn quarantine(&mut self) {self.phase=Phase::Quarantined;self.old_owners_quarantined=true;}
    pub(crate) fn begin_quiesce(&mut self)->Result {
        if self.restart_attempted || !matches!(self.phase,Phase::Running|Phase::Quarantined){return Err(EBUSY);}
        self.phase=Phase::Quiescing;self.old_owners_quarantined=true;Ok(())
    }
    /// Entire ordered transition. A failure consumes the phase, retains every
    /// old owner and cannot replay a previously published request. Adapters
    /// must implement native operations, not route these hooks to donor SLEEP.
    pub(crate) fn restart<O:Operations>(&mut self,ops:&mut O)->Result {
        self.begin_quiesce()?;
        self.restart_attempted=true;
        let result=self.restart_inner(ops);
        if result.is_err(){self.quarantine();}
        result
    }
    fn restart_inner<O:Operations>(&mut self,ops:&mut O)->Result {
        // Stalled work requires Apple recovery inspection86 and generation
        // response, or another fully source-bound recovery adapter. An idle
        // bool/control counter alone is not pending-job cancellation.
        let recovery=ops.quiesce_submissions_and_recover_pending()
            .and_then(|()|ops.publish_idle_policy_and_wait())
            .and_then(|()|ops.drain_transport());
        self.recovery_error=recovery.as_ref().err().copied();
        // Apple's recovery caller aborts when inspection fails. Independently
        // source-bound RTBuddy shutdown remains useful for retained power-down.
        // It cannot turn a failed recovery into fresh graph admission.
        let teardown=self.stop_retained(ops);
        self.teardown_error=teardown.as_ref().err().copied();
        if let Some(error)=self.recovery_error{return Err(error);}
        teardown?;
        self.start_fresh(ops)
    }
    fn stop_retained<O:Operations>(&mut self,ops:&mut O)->Result {
        self.management_ack=match ops.request_powergate_202_once() {
            Ok(())=>true,
            Err(error) if error==ETIMEDOUT => {ops.native_nmi_on_clean_timeout()?;false},
            Err(error)=>return Err(error),
        };
        ops.stop_cpu_fresh()?;
        ops.disable_fender_fresh()?;
        self.phase=Phase::OffIntent;
        ops.coordinate_off_once()?;
        ops.pm_put_once()?;
        let off=ops.provider_snapshot()?;
        self.off=Some(off);
        if !off.provider_off(){return Err(EIO);}
        self.phase=Phase::OffRetained;
        Ok(())
    }
    fn start_fresh<O:Operations>(&mut self,ops:&mut O)->Result {
        // BUSY remains visible, and strict_off may remain false. The source
        // supports a new retained-owner provider ON experiment; it does not
        // support releasing old pages, clearing BUSY, or reusing their queues.
        self.phase=Phase::OnIntent;
        ops.pm_get_once()?;
        if !ops.provider_snapshot()?.active(){return Err(EIO);}
        ops.coordinate_on_once()?;
        self.phase=Phase::Booting;
        ops.fresh_rtbuddy_data_boot_and_ap_handshake()?;
        let next=self.generation.checked_add(1).ok_or(EOVERFLOW)?;
        ops.fresh_application_generation(next)?;
        self.generation=next;
        // Old generation still quarantined. The replacement session owns new
        // Work/VM/notifier/queues and its own Lifecycle; never unseal this one.
        self.phase=Phase::OffRetained;
        Ok(())
    }
}

pub(crate) trait Operations {
    fn quiesce_submissions_and_recover_pending(&mut self)->Result;
    fn publish_idle_policy_and_wait(&mut self)->Result;
    fn drain_transport(&mut self)->Result;
    fn request_powergate_202_once(&mut self)->Result;
    fn native_nmi_on_clean_timeout(&mut self)->Result;
    fn stop_cpu_fresh(&mut self)->Result;
    fn disable_fender_fresh(&mut self)->Result;
    fn coordinate_off_once(&mut self)->Result;
    fn pm_put_once(&mut self)->Result;
    fn provider_snapshot(&mut self)->Result<ProviderState>;
    fn pm_get_once(&mut self)->Result;
    fn coordinate_on_once(&mut self)->Result;
    fn fresh_rtbuddy_data_boot_and_ap_handshake(&mut self)->Result;
    fn fresh_application_generation(&mut self,generation:u64)->Result;
}

/// Provider transitions belong to the caller's owned runtime-PM session and
/// paired native coordinate manager. Firmware/ASC work remains RTKit-owned.
pub(crate) trait Provider {
    fn held(&self)->bool;
    fn coordinate_off_once(&mut self)->Result;
    fn put_once(&mut self)->Result;
    fn snapshot(&mut self)->Result<ProviderState>;
    fn get_once(&mut self)->Result;
    fn coordinate_on_once(&mut self)->Result;
}
