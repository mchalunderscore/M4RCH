// Cold DATA restore is a Linux recovery hypothesis, not Apple API parity.
// It replaces only the loader-owned firmware reserved region, after CPUstop
// and owned OFF/ON. No allocator backing or application generation is freed.
struct NativeColdData { map:io::mem::Mem, bytes:KVec<u8> }
impl NativeColdData {
    fn capture(dev:&kernel::device::Device)->Result<Self> {
        let res=dev.of_node().ok_or(EINVAL)?
            .reserved_mem_region_to_resource_byname(c_str!("firmware"))?;
        if res.size()!=0x138000 || res.start()&0x3fff!=0{return Err(EINVAL);}
        // SAFETY: Loader-owned reserved backing; caller verified cold ASC.
        let map=unsafe {io::mem::Mem::try_new(res,io::mem::MemFlag::WB.into())?};
        let mut bytes=KVec::new();bytes.reserve(map.size(),GFP_KERNEL)?;
        for off in (0..map.size()).step_by(64) {
            unsafe {core::arch::asm!("dc civac, {addr}",addr=in(reg) map.ptr().add(off));}
        }
        crate::mem::sync();
        for off in 0..map.size() {bytes.push(unsafe {map.ptr().add(off).read_volatile()},GFP_KERNEL)?;}
        Ok(Self{map,bytes})
    }
    fn restore(&mut self)->Result {
        if self.bytes.len()!=self.map.size(){return Err(EIO);}
        for (off,value) in self.bytes.iter().enumerate() {
            unsafe {self.map.ptr().add(off).write_volatile(*value);}
        }
        for off in (0..self.map.size()).step_by(64) {
            unsafe {core::arch::asm!("dc cvac, {addr}",addr=in(reg) self.map.ptr().add(off));}
        }
        crate::mem::sync();Ok(())
    }
}

// SPDX-License-Identifier: GPL-2.0-only
impl Bootstrap {
    /// Source-bound recovery inspection, not cancellation/free permission.
    fn native_inspect_pending(&mut self, generation:u64)->Result {
        if !self.transport.native_t6040 || !self.render_failed{return Err(EBUSY);}
        let fw=self._firmware_space.as_ref().ok_or(EIO)?;
        if fw.read_u64(self.transport.roots.status_b+0x48f0)?!=generation{return Err(EBUSY);}
        let next=generation.checked_add(1).ok_or(EOVERFLOW)?;
        if generation>0x0000_0fff_ffff_ffff{return Err(EOVERFLOW);}
        // Apple AGXArmFirmwareASC vtable1d8 -> getNumDeviceRecoveries;
        // slot1e0 -> stoppedForHostRecovery. Both refer to support child13,
        // CPUowner960/GPUowner970/root+b0, not the small root+20 RegionC.
        self._rtkit.as_mut().send_message(0x21,0x0086_0000_0000_0000|generation)?;
        for _ in 0..2000 {
            self.native_recovery_drain()?;
            let fw=self._firmware_space.as_ref().ok_or(EIO)?;
            if fw.read_u64(self.transport.roots.status_b+0x48f0)?==next {
                if fw.read_u32(self.transport.roots.status_b+0x4910)?==0{return Err(EIO);}
                return self.native_finish_recovery_protocol(next);
            }
            kernel::time::delay::fsleep(kernel::time::Delta::from_millis(1));
        }
        Err(ETIMEDOUT)
    }

    /// Apple restartWorkQueue uses the existing shared graph: PRE1 -> host2
    /// -> POST3 -> host0. Host errors are attributed while firmware is stopped
    /// at POST3; this is not physical-page retirement or successful rendering.
    fn native_finish_recovery_protocol(&mut self,next:u64)->Result {
        let base=self.transport.roots.status_b;
        let mut pre=false;
        for _ in 0..2000 {
            self.native_recovery_drain()?;
            let fw=self._firmware_space.as_ref().ok_or(EIO)?;
            if fw.read_u64(base+0x48f0)?!=next{return Err(ESTALE);}
            if fw.read_u32(base+0x4900)?==1 {pre=true;break;}
            kernel::time::delay::fsleep(kernel::time::Delta::from_millis(1));
        }
        if !pre{return Err(ETIMEDOUT);}
        self._firmware_space.as_mut().ok_or(EIO)?.write_live(base+0x4900,&2u32.to_le_bytes())?;
        crate::mem::sync();
        let mut post=false;
        for _ in 0..2000 {
            self.native_recovery_drain()?;
            if self._firmware_space.as_ref().ok_or(EIO)?.read_u32(base+0x4900)?==3 {post=true;break;}
            kernel::time::delay::fsleep(kernel::time::Delta::from_millis(1));
        }
        if !post{return Err(ETIMEDOUT);}
        self.native_attribute_recovery_records(next)?;
        self._firmware_space.as_mut().ok_or(EIO)?.write_live(base+0x4900,&0u32.to_le_bytes())?;
        crate::mem::sync();Ok(())
    }

