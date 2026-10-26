#!/usr/bin/env python3
"""Compose native device geometry and actual allocation extents, offline only."""
def wiring(files, *, scene_count=80, state_count=36, group_shift=0, group_allowance=False,
           extra_scene_stride=False):
 assert 0<scene_count<=128 and state_count>0 and 0<=group_shift<32
 s=files['g16_runtime.rs'];start=s.index('    fn native_render_geometry(&self)');end=s.index('    fn submit_native_render_queue',start)
 s=s[:start]+'''    fn native_render_geometry(&self)->Result<crate::g16_t6040_pm_v9::Geometry> {
        // G16X halGetPMConfig resolves inherited G16 provider89d8c2c:
        // pagefactor4, registrationalignment4, divisor6144, fixed8,
        // bytes/unit8 and scenealignment16. Linux maximum is the requested
        // retained block count, with an explicitly reserved free ring entry.
        let maximum=*crate::module_parameters::tvb_max_blocks.value();
        let capacity=maximum.checked_add(1).ok_or(EINVAL)?;
        let memory=u64::from(maximum).checked_mul(0x20000).ok_or(EINVAL)?;
        let scene_stride=crate::g16_t6040_pm_v9::SceneBudget {
            memory_bytes:memory,divisor_units:6144,fixed_bytes:8,
            bytes_per_unit:8,alignment:16,groups:self.topology.clusters,
            group_shift:GROUP_SHIFT,group_allowance:GROUP_ALLOWANCE,
        }.stride().ok_or(EINVAL)?;
        Ok(crate::g16_t6040_pm_v9::Geometry{scene_count:SCENE_COUNT,state_count:STATE_COUNT,
            capacity,initial_blocks:11,page_factor:4,
            registration_stride:4,scene_stride,
            // PM1d4 is distinct from DevicePMConfig at1d8. Native typed
            // object allocation supplies zero; ordinary PMinit preserves it.
            extra_scene_stride:EXTRA_SCENE,parameter_field_1d4:0,native_count_154:11,
            native_count_15c:maximum,support_count:0})
    }
'''.replace('GROUP_SHIFT',str(group_shift)).replace('GROUP_ALLOWANCE',str(bool(group_allowance)).lower()).replace('SCENE_COUNT',str(scene_count)).replace('STATE_COUNT',str(state_count)).replace('EXTRA_SCENE',str(bool(extra_scene_stride)).lower())+s[end:]
 files['g16_runtime.rs']=s
 s=files['g16_t6040_pm_owned_v9.rs'];needle='        let plan = native::AllocationPlan::new(geometry).ok_or(EINVAL)?;';assert s.count(needle)==1
 s=s.replace(needle,'''        let mut geometry=geometry;
        let plan = native::AllocationPlan::new(geometry).ok_or(EINVAL)?;
        // Native HWstate30 is resource+78 byte extent, not support count.
        geometry.support_count=u32::try_from(plan.roles[6].mapped_bytes).map_err(|_|EINVAL)?;''')
 s=s.replace('    scenes: u64,','    scenes: [u64;2],').replace('            scenes: 0,','            scenes: [0;2],')
 start=s.index('    pub(crate) fn reserve_scene(');end=s.index('    /// Actual ordinary3D',start)
 s=s[:start]+'''    pub(crate) fn reserve_scene(&mut self) -> Result<u32> {
        for i in 0..self.geometry.scene_count {
            let bank=(i/64)as usize;let bit=1u64<<(i%64);
            if self.scenes[bank]&bit==0 {self.scenes[bank]|=bit;return Ok(i);}
        }
        Err(EBUSY)
    }
    pub(crate) fn release_scene(&mut self, i: u32) {
        if i < self.geometry.scene_count {
            self.scenes[(i/64)as usize]&=!(1u64<<(i%64));
        }
    }
    pub(crate) fn owns_scene(&self,i:u32)->bool {
        i<self.geometry.scene_count && self.scenes[(i/64)as usize]&(1u64<<(i%64))!=0
    }
'''+s[end:]
 files['g16_t6040_pm_owned_v9.rs']=s
 s=files['g16_t6040_pm_v9.rs'];assert 'self.scene_count > 64' in s
 files['g16_t6040_pm_v9.rs']=s.replace('self.scene_count > 64','self.scene_count > 128')
