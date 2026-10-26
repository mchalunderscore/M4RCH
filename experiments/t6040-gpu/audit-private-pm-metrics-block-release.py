#!/usr/bin/env python3
"""Qualify native metrics allocation release, including terminal block freeing."""
from pathlib import Path
base=Path(__file__).with_name('audit-private-pm-metrics.py')
setup=base.read_text().split('m.hook_add(u.UC_HOOK_CODE,metrics_hook);rng=')[0]
exec(compile(setup,str(base),'exec'))
START,END=0xfffffe00089f6ea4,0xfffffe00089f70d4
m.mem_map(0xfffffe00089f6000,4096);m.mem_write(START,read(START,END-START));POOLVT,FREE=0x233000,0x234000
m.mem_write(POOLVT+8,struct.pack('<Q',FREE));events=[]
def block_release_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);assert target==FREE
  assert m.reg_read(regs[0])==POOL and m.reg_read(regs[1])==RECORD;events.append(('free_record',));m.reg_write(regs[0],0);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,block_release_hook);rng=random.Random(604045);counts=dict(in_use=0,freed=0,cleared_slots=0)
for i in range(1024):
 block_index=i%8;slots=[8,32,64,128][(i//8)%4];used=bool(i&32);force=bool(i&64)
 pool=bytearray(rng.randbytes(0x100));struct.pack_into('<Q',pool,0,POOLVT);struct.pack_into('<QQ',pool,0x40,BLOCKS,16*8);struct.pack_into('<II',pool,0x50,16,8);struct.pack_into('<I',pool,0x60,slots);struct.pack_into('<Q',pool,0x90,BITS);struct.pack_into('<I',pool,0xa8,slots*16)
 bitbuf=bytearray(rng.randbytes(0x100));outer=sum(int(bool(struct.unpack_from('<Q',bitbuf,j*8)[0]))<<j for j in range(32));struct.pack_into('<Q',pool,0x88,outer)
 record=bytearray(rng.randbytes(0x100));struct.pack_into('<I',record,0,rng.randrange(1,100) if used else 0);blocks=bytearray(struct.pack('<16Q',*[RECORD]*16));ep=bytearray(pool);eb=bytearray(bitbuf);ev=bytearray(blocks)
 if not used:
  for slot in range(block_index*slots,(block_index+1)*slots):
   off=(slot//64)*8;word=struct.unpack_from('<Q',eb,off)[0]&~(1<<(slot%64));struct.pack_into('<Q',eb,off,word)
  new_outer=outer
  for group in range((block_index*slots)//64,((block_index+1)*slots-1)//64+1):
   if not struct.unpack_from('<Q',eb,group*8)[0]:new_outer &= ~(1<<group)
  struct.pack_into('<Q',ep,0x88,new_outer);struct.pack_into('<I',ep,0x54,7);struct.pack_into('<I',ep,0xa8,slots*15);struct.pack_into('<Q',ev,block_index*8,0);counts['freed']+=1;counts['cleared_slots']+=slots
 else:counts['in_use']+=1
 for addr,data in [(POOL,pool),(BITS,bitbuf),(RECORD,record),(BLOCKS,blocks)]:m.mem_write(addr,bytes(data))
 events.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X0,POOL),(c.UC_ARM64_REG_X1,block_index),(c.UC_ARM64_REG_X2,int(force)),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(START,STOP,count=1000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
 for addr,data in [(POOL,ep),(BITS,eb),(RECORD,record),(BLOCKS,ev)]:assert bytes(m.mem_read(addr,len(data)))==data,(i,hex(addr))
 assert events==([] if used else [('free_record',)])
report=dict(private_binary_sha256=sha,range=[hex(START),hex(END)],range_sha256=hashlib.sha256(read(START,END-START)).hexdigest(),counts=counts,qualification='1024 whole pool/bitmap/record/vector comparisons of actual releaseAllocationBlockIfPossible:512 in-use exits and512 zero-count frees, block indices0..7, slots8/32/64/128, partial/full/multiple bitmap words, force0/1;31000+ slot bits cleared and outer availability removed only when word becomes empty. External pool virtual8 freeAllocationBlock remains checked no-op; native vector entry zeroed, total slot capacity and allocated block count decremented. Fixtures16-entry vector so selected block is not last; replaceStorageArrays/shrink not qualified. No actual allocator teardown/cache/firmware lifetime proof.')
report['qualification']=report['qualification'].replace('31000+ slot bits',str(counts['cleared_slots'])+' slot bits')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
