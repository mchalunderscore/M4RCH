#!/usr/bin/env python3
"""Audit captured ADT bus windows without MMIO or assigning firmware roles."""
import argparse,json,struct,hashlib
from pathlib import Path
import adt

def decode_words(raw,step):
 if len(raw)%step:raise ValueError('Malformed property geometry')
 return list(struct.iter_unpack('<'+'Q'*(step//8),raw))

def translate(base,size,ranges):
 matches=[parent+base-child for child,parent,span in ranges if child<=base and size<=span and base-child<=span-size]
 if len(matches)!=1:raise ValueError('Missing or ambiguous full-window translation')
 return matches[0]

def audit(data):
 tree=adt.parse(data);bus=tree['/device-tree/arm-io'];gpu=tree['/device-tree/arm-io/sgx'];mcc=tree['/device-tree/arm-io/mcc']
 ranges=decode_words(bus['ranges'],24)
 def windows(node):
  return [{'raw_address':hex(a),'size':hex(n),'physical_address':hex(translate(a,n,ranges))} for a,n in decode_words(node['reg'],16)]
 gw=windows(gpu);mw=windows(mcc)
 # Current donor's literal offset/size requirements, not proposed T6040 mappings.
 requirements=[(17,0,0x20000),(26,0xd04000,0x8000),(27,0xd0d000,0x1000),(28,0xd58000,0x8000),(29,0xd10000,0x4000),(31,0xd40000,0x4000),(32,0xd60000,0x8000),(40,0xe1c000,0x4000),(22,0x1000000,0x8000),(39,0xe08000,0x8000),(41,0xe1f800,0x4000)]
 checks=[{'slot':slot,'offset':hex(offset),'bytes':hex(size),'fits_each_window':[offset+size<=int(w['size'],16) for w in gw]} for slot,offset,size in requirements]
 return {'adt_sha256':hashlib.sha256(data).hexdigest(),'gpu_windows':gw,'mcc_windows':mw,'active_mcc_mask':hex(int.from_bytes(gpu['active-mcc-bit-vector'],'little')),'donor_register_requirements':checks,'donor_second_window_rejections':sum(not x['fits_each_window'][1] for x in checks),'qualification':'Address containment only. No firmware role, register safety, IRQ semantics or initialization ABI inferred. No reads/writes performed.'}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('adt',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();result=json.dumps(audit(a.adt.read_bytes()),indent=2)+'\n'
 if a.output:a.output.write_text(result)
 else:print(result,end='')
