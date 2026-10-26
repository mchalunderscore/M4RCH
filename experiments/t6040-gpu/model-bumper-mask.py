#!/usr/bin/env python3
"""Execute captured Bumper mask producer/consumer instructions in RAM only."""
import argparse,sys,struct,json,hashlib
from pathlib import Path
import unicorn as u
from unicorn import arm64_const as c
KIT=Path(__file__).resolve().parent;sys.path.insert(0,str(KIT))
from firmware_text_contract import qualify
FW=0xfffffc0000000000;MAIN=0x5000000;HW=0x5010000;REG=0x5020000

def run(text,mask,clusters):
 qualify(text)
 m=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
 m.mem_map(FW,0x60000,u.UC_PROT_READ|u.UC_PROT_EXEC);m.mem_write(FW,text)
 m.mem_map(FW+0x60000,0x138000)
 m.mem_map(MAIN,0x30000)
 def put(address,value):m.mem_write(address,struct.pack('<Q',value))
 put(FW+0x18e4c0,MAIN);put(MAIN,HW);put(HW+0x2560,mask);put(HW+0x2568,0)
 put(FW+0x18f950,REG);m.mem_write(FW+0x18ceac,struct.pack('<I',clusters))
 m.reg_write(c.UC_ARM64_REG_X25,FW+0x18e000)
 accesses=[]
 def access(mu,kind,address,size,value,opaque):
  if REG<=address<REG+0x1000:accesses.append({'kind':'write' if kind==u.UC_MEM_WRITE else 'read','offset':hex(address-REG),'bytes':size,'value':hex(value) if kind==u.UC_MEM_WRITE else None})
 m.hook_add(u.UC_HOOK_MEM_READ|u.UC_HOOK_MEM_WRITE,access)
 m.emu_start(FW+0x395f4,FW+0x39624,count=40)
 assert m.reg_read(c.UC_ARM64_REG_PC)==FW+0x39624
 programmed=struct.unpack('<III',m.mem_read(REG+0xa0,12))
 m.emu_start(FW+0x2a774,FW+0x2a7c4,count=100)
 assert m.reg_read(c.UC_ARM64_REG_PC)==FW+0x2a7c4
 full=struct.unpack('<QQ',m.mem_read(FW+0x18bb60,16))
 fields=[struct.unpack('<QQ',m.mem_read(FW+0x18bb70+i*16,16)) for i in range(clusters)]
 expected=[(mask&(0x3ff<<(10*i)),0) for i in range(clusters)]
 assert full==(mask,0) and fields==expected
 return {'input_mask':hex(mask),'clusters':clusters,'programmed_words':[hex(x) for x in programmed],'full_mask':[hex(x) for x in full],'cluster_fields':[[hex(x) for x in row] for row in fields],'accesses':accesses}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('text',type=Path);p.add_argument('output',type=Path);a=p.parse_args();text=a.text.read_bytes()
 cases=[(0x3db|(0x3db<<10),2),(0xfffff,2),(0x3ff,1),(0,2)]
 result={'text_contract':qualify(text),'source_capture':str(a.text),'instruction_ranges':['0x395f4..0x39624','0x2a774..0x2a7c4'],'cases':[run(text,*case) for case in cases],'qualification':'Captured instructions run offline with explicit RAM register fixture. No physical bank identity, safe MMIO access, power prerequisites or native rendering established. Cluster output masks retain bit position; they are not shifted to bit zero.'}
 a.output.write_text(json.dumps(result,indent=2)+'\n');print('Four mask producer/consumer cases passed')
