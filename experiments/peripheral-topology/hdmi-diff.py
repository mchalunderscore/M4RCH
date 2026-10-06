#!/usr/bin/env python3
"""Compare selected display state without publishing raw EDIDs or serial numbers."""
import argparse,hashlib,json,plistlib,re
from pathlib import Path
FIELDS={'HDMI_HPD','HDMI_HPD-Debounced','HDMIPortID','PortNumber','PortType','PortTypeDescription','TransportsActive','TransportsProvisioned','TransportsSupported','IOFBOnline','IOFBActive','IOFBConnectFlags','IOFBDependentIndex','IOFBDependentID','IOFBTransportType','DisplayVendorID','DisplayProductID','port-number','port-type','primary-port-id','IOObjectClass'}
def collect(data):
 result={}
 def walk(nodes,parent=''):
  if isinstance(nodes,dict):nodes=[nodes]
  for node in nodes:
   path=parent+'/'+node.get('IORegistryEntryName','?')
   if re.search('dcpext|/dcp/|hdmi|dpphy|IOMobileFramebuffer|AppleDCPDPTX',path,re.I):
    props={k:v if not isinstance(v,bytes) else {'hex':v.hex()} for k,v in node.items() if k in FIELDS and isinstance(v,(int,str,bool,bytes))}
    for k,v in node.items():
     if 'edid' in k.lower() and isinstance(v,bytes):props[k]={'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()}
    if props:result[path]=props
   walk(node.get('IORegistryEntryChildren',[]),path)
 walk(data);return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('before',type=Path);p.add_argument('after',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 old=collect(plistlib.loads(a.before.read_bytes()));new=collect(plistlib.loads(a.after.read_bytes()))
 delta={path:{'before':old.get(path),'after':new.get(path)} for path in sorted(old.keys()|new.keys()) if old.get(path)!=new.get(path)}
 with a.output.open('x') as f:json.dump({'changed_nodes':delta},f,indent=2);f.write('\n')
 print('Changed selected nodes:',len(delta))
