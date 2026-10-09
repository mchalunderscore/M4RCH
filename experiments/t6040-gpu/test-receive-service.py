#!/usr/bin/env python3
"""Replay the actual receive-service C transport against saved and synthetic RAM.

Compiles the source prefix before its sysfs reader with checked memory stubs.
Owned 16 KiB pages have separate allocations; no kernel module or MMIO is used.
This verifies transport behavior, not hardware cache coherence or workqueues.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAPTURE = ROOT / 'out/gpc-telemetry-recovery/candidate/asc-graph-init/boot-f5f3a7cc-53aa-4fb1-9a60-3d8270925cfc'
DEFAULT_SERVICE = Path(__file__).with_name('asc-graph-init') / 'receive-service.h'

PREAMBLE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
#define PAGE_SIZE 16384U
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define BIT(n) (1ULL << (n))
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define pr_err(...) ((void)0)
static void *recovery_ptr(unsigned int offset);
static void recovery_invalidate(void *ptr,size_t bytes);
static u32 recovery_read32(unsigned int offset);
static void recovery_write32(unsigned int offset,u32 value);
static u32 get_unaligned_le32(const void *ptr) {
 const u8 *p=ptr;return (u32)p[0]|(u32)p[1]<<8|(u32)p[2]<<16|(u32)p[3]<<24;
}
static u16 get_unaligned_le16(const void *ptr) {
 const u8 *p=ptr;return (u16)p[0]|(u16)p[1]<<8;
}
'''

REPLAY = r'''
static u8 **pages,*original;
static unsigned int arena_bytes,page_count,acks,boundary_chunks;
static int append_ring=-1;
static u32 appended_producer;
static void *recovery_ptr(unsigned int offset) {
 assert(offset<arena_bytes);return pages[offset/PAGE_SIZE]+offset%PAGE_SIZE;
}
static unsigned int address_offset(const void *ptr,size_t size) {
 uintptr_t p=(uintptr_t)ptr;
 for(unsigned int i=0;i<page_count;i++) {
  uintptr_t start=(uintptr_t)pages[i];
  if(p>=start && p<start+PAGE_SIZE) {
   assert(size<=PAGE_SIZE-(p-start));
   return i*PAGE_SIZE+(unsigned int)(p-start);
  }
 }
 assert(!"Access outside owned page allocations");return 0;
}
static void put32(unsigned int offset,u32 value) {
 u8 *p=recovery_ptr(offset);address_offset(p,4);
 for(unsigned int i=0;i<4;i++) p[i]=(u8)(value>>(8*i));
}
static void recovery_invalidate(void *ptr,size_t bytes) {
 unsigned int offset=address_offset(ptr,bytes);
 if(bytes<72 && offset%PAGE_SIZE+bytes==PAGE_SIZE) boundary_chunks++;
 if(append_ring>=0 && offset==receive_rings[append_ring].ring) {
  put32(receive_rings[append_ring].state+32,appended_producer);append_ring=-1;
 }
}
static u32 recovery_read32(unsigned int offset) {
 void *p=recovery_ptr(offset);address_offset(p,4);return get_unaligned_le32(p);
}
static u8 byte_at(unsigned int offset) {return *(u8 *)recovery_ptr(offset);}
static void recovery_write32(unsigned int offset,u32 value) {
 unsigned int id;
 for(id=0;id<ARRAY_SIZE(receive_rings);id++) if(receive_rings[id].state==offset) break;
 assert(id<ARRAY_SIZE(receive_rings)); /* Only host read cursors may be written. */
 unsigned int capacity=receive_rings[id].capacity,old=recovery_read32(offset);
 unsigned int count=(value+capacity-old)%capacity;
 assert(value<capacity && count && count<=receive_journal.used);
 unsigned int first=receive_journal.used-count;
 /* Every acknowledged byte must already exist in the append journal. */
 for(unsigned int n=0;n<count;n++) {
  struct receive_record *r=&receive_journal.records[first+n];
  unsigned int index=(old+n)%capacity;
  assert(r->ring==id && r->index==index && r->sequence==first+n);
  for(unsigned int b=0;b<72;b++) assert(r->bytes[b]==byte_at(receive_rings[id].ring+index*72+b));
 }
 u8 before[48];for(unsigned int i=0;i<48;i++) before[i]=byte_at(offset+i);
 put32(offset,value);
 for(unsigned int i=4;i<48;i++) assert(before[i]==byte_at(offset+i));
 acks++;
}
static void reset(bool captured) {
 for(unsigned int i=0;i<page_count;i++) {
  memset(pages[i],0,PAGE_SIZE);memset(pages[i]+PAGE_SIZE,0xa5,64);
  if(captured) memcpy(pages[i],original+i*PAGE_SIZE,PAGE_SIZE);
 }
 receive_journal.used=receive_journal.status=receive_journal.doorbells=0;
 memset(receive_journal.records,0,sizeof(receive_journal.records));
 receive_enabled=true;receive_crashed=false;acks=boundary_chunks=0;append_ring=-1;
}
static void record(unsigned int id,unsigned int index,u32 type,u16 selector) {
 unsigned int start=receive_rings[id].ring+index*72;
 for(unsigned int i=0;i<72;i++) *(u8 *)recovery_ptr(start+i)=(u8)(i+index);
 put32(start,type);
 *(u8 *)recovery_ptr(start+20)=(u8)selector;
 *(u8 *)recovery_ptr(start+21)=(u8)(selector>>8);
}
static void cursors(unsigned int id,u32 read,u32 write) {
 put32(receive_rings[id].state,read);put32(receive_rings[id].state+32,write);
}
static void check_guards(void) {
 for(unsigned int i=0;i<page_count;i++) for(unsigned int j=0;j<64;j++) assert(pages[i][PAGE_SIZE+j]==0xa5);
}
int main(int argc,char **argv) {
 assert(argc==2);FILE *file=fopen(argv[1],"rb");assert(file);
 assert(!fseek(file,0,SEEK_END));long length=ftell(file);assert(length>0 && length%PAGE_SIZE==0);
 arena_bytes=(unsigned int)length;page_count=arena_bytes/PAGE_SIZE;rewind(file);
 original=malloc(arena_bytes);assert(original && fread(original,1,arena_bytes,file)==arena_bytes);fclose(file);
 pages=calloc(page_count,sizeof(*pages));assert(pages);
 for(unsigned int i=0;i<page_count;i++) {pages[i]=malloc(PAGE_SIZE+64);assert(pages[i]);}
 _Static_assert(sizeof(struct receive_record)==80,"Journal entry ABI");
 _Static_assert(sizeof(receive_journal)==64+65536*80,"Journal header ABI");

 reset(true);
 assert(recovery_read32(receive_rings[11].state)==0);
 assert(recovery_read32(receive_rings[11].state+32)==255);
 assert(receive_drain());assert(receive_journal.used==255 && acks==1);
 assert(recovery_read32(receive_rings[11].state)==255);
 assert(recovery_read32(receive_rings[11].state+32)==255);
 assert(boundary_chunks>0); /* Captured record227 crosses a16KiB boundary. */
 for(unsigned int i=0;i<255;i++) {
  struct receive_record *r=&receive_journal.records[i];
  assert(r->ring==11 && r->index==i && r->sequence==i);
  assert(!memcmp(r->bytes,original+receive_rings[11].ring+i*72,72));
 }
 assert(receive_drain() && receive_journal.used==255 && acks==1);
 check_guards();puts("PASS captured255: exact copies before ack, producer preserved, cross-page copy, repeat empty drain");

 reset(false);cursors(11,254,2);
 for(unsigned int i=0;i<4;i++) record(11,(254+i)%256,17,0);
 assert(receive_drain() && receive_journal.used==4 && acks==1);
 for(unsigned int i=0;i<4;i++) assert(receive_journal.records[i].index==(254+i)%256);
 assert(recovery_read32(receive_rings[11].state)==2);check_guards();
 puts("PASS wrap:254,255,0,1 acknowledged through2");

 reset(false);cursors(11,0,1);record(11,0,17,0);record(11,1,18,0);
 append_ring=11;appended_producer=2;
 assert(receive_drain() && receive_journal.used==1);
 assert(recovery_read32(receive_rings[11].state)==1 && recovery_read32(receive_rings[11].state+32)==2);
 assert(receive_drain() && receive_journal.used==2 && acks==2);
 puts("PASS producer snapshot: concurrent append preserved and consumed on next drain");

 for(unsigned int id=0;id<ARRAY_SIZE(receive_rings);id++) for(unsigned int producer=0;producer<2;producer++) {
  reset(false);cursors(id,producer?0:receive_rings[id].capacity,producer?receive_rings[id].capacity:0);
  assert(!receive_drain() && receive_journal.status==5 && receive_journal.used==0 && acks==0);
 }
 puts("PASS cursor bounds: all12rings reject invalid read and write without acknowledgement");

 reset(false);cursors(11,0,1);record(11,0,17,0);receive_journal.used=RECEIVE_CAPACITY;
 assert(!receive_drain() && receive_journal.status==3 && acks==0);
 assert(recovery_read32(receive_rings[11].state)==0 && !receive_drain());
 reset(false);cursors(11,0,2);record(11,0,17,0);record(11,1,18,0);receive_journal.used=RECEIVE_CAPACITY-1;
 assert(!receive_drain() && receive_journal.status==3 && receive_journal.used==RECEIVE_CAPACITY && acks==0);
 assert(recovery_read32(receive_rings[11].state)==0);
 puts("PASS journal full: full and partially copied batches remain unacknowledged and sealed");

 reset(false);cursors(0,0,2);record(0,0,0,0);record(0,1,1,23);
 assert(receive_drain() && receive_journal.used==2 && acks==1);
 for(unsigned int variant=0;variant<4;variant++) {
  reset(false);cursors(0,0,1);record(0,0,variant==0?4:variant==1?1:variant==2?32:31,24);
  assert(!receive_drain() && receive_journal.status==9 && receive_journal.used==1 && acks==0);
  assert(recovery_read32(receive_rings[0].state)==0);
 }
 puts("PASS event validation: accepted0/1, unsupported callback, invalid selector/type preserved without ack");

 reset(false);cursors(11,0,1);record(11,0,17,0);
 assert(receive_mailbox(0x0042000000000000ULL,0xdead0020ULL));
 assert(receive_journal.doorbells==1 && receive_journal.used==1 && !receive_crashed);
 assert(!receive_mailbox(0x1234,1) && receive_crashed && receive_journal.status==9);
 assert(!receive_mailbox(0x0042000000000000ULL,32) && acks==1);
 reset(false);assert(!receive_mailbox(0x0043000000000000ULL,32) && !receive_crashed && receive_journal.status==9);
 puts("PASS mailbox:42/EP32 drains, EP1 seals as crash, unexpected message seals, no post-failure ack");

 reset(false);receive_enabled=false;cursors(11,0,1);record(11,0,17,0);
 assert(receive_drain() && receive_journal.used==0 && acks==0);
 check_guards();puts("PASS disabled service: no copying or acknowledgement");
 for(unsigned int i=0;i<page_count;i++) free(pages[i]);
 free(pages);free(original);
 return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument('--service', type=Path, default=DEFAULT_SERVICE)
    parser.add_argument('--cc', default='cc')
    args = parser.parse_args()
    compiler = shutil.which(args.cc)
    if compiler is None:
        parser.error('A local C compiler is required')
    service = args.service.read_text()
    marker = 'static ssize_t receive_read('
    if service.count(marker) != 1:
        parser.error('Expected the actual receive-service prefix before its sysfs reader')
    prefix = service.split(marker)[0]
    layout = json.loads((args.capture.parent / 'graph-receipt.json').read_text())
    objects = {item['name']: item for item in layout['objects']}
    specs = [('receive13_state_a', 'receive13_aux', 0, 0, 256, 0x2000ffd3)]
    specs += [('receive13_state_b', 'receive13_ring', i*48, i*0x4800, 256, 4) for i in range(9)]
    specs += [('receive14_state_a', 'receive14_aux', 0, 0, 512, 0x20),
              ('receive14_state_b', 'receive14_ring', 0, 0, 256, 0x5fff0000)]
    rows = []
    for state, ring, state_offset, ring_offset, capacity, mask in specs:
        assert state_offset + 48 <= objects[state]['input_bytes']
        assert ring_offset + capacity*72 <= objects[ring]['input_bytes']
        rows.append((objects[state]['arena_offset'] + state_offset,
                     objects[ring]['arena_offset'] + ring_offset, capacity, mask))
    descriptors = 'static const struct { unsigned int state,ring,capacity,type_mask; } receive_rings[] = {\n'
    descriptors += ''.join(' {%dU,%dU,%dU,%dU},\n' % row for row in rows) + '};\n'
    source = PREAMBLE + descriptors + prefix + REPLAY
    with tempfile.TemporaryDirectory(prefix='m4rch-receive-replay-') as directory:
        c_file, binary = Path(directory) / 'replay.c', Path(directory) / 'replay'
        c_file.write_text(source)
        subprocess.run([compiler, '-std=c11', '-O0', '-Wall', '-Wextra', '-Werror',
                        str(c_file), '-o', str(binary)], check=True)
        subprocess.run([str(binary), str((args.capture / 'objects-after.bin').resolve())], check=True)
    print(json.dumps(dict(service_sha256=hashlib.sha256(service.encode()).hexdigest(),
                          capture_objects_sha256=hashlib.sha256((args.capture / 'objects-after.bin').read_bytes()).hexdigest(),
                          qualification='Actual C transport replay with stubbed RAM/cache helpers. '
                                        'No hardware/cache-coherency/workqueue lifecycle proof.'), indent=2))


if __name__ == '__main__':
    main()
