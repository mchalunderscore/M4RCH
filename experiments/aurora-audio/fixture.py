#!/usr/bin/env python3
"""Reduce the saved native metadata to loader-test inputs; addresses are never installed."""
import plistlib,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'out/aurora-audio'
r=plistlib.load(open(ROOT/'out/aurora-test/macos-adt.plist','rb'));selected={}
def walk(n):
 if isinstance(n,list):
  for c in n:walk(c)
  return
 name=n.get('IORegistryEntryName','')
 if name in ['chosen','sgx','gfx-asc','arm-io','iop-pmp-nub','aop','isp0'] or name.startswith(('atc-phy','usb-drd')) and len(name)==8:
  props={k:v for k,v in n.items() if isinstance(v,bytes) and len(k)<=31};props['name']=name.encode()+b'\0';selected[name]=props
 for c in n.get('IORegistryEntryChildren',[]):walk(c)
walk(r)
selected['chosen']['firmware-version']=b'mBoot-18000.161.10\0'.ljust(256,b'\0')
def node(props,children):
 data=struct.pack('<II',len(props),len(children))
 for k,v in props.items():data+=k.encode().ljust(32,b'\0')+struct.pack('<I',len(v))+v+bytes(-len(v)%4)
 return data+b''.join(children)
def generate():return node({'name':b'device-tree\0'},[node(selected['chosen'],[]),node(selected['arm-io'],[node(v,[]) for k,v in selected.items() if k not in ['chosen','arm-io']])])
(OUT/'adt-r12.bin').write_bytes(generate())
b=bytearray(selected['aop']['segment-ranges']);struct.pack_into('<Q',b,3*32,0x510df0000);selected['aop']['segment-ranges']=bytes(b)
(OUT/'adt-r12-sram.bin').write_bytes(generate())
