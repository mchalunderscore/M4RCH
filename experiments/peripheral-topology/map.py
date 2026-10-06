#!/usr/bin/env python3
"""Reduce a macOS IODeviceTree plist to peripheral resources and phandle links."""
import argparse,json,plistlib,re
from pathlib import Path
MATCH=re.compile(r'dcp|dcpext|display|hdmi|mca|admac|audio|codec|aop|isp|camera|mic|iop-audio',re.I)
FIELDS={'IOObjectClass','IOClass','IOProviderClass','IOName','IONameMatched','firmware-version','fw-version','CFBundleIdentifier','AAPL,phandle','name','compatible','device_type','reg','ranges','interrupts','interrupt-parent','clock-gates','clock-ids','power-gates','iommu-parent','dma-parent','dma-channels','clock-domain','external-power-provider','port-number','port-type','primary-port-id','transports-supported','iommu-instance','function-reset','function-admac_powerswitch','function-power','internal-mclk-src','mic-config','data-sources','input-data-selectors','default-input-data-selectors','cam-connections-scheme','camera-front','irq-destination-index','irq-destinations','channels-offset','#dma-channels','role','identifier'}
LINKS={'interrupt-parent','iommu-parent','dma-parent','external-power-provider'}
def value(obj):
 if isinstance(obj,bytes):
  result={'hex':obj.hex()}
  if len(obj)%4==0:result['u32le']=[int.from_bytes(obj[i:i+4],'little') for i in range(0,len(obj),4)]
  if obj and all(b==0 or 32<=b<127 for b in obj):result['strings']=[s.decode('ascii') for s in obj.split(b'\0') if s]
  return result
 return obj

def select(nodes):
 flat={}
 def walk(items,parent=''):
  if isinstance(items,dict):items=[items]
  for node in items:
   path=parent+'/'+str(node.get('IORegistryEntryName','?'));flat[path]=node
   walk(node.get('IORegistryEntryChildren',[]),path)
 walk(nodes)
 handles={}
 for path,node in flat.items():
  raw=node.get('AAPL,phandle')
  if isinstance(raw,bytes) and len(raw)==4:handles[int.from_bytes(raw,'little')]=path
 selected={p for p,n in flat.items() if MATCH.search(p.rsplit('/',1)[-1])}
 # Keep immediate bus providers and transitive scalar references as dependencies.
 queue=list(selected)
 while queue:
  path=queue.pop();parent=path.rsplit('/',1)[0]
  deps=[parent] if parent in flat else []
  for key in LINKS:
   raw=flat[path].get(key)
   if isinstance(raw,bytes) and len(raw)==4 and int.from_bytes(raw,'little') in handles:deps.append(handles[int.from_bytes(raw,'little')])
  for dep in deps:
   if dep not in selected:selected.add(dep);queue.append(dep)
 result=[]
 for path in sorted(selected):
  node=flat[path];props={k:value(v) for k,v in node.items() if k in FIELDS and isinstance(v,(bytes,str,int,bool)) and (not isinstance(v,bytes) or len(v)<=512)}
  refs={k:handles.get(int.from_bytes(v,'little'),'unresolved') for k,v in node.items() if k in LINKS and isinstance(v,bytes) and len(v)==4}
  result.append({'path':path,'properties':props,'scalar_phandle_links':refs})
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 data={'schema':1,'interpretation':'Raw ADT resources; little-endian decoding is a candidate interpretation, scalar phandles only. Not a Linux DT conversion or driver qualification.','nodes':select(plistlib.loads(a.input.read_bytes()))}
 with a.output.open('x') as f:json.dump(data,f,indent=2);f.write('\n')
 print('Selected resource nodes:',len(data['nodes']))
if __name__=='__main__':main()
