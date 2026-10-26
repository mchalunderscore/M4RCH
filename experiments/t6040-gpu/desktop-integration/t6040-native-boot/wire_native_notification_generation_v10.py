#!/usr/bin/env python3
"""Route RTKit/DRM wakeups and failures through their actual owned generation."""
from pathlib import Path
import re

def wiring(files):
    files['g16_notify.rs']=(Path(__file__).parent/'g16_notifications_v10.rs').read_text()
    s=files['g16.rs']
    marker='struct BootData {\n';assert s.count(marker)==1
    s=s.replace(marker,marker+'    notification_generation:u64,\n',1)
    marker='            BootData {\n';assert s.count(marker)==1
    s=s.replace(marker,marker+'                notification_generation:1,\n',1)
    s=s.replace('data.notifications.notify(false);','data.notifications.notify_generation(data.notification_generation,false);')
    s=s.replace('data.notifications.notify(true);','data.notifications.notify_generation(data.notification_generation,true);')
    before='''        let notifications=Arc::pin_init(Notifications::new(),GFP_KERNEL)?;
        let data=Arc::new(BootData{dev:self.bootstrap.dev.clone(),notifications:notifications.clone()},GFP_KERNEL)?;
        self.bootstrap._rtkit.as_mut().g16_rearm_retained(data)?;
        self.bootstrap.notifications=notifications;'''
    after='''        // Device, Bootstrap and every callback retain one shared hub. A
        // new epoch preserves old crash history and rejects stale callbacks.
        let notification_generation=self.bootstrap.native_application_generation.checked_add(1).ok_or(EOVERFLOW)?;
        let notifications=self.bootstrap.notifications.clone();
        let data=Arc::new(BootData{dev:self.bootstrap.dev.clone(),notifications:notifications.clone(),notification_generation},GFP_KERNEL)?;
        notifications.begin_generation(notification_generation)?;
        self.bootstrap._rtkit.as_mut().g16_rearm_retained(data)?;'''
    assert s.count(before)==1;s=s.replace(before,after)
    marker='''        self.open_control(dev.as_ref())?;
        // Only the fresh application's owner is admitted.'''
    assert s.count(marker)==1
    s=s.replace(marker,'''        self.open_control(dev.as_ref())?;
        self.notifications.commit_generation(generation)?;
        // Only the fresh application's owner is admitted.''',1)
    files['g16.rs']=s
    s=files['g16_drm.rs']
    s=s.replace('    failed: AtomicBool,','    failed_generation:AtomicU64,',1)
    s=s.replace('        failed: AtomicBool::new(false),','        failed_generation:AtomicU64::new(0),',1)
    marker='#[vtable]\nimpl drm::driver::Driver for Driver';assert s.count(marker)==1
    s=s.replace(marker,'''impl Data {
    fn generation_failed(&self)->bool {
        self.failed_generation.load(Ordering::Acquire)==self.notifications.current_generation()
    }
    fn mark_failed_generation(&self,generation:u64) {
        // A delayed old callback cannot erase a newer generation's failure.
        self.failed_generation.fetch_max(generation,Ordering::AcqRel);
    }
}

'''+marker,1)
    s=re.sub(r'([\w.]+)\.failed\.load\(Ordering::Acquire\)',r'\1.generation_failed()',s)
    replacements={
      'inner.device.failed.store(true, Ordering::Release);':'inner.device.mark_failed_generation(inner.generation);',
      'self.device.failed.store(true, Ordering::Release);':'self.device.mark_failed_generation(self.generation);',
      'this.device.failed.store(true, Ordering::Release);':'this.device.mark_failed_generation(failed_generation);',
      'job.execution.device.failed.store(true, Ordering::Release);':'job.execution.device.mark_failed_generation(job.execution.generation);'}
    for before,after in replacements.items():
        assert before in s,before;s=s.replace(before,after)
    marker='pub(crate) struct File {\n';assert s.count(marker)==1
    s=s.replace(marker,marker+'    generation:u64,\n',1)
    marker='                device: device.into(),\n';assert s.count(marker)==1
    s=s.replace(marker,marker+'                generation:device.notifications.current_generation(),\n',1)
    # Old File roots/GEM aliases belong to the retained application. An old
    # descriptor cannot unmap them or attach new commands to a fresh graph.
    marker='        let inner = file.inner();'
    head,tail=s.split(marker,1)
    tail='\n        if inner.generation!=inner.device.notifications.current_generation(){return;}'+tail
    tail=tail.replace(marker,marker+'\n        if inner.generation!=inner.device.notifications.current_generation(){return Err(ESTALE);}')
    s=head+marker+tail
    marker='impl PinnedDrop for File {\n    fn drop(self: Pin<&mut Self>) {';assert s.count(marker)==1
    s=s.replace(marker,marker+'''
        if self.generation!=self.device.notifications.current_generation() {
            core::mem::forget(self.state.clone());return;
        }''',1)
    marker='struct Execution {\n';assert s.count(marker)==1
    s=s.replace(marker,marker+'    generation:u64,\n',1)
    marker='            try_pin_init!(Execution {\n';assert s.count(marker)==1
    s=s.replace(marker,marker+'                generation:inner.generation,\n',1)
    marker='        let execution = &job.execution;';assert s.count(marker)==1
    s=s.replace(marker,marker+'''
        if execution.generation!=execution.device.notifications.current_generation() {
            execution.completion.set_error(ESTALE);let _=execution.completion.signal();return Err(ESTALE);
        }''',1)
    s=s.replace('execution.device.notifications.notify(false);','execution.device.notifications.notify_generation(execution.generation,false);')
    s=s.replace('job.execution.device.notifications.notify(false);','job.execution.device.notifications.notify_generation(job.execution.generation,false);')
    # The generic substring replacement above also matches job.execution.
    s=s.replace('job.execution.device.notifications.notify_generation(execution.generation,false);',
        'job.execution.device.notifications.notify_generation(job.execution.generation,false);')
    marker='''        let mut wake_result = Ok(());
        loop {'''
    assert s.count(marker)==1
    s=s.replace(marker,'''        let mut wake_result = Ok(());
        let mut wake_generation=this.device.notifications.current_generation();
        loop {
            let current=this.device.notifications.current_generation();
            if current!=wake_generation {wake_result=Ok(());wake_generation=current;}''',1)
    # Connect the actual whole recovery operation at the serialized terminal
    # error boundary. Never replay a job; old fences receive the original error.
    marker='''                runtime.poison();
                this.device.mark_failed_generation(failed_generation);'''
    assert s.count(marker)==1
    s=s.replace(marker,'''                let failed_generation=this.device.notifications.current_generation();
                let restarted=runtime.native_restart();
                if restarted.is_err(){runtime.poison();}
                runtime.native_finish_frontend_generation(failed_generation);
                this.device.mark_failed_generation(failed_generation);''',1)
    assert '.failed.' not in s
    files['g16_drm.rs']=s
    files['g16_runtime.rs']+='\nimpl Bootstrap {\n'+'\n    /// The frontend has terminally signalled every job from this generation.\n    /// Consume duplicate error delivery only; retain all old DMA owners.\n    pub(crate) fn native_finish_frontend_generation(&mut self,generation:u64) {\n        if self.native_application_generation==generation {\n            for flight in &mut self.flights {flight.native_recovery_reported=true;}\n        }\n        for old in &mut self.native_retained_applications {\n            if old.generation==generation {\n                for flight in &mut old.flights {flight.native_recovery_reported=true;}\n            }\n        }\n    }\n'+'\n}\n'
