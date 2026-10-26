// SPDX-License-Identifier: GPL-2.0-only
//! One frontend wakeup owner, with immutable generation identity per callback.
use kernel::sync::{CondVar,CondVarTimeoutResult,Mutex};
use kernel::{prelude::*,time::msecs_to_jiffies};
#[pin_data]
pub(crate) struct Notifications {
    #[pin] state:Mutex<State>,
    #[pin] changed:CondVar,
}
#[derive(Clone,Copy)]
struct Epoch { id:u64,crashed:bool }
struct State { sequence:u64,active:Epoch,retired:KVec<Epoch>,pending:Option<Epoch> }
impl Notifications {
    pub(crate) fn new()->impl PinInit<Self> {
        pin_init!(Self {state<-kernel::new_mutex!(State{sequence:0,
            active:Epoch{id:1,crashed:false},retired:KVec::new(),pending:None}),changed<-kernel::new_condvar!()})
    }
    pub(crate) fn current_generation(&self)->u64 {self.state.lock().active.id}
    /// Retain the previous crash tombstone. No old crashed flag is cleared.
    /// Called under exclusive Bootstrap/engine ownership before fresh boot.
    pub(crate) fn begin_generation(&self,generation:u64)->Result {
        let mut state=self.state.lock();
        if generation!=state.active.id.checked_add(1).ok_or(EOVERFLOW)?{return Err(EINVAL);}
        if state.pending.is_some(){return Err(EBUSY);}
        state.retired.reserve(1,GFP_KERNEL)?;
        state.pending=Some(Epoch{id:generation,crashed:false});Ok(())
    }
    /// Commit only after the fresh graph and opening control are accepted.
    pub(crate) fn commit_generation(&self,generation:u64)->Result {
        let mut state=self.state.lock();
        let next=state.pending.ok_or(EINVAL)?;
        if next.id!=generation{return Err(EINVAL);}
        if next.crashed{return Err(EIO);}
        let previous=state.active;state.retired.push(previous,GFP_KERNEL)?;
        state.pending=None;state.active=next;
        state.sequence=state.sequence.wrapping_add(1);self.changed.notify_one();Ok(())
    }
    /// Scheduler-only wakeup for the currently admitted generation.
    pub(crate) fn notify(&self,crashed:bool) {
        let mut state=self.state.lock();state.active.crashed|=crashed;
        state.sequence=state.sequence.wrapping_add(1);self.changed.notify_one();
    }
    /// RTKit and scheduler callbacks carry the generation they actually own.
    pub(crate) fn notify_generation(&self,generation:u64,crashed:bool) {
        let mut state=self.state.lock();
        if generation!=state.active.id {
            if let Some(next)=state.pending.as_mut().filter(|next|next.id==generation){next.crashed|=crashed;return;}
            if let Some(old)=state.retired.iter_mut().find(|old|old.id==generation){old.crashed|=crashed;}
            return;
        }
        state.active.crashed|=crashed;state.sequence=state.sequence.wrapping_add(1);
        self.changed.notify_one();
    }
    pub(crate) fn snapshot(&self)->Result<u64> {
        let state=self.state.lock();if state.active.crashed{return Err(EIO);}Ok(state.sequence)
    }
    pub(crate) fn wait(&self,sequence:u64,timeout_ms:u32)->Result {
        let mut remaining=msecs_to_jiffies(timeout_ms.max(1));let mut state=self.state.lock();
        while state.sequence==sequence&&!state.active.crashed {
            remaining=match self.changed.wait_interruptible_timeout(&mut state,remaining) {
                CondVarTimeoutResult::Woken{jiffies}|CondVarTimeoutResult::Signal{jiffies}=>jiffies,
                CondVarTimeoutResult::Timeout=>{
                    if state.sequence==sequence&&!state.active.crashed{return Err(ETIMEDOUT);}break;
                }
            };
        }
        if state.active.crashed{return Err(EIO);}Ok(())
    }
}
