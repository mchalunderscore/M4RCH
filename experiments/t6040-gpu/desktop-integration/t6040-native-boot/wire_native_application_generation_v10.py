#!/usr/bin/env python3
"""Split application allocation from platform boot; quarantine old generations.

Fixed ABI VAs may be rebound only after a strict OFF witness. No firmware TTBR
change, MMIO reacquisition, old-page free, or provider BUSY clear is introduced.
"""
from pathlib import Path
FIELDS=['_address_space','_firmware_space','_opening_client','timestamp_ranges','opening_notification_pending','tvb_pools','native_pm_pools','native_pending_credits','native_pm_owners','render_publication','native_leases','native_qos_manager','next_work_va','work_arenas','free_work','compute_publication','queue_events','render_failed','flights','publications','batch_works','context_roots','context_users','pressure_reported','render_support']
RESET={'_address_space':'Some(address_space)','_firmware_space':'Some(firmware_space)','_opening_client':'Some(opening_client)','timestamp_ranges':'KVec::new()','opening_notification_pending':'true','tvb_pools':'KVec::new()','native_pm_pools':'KVec::new()','native_pending_credits':'KVec::new()','native_pm_owners':'KVec::new()','render_publication':'*crate::module_parameters::fw_counter_start.value()','native_leases':'crate::g16_queue_owner::LeasePool::new()','native_qos_manager':'crate::g16_t6040_qos::ManagerState::new()','next_work_va':'0xffff_fc22_0000_0000','work_arenas':'[0..0,0..0]','free_work':'[KVec::new(),KVec::new()]','compute_publication':'*crate::module_parameters::fw_counter_start.value()','queue_events':'queue_events','render_failed':'true','flights':'KVec::new()','publications':'KVec::new()','batch_works':'0','context_roots':'[None;64]','context_users':'[0;64]','pressure_reported':'core::sync::atomic::AtomicU64::new(0)','render_support':'render_support'}
def wiring(files):
    s=files['g16.rs']
    # Extract the already integrated normal allocation path, including all
    # source bindings previously composed by other agents.
    begin=s.index('        let mut firmware_space = crate::g16_vm::FirmwareSpace::attach(dev)?;')
    end=s.index('        let mut session = Self {',begin)
    allocation=s[begin:end]
    # The shared function builds new private client roots; borrowed firmware
    # root stays owned by the loader and old physical pages remain quarantined.
    function='''
    fn build_application_graph(dev:&kernel::device::Device,
        platform:&crate::g16_platform::Platform, transport:crate::g16_transport::Transport,
        bundle:&[u8],region_c:&[u8],native_aonptd:&[u8])
        ->Result<(crate::g16_vm::AddressSpace,crate::g16_vm::FirmwareSpace,crate::g16_vm::AddressSpace)> {
        let native_t6040=transport.native_t6040;
        let pointers=transport.roots;
        let sgx_physical=platform.sgx_physical()?;
        let mut address_space=crate::g16_vm::AddressSpace::new()?;
'''+allocation+'''        Ok((address_space,firmware_space,opening_client))
    }
'''
    s=s[:begin]+'''        let (address_space,firmware_space,opening_client)=Self::build_application_graph(
            dev,&platform,transport,&bundle,&region_c,&native_aonptd)?;
'''+s[end:]
    # Preserve the cold geometry check but discard its temporary root before
    # making the independently owned application roots.
    s=s.replace('        address_space.check_borrowed_root(dev)?;','        address_space.check_borrowed_root(dev)?;\n        drop(address_space);',1)
    import re
    struct=s[s.index('pub(crate) struct Bootstrap {'):s.index('// SAFETY: The session owns')]
    declarations=[]
    for field in FIELDS:
        m=re.search(r'^    '+re.escape(field)+r':([^\n]+)',struct,re.M)
        assert m,field
        declarations.append('    '+field+':'+m.group(1))
    template='''
struct NativeApplicationTemplate {
    platform:crate::g16_platform::Platform,
    bundle:KVec<u8>,region_c:KVec<u8>,aonptd:KVec<u8>,
}
#[allow(dead_code)]
struct NativeRetainedApplication {
    generation:u64,
'''+ '\n'.join(declarations)+ '\n}\n'
    s=s.replace('pub(crate) struct Bootstrap {',template+'\npub(crate) struct Bootstrap {',1)
    s=s.replace('    transport: crate::g16_transport::Transport,','''    transport: crate::g16_transport::Transport,
    native_application_template:NativeApplicationTemplate,
    native_application_generation:u64,
    native_retained_applications:KVec<NativeRetainedApplication>,''',1)
    anchor='            maximum_frequency_khz: platform.freq_a[10] * 1000,'
    assert s.count(anchor)==1
    s=s.replace(anchor,anchor+'''
            native_application_template:NativeApplicationTemplate{platform,bundle,region_c,aonptd:native_aonptd},
            native_application_generation:1,
            native_retained_applications:KVec::new(),''')
    # Dropping old borrowed table owners must never tear down a later graph.
    anchor='            core::mem::forget(self._firmware_space.take());'
    assert s.count(anchor)==1
    s=s.replace(anchor,anchor+'''
            core::mem::forget(core::mem::replace(&mut self.native_retained_applications,KVec::new()));''')
    for method in ('publish','open_control'):
        before='    fn '+method+'(&mut self, pdev: &platform::Device<Core>) -> Result {\n        let dev = pdev.as_ref();'
        assert s.count(before)==1
        s=s.replace(before,'    fn '+method+'(&mut self, dev: &kernel::device::Device) -> Result {')
        s=s.replace('session.'+method+'(pdev)?;','session.'+method+'(dev)?;')
    moves='\n'.join('            '+f+':core::mem::replace(&mut self.'+f+','+RESET[f]+'),' for f in FIELDS)
    method='''
    fn native_fresh_application_generation(&mut self,generation:u64,
        off:crate::g16_t6040_lifecycle_v10::ProviderState)->Result {
        // Fresh AP boot is not proof of retirement. A prior strict OFF
        // observation is mandatory before any fixed firmware VA is rebound.
        if !self.transport.native_t6040 || !off.strict_off()
            || generation!=self.native_application_generation.checked_add(1).ok_or(EOVERFLOW)? {
            return Err(EBUSY);
        }
        self.render_failed=true;
        self.native_retained_applications.reserve(1,GFP_KERNEL)?;
        let queue_events=Arc::new(core::sync::atomic::AtomicU64::new(0),GFP_KERNEL)?;
        let render_support=Arc::new(core::sync::atomic::AtomicU64::new(0),GFP_KERNEL)?;
        self._firmware_space.as_mut().ok_or(EIO)?.detach_application_mappings()?;
        let t=&self.native_application_template;
        let (address_space,firmware_space,opening_client)=Self::build_application_graph(
            self.dev.as_ref(),&t.platform,self.transport,&t.bundle,&t.region_c,&t.aonptd)?;
        let old=NativeRetainedApplication{generation:self.native_application_generation,
'''+moves+'''
        };
        self.native_retained_applications.push(old,GFP_KERNEL)?;
        self.native_application_generation=generation;
        let dev=self.dev.clone();
        self.publish(dev.as_ref())?;
        self.open_control(dev.as_ref())?;
        // Only the fresh application's owner is admitted. Quarantined queue
        // handles retain the previous generation and cannot submit again.
        self.render_failed=false;
        Ok(())
    }
'''
    marker='impl Bootstrap {\n';assert s.count(marker)>=1
    s=s.replace(marker,marker+function+method,1)
    files['g16.rs']=s
    s=files['g16_vm.rs'];marker='impl FirmwareSpace {\n';assert s.count(marker)==1
    s=s.replace(marker,marker+'''
    /// Caller must own a strict previous GPU OFF witness and fresh firmware
    /// application boot. Retain this owner permanently after detaching PTEs;
    /// its pages/tables are never freed or reused by the replacement owner.
    pub(crate) fn detach_application_mappings(&mut self)->Result {
        for region in self.regions.values() {
            self.table.unmap_pages(region.va..region.va+(region.pages.len()*UAT_PGSZ)as u64)?;
        }
        for range in &self.external {self.table.unmap_pages(range.clone())?;}
        self.table.sync();self.table.invalidate(None);crate::mem::sync();
        self.table.clear_invalidations();Ok(())
    }
''',1);files['g16_vm.rs']=s
    s=files['g16_runtime.rs']
    marker='pub(crate) struct FirmwareQueues {';assert s.count(marker)==1
    s=s.replace(marker,marker+'\n    native_application_generation:u64,',1)
    marker='            lanes: None,';assert s.count(marker)==1
    s=s.replace(marker,'            native_application_generation:0,\n'+marker,1)
    marker='        let mut queue = queues.lock();';assert s.count(marker)>=1
    s=s.replace(marker,marker+'''
        if self.transport.native_t6040 {
            if queue.native_application_generation==0 {queue.native_application_generation=self.native_application_generation;}
            if queue.native_application_generation!=self.native_application_generation{return Err(ESTALE);}
        }''')
    marker='    fn acquire_context(&mut self, roots: g16_vm::Roots, preferred: usize) -> Result<u32> {'
    assert s.count(marker)==1
    s=s.replace(marker,marker+'''
        // An existing userspace VM may still contain aliases to old Work/PB
        // pages. Fresh queues must use a fresh VM after application restart.
        if self.transport.native_t6040 && self.native_retained_applications.iter().any(|old|
            old.context_roots.iter().flatten().any(|r|r.low==roots.low || r.high==roots.high)) {
            return Err(ESTALE);
        }
''',1)
    files['g16_runtime.rs']=s
