#!/usr/bin/env python3
"""Execute G16 native parameter-buffer descriptor load/store roundtrip."""
from pathlib import Path
from private_pb_ring import load_entry,store_entry
base=Path(__file__).with_name('audit-private-render-inputs.py');setup=base.read_text().split('rng=random.Random(604011);')[0].replace('m.hook_add(u.UC_HOOK_CODE,hook)','handle=m.hook_add(u.UC_HOOK_CODE,hook)')
exec(compile(setup,str(base),'exec'));m.hook_del(handle)
STORE,LOAD,END=0xfffffe00089d6eb4,0xfffffe00089d6f54,0xfffffe00089d7054
m.mem_map(0xfffffe00089d6000,0x2000);m.mem_write(STORE,read(STORE,END-STORE));m.mem_map(0x220000,0x30000)
GPU,RES,MAPOBJ,MVT,RING,STATE,SAVED,GET=0x220000,0x240000,0x241000,0x242000,0x243000,0x244000,0x245000,0x246000
m.mem_write(GPU+0xf928,struct.pack('<Q',RES));m.mem_write(RES+0x60,struct.pack('<Q',MAPOBJ));m.mem_write(MAPOBJ,struct.pack('<Q',MVT));m.mem_write(MVT+0x138,struct.pack('<Q',GET))
provider_calls=[]
def ring_hook(m,address,size,user):
 word=struct.unpack('<I',m.mem_read(address,4))[0]
 if word&0xfffffc00==0xd73f0800:
  target=m.reg_read(regs[(word>>5)&31]);assert target==GET and m.reg_read(c.UC_ARM64_REG_X0)==MAPOBJ;provider_calls.append(('ring_cpu_map',));m.reg_write(c.UC_ARM64_REG_X0,RING);m.reg_write(c.UC_ARM64_REG_PC,address+4);return
 hook(m,address,size,user)
m.hook_add(u.UC_HOOK_CODE,ring_hook);rng=random.Random(604031);counts=dict(loads=0,stores=0)
for i in range(1024):
 index=i%32;ring=rng.randbytes(0x1000);state=bytearray(rng.randbytes(0x100));saved=rng.randbytes(16);expected=bytearray(ring);entry=load_entry(ring[index*16:index*16+16],state,saved);expected[index*16:index*16+16]=entry
 m.mem_write(RING,ring);m.mem_write(STATE,bytes(state));m.mem_write(SAVED,saved);provider_calls.clear()
 for fn in (LOAD,STORE):
  for reg in regs:m.reg_write(reg,0)
  for reg,val in [(c.UC_ARM64_REG_X0,GPU),(c.UC_ARM64_REG_X1,STATE),(c.UC_ARM64_REG_X2,SAVED),(c.UC_ARM64_REG_X3,index),(c.UC_ARM64_REG_SP,STACK),(c.UC_ARM64_REG_LR,STOP)]:m.reg_write(reg,val)
  m.emu_start(fn,STOP,count=400);assert m.reg_read(c.UC_ARM64_REG_PC)==STOP and m.reg_read(c.UC_ARM64_REG_SP)==STACK
  assert bytes(m.mem_read(RING,len(ring)))==expected
  assert bytes(m.mem_read(STATE,len(state)))==bytes(state)
  assert bytes(m.mem_read(SAVED,16))==(saved if fn==LOAD else store_entry(entry));counts['loads' if fn==LOAD else 'stores']+=1
 assert provider_calls==[('ring_cpu_map',)]*2
report=dict(private_binary_sha256=sha,range=[hex(STORE),hex(END)],range_sha256=hashlib.sha256(read(STORE,END-STORE)).hexdigest(),counts=counts,entry_size=16,capacity_index_cases=32,qualification='Actual complete G16 halLoadPBDesc and halStorePBDesc1024 full-buffer roundtrips, independent bitfield models, randomized address/state/saved/ring bytes. Resource60 virtual138 mapping explicit service. Address bit42, high address bits, preserved packed bits,22-bit cursor values and bit31 preserved/masked as observed. Index0..31 only. No live ring capacity/cache visibility or firmware acceptance proved.')
args.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
