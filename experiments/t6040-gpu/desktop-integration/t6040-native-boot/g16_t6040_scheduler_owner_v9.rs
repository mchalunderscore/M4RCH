// SPDX-License-Identifier: GPL-2.0-only
//! Retained scheduler accounting around the actual native hardware entry ring.
//! Caller serializes access with Gravity's ownership mutex. An interrupted
//! write quarantines the state; no retry/reuse follows ambiguous publication.
#[derive(Clone,Copy,Debug,PartialEq)]
pub struct State {
    pub queue_id:u8,
    pub capacity:u16,
    pub timestamp:u64,
    pub pending:u32,
    pub cached_previous:Option<u64>,
    pub quarantined:bool,
}
#[derive(Clone,Copy,Debug,PartialEq)]
pub struct Prepared { pub slot:u16,pub submitted:u64,pub next:u64,old_pending:u32 }
/// Move this into the retained Flight. No Clone/Copy: credit retires once.
#[derive(Debug,PartialEq)]
pub struct Credit {queue_id:u8,capacity:u16,first:u64,end:u64,count:u32,retired:bool}
impl Credit {
    pub fn count(&self)->u32{self.count}
    /// Include scheduling NOPs and the real entry in one descriptor's count.
    pub fn append(&mut self,other:&mut Self)->Option<()> {
        if self.retired||other.retired||self.queue_id!=other.queue_id||self.capacity!=other.capacity
            ||self.end!=other.first{return None;}
        let count=self.count.checked_add(other.count)?;
        if count>u32::from(self.capacity){return None;}
        self.end=other.end;self.count=count;other.retired=true;Some(())
    }
}
pub fn next_timestamp(timestamp:u64,capacity:u16)->Option<u64> {
    if !(1..=256).contains(&capacity){return None;}
    let low=((timestamp&255)+1)%u64::from(capacity);
    let middle=timestamp.wrapping_add(if low==0{256}else{0})&0xffffffff00;
    Some((timestamp&0xffffff0000000000)|middle|low)
}
impl State {
    /// All initial values must come from the actual owner initialization.
    /// This constructor supplies no guessed epoch, cached prior or completion.
    pub fn from_values(queue_id:u8,capacity:u16,timestamp:u64,pending:u32,cached_previous:Option<u64>)->Option<Self> {
        if queue_id>=128||!(1..=256).contains(&capacity)||timestamp&255>=u64::from(capacity)
            ||pending>u32::from(capacity){return None;}
        Some(Self{queue_id,capacity,timestamp,pending,cached_previous,quarantined:false})
    }
    /// Refuse full queues before touching backing. Native's equality diagnostic
    /// occurs after LDADD; Linux admission must prevent that overflowing path.
    pub fn begin(&mut self,submitted:u64,next:u64)->Option<Prepared> {
        if self.quarantined||self.pending>=u32::from(self.capacity)||submitted!=self.timestamp
            ||Some(next)!=next_timestamp(submitted,self.capacity){return None;}
        let prepared=Prepared{slot:(submitted&255)as u16,submitted,next,old_pending:self.pending};
        self.quarantined=true;
        Some(prepared)
    }
    /// Call only after the owned slot's full0x200bytes and publication barrier.
    /// Firmware transport announcement is a subsequent, separately owned step.
    pub fn commit(&mut self,p:Prepared)->Option<Credit> {
        if !self.quarantined||p.submitted!=self.timestamp||p.old_pending!=self.pending
            ||p.slot!=((self.timestamp&255)as u16)||Some(p.next)!=next_timestamp(self.timestamp,self.capacity)
            ||self.pending>=u32::from(self.capacity){return None;}
        self.timestamp=p.next;self.pending+=1;self.cached_previous=Some(p.submitted);
        self.quarantined=false;Some(Credit{queue_id:self.queue_id,capacity:self.capacity,
            first:p.submitted,end:p.next,count:1,retired:false})
    }
    /// Caller requires authoritative descriptor completion and DMA lifetime
    /// evidence. Queue prefetch/type1 bits alone never authorize this call.
    pub fn retire(&mut self,credit:&mut Credit)->Option<()> {
        if self.quarantined||credit.retired||credit.queue_id!=self.queue_id
            ||credit.capacity!=self.capacity||credit.count>self.pending{return None;}
        self.pending-=credit.count;credit.retired=true;Some(())
    }
}
