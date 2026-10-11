#!/usr/bin/env python3
"""Construct an overlay from caller-captured current ADT and expanded live OF.

The launcher must capture both inputs in this boot AFTER loading the metadata
bridge (which supplies the existing GFX provider's phandle). Never pass saved
trial inputs. This script itself reads no hardware or implicit live files.
"""
import argparse,importlib.util,json,struct,subprocess,uuid
from pathlib import Path
from native_adt_bridge_v7 import node_properties,raw_inputs,pin
KIT=Path(__file__).resolve().parent
OWNER='/soc/power-management@288e80000/power-controller@110'
SOURCES={'ttbs':'gpu-region','pagetables':'gfx-shared-region','l2':'gfx-shared-l2-region','handoff':'gfx-handoff','firmware':'gfx-data'}
def original(path):
 parser=KIT/'adt.py'
 if not parser.exists():parser=KIT.parents[3]/'experiments/t6040-gpu/adt.py'
 spec=importlib.util.spec_from_file_location('current_loader_adt',parser)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module.parse(path.read_bytes()),parser
def translate(tree,node,index):
 words=struct.unpack('<'+'Q'*(len(node['reg'])//8),node['reg']);base,size=words[index*2:index*2+2]
 data=tree['/device-tree/arm-io']['ranges'];ranges=struct.unpack('<'+'Q'*(len(data)//8),data)
 hits=[(physical+base-child,size) for child,physical,span_ in zip(ranges[::3],ranges[1::3],ranges[2::3]) if base>=child and base+size<=child+span_]
 if len(hits)!=1:raise ValueError('Unique original ADT translation required')
 return hits[0]
def value(data):return '['+' '.join(f'{x:02x}' for x in data)+']'
def span(base,size):return '<'+' '.join(f'0x{x:x}' for x in (base>>32,base&0xffffffff,size>>32,size&0xffffffff))+'>'
def make(adt,of,output,boot_id):
 uuid.UUID(boot_id)
 output.mkdir(parents=True,exist_ok=False)
 tree,_=original(adt);before=node_properties(of.read_bytes());sgx=tree['/device-tree/arm-io/sgx'];asc=tree['/device-tree/arm-io/gfx-asc']
 assert all(x in before['/']['compatible'].split(b'\0') for x in (b'apple,j614s',b'apple,t6040'))
 assert not any(b'apple,agx-t6040' in p.get('compatible',b'').split(b'\0') for p in before.values())
 provider=before[OWNER];assert provider['label']==b'gfx\0' and provider['reg']==struct.pack('>II',0x110,4)
 handle=int.from_bytes(provider['phandle'],'big');assert handle not in (0,0xffffffff)
 banks=[]
 for p in before.values():
  if p.get('device_type')==b'memory\0':
   assert len(p['reg'])%16==0
   banks += [struct.unpack_from('>QQ',p['reg'],i) for i in range(0,len(p['reg']),16)]
 assert banks
 def u64(key):
  assert len(sgx[key])==8
  return struct.unpack('<Q',sgx[key])[0]
 regions={}
 for name,source in SOURCES.items():
  b,n=u64(source+'-base'),u64(source+'-size')
  assert b and n>=0x4000 and not((b|n)&0x3fff) and b+n<(1<<64)
  assert all(b+n<=a or a+s<=b for a,s in banks),'reservation intersects Linux memory bank'
  assert all(b+n<=a or a+s<=b for a,s in regions.values()),'overlapping loader spans'
  regions[name]=(b,n)
 private=(u64('rtkit-private-vm-region-base'),u64('rtkit-private-vm-region-size'))
 assert private==(0xfffffc0000000000,0x2000000000)
 names=asc['segment-names'].split(b'\0')[0].split(b';');ranges=asc['segment-ranges'];assert len(ranges)==len(names)*32
 segments=[(name,struct.unpack_from('<4Q',ranges,i*32)) for i,name in enumerate(names)]
 data=next(x for name,x in segments if name==b'__DATA');assert data[0]==data[2] and (data[2],data[3]&0xffffffff)==regions['firmware']
 sgxr=translate(tree,sgx,0);ascr=translate(tree,asc,0)
 assert sgxr==(0x288000000,0x3758000) and ascr==(0x28a600000,0x88000)
 aics=[p for p in before.values() if b'apple,t6040-aic3' in p.get('compatible',b'').split(b'\0')];assert len(aics)==1
 aic=int.from_bytes(aics[0]['phandle'],'big')
 irqs=struct.unpack('<4I',asc['interrupts']);irqs=[irqs[1],irqs[0],irqs[3],irqs[2]]
 text='/dts-v1/;\n/plugin/;\n/ {\nfragment@0 { target-path="/reserved-memory"; __overlay__ { #address-cells=<2>; #size-cells=<2>;\n'
 for name,(b,n) in regions.items():text+=f'native_{name}: native-gpu-{name}@{b:x} {{ reg={span(b,n)}; no-map; }};\n'
 text+='}; };\nfragment@1 { target-path="/soc"; __overlay__ { #address-cells=<2>; #size-cells=<2>;\n'
 text+='native_mailbox: mailbox@28a608000 { compatible="apple,t8140-asc-mailbox","apple,asc-mailbox-v4"; status="okay"; #mbox-cells=<0>; '
 text+=f'reg={span(ascr[0]+0x8000,0x4000)}; power-domains=<{handle}>; interrupt-parent=<{aic}>; interrupts=<'+' '.join(f'0 {i} 4' for i in irqs)+'>; interrupt-names="send-empty","send-not-empty","recv-empty","recv-not-empty"; };\n'
 text+='gpu@28a600000 { compatible="apple,agx-t6040"; status="okay"; '
 text+=f'reg={span(*ascr)}, {span(*sgxr)}; reg-names="asc","sgx"; mboxes=<&native_mailbox>; power-domains=<{handle}>; '
 text+='memory-region=<'+' '.join('&native_'+name for name in regions)+'>; memory-region-names='+','.join('"'+n+'"' for n in regions)+';\n'
 props=raw_inputs(sgx)|{'apple,rtkit-private-vm-region':struct.pack('>QQ',*private),'apple,firmware-build':tree['/device-tree/chosen']['firmware-version'].split(b'\0')[0]+b'\0','apple,chip-revision':struct.pack('>I',int.from_bytes(tree['/device-tree/arm-io']['chip-revision'],'little'))}
 for key,data in props.items():text+=f'{key}={value(data)};\n' if data else f'{key};\n'
 text+='}; }; }; };\n'
 dts=output/'native-current.dts';dts.write_text(text);dtbo=output/'native-current.dtbo'
 subprocess.run(['dtc','-@','-I','dts','-O','dtb','-o',str(dtbo),str(dts)],check=True,stderr=(output/'dtc.log').open('w'))
 receipt={'schema':'m4rch.current-loader-overlay.v15','boot_id':boot_id,'inputs':[pin(adt),pin(of)],'output':pin(dtbo),'provider_handle':handle,'loader_regions':{k:{'physical':hex(b),'bytes':n} for k,(b,n) in regions.items()},'outside_current_OF_memory_banks':True,'hardware_actions':[],'overlay_applied':False,'capture_freshness':'Caller must capture ADT and expanded OF in the stated boot; hashes alone do not prove freshness.'}
 (output/'overlay-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adt',type=Path,required=True);p.add_argument('--of',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--boot-id',required=True);a=p.parse_args();make(a.adt,a.of,a.output,a.boot_id)
