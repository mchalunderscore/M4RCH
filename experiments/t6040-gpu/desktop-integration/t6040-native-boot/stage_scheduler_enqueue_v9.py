#!/usr/bin/env python3
"""Connect retained native scheduler accounting to actual Gravity slot writes.

No startup gates are opened. Initial state and completion remain actual caller
inputs; no fabricated firmware completion or capacity credit is provided.
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
 p=target/'asahi_m4.rs';s=p.read_text();assert s.count('mod g16_vm;')==1
 s=s.replace('mod g16_vm;','#[allow(dead_code)] mod g16_t6040_scheduler_owner_v9;\nmod g16_vm;');p.write_text(s)
 p=target/'g16_runtime.rs';s=p.read_text()
 def replace(a,b):
  nonlocal s
  assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
 replace('    ksm_ring: u64,\n    head: u32,','    ksm_ring: u64,\n    ksm_state: Option<crate::g16_t6040_scheduler_owner_v9::State>,\n    head: u32,')
 replace('                    head: 0,\n                    new: true,','                    ksm_state: None,\n                    head: 0,\n                    new: true,')
 s+='''
impl Bootstrap {
    /// Bind source-derived initial timestamp/prior before native enqueue. This
    /// must happen once per retained lane; no implicit zero-epoch assumption.
    fn initialize_native_scheduler(&mut self,owner:&mut FirmwareQueues,stage:usize,
                                   timestamp:u64,cached_previous:Option<u64>)->Result {
        if !self.transport.native_t6040{return Err(EINVAL);}
        let id=owner.leases.ok_or(EIO)?.work_queue_id.get(stage).copied().ok_or(EINVAL)?;
        let lane=owner.lanes.as_mut().ok_or(EIO)?.get_mut(stage).ok_or(EINVAL)?;
        if lane.ksm_ring==0||lane.ksm_state.is_some(){return Err(EINVAL);}
        lane.ksm_state=Some(crate::g16_t6040_scheduler_owner_v9::State::from_values(
            u8::try_from(id).map_err(|_|EINVAL)?,256,timestamp,0,cached_previous).ok_or(EINVAL)?);
        Ok(())
    }

    /// Stage a complete native entry before its opcode14 firmware notification.
    /// Failed writes leave this retained lane quarantined. No completion credit
    /// or resource release is inferred from having copied bytes into the ring.
    fn stage_native_scheduler_entry(&mut self,owner:&mut FirmwareQueues,stage:usize,
                                    record:&[u8;0x200],submitted:u64,next:u64)
                                    ->Result<crate::g16_t6040_scheduler_owner_v9::Credit> {
        if !self.transport.native_t6040{return Err(EINVAL);}
        let lane=owner.lanes.as_mut().ok_or(EIO)?.get_mut(stage).ok_or(EINVAL)?;
        let state=lane.ksm_state.as_mut().ok_or(EIO)?;
        let header=u64::from_le_bytes(record[0..8].try_into().map_err(|_|EINVAL)?);
        if ((header>>42)&127)!=u64::from(state.queue_id){return Err(EINVAL);}
        let prepared=state.begin(submitted,next).ok_or(EBUSY)?;
        let address=lane.ksm_ring.checked_add(u64::from(prepared.slot)*0x200).ok_or(EINVAL)?;
        let fw=self._firmware_space.as_mut().ok_or(EIO)?;
        fw.write_live(address,record)?;
        crate::mem::sync();
        state.commit(prepared).ok_or(EIO)
    }

    /// Called only by the authoritative completion consumer, with this Flight's
    /// exact accumulated NOP+real-entry credit. Never from a prefetch cursor.
    fn retire_native_scheduler_entries(&mut self,owner:&mut FirmwareQueues,stage:usize,
                                       credit:&mut crate::g16_t6040_scheduler_owner_v9::Credit)->Result {
        let lane=owner.lanes.as_mut().ok_or(EIO)?.get_mut(stage).ok_or(EINVAL)?;
        lane.ksm_state.as_mut().ok_or(EIO)?.retire(credit).ok_or(EINVAL)
    }
}
''';p.write_text(s)
 owner=out/'build-owner';shutil.copytree(target,owner);shutil.copyfile(base/'build-owner/Makefile',owner/'Makefile')
 j=dict(schema='m4rch.native-scheduler-enqueue-stage-v9',base=str(base),stage=str(out),source_files=[pin(p)for p in sorted(target.rglob('*'))if p.is_file()],inputs=[pin(__file__),pin(KIT/'g16_t6040_scheduler_owner_v9.rs'),pin(base/'stage-receipt.json')],hardware_actions=[],submission_enabled=False,remaining=['Bind actual initial timestamp and cached prior','Call enqueue from complete native render/PM/transport branch','Consume actual firmware completion and native pending retirement before reuse'])
 (out/'stage-receipt.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(dict(stage=str(out),sources=len(j['source_files']))))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();stage(a.base.resolve(),a.out.resolve())
