#!/usr/bin/env python3
"""Bounded offline RTKit crashlog decoder following the pinned kernel decoder.
No firmware execution. Supports string, version and stack records; retains
metadata for other section types without inferring their contents.
"""
import argparse,hashlib,json,struct
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('boot_directory',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
w=a.boot_directory;before=(w/'data-before.bin').read_bytes();after=(w/'data-after.bin').read_bytes()
# Exact firmware-owned crashlog offer: DATA+a0000, extent8000.
start=0xa0000;extent=0x8000;b=after[start:start+extent]
if len(b)!=extent or b[:4]!=b'EHLC':raise ValueError('Missing crashlog header')
_,version,size,flags=struct.unpack_from('<4I',b)
if not 0x20<=size<=len(b):raise ValueError('Invalid crashlog extent')
sections=[];messages=[];stack=[];offset=0x20;footer=False
while offset<size:
 if offset+16>size:raise ValueError('Truncated section header')
 tag=b[offset:offset+4]
 # This firmware repeats its full 32-byte header as the terminal record;
 # the old kernel decoder's section-length check does not handle that form.
 if tag==b'EHLC':
  if offset+0x20!=size or b[offset:offset+0x20]!=b[:0x20]:
   raise ValueError('Terminal header does not exactly repeat the opening header')
  footer=True;sections.append({'offset':hex(offset),'fourcc':'CLHE','bytes':0x20,'form':'exact repeated header'});break
 length=struct.unpack_from('<I',b,offset+12)[0]
 if length<16 or offset+length>size:raise ValueError('Invalid section length')
 payload=b[offset+16:offset+length]
 entry={'offset':hex(offset),'fourcc':tag[::-1].decode('ascii',errors='replace'),'bytes':length}
 if tag==b'EHLC':footer=True;sections.append(entry);break
 if tag==b'rtsC':
  if len(payload)<4:raise ValueError('Truncated string section')
  entry['id']=struct.unpack_from('<I',payload)[0]
  entry['text']=payload[4:].split(b'\0')[0].decode('utf-8',errors='replace');messages.append(entry['text'])
 elif tag==b'revC':
  if len(payload)<16:raise ValueError('Truncated version section')
  entry['text']=payload[16:].split(b'\0')[0].decode('utf-8',errors='replace')
 elif tag==b'8grC':
  # Exact packed layout from the pinned kernel rtkit-crashlog.c, size0x350.
  if len(payload)<0x350:raise ValueError('Truncated register section')
  entry['registers']={f'x{i}':hex(struct.unpack_from('<Q',payload,8+i*8)[0]) for i in range(31)}
  for name,position in [('sp',0x100),('pc',0x108),('psr',0x110),('far',0x330),('esr',0x340)]:
   entry[name]=hex(struct.unpack_from('<Q',payload,position)[0])
 elif tag==b'tscC':
  if len(payload)<8:raise ValueError('Truncated stack section')
  entry['task'],entry['unknown']=struct.unpack_from('<II',payload)
  addresses=[]
  for off in range(8,len(payload)-7,8):
   address=struct.unpack_from('<Q',payload,off)[0]
   if not address:break
   addresses.append(hex(address));stack.append(address)
  entry['addresses']=addresses
 sections.append(entry);offset+=length
if not footer:raise ValueError('Crashlog has no footer')
expected='Host-mapped FW allocations are disabled, but FW only supports enabled (init_data_addr=0xfffffc2000100000)!'
r={'boot_id':json.loads((w/'attempt.json').read_text())['boot_id'],
   'data_before_sha256':hashlib.sha256(before).hexdigest(),'data_after_sha256':hashlib.sha256(after).hexdigest(),
   'crashlog_offset':hex(start),'crashlog_bytes':size,'version':version,'flags':flags,'footer_valid':footer,
   'sections':sections,'expected_rejection':expected in messages,
   'parser_callsite_present':0xfffffc000002fa2c in stack,
   'crashlog_newly_written':before[start:start+size]!=after[start:start+size],
   'qualification':('Expected rejection plus parser callsite corroborates firmware root consumption and successful interface comparison. This negative control does not establish complete initialization, queue execution or rendering.' if expected in messages and 0xfffffc000002fa2c in stack else 'Structured crashlog decoding only; interpret registers/stack with matching instructions and independent object capture. No initialization or rendering success established.')}
a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k] for k in ['crashlog_bytes','footer_valid','expected_rejection','parser_callsite_present','crashlog_newly_written']},indent=2))
