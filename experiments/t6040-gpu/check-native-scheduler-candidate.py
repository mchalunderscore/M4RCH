#!/usr/bin/env python3
"""Compare reusable candidate serializer directly to the complete native work slice."""
from pathlib import Path
import sys
from native_scheduler_candidate import prepare
from private_nop_body import convert_timestamp
base=Path(__file__).with_name('audit-private-work-record.py')
exec(compile(base.read_text().split('rng=random.Random(604004)')[0],str(base),'exec'))
rng=random.Random(604025);counts=dict(native_candidate_records=0,native_accounting=0);examples=[]
for i in range(128):
 n=i%9;capacity=[1,2,3,16,256][i%5];timestamp=rng.getrandbits(40);initial=rng.getrandbits(40);qid=i%128;previous=rng.getrandbits(40);ap_address=0x1001000000;ap_count=[0,1,64][i%3];payload=[0x1002000000,0x1003000000];priority=i%4
 deps=[];dep=bytearray(4+n*12);struct.pack_into('<I',dep,0,n);epochs={}
 for idx in range(24):
  epochs[idx]=(rng.getrandbits(32),rng.getrandbits(32));m.mem_write(0x20a000+0x1458+idx*24,struct.pack('<2Q',*epochs[idx]))
 for j in range(n):
  event=rng.getrandbits(32);idx=j;epoch=epochs[idx][event>>31];deps.append(dict(event=event,index=idx,epoch=epoch));struct.pack_into('<3I',dep,4+j*12,event,idx,0)
 qos=[i%256,i%65536,i%32];kind=i%4;lists=[dict(address=0x1004000000+j*0x1000,count=[87,16,23,10][j]) for j in range(4)];masks=[rng.getrandbits(64) for _ in range(4)];aux=0x1005000000
 binding=dict(queue=dict(timestamp=timestamp,id=qid,priority=priority,capacity=capacity,previous=previous,initial=initial,pending=capacity-1),aperture=dict(address=ap_address,index=i%64,count=ap_count),payload=payload,dependencies=deps,qos=qos,rce_kind=kind,register_lists=lists,masks=masks,auxiliary=aux,alternate_kind=bool(i&1),extra_flag=bool(i&2))
 original=rng.randbytes(0x200);expected,_,receipt=prepare(binding,original)
 queue=bytearray(0x100)
 for off,val,fmt in [(0xc,qid,'I'),(0x10,capacity,'I'),(0x1c,priority,'I'),(0x44,capacity-1,'I'),(0x48,timestamp,'Q'),(0x68,0x209000,'Q'),(0x90,initial,'Q'),(0xa0,previous,'Q')]:struct.pack_into('<'+fmt,queue,off,val)
 queue[0x98]=1;rce=bytearray(0x48);struct.pack_into('<I',rce,0,kind)
 for j,x in enumerate(lists):struct.pack_into('<QH',rce,8+j*16,x['address'],x['count'])
 m.mem_write(0x207010,struct.pack('<Q',0x205000));m.mem_write(0x208000,struct.pack('<Q2I',ap_address,i%64,ap_count));m.mem_write(0x208100,struct.pack('<Q',0x208200));m.mem_write(0x208200,struct.pack('<2Q',*payload))
 for addr,data in [(0x200000,original),(0x201000,bytes(queue)),(0x202000,bytes(dep)),(0x203000,struct.pack('<3I',*qos)),(0x204000,bytes(rce)),(0x205000,struct.pack('<4Q',*masks))]:m.mem_write(addr,data)
 m.mem_write(0x209140,struct.pack('<Q',0x20a000));m.mem_write(0x206018,struct.pack('<Q',0x20c000))
 for reg,val in [(c.UC_ARM64_REG_X21,0x200000),(c.UC_ARM64_REG_X19,0x201000),(c.UC_ARM64_REG_X25,0x202000),(c.UC_ARM64_REG_X23,0x203000),(c.UC_ARM64_REG_X22,0x204000),(c.UC_ARM64_REG_X27,0x208000),(c.UC_ARM64_REG_X26,0x208100),(c.UC_ARM64_REG_X29,0x207000),(c.UC_ARM64_REG_W24,i&1),(c.UC_ARM64_REG_W28,(i>>1)&1),(c.UC_ARM64_REG_X20,aux),(c.UC_ARM64_REG_SP,0x206000)]:m.reg_write(reg,val)
 m.emu_start(start,end,count=1500);assert bytes(m.mem_read(0x200000,0x200))==expected
 actual_queue=bytes(m.mem_read(0x201000,0x100));assert struct.unpack_from('<Q',actual_queue,0x48)[0]==receipt['next_timestamp'];assert struct.unpack_from('<I',actual_queue,0x44)[0]==capacity;assert actual_queue[0x98]==1 and struct.unpack_from('<Q',actual_queue,0xa0)[0]==timestamp
 counts['native_candidate_records']+=1;counts['native_accounting']+=1
 if i<2:examples.append(dict(binding=binding,work_sha256=hashlib.sha256(expected).hexdigest()))
report=dict(private_binary_sha256=sha,counts=counts,examples=examples,qualification='Reusable candidate serializer compared directly to actual complete native work prefix/body/accounting slice in emulator RAM.128 explicit representable bindings, random original record bytes, dependency counts0..8, cached previous timestamps, capacities1/2/3/16/256 and all flags. Only changed accounting fields compared; fixture queue identity not live. No resource mapping/queue registration/work validity/GPU submission or completion.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
