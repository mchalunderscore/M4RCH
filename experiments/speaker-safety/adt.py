#!/usr/bin/env python3
"""Decode saved Apple device-tree metadata for the speaker-safety audit."""
import struct

def parse(data):
    result={};offset=0;budget=10000
    def take(n):
        nonlocal offset
        if n<0 or offset+n>len(data):raise ValueError('Truncated ADT')
        value=data[offset:offset+n];offset+=n;return value
    def node(parent,depth):
        nonlocal budget
        budget-=1
        if depth>64 or budget<0:raise ValueError('ADT tree limit')
        start=offset
        properties,children=struct.unpack('<II',take(8))
        if properties>4096 or children>4096:raise ValueError('ADT count limit')
        props={}
        for _ in range(properties):
            name=take(32).split(b'\0')[0].decode('ascii');size=struct.unpack('<I',take(4))[0]&0x7fffffff
            if size>16*1024*1024:raise ValueError('ADT property limit')
            value=take(size);take((-size)%4)
            if name in props:raise ValueError('Duplicate ADT property')
            props[name]=value
        name=props.get('name',b'').split(b'\0')[0].decode('ascii')
        if '/' in name:raise ValueError('Invalid node name')
        path=parent+'/'+name if parent else '/'+name
        if path in result:
            if path.rstrip('/').endswith(('/chosen', '/sgx', '/arm-io')) or '/sgx/' in path:
                raise ValueError('Ambiguous GPU contract node: '+path)
            # Preserve repeated siblings; selected GPU nodes must remain unique.
            path += '@adt-offset-%x' % start
            if path in result:raise ValueError('ADT disambiguation collision')
        result[path]=props
        for _ in range(children):node(path.rstrip('/'),depth+1)
    node('',0);return result
