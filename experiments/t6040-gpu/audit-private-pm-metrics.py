#!/usr/bin/env python3
"""Execute native PM page-metrics registration and bitmap/resource outputs."""
from pathlib import Path
base=Path(__file__).with_name('audit-private-render-inputs.py');setup=base.read_text().split('rng=random.Random(604011);')[0].replace('m.hook_add(u.UC_HOOK_CODE,hook)','handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(handle)
START,END=0xfffffe00089f740c,0xfffffe00089f7890
m.mem_map(0xfffffe00089f7000,4096);m.mem_write(START,read(START,END-START));m.mem_map(0x220000,0x20000)
GART,POOL,BLOCKS,RECORD,RESOURCE,BITS,RVT,MAP0,MAP1,CPU,LOCKOBJ,OUT,GV,RETAIN,GET0,GET1,GETCPU,TARGET,SUPPORT=[0x220000+0x1000*j for j in range(19)]
m.mem_write(GART,struct.pack('<Q',GV));m.mem_write(GART+0x1e0,struct.pack('<Q',POOL));m.mem_write(GV+0x220,struct.pack('<Q',TARGET))
m.mem_write(RESOURCE,struct.pack('<Q',RVT));m.mem_write(RESOURCE+0x48,struct.pack('<Q',SUPPORT));m.mem_write(RESOURCE+0x50,struct.pack('<Q',MAP0));m.mem_write(RESOURCE+0x58,struct.pack('<Q',MAP1));m.mem_write(RESOURCE+0x60,struct.pack('<Q',CPU));m.mem_write(RVT+0x20,struct.pack('<Q',RETAIN))
for obj,target,slot in [(MAP0,GET0,0x158),(MAP1,GET1,0x158),(CPU,GETCPU,0x138)]:m.mem_write(obj,struct.pack('<Q',obj+0x100));m.mem_write(obj+0x100+slot,struct.pack('<Q',target))
events=[]
def metrics_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0];x0=m.reg_read(regs[0])
 if word&0xfffffc00==0xd73f0800:
  t=m.reg_read(regs[(word>>5)&31])
  if t==RETAIN:assert x0==RESOURCE;value=0;events.append(('retain',))
  elif t in (GET0,GET1,GETCPU):
   k=[GET0,GET1,GETCPU].index(t);assert x0==[MAP0,MAP1,CPU][k];value=bases[k];events.append(('map',k))
  elif t==TARGET:assert x0==GART;value=required;events.append(('target_size',))
  else:raise AssertionError(hex(t))
  m.reg_write(regs[0],value);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 if word&0xfc000000==0x94000000:
  imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm;t=address+imm*4
  if t in (0xfffffe000b7b13c4,0xfffffe000b7b27c0):
   assert x0==LOCKOBJ;events.append(('lock' if t==0xfffffe000b7b13c4 else 'unlock',));m.reg_write(regs[0],0);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
  if t==0xfffffe000a7c4914:
   assert x0==SUPPORT and m.reg_read(regs[1])==required;events.append(('resize',));m.reg_write(regs[0],0);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,metrics_hook);rng=random.Random(604044);counts=dict(success=0,empty_pool=0,resources=0,mapped_outputs=0,resizes=0)
for i in range(1024):
 group=i%8;bit=(i//8)%64;index=group*64+bit;slots=64 if i&512 else 128;stride=[4,8,16,32][i%4];empty=bool(i&64);onebit=bool(i&128);required=32+i%64
 pool=bytearray(rng.randbytes(0x100));struct.pack_into('<Q',pool,0x10,0 if empty else RESOURCE);struct.pack_into('<I',pool,0x2c,0);struct.pack_into('<Q',pool,0x38,LOCKOBJ);struct.pack_into('<QQ',pool,0x40,BLOCKS,8*8);struct.pack_into('<I',pool,0x60,slots);struct.pack_into('<Q',pool,0x88,1<<group);struct.pack_into('<Q',pool,0x90,BITS);struct.pack_into('<Q',pool,0xa0,stride)
 bitmap=bytearray(rng.randbytes(0x100));mask=(1<<bit) if onebit else ((1<<bit)|((rng.getrandbits(64)>>(bit+1))<<(bit+1)));struct.pack_into('<Q',bitmap,group*8,mask)
 record=bytearray(rng.randbytes(0x100));struct.pack_into('<Q',record,8,RESOURCE);counter=rng.randrange(0,1000);struct.pack_into('<I',record,0,counter)
 output=bytearray(rng.randbytes(0x40));eo=bytearray(output);ep=bytearray(pool);eb=bytearray(bitmap);er=bytearray(record)
 flags=[bool(i&1),bool(i&2),bool(i&4)];bases=[0x300000,0x400000,0x500000];support_size=required+1 if i&256 else required-1;m.mem_write(SUPPORT+0x78,struct.pack('<I',support_size))
 expected_events=[('lock',)]
 if empty:struct.pack_into('<I',eo,0,0xffffffff);expected_events.append(('unlock',));counts['empty_pool']+=1
 else:
  struct.pack_into('<Q',eo,0x20,RESOURCE);struct.pack_into('<I',er,0,counter+1);expected_events.append(('retain',))
  for j,flag in enumerate(flags):
   if flag:struct.pack_into('<Q',eo,8+j*8,bases[j]+stride*(index%slots));expected_events.append(('map',j));counts['mapped_outputs']+=1
  new_mask=mask&~(1<<bit);struct.pack_into('<Q',eb,group*8,new_mask)
  if not new_mask:struct.pack_into('<Q',ep,0x88,0)
  struct.pack_into('<I',eo,0,index);expected_events += [('unlock',),('target_size',)]
  if support_size<required:expected_events.append(('resize',));counts['resizes']+=1
  counts['success']+=1;counts['resources']+=1
 for addr,data in [(POOL,pool),(BITS,bitmap),(RECORD,record),(OUT,output)]:m.mem_write(addr,bytes(data))
 m.mem_write(BLOCKS,struct.pack('<8Q',*[RECORD]*8));events.clear()
 for reg in regs:m.reg_write(reg,0)
 values=[GART,S,OUT,OUT+24 if flags[2] else 0,OUT+8 if flags[0] else 0,OUT+16 if flags[1] else 0,OUT+32]
 for reg,val in list(zip(regs,values))+[(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
 m.emu_start(START,STOP,count=2000);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK and m.reg_read(c.UC_ARM64_REG_W0)==int(not empty)
 for addr,data in [(POOL,ep),(BITS,eb),(RECORD,er),(OUT,eo)]:assert bytes(m.mem_read(addr,len(data)))==data,(i,hex(addr))
 assert events==expected_events,(i,events,expected_events)
report=dict(private_binary_sha256=sha,range=[hex(START),hex(END)],range_sha256=hashlib.sha256(read(START,END-START)).hexdigest(),counts=counts,qualification='Actual requestPMPageMetricsBuffer1024 full stack/bitmap/block-record/output comparisons:512 success and512 empty pool, first-set outer group0..7 and inner bit0..63, slots64/128, stride4/8/16/32, optional three map outputs, singleton/non-singleton masks, resource retain/output6, count increment, free-bit removal and support resize. Existing pool/backing only; lazy grow, mode1 low-water hook, encoded span nonzero upper bias, invalid asserts and actual retain/map/mutex/resize implementations excluded. Block vector fixtures alias the same record. No live resource identity or GPU command.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
