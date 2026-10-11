#!/usr/bin/env python3
"""Join separate native KSM storage/configuration into a retained Gravity stage.

Keeps submission gates closed. Capacity256 is an explicit Linux experiment.
Does not install/load a module, access hardware or change a frozen trial.
"""
import argparse,hashlib,json,shutil
from pathlib import Path
KIT=Path(__file__).resolve().parent
def pin(p):
 p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def stage(base,out):
 src=base/'source/linux/drivers/gpu/drm/asahi';dst=out/'source/linux/drivers/gpu/drm/asahi'
 out.mkdir(parents=True,exist_ok=False);shutil.copytree(src,dst)
 p=dst/'g16_runtime.rs';s=p.read_text()
 def replace(a,b):
  nonlocal s
  assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
 replace('    ring: u64,\n    head: u32,','    ring: u64,\n    /// Separate native 256-entry, 0x200-byte hardware scheduler backing.\n    ksm_ring: u64,\n    head: u32,')
 replace('self.next_work_va = base.checked_add(0x24000).ok_or(ENOSPC)?;',
         'self.next_work_va = base.checked_add(if self.transport.native_t6040 { 0x84000 } else { 0x24000 }).ok_or(ENOSPC)?;')
 replace('                    ring: queue + 0x8000,\n                    head: 0,',
         '                    ring: queue + 0x8000,\n                    ksm_ring: if self.transport.native_t6040 { base + 0x24000 + stage as u64 * 0x20000 } else { 0 },\n                    head: 0,')
 replace('''                    // AGXKSMKickQueue+80/+88 are two task mappings of the
                    // same IOGPUSysMemory backing. Own that alias concretely.
                    let device_ring = 0x72_0000_0000 + (lane.ring - 0xffff_fc22_0000_0000);
                    let pa = fw.physical(lane.ring)?;
                    self._address_space.as_mut().ok_or(EIO)?.map_work_alias(device_ring, pa)?;''',
 '''                    // Hardware KSM entries are not the 8-byte firmware pointer
                    // ring. Explicit Linux capacity256, native entry stride200.
                    fw.alloc(lane.ksm_ring, 0x20000, PROT_FW_SHARED_RW)?;
                    for offset in (0..0x20000u64).step_by(0x4000) {
                        let address = lane.ksm_ring + offset;
                        let device = 0x72_0000_0000 + (address - 0xffff_fc22_0000_0000);
                        let pa = fw.physical(address)?;
                        self._address_space.as_mut().ok_or(EIO)?.map_work_alias(device, pa)?;
                    }''')
 replace('let device_ring = 0x72_0000_0000 + (lane.ring - 0xffff_fc22_0000_0000);',
         'let device_ring = 0x72_0000_0000 + (lane.ksm_ring - 0xffff_fc22_0000_0000);')
 replace('let command = input.configuration(device_ring, leases.work_queue_id[stage],',
         'let command = input.configuration(device_ring, lane.ksm_ring, leases.work_queue_id[stage],')
 p.write_text(s)
 p=dst/'g16_queue_owner.rs';s=p.read_text()
 s=s.replace('two views of the same owned KSM pointer-ring','two views of the separately owned hardware KSM entry-ring')
 assert s.count('configuration(&self, device_ring: u64, work_queue_id: u32,')==1
 s=s.replace('configuration(&self, device_ring: u64, work_queue_id: u32,','configuration(&self, device_ring: u64, firmware_ksm_ring: u64, work_queue_id: u32,')
 s=s.replace('device_ring == 0 || self.ring == 0','device_ring == 0 || firmware_ksm_ring == 0')
 s=s.replace('copy_from_slice(&self.ring.to_le_bytes());','copy_from_slice(&firmware_ksm_ring.to_le_bytes());')
 p.write_text(s)
 owner=out/'build-owner';shutil.copytree(dst,owner);shutil.copyfile(base/'build-owner/Makefile',owner/'Makefile')
 rows=[pin(p)for p in sorted(dst.rglob('*'))if p.is_file()]
 j=dict(schema='m4rch.native-render-transport-stage-v9',base=str(base),stage=str(out),source_files=rows,inputs=[pin(__file__),pin(base/'stage-receipt.json')],hardware_actions=[],submission_enabled=False,experimental_policy={'ksm_capacity':256,'entry_stride':512,'mapping':'Retained existing bootstrap address space and firmware aliases'},remaining=['Actual hardware entry enqueue and pending/completed accounting','Native command/PM/transport caller branch','Complete retirement and power teardown hardware validation'])
 (out/'stage-receipt.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(dict(stage=str(out),source_count=len(rows))))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();stage(a.base.resolve(),a.out.resolve())
