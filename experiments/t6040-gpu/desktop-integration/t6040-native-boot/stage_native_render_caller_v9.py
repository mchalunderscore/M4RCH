#!/usr/bin/env python3
"""Connect Gravity's gated native render caller with retained actual resources.

No module installation/loading or hardware operations. Explicit Linux device,
notifier and event policies remain hypotheses; this does not open startup gates.
"""
import argparse,hashlib,json,re,shutil
from pathlib import Path
KIT=Path(__file__).resolve().parent
ROOT=KIT.parents[3]
def pin(p):
 p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def stage(base,out):
 src=base/'source/linux/drivers/gpu/drm/asahi';dst=out/'source/linux/drivers/gpu/drm/asahi'
 out.mkdir(parents=True,exist_ok=False);shutil.copytree(src,dst)
 modules=['g16_t6040_descriptor_v10','g16_t6040_descriptor_provider_v10','g16_t6040_resource_address_v9',
 'g16_t6040_render_policy_v9','g16_t6040_rce_ram_v9','g16_t6040_render_envelope_v9','g16_t6040_render_job_v9',
 'g16_t6040_ksm_work_v8','g16_t6040_postkick_v9','g16_t6040_work_layout_v9','g16_t6040_ta_sku_v9',
 'g16_t6040_fragment_sku_v9','g16_t6040_bm_init_v9','g16_t6040_dependency_v9']
 for m in modules:shutil.copyfile(KIT/(m+'.rs'),dst/(m+'.rs'))
 private=ROOT/'out/private-apple/native-rce-semantic-v9.rs'
 shutil.copyfile(private,dst/'g16_native_rce_semantic_v9.rs')
 p=dst/'asahi_m4.rs';s=p.read_text();assert s.count('mod g16_vm;')==1
 s=s.replace('mod g16_vm;', '\n'.join('#[allow(dead_code)] mod '+m+';' for m in modules+['g16_native_rce_semantic_v9'])+'\nmod g16_vm;');p.write_text(s)
 p=dst/'g16.rs';s=p.read_text()
 s=s.replace('    tvb_pools: KVec<crate::g16_tvb::Tvb>,','    tvb_pools: KVec<crate::g16_tvb::Tvb>,\n    native_pm_pools: KVec<render_runtime::NativePmSlot>,\n    native_pending_credits: KVec<render_runtime::NativeCreditStaging>,\n    native_pm_owners: KVec<Arc<Mutex<crate::g16_vm::AddressSpace>>>,')
 # Kernel sync imports are fully qualified to preserve existing module scope.
 s=s.replace('KVec<Arc<Mutex<crate::g16_vm::AddressSpace>>>','KVec<kernel::sync::Arc<kernel::sync::Mutex<crate::g16_vm::AddressSpace>>>')
 s=s.replace('            tvb_pools: KVec::new(),','            tvb_pools: KVec::new(),\n            native_pm_pools: KVec::new(),\n            native_pending_credits: KVec::new(),\n            native_pm_owners: KVec::new(),');p.write_text(s)
 p=dst/'g16_t6040_pm_owned_v9.rs';s=p.read_text();s=s.replace('    pub(crate) fn release_scene(&mut self, i: u32) {',
 '    pub(crate) fn owns_scene(&self,i:u32)->bool {i<self.geometry.scene_count && self.scenes&(1u64<<i)!=0}\n    pub(crate) fn release_scene(&mut self, i: u32) {');p.write_text(s)
 p=dst/'g16_runtime.rs';s=p.read_text()
 def replace(a,b,n=1):
  nonlocal s
  assert s.count(a)==n,(a,s.count(a));s=s.replace(a,b)
 replace('    pub(crate) event: u32,\n}', '    pub(crate) event: u32,\n    pub(crate) native_identity: Option<(u64,u8)>,\n}')
 # Give every complete old Stamp literal no native identity. Struct-update
 # literals already inherit it. This source script audits the resulting count.
 s=re.sub(r'(event: a\.[a-z_]+(?: as u32)?,\n)(\s+})',r'\1            native_identity: None,\n\2',s)
 replace('''        let initbm = !self
            .tvb_pools
            .iter()
            .any(|p| p.root == root && p.initialized);''','''        let initbm=if self.transport.native_t6040 {
            !self.native_pm_pools.iter().any(|p|p.root==root&&p.initialized)
        }else{!self.tvb_pools.iter().any(|p|p.root==root&&p.initialized)};''')
 replace('''                1 + u32::from(initbm) + dependencies.iter().flatten().count() as u32,
                2,
                0,''','''                1 + u32::from(initbm) + if self.transport.native_t6040&&params.vdm_barrier_fragment {
                    u32::from(dependencies[1].is_some())
                }else{dependencies.iter().flatten().count() as u32},
                2 + u32::from(self.transport.native_t6040&&params.vdm_barrier_fragment&&dependencies[0].is_some()),
                0,''')
 replace('''        let mut guard = owner.lock();
        let client = &mut *guard;
        let root = client.roots().low;
        let index = match self.tvb_pools''','''        if self.transport.native_t6040 {
            return self.submit_native_render_queue(queue,queues,owner,params,support,timestamps,dependencies);
        }
        let mut guard = owner.lock();
        let client = &mut *guard;
        let root = client.roots().low;
        let index = match self.tvb_pools''')
 replace('''        if queue.pending == 0 {
            queue.events = None;
        }''','''        if queue.pending == 0 && !self.render_failed {
            queue.events = None;
        }''',2)
 replace('''            let mut render = self.flights[index].render.take().ok_or(EIO)?;''','''            // Native growth/partial events must never mutate donor TVB state.
            // Leave all native resources retained until the native reply path
            // is integrated; ordinary unsupported events fail explicitly.
            if self.flights[index].native_notifier.is_some(){return Err(ENOTSUPP);}
            let mut render = self.flights[index].render.take().ok_or(EIO)?;''')
 replace('''            let owner_handle = flight.owner.clone();''','''            // Validate the native scene lease before spending any scheduler
            // credit, so a missing owner cannot leave partially retired state.
            let native_render=flight.native_notifier.is_some();
            if native_render {
                let r=flight.render.as_ref().ok_or(EIO)?;
                let p=self.native_pm_pools.iter().find(|p|p.root==r.root).ok_or(EIO)?;
                if !p.pm.owns_scene(r.scene){return Err(EIO);}
            }
            let owner_handle = flight.owner.clone();''')
 replace('''            if let Some((root,scene)) = render_root_scene {
                let pool = self
                    .tvb_pools
                    .iter_mut()
                    .find(|p| p.root == root)
                    .ok_or(EIO)?;
                pool.release_scene(scene);
            }''','''            if let Some((root,scene)) = render_root_scene {
                if native_render {
                    self.native_pm_pools.iter_mut().find(|p|p.root==root).ok_or(EIO)?.pm.release_scene(scene);
                } else {
                    self.tvb_pools.iter_mut().find(|p|p.root==root).ok_or(EIO)?.release_scene(scene);
                }
            }''')
 s+='\n'+(KIT/'native_render_caller_v9.rs').read_text();p.write_text(s)
 owner=out/'build-owner';shutil.copytree(dst,owner);shutil.copyfile(base/'build-owner/Makefile',owner/'Makefile')
 j=dict(schema='m4rch.native-render-caller-stage.v9',base=str(base),stage=str(out),source_files=[pin(p)for p in sorted(dst.rglob('*'))if p.is_file()],
 inputs=[pin(__file__),pin(KIT/'native_render_caller_v9.rs'),pin(base/'stage-receipt.json')],hardware_actions=[],submission_enabled=False,
 private_generated_source_local_only=True,linux_hypotheses=dict(pm=dict(initial_blocks=11,scene_count=36,state_count=36,scene_stride=0x4000,registration_stride=0x4000,parameter_field_1d4=0,native_count_154=0,native_count_15c=0,support_count=1,capacity='tvb_max_blocks'),scheduler=dict(initial='fw_counter_start',initial_prior='initial minus one modulo40bits',capacity=256,no_scheduling_nops=True),event=dict(epochs=[1,1],stamps='Gravity per-lane g16_stamp progression',notifier='owned uncached Work18100; source initialization unbound'),ta_aperture='private allocator relative to1000000000',qos=[0,16,0],mask_placement='ADT core masks in first two words',first_draw_growth_disabled=True),remaining=['Apple native notifier/event initializer and scene geometry are explicit Linux hypotheses','Native growth/partial replies explicitly refuse and retain owners','Real firmware/GPU completion and teardown remain unproved'])
 (out/'stage-receipt.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(dict(stage=str(out),source_count=len(j['source_files']))))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();stage(a.base.resolve(),a.out.resolve())
