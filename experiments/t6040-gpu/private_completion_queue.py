#!/usr/bin/env python3
"""Checked numeric G16 completion queue descriptors; mappings supplied explicitly."""
import struct

def populate(initial,capacity,mappings):
 if len(initial)!=0x80 or len(mappings)!=4:raise ValueError('Four32-byte descriptors required')
 if type(capacity) is not int or not 0<=capacity<1<<32:raise ValueError('Capacity must fit u32')
 result=bytearray(initial)
 for index,mapping in enumerate(mappings):
  offset=index*0x20;struct.pack_into('<Q',result,offset,0)
  if mapping is None:continue
  if len(mapping)!=2 or any(type(v) is not int or not 0<=v<1<<64 for v in mapping):raise ValueError('Two explicit u64 mapping158 results required')
  struct.pack_into('<QQIIII',result,offset,*mapping,capacity,0x40,index,0)
 return bytes(result)

def allocation_bytes(capacity):
 if type(capacity) is not int or not 0<=capacity<1<<32:raise ValueError('Capacity must fit u32')
 return ((capacity*0x40+0xff)&0x7fffffff00)
