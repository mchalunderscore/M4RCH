#!/usr/bin/env python3
"""Inspect a local GFX IM4P payload's FTAB/Mach-O layout; never execute it."""
import argparse,hashlib,json,re,struct
from pathlib import Path

def layout(blob):
 if len(blob)<48 or blob[32:40]!=b'rkosftab':raise ValueError('Not an FTAB payload')
 count=struct.unpack_from('<I',blob,40)[0]
 if not 1<=count<=64 or 48+count*16>len(blob):raise ValueError('Invalid FTAB count')
 result=[];regions=[]
 for i in range(count):
  tag,off,size,reserved=struct.unpack_from('<4sIII',blob,48+i*16)
  if reserved or off<48+count*16 or size<32 or off+size>len(blob):raise ValueError('Invalid FTAB entry')
  if any(off<end and start<off+size for start,end in regions):raise ValueError('Overlapping FTAB entries')
  regions.append((off,off+size));image=blob[off:off+size]
  magic,cpu,subtype,filetype,ncmds,cmdbytes,flags,res=struct.unpack_from('<8I',image)
  if magic!=0xfeedfacf or cpu!=0x100000c or ncmds>4096 or 32+cmdbytes>size:raise ValueError('Unsupported Mach-O geometry')
  p=32;segments=[]
  for _ in range(ncmds):
   if p+8>32+cmdbytes:raise ValueError('Truncated load command')
   cmd,length=struct.unpack_from('<II',image,p)
   if length<8 or p+length>32+cmdbytes:raise ValueError('Invalid load command size')
   if cmd==0x19:
    if length<72:raise ValueError('Truncated segment')
    name,vm,span,fo,fs,maxprot,prot,nsect,sflags=struct.unpack_from('<16sQQQQIIII',image,p+8)
    if fo+fs>size or 72+nsect*80>length:raise ValueError('Invalid segment extent')
    segments.append({'name':name.rstrip(b'\0').decode('ascii'),'virtual_address':hex(vm),'virtual_bytes':span,'file_offset':fo,'file_bytes':fs,'protection':prot})
   p+=length
  if p!=32+cmdbytes:raise ValueError('Load command length mismatch')
  result.append({'tag':tag.decode('ascii'),'bytes':size,'sha256':hashlib.sha256(image).hexdigest(),'segments':segments,'rtkit_strings':sorted(set(x.decode() for x in re.findall(rb'RTKit(?:_release)?-[A-Za-z0-9_.-]+',image)))})
 return {'payload_sha256':hashlib.sha256(blob).hexdigest(),'images':result,'qualification':'Static container and Mach-O metadata only. Entry tags are not assigned to clusters; no firmware execution or shared-object ABI qualification.'}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('payload',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();s=json.dumps(layout(a.payload.read_bytes()),indent=2)+'\n'
 if a.output:a.output.write_text(s)
 else:print(s,end='')
