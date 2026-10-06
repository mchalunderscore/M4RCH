#!/usr/bin/env python3
"""Decode loader-reserved Apple device-tree metadata, not firmware code."""
import argparse,json,struct
from pathlib import Path

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
        if path in result:raise ValueError('Duplicate ADT path')
        result[path]=props
        for _ in range(children):node(path.rstrip('/'),depth+1)
    node('',0);return result

def selected(tree):
    result={}
    for path,props in tree.items():
        if path.rstrip('/').endswith('/chosen'):
            result[path]={k:v.hex() for k,v in props.items() if k in ('firmware-version','system-firmware-version','iboot-stage-one-tag','iboot-stage-two-tag','chip-id','board-id')}
        elif path.rstrip('/').endswith('/sgx') or '/sgx/' in path or path.rstrip('/').endswith('/arm-io'):
            result[path]={k:v.hex() for k,v in props.items() if k not in ('AAPL,phandle',)}
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.input.stat().st_size>16*1024*1024:raise ValueError('ADT size limit')
    tree=parse(a.input.read_bytes());report={'schema':'m4rch.selected-adt.v1','node_count':len(tree),'nodes':selected(tree)}
    with a.output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
if __name__=='__main__':main()