    fn native_idle_policy(&mut self)->Result {
        let fw=self._firmware_space.as_mut().ok_or(EIO)?;
        let guard=self._sgx.try_access().ok_or(ENODEV)?;
        let old=read_cursor(&self.transport,fw,&guard,12,2)?;
        let read=read_cursor(&self.transport,fw,&guard,12,0)?;
        let prefetch=read_cursor(&self.transport,fw,&guard,12,1)?;
        if old>=256 || read!=old || prefetch!=old{return Err(EBUSY);}
        let consumed=fw.read_u32(self.transport.roots.status_b+0xe438)?;
        let assertion=fw.read_packed_u32(self.transport.roots.region_c+0xe51)?;
        if consumed!=assertion{return Err(EBUSY);}
        let next=(old+1)&255;
        let mut record=[0u8;64];record[..4].copy_from_slice(&10u32.to_le_bytes());
        record[4..8].copy_from_slice(&1u32.to_le_bytes());
        fw.write_live(self.transport.channels[12].ring+u64::from(old)*64,&record)?;
        assert_control(&self.transport,fw,10)?;
        write_cursor(&self.transport,fw,&guard,12,2,next)?;
        crate::mem::sync();drop(guard);
        self._rtkit.as_mut().send_message(0x21,0x0084_0000_0000_0000)?;
        let expected=consumed.wrapping_add(1);
        for _ in 0..2000 {
            self.native_recovery_drain()?;
            let fw=self._firmware_space.as_ref().ok_or(EIO)?;
            let done=fw.read_u32(self.transport.roots.status_b+0xe438)?==expected
                && fw.read_u32(self.transport.cursor(12,0).ok_or(EINVAL)?)?==next
                && fw.read_u32(self.transport.cursor(12,1).ok_or(EINVAL)?)?==next;
            if done {
                // This is command processing. GPUstatus1 persisting is recorded
                // separately and does not prevent native recovery202/NMI.
                return Ok(());
            }
            kernel::time::delay::fsleep(kernel::time::Delta::from_millis(1));
        }
        Err(ETIMEDOUT)
    }

    fn native_disable_fender(&mut self)->Result {
        let guard=self._sgx.try_access().ok_or(ENODEV)?;
        let io=guard.relaxed();let before=io.read32(0xd06030);
        if before==u32::MAX{return Err(EIO);}
        io.write32(before|4,0xd06030);
        if io.read32(0xd06030)!=before|4{return Err(EIO);}
        crate::mem::sync();Ok(())
    }
}

