/* SPDX-License-Identifier: GPL-2.0-only */
/* Native 72-byte RX transport, also used by Gravity's notification worker.
 * All calls hold graph_io_lock, or precede the resident worker's startup.
 * This only acknowledges copied transport records; no GPU backing is freed.
 */
#define RECEIVE_CAPACITY 65536U
struct receive_record { u16 ring,index; u32 sequence; u8 bytes[72]; };
static struct {
 u32 magic,version,entry_bytes,capacity,used,status,doorbells,reserved;
 u64 reserved64[4];
 struct receive_record records[RECEIVE_CAPACITY];
} receive_journal = { .magic=0x5852474d, .version=1, .entry_bytes=80,
 .capacity=RECEIVE_CAPACITY };
static_assert(sizeof(struct receive_record)==80);
static_assert(sizeof(receive_journal)==64+RECEIVE_CAPACITY*80);
static bool receive_enabled,receive_crashed;
static bool receive_fail(u32 reason)
{
 receive_journal.status|=1|reason;
 pr_err("m4rch receive: sealed status=%#x records=%u doorbells=%u\n",
  receive_journal.status,receive_journal.used,receive_journal.doorbells);
 return false;
}
static void receive_copy(u8 *to,unsigned int offset,size_t size)
{
 while(size) {
  size_t n=min_t(size_t,size,PAGE_SIZE-offset%PAGE_SIZE);
  void *from=recovery_ptr(offset);
  recovery_invalidate(from,n);memcpy(to,from,n);
  to+=n;offset+=n;size-=n;
 }
}
static bool receive_drain(void)
{
 unsigned int id;
 if(!receive_enabled) return true;
 if(receive_journal.status) return false;
 for(id=0;id<ARRAY_SIZE(receive_rings);id++) {
  unsigned int state=receive_rings[id].state,capacity=receive_rings[id].capacity;
  u32 read=recovery_read32(state),write=recovery_read32(state+0x20),initial=read;
  if(read>=capacity || write>=capacity) return receive_fail(4);
  /* Snapshot producer once; at most capacity-1 records per queue per call.
   * Firmware retains unread slots until this host advances the consumer. */
  while(read!=write) {
   struct receive_record *record;u32 type;
   if(receive_journal.used==RECEIVE_CAPACITY) return receive_fail(2);
   record=&receive_journal.records[receive_journal.used];
   record->ring=id;record->index=read;record->sequence=receive_journal.used;
   receive_copy(record->bytes,receive_rings[id].ring+read*72,72);
   receive_journal.used++;
   type=get_unaligned_le32(record->bytes);
   if(type>=32 || !(receive_rings[id].type_mask&BIT(type))) return receive_fail(8);
   /* Native controller event0 is a no-op callback; event1 carries completion
    * bits. Preserve other event records without pretending to handle
    * recovery/error callbacks, and leave their slot unacknowledged. */
   if(id==0 && (type>1 || (type==1 && get_unaligned_le16(record->bytes+20)>=24)))
    return receive_fail(8);
   read=(read+1)%capacity;
  }
  if(read!=initial) {
   /* Same invalidate/store/clean publication used by Gravity write_live.
    * Preserve producer+0x20; never zero/reset any firmware-owned cursor. */
   recovery_write32(state,read);
  }
 }
 return true;
}
static bool receive_mailbox(u64 message,u64 metadata)
{
 if((metadata&0xff)==32 && message==0x0042000000000000ULL) {
  receive_journal.doorbells++;
  return receive_drain();
 }
 if((metadata&0xff)==1) receive_crashed=true;
 pr_err("m4rch receive: unexpected message=%#llx metadata=%#llx\n",message,metadata);
 return receive_fail(8);
}
static ssize_t receive_read(struct file *file,struct kobject *kobj,
 const struct bin_attribute *attr,char *buf,loff_t off,size_t count)
{
 if(off<0) return -EINVAL;
 if(off>=sizeof(receive_journal)) return 0;
 count=min_t(size_t,count,sizeof(receive_journal)-off);
 mutex_lock(&graph_io_lock);
 memcpy(buf,(u8 *)&receive_journal+off,count);
 mutex_unlock(&graph_io_lock);
 return count;
}
static struct bin_attribute receive_raw={.attr={.name="notifications",.mode=0400},
 .read=receive_read,.size=sizeof(receive_journal)};
