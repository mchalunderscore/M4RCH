#!/usr/bin/env python3
"""Execute native PM scene array initialization and final pointer publication."""
from pathlib import Path
import sys
from private_render_inputs import U64
base=Path(__file__).with_name('audit-private-render-inputs.py')
setup=base.read_text().split('rng=random.Random(604011);')[0].replace('m.hook_add(u.UC_HOOK_CODE,hook)','handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(handle)
START,END=0xfffffe00089fcf2c,0xfffffe00089fd040
m.mem_map(0xfffffe00089fc000,0x2000);m.mem_write(START,read(START,END-START));m.mem_map(0x220000,0x40000)
RECORD,SCENE,CONFIG,SCRATCH=0x230000,0x234000,0x238000,0x23c000
calls=[]
def scene_hook(m,address,size,user):
 if address==0xfffffe00089fcf44:
  ptr=m.reg_read(c.UC_ARM64_REG_X0);length=m.reg_read(c.UC_ARM64_REG_W1);assert ptr==SCRATCH;calls.append(length);m.mem_write(ptr,bytes(length));m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,scene_hook)
rng=random.Random(604023);counts=dict(scene_arrays=0,scene_records=0,vector_elements=0);examples=[]
for i in range(1024):
 n=i%33;alignment=[1,2,4,8,16,32,64,128][i%8];stride=(alignment+3)&(-alignment);maps=[rng.getrandbits(48) for _ in range(3)]
 obj=bytearray(rng.randbytes(0x300));struct.pack_into('<Q',obj,0x88,VB);struct.pack_into('<Q',obj,0xa8,VA);struct.pack_into('<I',obj,0xb0,n)
 records=rng.randbytes(0x1100);scenes=rng.randbytes(0x1100);scratch=rng.randbytes(0x2000);va=bytearray(rng.randbytes(0x110));vb=bytearray(rng.randbytes(0x110));expected_scenes=bytearray(scenes)
 for j in range(n):
  struct.pack_into('<Q',va,j*8,RECORD+j*0x80);struct.pack_into('<Q',vb,j*8,SCENE+j*0x80)
  struct.pack_into('<QQ',expected_scenes,j*0x80,(maps[0]+j*stride)&U64,(maps[1]+j*stride)&U64)
 expected_obj=bytearray(obj)
 for off,val in [(0xb8,RECORD+n*0x80),(0xc8,maps[2]),(0x98,CONFIG),(0xa0,maps[2]+0x40),(0x80,CONFIG+0x40)]:struct.pack_into('<Q',expected_obj,off,val&U64)
 original_va=rng.randbytes(0x110);original_vb=rng.randbytes(0x110)
 # Model only the initialized vector prefix; unused tails must remain unchanged.
 expected_va=va[:n*8]+original_va[n*8:];expected_vb=vb[:n*8]+original_vb[n*8:]
 for addr,data in [(S,bytes(obj)),(RECORD,records),(SCENE,scenes),(VA,original_va),(VB,original_vb),(SCRATCH,scratch)]:m.mem_write(addr,data)
 for off,val in [(0x20,alignment),(0x28,maps[1]),(0x30,maps[0]),(0x38,SCRATCH),(0x10,maps[2])]:m.mem_write(STACK+off,struct.pack('<Q',val))
 calls.clear()
 for reg in regs:m.reg_write(reg,0)
 for reg,val in [(c.UC_ARM64_REG_X19,S),(c.UC_ARM64_REG_X20,n),(c.UC_ARM64_REG_X23,RECORD),(c.UC_ARM64_REG_X24,SCENE),(c.UC_ARM64_REG_X28,CONFIG),(c.UC_ARM64_REG_SP,STACK)]:m.reg_write(reg,val)
 m.emu_start(START,END,count=8000);assert m.reg_read(c.UC_ARM64_REG_PC)==END
 assert bytes(m.mem_read(S,len(obj)))==expected_obj and bytes(m.mem_read(SCENE,len(scenes)))==expected_scenes
 assert bytes(m.mem_read(RECORD,len(records)))==records
 assert bytes(m.mem_read(VA,len(original_va)))==expected_va and bytes(m.mem_read(VB,len(original_vb)))==expected_vb
 assert bytes(m.mem_read(SCRATCH,len(scratch)))==bytes(n*stride)+scratch[n*stride:];assert calls==[n*stride]
 counts['scene_arrays']+=1;counts['scene_records']+=n;counts['vector_elements']+=2*n
 if i<8:examples.append(dict(count=n,alignment=alignment,stride=stride,scene_element_bytes=0x80,zero_bytes=n*stride))
report=dict(private_binary_sha256=sha,range=[hex(START),hex(END)],range_sha256=hashlib.sha256(read(START,END-START)).hexdigest(),counts=counts,examples=examples,qualification='Actual PM initializer alignment/zero/scene-array/publication slice. Independent complete object, vectors, scene array and scratch comparisons; record backing unchanged. Count0..32, power-of-two alignment1..128, valid vector capacity equal count. Distinct synthetic map domains from saved stack; preceding resource allocation, vtable registration, bounds failures, remaining initializer and HWPB reset excluded. Zero helper explicit byte-service implementation. No live PM or GPU job proved.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
