//! Native 0x200-byte hardware scheduler record serialization.
//! Numeric transfer of previously source-qualified private_work_prefix/body.
//! This does not initialize TA/3D commands, execute their microsequences, publish
//! the queue, or establish completion. The caller owns all supplied identities.
pub const BYTES: usize = 0x200;
const U40: u64 = (1 << 40) - 1;
const U47: u64 = (1 << 47) - 1;
#[derive(Clone, Copy)]
pub struct RegisterList { pub gpu_address: u64, pub count: u8 }
#[derive(Clone, Copy)]
pub struct Dependency { pub converted_timestamp: u64, pub queue_id: u8 }
pub struct Bindings<'a> {
    pub timestamp: u64, pub queue_id: u8, pub priority: u8,
    pub capacity: u16, pub previous: u64,
    pub command: u64, pub firmware_queue: u64,
    pub aperture_address: u64, pub aperture_index: u8, pub aperture_count: u8,
    pub alternate_kind: bool, pub extra_flag: bool,
    pub dependencies: &'a [Dependency], pub qos: (u8,u16,u8),
    pub rce_kind: u8, pub register_lists: [RegisterList;4],
    pub masks: [u64;4], pub auxiliary: u64,
}
fn get(out: &[u8], offset: usize) -> u64 { u64::from_le_bytes(out[offset..offset+8].try_into().unwrap()) }
fn put(out: &mut [u8], offset: usize, value: u64) { out[offset..offset+8].copy_from_slice(&value.to_le_bytes()); }
/// Validate the complete binding before changing any output bytes.
pub fn write(out: &mut [u8], b: &Bindings<'_>) -> Option<u64> {
    if out.len()!=BYTES || b.queue_id>=128 || b.priority>=4 || !(1..=256).contains(&b.capacity)
        || b.dependencies.len()>8 || b.dependencies.iter().any(|d|d.queue_id>=24)
        || b.aperture_index>=64 || b.aperture_count>64 || (b.aperture_count!=0 && b.aperture_address&31!=0)
        || b.qos.2>=32 || b.rce_kind>=4 || b.command==0 || b.firmware_queue==0
        || b.register_lists.iter().any(|r|r.gpu_address&31!=0 || r.count>=128 || (r.gpu_address==0)!=(r.count==0)) { return None; }
    if b.aperture_count!=0 {
        let mut word=(get(out,8)&!63)|u64::from(b.aperture_index);
        word&=0xfffe00000000003f;
        word=(word&!(((1u64<<38)-1)<<6))|(((b.aperture_address>>5)&((1u64<<38)-1))<<6);
        word=(word&0xf03fffffffffffff)|((u64::from(b.aperture_count)-1)<<54);
        put(out,8,word);
    }
    let mut header=(get(out,0)&!3)|if b.alternate_kind {2} else {0};
    header=(header&0xf800000000000003)|((b.timestamp&U47)<<2)|(u64::from(b.queue_id)<<42);
    if b.aperture_count!=0 { header|=1<<58; }
    header=(header&0xc401fffffffffffe)|(u64::from(b.priority)<<59)|if b.extra_flag {1<<61} else {0};
    put(out,0,header);put(out,0x10,b.command);put(out,0x18,b.firmware_queue);
    for (i,d) in b.dependencies.iter().enumerate() {
        put(out,0x28+8*i,(get(out,0x28+8*i)&0xffff800000000000)|d.converted_timestamp|(u64::from(d.queue_id)<<40));
        put(out,0x20,get(out,0x20)|(1<<i));
    }
    let i=b.dependencies.len();
    put(out,0x28+8*i,(get(out,0x28+8*i)&!U47)|(b.previous&U47)|(u64::from(b.queue_id)<<40));
    let mut word=get(out,0x20)|(1<<i);
    word=(word&!(255<<32))|(u64::from(b.qos.0)<<32);
    word=(word&!(31<<40))|(u64::from(b.qos.2)<<40);
    word=(word&!(65535<<48))|(u64::from(b.qos.1)<<48);
    put(out,0x20,word);out[0x148]=b.rce_kind;
    for (i,r) in b.register_lists.iter().enumerate() {
        put(out,0x150+i*8,(get(out,0x150+i*8)&0xfffc000000000000)|((r.gpu_address>>5)&((1u64<<38)-1))|(u64::from(r.count)<<43));
    }
    for (i,m) in b.masks.iter().enumerate() { put(out,0x128+i*8,*m); }
    put(out,0x178,b.auxiliary);
    let low=((b.timestamp&255)+1)%u64::from(b.capacity);
    let middle=b.timestamp.wrapping_add(if low==0 {256} else {0})&0xffffffff00;
    Some((b.timestamp&0xffffff0000000000)|middle|low)
}
/// Event-machine arithmetic, retaining the source's wrapping unsigned behavior.
pub fn convert_timestamp(epoch:u64,event:u32,capacity:u16,initial:u64)->Option<u64> {
    if !(1..=256).contains(&capacity) { return None; }
    let combined=((epoch<<24)|u64::from(event>>8)).wrapping_sub(1);
    let c=u64::from(capacity);let quotient=combined/c;let remainder=combined%c;
    let sum=(initial&255)+(remainder&255);let carry=sum/c;let slot=sum%c;
    let high=((initial>>8).wrapping_add(quotient).wrapping_add(carry))&0xffffffff;
    Some((high<<8)|(slot&255))
}
/// Logical command spans; selected TA pool allocation rounds its 0x9a0 live
/// producer span to 0x9c0. A native command cannot reuse donor offsets.
pub const TA_POOL_STRIDE: usize=0x9c0;
pub const FRAGMENT_BYTES: usize=0x2240;
pub const COMPUTE_BYTES: usize=0x1040;
pub const TIMESTAMP_MASK: u64=U40;
