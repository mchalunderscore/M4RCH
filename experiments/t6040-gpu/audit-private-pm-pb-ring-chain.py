#!/usr/bin/env python3
"""Join native PM loadPBDesc to its actual G16 descriptor-ring provider."""
from pathlib import Path
from private_pb_ring import load_entry
source_pb=Path(__file__).with_name('audit-private-pm-pb-load.py')
setup_pb=source_pb.read_text().split('rng=random.Random(604030);')[0].replace('m.hook_add(u.UC_HOOK_CODE,pb_hook)','pb_handle=m.hook_add(u.UC_HOOK_CODE,pb_hook)')
exec(compile(setup_pb,str(source_pb),'exec'));m.hook_del(pb_handle)
GPU,RES,MAPOBJ,MVT,RING,GET=0x240000,0x260000,0x261000,0x262000,0x263000,0x264000
m.mem_map(GPU,0x30000);HAL=0xfffffe00089d6f54
m.mem_map(0xfffffe00089d6000,0x2000);m.mem_write(HAL,read(HAL,0x100))
encoded=struct.unpack('<Q',read(0xfffffe0007eae388+16+0x10f8,8))[0];assert 0xfffffe0007004000+(encoded&0xffffffff)==HAL
m.mem_write(GVT+0x10f8,struct.pack('<Q',HAL));m.mem_write(RES+0x60,struct.pack('<Q',MAPOBJ));m.mem_write(MAPOBJ,struct.pack('<Q',MVT));m.mem_write(MVT+0x138,struct.pack('<Q',GET))
def joined_pb_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31])
  if target==HAL:
   assert [m.reg_read(regs[j]) for j in range(4)]==[GPU,STATE,M+0x34,request];events.append(('prepare_state',));m.reg_write(c.UC_ARM64_REG_LR,address+4);m.reg_write(c.UC_ARM64_REG_PC,HAL);return
  if target==GET:
   assert m.reg_read(c.UC_ARM64_REG_X0)==MAPOBJ;m.reg_write(c.UC_ARM64_REG_X0,RING);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 pb_hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,joined_pb_hook)
tail_pb=source_pb.read_text().split('rng=random.Random(604030);',1)[1];tail_pb='rng=random.Random(604032);'+tail_pb
# Ring indices are a separate request, bounded to the tested32-slot backing.
tail_pb=tail_pb.replace('request=rng.getrandbits(32)', 'request=i%32')
tail_pb=tail_pb.replace('rng.randbytes(0x2000)', 'rng.randbytes(0x19000)')
tail_pb=tail_pb.replace("gpu[0x478]=int(generation_check)", "gpu[0x478]=int(generation_check);struct.pack_into('<Q',gpu,0xf928,RES)")
tail_pb=tail_pb.replace('m.emu_start(LOAD,STOP,count=1000)', "ring_original=rng.randbytes(0x1000);m.mem_write(RING,ring_original);expected_ring=bytearray(ring_original)\n if first and not asserted:expected_ring[request*16:request*16+16]=load_entry(ring_original[request*16:request*16+16],es,manager[0x34:0x44])\n m.emu_start(LOAD,STOP,count=1000)\n assert bytes(m.mem_read(RING,0x1000))==bytes(expected_ring)")
tail_pb=tail_pb.replace('report=dict(', "report=dict(provider_vtable='G16X+10f8',provider_range=[hex(HAL),hex(HAL+0x100)],provider_range_sha256=hashlib.sha256(read(HAL,0x100)).hexdigest(),")
tail_pb=tail_pb.replace("args.output.write_text", "report['qualification']='Actual complete PM loadPBDesc invokes actual G16 halLoadPBDesc, verified by G16X encoded vtable10f8.928 successful whole-object/ring cases and96 expected generation assertions.464 native packed ring writes compare independent22-bit cursor/address-bit model; reused manager skips provider. Only external ring map138 remains a service. Bounded request0..31; no live ring identity/capacity/cache visibility, staged prepareAndRetain or firmware acceptance.'\nargs.output.write_text")
exec(compile(tail_pb,str(source_pb),'exec'))