/// Firmware/ASC half of the actual combined adapter. PM/coordinate ownership
/// is supplied by the caller's retained Session, never an unowned raw write.
struct NativeLifecycleAdapter<'a,P:crate::g16_t6040_lifecycle_v10::Provider> {
    bootstrap:&'a mut Bootstrap, provider:&'a mut P,
    recovery_generation:u64, stopped:bool, ack:bool,
    off:Option<crate::g16_t6040_lifecycle_v10::ProviderState>,
}
impl<P:crate::g16_t6040_lifecycle_v10::Provider>
    crate::g16_t6040_lifecycle_v10::Operations for NativeLifecycleAdapter<'_,P> {
    fn quiesce_submissions_and_recover_pending(&mut self)->Result {
        if !self.provider.held(){return Err(EBUSY);}
        if !self.bootstrap.flights.is_empty(){self.bootstrap.native_inspect_pending(self.recovery_generation)?;}
        Ok(())
    }
    fn publish_idle_policy_and_wait(&mut self)->Result {self.bootstrap.native_idle_policy()}
    fn drain_transport(&mut self)->Result {self.bootstrap.native_recovery_drain()}
    fn request_powergate_202_once(&mut self)->Result {
        if !self.provider.held(){return Err(EBUSY);}
        let guard=self.bootstrap._asc.try_access().ok_or(ENODEV)?;
        // SAFETY: Devres guard owns the entire ASC aperture; provider reference
        // is held and Bootstrap mutex excludes all GPU submissions.
        let ack=unsafe {self.bootstrap._rtkit.as_mut().g16_powergate(guard.addr(),0x4000)}?;
        self.stopped=true;self.ack=ack;
        // The kernel API executes native202/NMI/CPUstop as one serialized
        // transaction. These follow-up hooks validate that consumed result.
        if ack {Ok(())} else {Err(ETIMEDOUT)}
    }
    fn native_nmi_on_clean_timeout(&mut self)->Result {
        if self.stopped&&!self.ack{Ok(())}else{Err(EIO)}
    }
    fn stop_cpu_fresh(&mut self)->Result {if self.stopped{Ok(())}else{Err(EIO)}}
    fn disable_fender_fresh(&mut self)->Result {self.bootstrap.native_disable_fender()}
    fn coordinate_off_once(&mut self)->Result {self.provider.coordinate_off_once()}
    fn pm_put_once(&mut self)->Result {self.provider.put_once()}
    fn provider_snapshot(&mut self)->Result<crate::g16_t6040_lifecycle_v10::ProviderState> {
        let state=self.provider.snapshot()?;
        if !state.domain_on {self.off=Some(state);}
        Ok(state)
    }
    fn pm_get_once(&mut self)->Result {self.provider.get_once()}
    fn coordinate_on_once(&mut self)->Result {self.provider.coordinate_on_once()}
    fn fresh_rtbuddy_data_boot_and_ap_handshake(&mut self)->Result {
        // New callback data prevents old crash/recovery tombstones from being
        // cleared or mistaken for a new generation's notifications.
        let notifications=Arc::pin_init(Notifications::new(),GFP_KERNEL)?;
        let data=Arc::new(BootData{dev:self.bootstrap.dev.clone(),notifications:notifications.clone()},GFP_KERNEL)?;
        self.bootstrap._rtkit.as_mut().g16_rearm_retained(data)?;
        self.bootstrap.notifications=notifications;
        self.bootstrap.native_cold_data.as_mut().ok_or(EIO)?.restore()?;
        let guard=self.bootstrap._asc.try_access().ok_or(ENODEV)?;
        let io=guard.relaxed();let control=io.read32(0x44);
        if control==u32::MAX || control&0x30!=0{return Err(EBUSY);}
        io.write32(control|0x10,0x44);
        if io.read32(0x44)&0x10==0{return Err(EIO);}
        drop(guard);crate::mem::sync();
        // Autonomous HELLO/map/Running20 + ownB20 through RTKit's managed
        // parser. Never stock wake/INIT220 and never an EP0 raw race.
        self.bootstrap._rtkit.as_mut().boot()?;
        for ep in [0x20,0x21] {
            if !self.bootstrap._rtkit.as_mut().has_endpoint(ep){return Err(ENODEV);}
            self.bootstrap._rtkit.as_mut().start_endpoint(ep)?;
        }
        Ok(())
    }
    fn fresh_application_generation(&mut self,generation:u64)->Result {
        self.bootstrap.native_fresh_application_generation(generation,self.off.ok_or(EIO)?)
    }
}

impl crate::g16_t6040_lifecycle_v10::Provider for crate::g16_native_pm_v10::Session {
    fn held(&self)->bool {crate::g16_native_pm_v10::Session::held(self)}
    fn coordinate_off_once(&mut self)->Result {self.coordinate(false)}
    fn put_once(&mut self)->Result {crate::g16_native_pm_v10::Session::put_once(self)}
    fn snapshot(&mut self)->Result<crate::g16_t6040_lifecycle_v10::ProviderState> {
        let (word,domain_on)=self.provider_snapshot()?;
        Ok(crate::g16_t6040_lifecycle_v10::ProviderState{word,domain_on})
    }
    fn get_once(&mut self)->Result {crate::g16_native_pm_v10::Session::get_once(self)}
    fn coordinate_on_once(&mut self)->Result {self.coordinate(true)}
}
