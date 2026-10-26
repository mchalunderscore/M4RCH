#!/usr/bin/env python3
"""Complete native POST recovery record attribution without DMA retirement."""
def wiring(files):
    s=files['g16_runtime.rs']
    marker='pub(super) struct Flight {';assert s.count(marker)==1
    definition='''
/// Native AGFIRecoveryInfo record retained with exact submitted stage identity.
/// Error delivery is separate from queue credit, page and notifier retirement.
#[derive(Clone,Copy,Debug)]
#[allow(dead_code)]
pub(super) struct NativeRecoveryRecord {
    generation:u64, record_index:u16, flags:u32, stamp_index:u32, stamp_value:u32,
}
'''
    s=s.replace(marker,definition+marker,1)
    marker='    native_notifier: Option<u64>,';assert s.count(marker)==1
    s=s.replace(marker,marker+'''
    native_recovery:[Option<NativeRecoveryRecord>;2],
    native_recovery_reported:bool,''')
    # All constructors initialize independent recovery bookkeeping. Both old
    # donor paths and native paths remain source-compatible.
    s=s.replace('native_notifier: None,','native_notifier: None,native_recovery:[None,None],native_recovery_reported:false,')
    s=s.replace('native_notifier:Some(notifier)},','native_notifier:Some(notifier),native_recovery:[None,None],native_recovery_reported:false},')
    marker='impl Bootstrap {\n';assert s.count(marker)>=1
    method='''
    /// Called only between firmware POST3 and the host's resume0 publication.
    /// Apple 89c9d9c/89c9fb4 both traverse 256 records at support+40b8;
    /// flags bit0 validates, bits4..10 select stamp index, second word is value.
    pub(super) fn native_attribute_recovery_records(&mut self,generation:u64)->Result {
        if !self.transport.native_t6040 || !self.render_failed{return Err(EBUSY);}
        let base=self.transport.roots.status_b;
        let fw=self._firmware_space.as_ref().ok_or(EIO)?;
        if fw.read_u64(base+0x48f0)?!=generation || fw.read_u32(base+0x4900)?!=3 {
            return Err(EBUSY);
        }
        self.native_recovery_records.reserve(256,GFP_KERNEL)?;
        for index in 0..256u64 {
            let flags=fw.read_u32(base+0x40b8+index*8)?;
            if flags&1==0{continue;}
            let record=NativeRecoveryRecord{generation,record_index:index as u16,
                flags,stamp_index:(flags>>4)&0x7f,
                stamp_value:fw.read_u32(base+0x40bc+index*8)?};
            // Preserve all valid rows, including orphan/unmatched identities.
            // Do not manufacture a submitted job or a successful completion.
            self.native_recovery_records.push(record,GFP_KERNEL)?;
            for flight in &mut self.flights {
                if flight.native_notifier.is_none(){continue;}
                for stage in 0..2 {
                    if flight.stamps[stage].is_some_and(|stamp|
                        stamp.event==record.stamp_index && stamp.value==record.stamp_value) {
                        if let Some(previous)=flight.native_recovery[stage] {
                            if previous.generation!=generation{return Err(EIO);}
                        }
                        flight.native_recovery[stage]=Some(record);
                    }
                }
            }
        }
        // The firmware recovery callback carries bit1 (abort) and bit2
        // (callback detail) to native error metadata. Linux retains these raw
        // bits and reports EIO for the affected submitted job. It never writes
        // successful stamps, notifier counts or scheduler consumer credits.
        Ok(())
    }

    fn native_take_recovery_error(&mut self)->Option<(u64,Result)> {
        for flight in &mut self.flights {
            if !flight.native_recovery_reported && flight.native_recovery.iter().any(Option::is_some) {
                flight.native_recovery_reported=true;
                return Some((flight.id,Err(EIO)));
            }
        }
        for old in &mut self.native_retained_applications {
            for flight in &mut old.flights {
                if !flight.native_recovery_reported && flight.native_recovery.iter().any(Option::is_some) {
                    flight.native_recovery_reported=true;
                    return Some((flight.id,Err(EIO)));
                }
            }
        }
        None
    }
'''
    s=s.replace(marker,marker+method,1)
    marker='    pub(crate) fn retire(&mut self) -> Result<Option<(u64, Result)>> {'
    assert s.count(marker)==1
    s=s.replace(marker,marker+'''
        // Userspace receives terminal error attribution once, while the old
        // Flight remains the owner of all DMA backing and scheduler credits.
        if let Some(result)=self.native_take_recovery_error(){return Ok(Some(result));}''',1)
    files['g16_runtime.rs']=s
    s=files['g16.rs']
    marker='    native_retained_applications:KVec<NativeRetainedApplication>,'
    assert s.count(marker)==1
    s=s.replace(marker,marker+'\n    native_recovery_records:KVec<render_runtime::NativeRecoveryRecord>,',1)
    marker='            native_retained_applications:KVec::new(),';assert s.count(marker)==1
    s=s.replace(marker,marker+'\n            native_recovery_records:KVec::new(),',1)
    files['g16.rs']=s
