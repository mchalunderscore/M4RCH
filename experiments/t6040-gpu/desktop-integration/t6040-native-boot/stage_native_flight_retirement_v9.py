#!/usr/bin/env python3
"""Join native scheduler credits/notifier into actual Gravity Flight retirement.

The producer supplies actual owned notifier and NOP+real-entry credits. Existing
stamp/transport predicates remain; no firmware completion is fabricated here.
"""
import argparse,hashlib,json,shutil
from pathlib import Path
KIT=Path(__file__).resolve().parent
def pin(p):
 p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def stage(base,out):
 source=base/'source/linux/drivers/gpu/drm/asahi';target=out/'source/linux/drivers/gpu/drm/asahi'
 out.mkdir(parents=True,exist_ok=False);shutil.copytree(source,target)
 shutil.copyfile(KIT/'g16_t6040_scheduler_owner_v9.rs',target/'g16_t6040_scheduler_owner_v9.rs')
 p=target/'g16_runtime.rs';s=p.read_text()
 def replace(a,b,n=1):
  nonlocal s
  assert s.count(a)==n,(a,s.count(a));s=s.replace(a,b)
 replace('    render: Option<RenderFlight>,\n}',
 '''    render: Option<RenderFlight>,
    native_scheduler_credits: [Option<crate::g16_t6040_scheduler_owner_v9::Credit>;2],
    native_notifier: Option<u64>,
}''')
 replace('''                scratch,
                client:''','''                native_scheduler_credits: [None,None],
                native_notifier: None,
                scratch,
                client:''',2)
 replace('''            let notifier = flight.id
                + if flight.render.is_some() {
                    0x200
                } else {
                    0x1400
                };''','''            let notifier = flight.native_notifier.unwrap_or(flight.id
                + if flight.render.is_some() {0x200} else {0x1400});''')
 replace('''            if let Some(render) = &flight.render {
                let pool = self
                    .tvb_pools
                    .iter_mut()''','''            // Validate every native lane before releasing any scene, mapping,
            // context, scratch or Work lease. This count is scheduler entries,
            // distinct from the outstanding Flight count decremented below.
            let owner_handle = flight.owner.clone();
            let mut owner = owner_handle.lock();
            for (stage,credit) in flight.native_scheduler_credits.iter().enumerate() {
                if let Some(credit)=credit {
                    let lane=owner.lanes.as_ref().ok_or(EIO)?.get(stage).ok_or(EIO)?;
                    if !lane.ksm_state.as_ref().ok_or(EIO)?.can_retire(credit){return Err(EIO);}
                }
            }
            // Immutable Flight use ends before moving its non-copy credits.
            let render_root_scene=flight.render.as_ref().map(|r|(r.root,r.scene));
            for (stage,credit) in self.flights[index].native_scheduler_credits.iter_mut().enumerate() {
                if let Some(credit)=credit {
                    owner.lanes.as_mut().ok_or(EIO)?.get_mut(stage).ok_or(EIO)?
                        .ksm_state.as_mut().ok_or(EIO)?.retire(credit).ok_or(EIO)?;
                }
            }
            if let Some((root,scene)) = render_root_scene {
                let pool = self
                    .tvb_pools
                    .iter_mut()''')
 replace('''.find(|p| p.root == render.root)
                    .ok_or(EIO)?;
                pool.release_scene(render.scene);
            }
            let mut owner = flight.owner.lock();''','''.find(|p| p.root == root)
                    .ok_or(EIO)?;
                pool.release_scene(scene);
            }''')
 replace('self.context_users[flight.context as usize] -= 1;',
         'self.context_users[self.flights[index].context as usize] -= 1;')
 p.write_text(s)
 owner=out/'build-owner';shutil.copytree(target,owner);shutil.copyfile(base/'build-owner/Makefile',owner/'Makefile')
 j=dict(schema='m4rch.native-flight-retirement-stage.v9',base=str(base),stage=str(out),source_files=[pin(p)for p in sorted(target.rglob('*'))if p.is_file()],inputs=[pin(__file__),pin(KIT/'g16_t6040_scheduler_owner_v9.rs'),pin(base/'stage-receipt.json')],hardware_actions=[],submission_enabled=False,remaining=['Native producer sets actual notifier and both retained credit fields','Native PM scene/growth routing replaces donor TVB in caller stage','Hardware validates native stamp/notifier/transport completion before resource reuse'])
 (out/'stage-receipt.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(dict(stage=str(out),source_count=len(j['source_files']))))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();stage(a.base.resolve(),a.out.resolve())
