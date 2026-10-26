#!/usr/bin/env python3
"""Stage typed native PM owners/allocator offline. Does not enable submission."""
import argparse,hashlib,json,shutil
from pathlib import Path
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[3]
def pin(p):p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def stage(base,out):
 source=base/'source/linux/drivers/gpu/drm/asahi';target=out/'source/linux/drivers/gpu/drm/asahi';owner=out/'build-owner';out.mkdir(exist_ok=False,parents=True);shutil.copytree(source,target)
 for n in ['g16_t6040_pm_v9.rs','g16_t6040_pm_owned_v9.rs']:shutil.copyfile(KIT/n,target/n)
 p=target/'asahi_m4.rs';s=p.read_text();assert s.count('mod g16_tvb;')==1;s=s.replace('mod g16_tvb;','mod g16_tvb;\n#[allow(dead_code)] mod g16_t6040_pm_v9;\n#[allow(dead_code)] mod g16_t6040_pm_owned_v9;');p.write_text(s)
 p=target/'g16_vm.rs';s=p.read_text();marker='impl AddressSpace {';assert s.count(marker)==1
 method='''impl AddressSpace {
    /// Reserve client aliases of freshly owned nativePM firmware pages. The
    /// reservation is permanent until this retained address space retires.
    /// Actual mapping is caller-owned and uses map_work_alias identity checks.
    pub(crate) fn reserve_native_pm_alias(&mut self,size:usize)->Result<u64> {
        if size==0 || size&0x3fff!=0{return Err(EINVAL);}
        let mut arena=self.render_arena.clone();
        let range=arena.alloc_back(size as u64,0x4000).ok_or(ENOSPC)?;
        for va in (range.start..range.end).step_by(0x4000) {
            if self.pages.get(&va).is_some() || self.low.translate(va)?.is_some(){return Err(EEXIST);}
        }
        self.render_arena=arena;Ok(range.start)
    }
''';s=s.replace(marker,method);p.write_text(s)
 shutil.copytree(target,owner);shutil.copyfile(base/'build-owner/Makefile',owner/'Makefile')
 rows=[pin(p) for p in sorted(target.rglob('*')) if p.is_file()];edits=[p['path']for p in rows if not (source/Path(p['path']).relative_to(target)).exists() or pin(source/Path(p['path']).relative_to(target))['sha256']!=p['sha256']]
 report=dict(schema='m4rch.native-pm-owned-source-stage.v9',base=str(base),stage=str(out),source_files=rows,edited=edits,inputs=[pin(__file__),pin(KIT/'g16_t6040_pm_v9.rs'),pin(KIT/'g16_t6040_pm_owned_v9.rs'),pin(base/'stage-receipt.json')],submission_enabled=False,hardware_actions=[],remaining=['Runtime uses explicit qualified native geometry and these owners instead of donorTVB serialized fields','Join retained command/SKU/controller/descriptor sources before readiness'])
 (out/'stage-receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(stage=str(out),edited=edits)))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();stage(a.base.resolve(),a.out.resolve())
