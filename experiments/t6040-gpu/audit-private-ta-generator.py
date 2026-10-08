#!/usr/bin/env python3
"""Run complete native TA register producer with explicit RAM providers.

The output is numeric producer evidence, not a valid initialized render job.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
from private_rce_entry import encode_entry
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('donor',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
checker=Path(__file__).with_name('audit-private-3d-input-generator.py');prefix=checker.read_text().split('rng=random.Random(604010);fixtures=[]')[0];ns={'__file__':str(checker),'__name__':'ta'};old=sys.argv;sys.argv=[str(checker),str(a.macho),str(a.output)]
try:exec(compile(prefix,str(checker),'exec'),ns)
finally:sys.argv=old
m=ns['m'];c=ns['c'];A,C,D=[ns[k] for k in ('A','C','D')];BASE=0xfffffe0000000000;START=BASE+0x89dd2c4;END=BASE+0x89df4c0
m.mem_map(BASE+0x89dd000,0x2000);m.mem_write(START,ns['read'](START,BASE+0x89df6ec-START))
counts={'complete_ta_producer':0,'independent_entry_bytes':0,'metadata_links':0};fixtures=[];baseline=None
for i in range(128):
 desc=bytearray(0x1800)
 for off,val in [(0xfa0,0x830000000),(0x1230,ns['O']),(0x190,ns['O']),(0x1428,ns['R1'])]:struct.pack_into('<Q',desc,off,val)
 desc[0x1558]=i&1;desc[0x960]=[0,2,3][i%3]
 m.mem_write(C,bytes(0x3000));m.mem_write(D,bytes(desc));m.mem_write(ns['O'],bytes(0x100));m.mem_write(A+0x6d0,bytes(8));ns['mapped']=0x840000000;ns['entries'].clear();ns['calls'].clear();ns['pending']=None;ns['map_calls']=0
 for reg in ns['regs']:m.reg_write(reg,0)
 for reg,v in [(c.UC_ARM64_REG_X0,A),(c.UC_ARM64_REG_X1,C),(c.UC_ARM64_REG_X2,D),(c.UC_ARM64_REG_SP,ns['STACK']),(c.UC_ARM64_REG_LR,ns['STOP'])]:m.reg_write(reg,v)
 m.emu_start(START,ns['STOP'],count=100000);assert m.reg_read(c.UC_ARM64_REG_PC)==ns['STOP'];assert m.reg_read(c.UC_ARM64_REG_SP)==ns['STACK']
 cmd=bytes(m.mem_read(C,0x3000));final=bytes(m.mem_read(D,0x1800));n,length=struct.unpack_from('<HH',cmd,0x768);exported=struct.unpack_from('<H',final,0x1570)[0]
 assert length==n*12 and struct.unpack_from('<Q',cmd,0x760)[0]==0x830000060
 assert struct.unpack_from('<Q',final,0x1568)[0]==0x830000060 and exported<=n;counts['metadata_links']+=2
 for off,reg,flag,value in ns['entries']:
  assert cmd[off:off+12]==encode_entry(bytes(12),reg,flag,value),(i,hex(off));counts['independent_entry_bytes']+=1
 records=[]
 for j in range(n):
  header,value=struct.unpack_from('<IQ',cmd,0x60+12*j);records.append({'register':hex(header&0x3fff8),'flag':header&1,'value':hex(value)})
 if i==0:baseline=records
 counts['complete_ta_producer']+=1
 if i<6:fixtures.append({'case':i,'descriptor1558':desc[0x1558],'descriptor960':desc[0x960],'backing_count':n,'exported_count':exported,'encoder_calls':len(ns['entries']),'map_calls':ns['map_calls'],'command_sha256':hashlib.sha256(cmd).hexdigest()})
donor=json.loads(a.donor.read_text())['registers']['ta']
# First baseline lacks conditional initial entry. Compare presence with flags;
# duplicates remain listed, and are not described as conclusively binned differences.
nd={(int(r['register'],0),r['flag']) for r in baseline};dd={(int(r['register'],0)&0x3fff8,int(r['register'],0)&1) for r in donor}
report={'private_binary_sha256':ns['sha'],'native_range':[hex(START),hex(END)],'native_range_sha256':hashlib.sha256(ns['read'](START,END-START)).hexdigest(),'counts':counts,'fixtures':fixtures,'baseline_records':baseline,'donor_comparison':{'shared_unique_identities':len(nd&dd),'native_only_unique':[{'register':hex(r),'flag':f} for r,f in sorted(nd-dd)],'donor_only_unique':[{'register':hex(r),'flag':f} for r,f in sorted(dd-nd)]},'qualification':'Complete native TA producer and actual encoder/append/empty override execute in Unicorn RAM. Hash-pinned 3D harness supplies shared helper slots; PAC bypassed. One map158 provider returns synthetic address, descriptor1230/190 objects are zero fixture data. 128 flag/subtype cases; not128 independently meaningful full render inputs. Every actual encoder output compared to independent entry codec; manually written registers and complete recipe semantics only observed. Metadata pointers/counts checked. Donor is T8132 and baseline omits conditional entry, so identity differences do not alone prove binned-hardware differences. No initialized parameter manager, live queue, GPU execution or submission-ready TA job.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts,fixtures[:2])
