#!/usr/bin/env python3
"""Compose native ordinary geometry/loader with native 3D register generation."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('target',type=Path);p.add_argument('donor',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
def harness(name,marker):
 path=Path(__file__).with_name(name);s=path.read_text().split(marker)[0];old=sys.argv;sys.argv=[str(path),str(a.macho),str(a.output)];ns={'__name__':'geometry_bridge','__file__':str(path)}
 try:exec(compile(s,str(path),'exec'),ns)
 finally:sys.argv=old
 return ns
geo=harness('audit-private-render-geometry.py','rng=random.Random(604018);')
gm=geo['m'];accel=bytearray(0x12000);obj=bytearray(0x400)
for off,val in [(0x3c,2),(0x40,64),(0x44,64),(0x48,1),(0x90,32),(0x94,32),(0x98,1)]:struct.pack_into('<I',obj,off,val)
struct.pack_into('<Q',obj,0x120,geo['A']);struct.pack_into('<Q',obj,0x130,geo['N']);struct.pack_into('<I',accel,0x4e4,2);struct.pack_into('<Q',accel,0x11188,16<<30);struct.pack_into('<Q',accel,0,geo['VT'])
geo['provider']=2;gm.mem_write(geo['O'],bytes(obj));gm.mem_write(geo['A'],bytes(accel));geo['run'](geo['GEO'],x0=geo['O'],x2=0)
native_geometry=bytes(gm.mem_read(geo['O'],0x400));assert native_geometry==geo['geometry'](obj,accel,0,2)
geo['maps']=[0x1001000000,0x10045d0000,0x10045d0000]
gm.mem_write(geo['D'],bytes(0x1000));geo['run'](geo['LOADER'],x0=geo['D'],x1=geo['O']);loaded=bytes(gm.mem_read(geo['D'],0x1000))
ns=harness('audit-private-3d-input-generator.py','rng=random.Random(604010);fixtures=[]');m=ns['m'];c=ns['c'];A,C,D,O=[ns[k] for k in ('A','C','D','O')]
target=json.loads((a.target/'receipt.json').read_text());donor=json.loads(a.donor.read_text());assert int(target['shader_base'],0)==1<<40
base=1<<40;bg=base+int(target['background_candidate']['launch_byte_offset'],0);eot=base+int(target['tile_store']['launch_offset'],0)
common=bytearray(0x400)
for off,val in [(0xa0,0xffff800000000000),(0xa8,bg),(0xc0,0),(0xc8,eot),(0xe0,0x1000002000),(0xe8,0x1000002040)]:struct.pack_into('<Q',common,off,val)
struct.pack_into('<II',common,0x1c8,64,64)
desc=bytearray(loaded)
for off,val in [(0x440,0x820030000),(0x190,O),(0x918,O),(0xb90,ns['R1']),(0x638,0xffff800000000000),(0x640,bg),(0x780,0),(0x788,eot)]:struct.pack_into('<Q',desc,off,val)
for off,val in [(0x4a4,32),(0x4a8,32)]:struct.pack_into('<I',desc,off,val)
m.mem_write(D,bytes(desc));m.mem_write(0x232000,bytes(common))
for reg in ns['regs']:m.reg_write(reg,0)
m.reg_write(c.UC_ARM64_REG_X0,D);m.reg_write(c.UC_ARM64_REG_X1,0x232000);m.reg_write(c.UC_ARM64_REG_X30,ns['STOP']);m.emu_start(0xfffffe00089ebbe4,ns['STOP'],count=500)
assert bytes(m.mem_read(D,0x1000))==ns['copy_common'](desc,common)
m.mem_write(C,bytes(0x3000));m.mem_write(A+0x6d0,bytes(8));m.mem_write(O,bytes(0x100));ns['mapped']=0x820000000;ns['pending']=None
for reg in ns['regs']:m.reg_write(reg,0)
for reg,val in [(c.UC_ARM64_REG_X0,A),(c.UC_ARM64_REG_X1,C),(c.UC_ARM64_REG_X2,D),(c.UC_ARM64_REG_SP,ns['STACK']),(c.UC_ARM64_REG_LR,ns['STOP'])]:m.reg_write(reg,val)
m.emu_start(ns['START'],ns['STOP'],count=200000);assert m.reg_read(c.UC_ARM64_REG_PC)==ns['STOP'] and ns['pending'] is None
cmd=bytes(m.mem_read(C,0x3000));final_desc=bytes(m.mem_read(D,0x1000));phases=[]
for j in range(4):
 records=[];n=struct.unpack_from('<H',cmd,0x7a8+j*0x720)[0]
 for i in range(n):
  header,value=struct.unpack_from('<IQ',cmd,0xa0+j*0x720+12*i);records.append({'register':hex(header&0x3fff8),'flag':header&1,'value':hex(value)})
 phases.append(records)
expected={0x100b0:0x40004,0x16030:0x40004,0x100d8:0x1001,0x16098:0x10045d0000,0x16428:0x1001000000,0x16060:0x10045d0000,0x16430:0x50000000,0x15130:struct.unpack_from('<I',native_geometry,0xc8)[0],0x15138:struct.unpack_from('<I',native_geometry,0xcc)[0],0x15370:bg,0x15380:eot}
for reg,v in expected.items():assert [int(r['value'],0) for r in phases[0] if int(r['register'],0)==reg]==[v],hex(reg)
# Compare ordered identities. A duplicate's occurrence is part of its identity;
# never collapse the register list to a dict or silently sort its writes.
def identities(records,native):
 seen={};out=[]
 for r in records:
  raw=int(r['register'],0);flag=r['flag'] if native else raw&1;reg=raw&0x3fff8;key=(reg,flag);occ=seen.get(key,0);seen[key]=occ+1;out.append((reg,flag,occ))
 return out
exported=struct.unpack_from('<H',final_desc,0x830)[0];nrec=phases[0][:exported];drec=donor['registers']['3d'];ni=identities(nrec,True);di=identities(drec,False)
only_n=[{'register':hex(r),'flag':f,'occurrence':o} for r,f,o in ni if (r,f,o) not in di];only_d=[{'register':hex(r),'flag':f,'occurrence':o} for r,f,o in di if (r,f,o) not in ni]
shared_n=[x for x in ni if x in di];shared_d=[x for x in di if x in ni];assert shared_n==shared_d
values_n=dict(zip(ni,nrec));values_d=dict(zip(di,drec));different=[];matching=0
for key in shared_n:
 x=int(values_n[key]['value'],0);y=int(values_d[key]['value'],0)
 if x==y:matching+=1
 else:different.append({'register':hex(key[0]),'flag':key[1],'occurrence':key[2],'native':hex(x),'donor':hex(y)})
report={'private_binary_sha256':ns['sha'],'donor_receipt_sha256':hashlib.sha256(a.donor.read_bytes()).hexdigest(),'target_receipt_sha256':hashlib.sha256((a.target/'receipt.json').read_bytes()).hexdigest(),'composition':['native ordinary geometry','native render target loader','native common-record copier','native full 3D register generator'],'checked_values':len(expected),'phase_backing_counts':[len(x) for x in phases],'phase_exported_counts':[struct.unpack_from('<H',final_desc,0x830+j*16)[0] for j in range(4)],'phases':phases,'donor_comparison':{'shared_order_equal':True,'shared_identities':len(shared_n),'equal_values':matching,'only_native':only_n,'only_donor':only_d,'different_values':different},'geometry_object_sha256':hashlib.sha256(native_geometry).hexdigest(),'descriptor_sha256':hashlib.sha256(final_desc).hexdigest(),'qualification':'Complete native geometry/loader/client-copy/register-generator chain in offline RAM. Synthetic resource map bases, provider1050, accelerator topology inputs, client pipeline/state addresses. Eleven independently expected register values checked. Source-compatible G16 donor ordered identities compared without reordering/collapsing duplicates; differing values may reflect unspecified native descriptor fields, donor fixtures or genuine variant defaults, not all hardware differences. T6040 native sequence retained. No live allocation/microsequence/completion or rendering proof.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(report['phase_exported_counts'],report['donor_comparison'])
