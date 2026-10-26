// SPDX-License-Identifier: GPL-2.0-only
// Included in g16_runtime by stage_native_render_caller_v9.py.
// This caller is compiled while BUNDLE_COMPLETE remains closed. Named Linux
// experiments below are not claims about Apple's device policy or acceptance.
pub(super) struct NativePmSlot {
    root: u64,
    owner: Arc<Mutex<g16_vm::AddressSpace>>,
    pm: crate::g16_t6040_pm_owned_v9::NativePm,
    initialized: bool,
}
pub(super) struct NativeCreditStaging {
    owner: Arc<Mutex<FirmwareQueues>>,
    work: u64,
    credits:[Option<crate::g16_t6040_scheduler_owner_v9::Credit>;2],
}
impl Bootstrap {
    fn native_render_geometry(&self)->Result<crate::g16_t6040_pm_v9::Geometry> {
        // LINUX_NATIVE_PM_PAGE_GEOMETRY: independent 16KiB registration and
        // scene payload allocations; 11 initial actual blocks, 36 leases.
        // Native configuration counts/1d4 are explicitly experimental zero.
        Ok(crate::g16_t6040_pm_v9::Geometry{scene_count:36,state_count:36,
            capacity:*crate::module_parameters::tvb_max_blocks.value(),initial_blocks:11,
            page_factor:4,registration_stride:0x4000,scene_stride:0x4000,
            extra_scene_stride:false,parameter_field_1d4:0,native_count_154:0,
            native_count_15c:0,support_count:1})
    }
    fn submit_native_render_queue(&mut self,queue:&mut FirmwareQueues,
        queues:Arc<Mutex<FirmwareQueues>>,owner:Arc<Mutex<g16_vm::AddressSpace>>,
        input:&render::Parameters,support:&Support,timestamps:[u64;4],
        dependencies:&[Option<Stamp>;2])->Result<Receipt> {
        use crate::{g16_t6040_pm_v9 as pm,g16_t6040_work_layout_v9 as layout};
        if self.render_failed||!input.valid(){return Err(EINVAL);}
        // Native dependency identity is retained by its producer, not inferred
        // from Linux VM/event IDs. Donor compute dependencies explicitly refuse.
        for dep in dependencies.iter().flatten(){if dep.native_identity.is_none(){return Err(ENOTSUPP);}}
        let mut guard=owner.lock();let client=&mut *guard;let root=client.roots().low;
        let pool_index=match self.native_pm_pools.iter().position(|p|p.root==root){
            Some(i)=>i,None=>{
                self.native_pm_pools.reserve(1,GFP_KERNEL)?;
                let geometry=self.native_render_geometry()?;
                let plan=pm::AllocationPlan::new(geometry).ok_or(EINVAL)?;
                let base=self.next_work_va;
                self.next_work_va=base.checked_add(plan.mapped_bytes as u64).ok_or(ENOSPC)?;
                // Partial allocation is retained by both FW and client owners.
                // Store the client pin before creating any external alias.
                self.native_pm_owners.push(owner.clone(),GFP_KERNEL)?;
                self.render_failed=true;
                let resource=crate::g16_t6040_pm_owned_v9::NativePm::new(
                    self._firmware_space.as_mut().ok_or(EIO)?,client,base,geometry)?;
                self.native_pm_pools.push(NativePmSlot{root,owner:owner.clone(),pm:resource,initialized:false},GFP_KERNEL)?;
                self.render_failed=false;self.native_pm_pools.len()-1
            }
        };
        let scene=self.native_pm_pools[pool_index].pm.reserve_scene()?;
        self.render_failed=true;
        // Native PM never enters donor Tvb initialization/growth or scene math.
        let roles=self.native_pm_pools[pool_index].pm.roles;
        let geometry=self.native_pm_pools[pool_index].pm.geometry;
        let views=roles.scene(geometry,scene).ok_or(EINVAL)?;
        let initbm=!self.native_pm_pools[pool_index].initialized;
        let mut p=*input;p.scene_slot=u64::from(scene);p.cycle=views.payload_device;
        // LINUX_FIRST_DRAW_NO_GROWTH: use the eleven real initial blocks only.
        // Optional partial/growth SKU flags are disabled explicitly; a firmware
        // request is retained and refused, never serviced by donor TVB code.
        p.request_tvb_growth=false;p.fragment_sync_grow=false;
        // Actual descriptor-table admission comes from this retained support
        // lease, not a research fixture. Table publication is ordered below.
        let admission=7+u64::from(support.index);
        p.tiling_admission=admission;p.fragment_admission=admission;
        let scratch=client.prepare_render(&mut p)?;
        let base=self.allocate_work(true)?;let plan=layout::Layout::new(base).ok_or(EINVAL)?;
        let mut a=render::Addresses::bootstrap().publication(self.render_publication);
        let lanes=*queue.lanes.as_ref().ok_or(EIO)?;
        a.tiling_queue=lanes[0].queue;a.fragment_queue=lanes[1].queue;
        a.tiling_event=u64::from(queue.event(0)?);a.fragment_event=u64::from(queue.event(1)?);
        a.support=support.address();a.render_shared_state=support.address()+0x1000;
        a.tiling_status_page=p.ta_status&!0x3fff;a.fragment_status_page=p.fragment_status&!0x3fff;
        let ordinal=queue.render_count;
        // LINUX_NATIVE_EVENT_POLICY retains existing Gravity public-event stamp
        // progression until Apple notifier/event initialization is connected.
        a.tiling_stamp=u64::from(g16_stamp::value(ordinal,0xc00));
        a.fragment_stamp=u64::from(g16_stamp::value(ordinal,0x100));
        a.tiling_driver_stamp=plan.stages[0].driver_stamp_fw;
        a.fragment_driver_stamp=plan.stages[1].driver_stamp_fw;
        a.tiling_firmware_stamp=lanes[0].firmware_stamp();
        a.fragment_firmware_stamp=lanes[1].firmware_stamp();
        a.tiling_work=plan.stages[0].command.firmware;
        a.fragment_work=plan.stages[1].command.firmware;
        a.tiling_microsequence=plan.stages[0].sku_fw;a.fragment_microsequence=plan.stages[1].sku_fw;
        a.tiling_shared_tail=plan.stages[0].shared_state_fw;
        a.fragment_shared_tail=plan.stages[1].shared_state_fw;
        a.tiling_user_timestamp_start=timestamps[0];a.tiling_user_timestamp_end=timestamps[1];
        a.fragment_user_timestamp_start=timestamps[2];a.fragment_user_timestamp_end=timestamps[3];
        // Native notifier gets its own uncached subrange, separate from native
        // command scratch at Work+200. Binding remains named Linux experiment.
        let notifier=base+0x18100;a.event_control=notifier;a.event_count_array=notifier+0x100;
        let status_fw=self.next_work_va;self.next_work_va=status_fw.checked_add(0x8000).ok_or(ENOSPC)?;
        for (i,page) in plan.pages.iter().enumerate(){
            let fw=self._firmware_space.as_mut().ok_or(EIO)?;let pa=fw.physical(page.firmware)?;
            self._address_space.as_mut().ok_or(EIO)?.map_work_alias(page.device,pa)?;
            client.map_work_alias(page.device,pa)?;
            let status=if i==0{a.tiling_status_page}else{a.fragment_status_page};
            let pa=client.low.translate(status)?.ok_or(EINVAL)?;
            fw.map_external(status_fw+i as u64*0x4000,pa,0x4000,crate::pgtable::prot::PROT_FW_SHARED_RW)?;
        }
        client.sync();self._address_space.as_mut().ok_or(EIO)?.sync();
        self._firmware_space.as_mut().ok_or(EIO)?.sync();
        self.invalidate_client(client);self.invalidate_client(self._address_space.as_ref().ok_or(EIO)?);
        a.context_id=u64::from(self.acquire_context(client.roots(),9)?);
        // LINUX_NATIVE_SCHEDULER_EPOCH explicitly uses requested Linux counter
        // start; Apple's accelerator ee48 initializer is not claimed equal.
        for i in 0..2{if queue.lanes.as_ref().ok_or(EIO)?[i].ksm_state.is_none(){
            self.initialize_native_scheduler(queue,i,*crate::module_parameters::fw_counter_start.value(),None)?;
        }}
        self.native_pm_pools[pool_index].pm.increment(self._firmware_space.as_mut().ok_or(EIO)?)?;
        let descriptor=self.native_pm_pools[pool_index].pm.descriptor()?;
        let fw=self._firmware_space.as_mut().ok_or(EIO)?;
        fw.write_live(0xfffffc2000128000u64+admission*16,&descriptor)?;
        // Real per-Work notifier storage is initialized without reusing donor
        // command bytes. The 94 count is conservative until FW clears it.
        let mut notifier_bytes=[0u8;0x100];notifier_bytes[..8].copy_from_slice(&a.event_count_array.to_le_bytes());
        notifier_bytes[8..12].copy_from_slice(&(a.fragment_stamp as u32).to_le_bytes());
        notifier_bytes[0x10..0x14].copy_from_slice(&0x50u32.to_le_bytes());
        notifier_bytes[0x24..0x28].copy_from_slice(&(a.context_id as u32).to_le_bytes());
        notifier_bytes[0x94..0x98].copy_from_slice(&2u32.to_le_bytes());
        fw.write_live(notifier,&notifier_bytes)?;fw.write_live(a.event_count_array,&2u32.to_le_bytes())?;
        for (address,value) in [(a.tiling_driver_stamp,a.tiling_stamp),(a.fragment_driver_stamp,a.fragment_stamp)]{
            fw.write_live(address,&g16_stamp::previous(value as u32).to_le_bytes())?;
        }
        let ta=self.build_native_render_stage(&p,&a,roles,geometry,scene,plan.stages[0],status_fw,queue,0,dependencies,None)?;
        let ta_identity=(ta.0.submitted_timeline,queue.lanes.as_ref().ok_or(EIO)?[0].ksm_state.ok_or(EIO)?.queue_id);
        let frag=self.build_native_render_stage(&p,&a,roles,geometry,scene,plan.stages[1],status_fw+0x4000,queue,1,dependencies,Some(ta_identity))?;
        // Pin exact non-copy scheduler credit before the first slot write or
        // announcement. Partial publication cannot drop the only retirement
        // identity; it remains quarantined with the owning queue and Work.
        self.native_pending_credits.push(NativeCreditStaging{owner:queues.clone(),work:base,credits:[None,None]},GFP_KERNEL)?;
        let credit_index=self.native_pending_credits.len()-1;
        let mut heads=[0;2];let mut epochs=[0;2];
        // Every command/SKU/transport image is ready before either lane is
        // announced. Linux first-job policy emits no scheduling NOPs.
        for i in [1usize,0]{self.write_native_configuration(queue,i,if i==0{a.tiling_uuid}else{a.fragment_uuid}as u32)?;}
        self.publish_native_qos(queue,&[1,0])?;
        if initbm{
            let mut bm=[0u8;0x18];crate::g16_t6040_bm_init_v9::write(&mut bm,
                crate::g16_t6040_bm_init_v9::Bindings{descriptor_1274:(p.tiling_work_stamp>>8)as u32,
                    descriptor_1218:admission as u32,manager_fw:roles.hw_state.firmware,caller_word_21:1}).ok_or(EINVAL)?;
            self._firmware_space.as_mut().ok_or(EIO)?.write_live(plan.bm_fw,&bm)?;
        }
        for i in [1usize,0]{
            let (result,record)=if i==0{&ta}else{&frag};
            let credit=self.stage_native_scheduler_entry(queue,i,record,result.submitted_timeline,result.next_timeline)?;
            self.native_pending_credits[credit_index].credits[i]=Some(credit);
            let mut lane=queue.lanes.as_ref().ok_or(EIO)?[i];
            let mut pos=(lane.head+u32::from(lane.new))%0x500;
            let fw=self._firmware_space.as_mut().ok_or(EIO)?;
            // Firmware barriers and hardware dependencies describe the same
            // retained producer identity; neither replaces the other.
            let ta_stamp=Stamp{address:a.tiling_firmware_stamp,value:a.tiling_stamp as u32,
                event:a.tiling_event as u32,native_identity:Some(ta_identity)};
            let stage_deps=if i==0 {
                if p.vdm_barrier_fragment{[None,dependencies[1],None]}else{[dependencies[0],dependencies[1],None]}
            }else{[if p.vdm_barrier_fragment{dependencies[0]}else{None},None,Some(ta_stamp)]};
            for (j,dep) in stage_deps.iter().flatten().enumerate(){
                let (timeline,qid)=dep.native_identity.ok_or(ENOTSUPP)?;
                // Borrowed SKU suffix lies after its fixed 0x2000 capacity and
                // before the next retained Work page: three0x80 record slots.
                let address=plan.stages[i].sku_fw+0x2000+j as u64*0x80;
                let mut barrier=[0u8;crate::g16_t6040_dependency_v9::BYTES];
                crate::g16_t6040_dependency_v9::write(&mut barrier,
                    crate::g16_t6040_dependency_v9::Bindings{stamp_base:dep.address,stamp_offset:0,
                        hardware_timestamp:timeline,hardware_queue:u32::from(qid),wait_value:dep.value,
                        producer_event:dep.event,consumer_stamp:if i==0{a.tiling_stamp}else{a.fragment_stamp}as u32,
                        uuid:if i==0{a.tiling_uuid}else{a.fragment_uuid},selected_event:-1});
                fw.write_live(address,&barrier)?;
                fw.write_live(lane.ring+u64::from(pos)*8,&address.to_le_bytes())?;pos=(pos+1)%0x500;
            }
            if i==0&&initbm{fw.write_live(lane.ring+u64::from(pos)*8,&plan.bm_fw.to_le_bytes())?;pos=(pos+1)%0x500;}
            fw.write_live(lane.ring+u64::from(pos)*8,&plan.stages[i].postkick_fw.to_le_bytes())?;
            heads[i]=(pos+1)%0x500;lane.head=heads[i];
            epochs[i]=self.stage_queue(queue.priority as usize*3+i,lane,if i==0{a.tiling_event}else{a.fragment_event}as u32,self.render_publication.wrapping_add(1))?;
        }
        let frag_identity=(frag.0.submitted_timeline,queue.lanes.as_ref().ok_or(EIO)?[1].ksm_state.ok_or(EIO)?.queue_id);
        let stamp=Stamp{address:a.fragment_firmware_stamp,value:a.fragment_stamp as u32,event:a.fragment_event as u32,native_identity:Some(frag_identity)};
        let ta_stamp=Stamp{address:a.tiling_firmware_stamp,value:a.tiling_stamp as u32,event:a.tiling_event as u32,native_identity:Some(ta_identity)};
        let lanes=queue.lanes.as_mut().ok_or(EIO)?;for i in 0..2{lanes[i].head=heads[i];lanes[i].new=false;}
        self.flights.push(Flight{id:base,owner:queues,context:a.context_id as u32,started:Instant::now(),
            stamps:[Some(ta_stamp),Some(stamp)],driver_stamps:[Some(Stamp{address:a.tiling_driver_stamp,..ta_stamp}),Some(Stamp{address:a.fragment_driver_stamp,..stamp})],
            scratch,client:owner.clone(),queues:[(lanes[0].pointers,heads[0]),(lanes[1].pointers,heads[1])],
            channels:[(queue.priority as usize*3,(epochs[0]+1)&255),(queue.priority as usize*3+1,(epochs[1]+1)&255)],
            render:Some(RenderFlight{addresses:a,client:owner.clone(),root,events:RenderEvents::default(),scene}),
            native_scheduler_credits:[None,None],native_notifier:Some(notifier)},GFP_KERNEL)?;
        let flight_index=self.flights.len()-1;
        for i in 0..2{self.flights[flight_index].native_scheduler_credits[i]=self.native_pending_credits[credit_index].credits[i].take();}
        self.native_pending_credits.remove(credit_index).map_err(|_|EIO)?;
        self.native_pm_pools[pool_index].initialized=true;queue.pending+=1;queue.last[0]=Some(stamp);
        queue.render_count=ordinal.wrapping_add(1);self.render_publication=self.render_publication.wrapping_add(1);
        support.submissions.fetch_add(2,Ordering::Relaxed);self.batch_works+=1;self.render_failed=false;
        Ok(Receipt{id:base,stamp})
    }
    fn build_native_render_stage(&mut self,p:&render::Parameters,a:&render::Addresses,
        roles:crate::g16_t6040_pm_v9::OwnedRoles,geometry:crate::g16_t6040_pm_v9::Geometry,
        scene_index:u32,stage:crate::g16_t6040_work_layout_v9::Stage,status_fw:u64,
        queue:&FirmwareQueues,index:usize,dependencies:&[Option<Stamp>;2],
        ta_identity:Option<(u64,u8)>)->Result<(crate::g16_t6040_render_job_v9::ResultInfo,[u8;0x200])> {
        use crate::{g16_t6040_descriptor_provider_v10 as provider,g16_t6040_descriptor_v10 as descriptor,
            g16_t6040_resource_address_v9 as address,g16_t6040_rce_ram_v9 as rce,
            g16_t6040_render_envelope_v9 as envelope,g16_t6040_ksm_work_v8 as ksm,
            g16_t6040_render_job_v9 as job,g16_t6040_pm_v9 as pm};
        let mut bytes=KVec::new();bytes.extend_with(0x7c00,0u8,GFP_KERNEL)?;
        let (command,tail)=bytes.as_mut_slice().split_at_mut(0x3000);
        let (desc,tail)=tail.split_at_mut(0x1800);
        let (scratch,tail)=tail.split_at_mut(0x400);
        let (context,tail)=tail.split_at_mut(0x100);
        let (scene,tail)=tail.split_at_mut(0x100);
        let (envelope_context,tail)=tail.split_at_mut(0x600);
        let (stack,tail)=tail.split_at_mut(0x100);
        let (source,tail)=tail.split_at_mut(0x400);
        let (sku_stack,tail)=tail.split_at_mut(0x300);
        let (stream,_)=tail.split_at_mut(0x2000);
        let command:&mut[u8;0x3000]=command.try_into().map_err(|_|EINVAL)?;
        let desc:&mut[u8;0x1800]=desc.try_into().map_err(|_|EINVAL)?;
        let context:&mut[u8;0x100]=context.try_into().map_err(|_|EINVAL)?;
        let scene:&mut[u8;0x100]=scene.try_into().map_err(|_|EINVAL)?;
        // LINUX_PRIVATE_TA_APERTURE: these resources are retained in the actual
        // client's private arena. No firmware alias is substituted for slot160.
        let ta=descriptor::UserAddresses::from_mappings(
            [p.tilemap,p.layermeta,p.heapmeta,p.tpc,p.encoder,p.deflake_1,p.deflake_2,p.deflake_3]
            .map(|v|address::Address::from_mapping(v,address::Aperture::Allocator{base:0x10_0000_0000})));
        let v=roles.scene(geometry,scene_index).ok_or(EINVAL)?;
        let phase=if index==0{provider::Phase::Tiling}else{provider::Phase::Fragment};
        let status=provider::prepare_into(desc,command,context,scene,p,&ta,phase,
            provider::Policy{experimental_linux_lifecycle:true,scene_header:v.header,
                context_special_mode:false,tiling_initial_barrier:false,
                suppress_ta_timestamps:true,suppress_fragment_timestamps:true,
                descriptor_113b:0,descriptor_1141:0,descriptor_1142:0}).ok_or(ENOTSUPP)?;
        pm::bind_descriptor(desc,geometry,roles,scene_index).ok_or(EINVAL)?;
        let lanes=queue.lanes.as_ref().ok_or(EIO)?;let state=lanes[index].ksm_state.ok_or(EIO)?;
        let event=if index==0{a.tiling_event}else{a.fragment_event}as u32;
        let stamp=if index==0{a.tiling_stamp}else{a.fragment_stamp}as u32;
        // LINUX_NATIVE_NOTIFIER_BINDING: actual retained allocations and queue
        // stamps, but initialized completion-field policy remains experimental.
        let putq=|d:&mut[u8],o:usize,v:u64|{d[o..o+8].copy_from_slice(&v.to_le_bytes());};
        let putw=|d:&mut[u8],o:usize,v:u32|{d[o..o+4].copy_from_slice(&v.to_le_bytes());};
        putq(desc,0x188,a.event_control);
        let (primary,driver,event_offset,count_offset)=if index==0{(0x1408,0x1418,0x1420,0xe38)}else{(0xb70,0xb80,0xb88,0x2dc)};
        putq(desc,primary,lanes[index].firmware_stamp());putq(desc,driver,stage.driver_stamp_fw);
        putw(desc,event_offset,event);putw(desc,count_offset,1);
        putw(desc,0x210,stamp);putw(desc,if index==0{0xe08}else{0x964},u32::from(state.queue_id));
        putq(desc,if index==0{0xe30}else{0xab0},stage.shared_state_fw+0x100);
        let profiles=if index==0{[a.tiling_user_timestamp_start,a.tiling_user_timestamp_end]}else{[a.fragment_user_timestamp_start,a.fragment_user_timestamp_end]};
        putq(desc,if index==0{0x13d8}else{0xac0},profiles[0]);putq(desc,if index==0{0x13e0}else{0xac8},profiles[1]);
        // Source-native timestamp pairs and internal destinations are distinct.
        putq(stack,0x40,stage.driver_stamp_fw);putw(stack,0x48,event);putw(stack,0x4c,stamp);
        putq(stack,0x50,stage.shared_state_fw);putw(stack,0x5c,event);
        let mut deps=KVec::new();
        if index==0{
            for (i,dep) in dependencies.iter().enumerate(){
                if i==0&&p.vdm_barrier_fragment{continue;}
                if let Some(dep)=dep{let (timeline,qid)=dep.native_identity.ok_or(ENOTSUPP)?;
                    deps.push(ksm::Dependency{converted_timestamp:timeline,queue_id:qid},GFP_KERNEL)?;}
            }
        }else{
            if p.vdm_barrier_fragment{if let Some(dep)=dependencies[0]{let (timeline,qid)=dep.native_identity.ok_or(ENOTSUPP)?;
                deps.push(ksm::Dependency{converted_timestamp:timeline,queue_id:qid},GFP_KERNEL)?;}}
            if let Some((timeline,qid))=ta_identity{deps.push(ksm::Dependency{converted_timestamp:timeline,queue_id:qid},GFP_KERNEL)?;}
        }
        let mut scheduler=ksm::Bindings{timestamp:state.timestamp,queue_id:state.queue_id,
            priority:queue.public_priority as u8,capacity:state.capacity,
            // LINUX_NATIVE_INITIAL_PRIOR is an explicit invalid-before-first
            // timeline seed, not Apple's accelerator ee48 initialization.
            previous:state.cached_previous.unwrap_or(state.timestamp.wrapping_sub(1)&ksm::TIMESTAMP_MASK),
            command:stage.command.firmware,firmware_queue:lanes[index].queue,
            aperture_address:0,aperture_index:0,aperture_count:0,alternate_kind:false,extra_flag:false,
            dependencies:deps.as_slice(),qos:(0,16,0),rce_kind:index as u8,
            register_lists:[ksm::RegisterList{gpu_address:0,count:0};4],
            // LINUX_NATIVE_MASK_PLACEMENT supplies actual topology masks in
            // the first two mask words; Apple's scheduling policy is unbound.
            masks:[self.topology.core_masks[0],self.topology.core_masks[1],0,0],auxiliary:stage.shared_state_fw};
        // LINUX_QOS_RECORD_POLICY currently selects0/16/0; real topology masks
        // come from this device's retained ADT-derived profile.
        let providers=rce::Providers{gpu_clusters:self.topology.clusters,address_bit47:false,
            ppp_bit9:provider::required_ppp_bit9(p).ok_or(ENOTSUPP)?,descriptor_policy:0,
            fragment_policy:0,controller_mode:0,controller_feature:0,
            command_gpu:stage.command.device,parameter_gpu:status};
        let mut backing=rce::Backing{command,descriptor:desc,
            scratch:scratch.try_into().map_err(|_|EINVAL)?,context,scene,providers};
        let mut record=[0u8;0x200];
        let result=if index==0{
            job::tiling(&mut backing,&envelope::TaBindings{context:envelope_context,stack,
                serial:self.render_publication,firmware_translations:pm::translations(v),
                completion_firmware:status_fw,x26:stage.driver_stamp_fw,w21:stamp,w22:event,
                accelerator_mode:0,aperture_flags:0},
                crate::g16_t6040_ta_sku_v9::Bindings{command_gpu:stage.command.device,
                    translated_state:v.aux_firmware,fw_state:stage.shared_state_fw,
                    state:stage.shared_state_fw+0x100,counter:v.counter_firmware,
                    resource_type:0,context_id:a.context_id as u32,resource_map:status,
                    feature:0,channel_config:0,timestamp_index:event,stream_fw:stage.sku_fw},
                stream,stage,&mut scheduler,&mut record)
        }else{
            let frame=[0u8;24];
            // Actual owned PM firmware state is the startup stack's pointer78.
            putq(sku_stack,0x78,stage.shared_state_fw);putq(sku_stack,0x70,stage.driver_stamp_fw);
            job::fragment(&mut backing,&envelope::FragmentBindings{source,frame:&frame,stack,
                context:envelope_context,serial:self.render_publication,counter:queue.render_count as u32,
                w21:stamp,w22:event,firmware_translations:pm::translations(v),
                // LINUX_NATIVE_EVENT_EPOCHS starts both event banks at1;
                // driver event-machine initialization remains to be integrated.
                completion_firmware:status_fw,epochs:[1,1],capacity:state.capacity,
                initial:*crate::module_parameters::fw_counter_start.value(),aperture_flags:0},
                crate::g16_t6040_fragment_sku_v9::Bindings{command_gpu:stage.command.device,
                    parameter_gpu:roles.hw_state.device,state_fw:stage.shared_state_fw+0x100,
                    resource_type:0,resource_map:status,context_id:a.context_id as u32,
                    accelerator_config:0,accelerator_feature:0,channel_config:0,mode:0,
                    timestamp_index:event,stream_fw:stage.sku_fw,omit_end_timestamp:true},
                stream,sku_stack.try_into().map_err(|_|EINVAL)?,stage,&mut scheduler,&mut record)
        }.map_err(|_|EINVAL)?;
        let mut postkick=[0u8;0x18];result.write_transport(&mut postkick,1,0).ok_or(EINVAL)?;
        let fw=self._firmware_space.as_mut().ok_or(EIO)?;
        fw.write_live(stage.command.firmware,backing.command)?;
        fw.write_live(stage.sku_fw,stream)?;
        fw.write_live(stage.ksm.firmware,&record)?;
        fw.write_live(stage.postkick_fw,&postkick)?;
        Ok((result,record))
    }
}
