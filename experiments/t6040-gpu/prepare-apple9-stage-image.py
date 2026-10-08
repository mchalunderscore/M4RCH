#!/usr/bin/env python3
"""Offline candidate USC image: compiled bodies, persistent entries, roots, launches."""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('shaders',type=Path);p.add_argument('launcher',type=Path);p.add_argument('output',type=Path);p.add_argument('--shader-base',type=lambda v:int(v,0),required=True);a=p.parse_args()
if a.shader_base<0 or a.shader_base%0x100000000 or a.shader_base>=1<<48:raise ValueError('Use an aligned fixture 4-GiB USC heap base below 48 bits')
a.output.mkdir(parents=True,exist_ok=False)
image=bytearray(0x50000);stages={}
for name,stage,block,body,roots,launch in [('vertex',0,0x400,0x10000,0x40000,0x30000),('fragment',1,0x4c0,0x20000,0x40400,0x30400)]:
 binary=(a.shaders/(name+'.bin')).read_bytes();meta=json.loads((a.shaders/(name+'.bin.json')).read_text())
 assert len(binary)==meta['binary_size'] and len(binary)<=0x10000
 if meta['scratch_size'] or meta['apple9_preamble_size'] or meta['apple9_resource_count'] or meta['apple9_texture_mask'] or meta['apple9_sampler_mask'] or meta['apple9_image_mask']:raise ValueError('This fixture only supports scratch/resource/preamble-free canonical shaders')
 assert meta['varying_components']==3 and (stage or meta['apple9_publication_count']==7)
 entry=block+0x80;displacement=body-entry
 # Gravity Apple9 signed instruction-start-relative branch; no execution claim.
 branch=b'\x0f\x00\x54'+(displacement&((1<<48)-1)).to_bytes(6,'little')+b'\0'
 struct.pack_into('<I',image,block,0xc0);image[entry:entry+10]=branch;image[entry+10:entry+14]=b'\x0e\0\0\0'
 image[body:body+len(binary)]=binary
 dest=a.output/(name+'-launch.bin')
 args=[stage,str(dest),a.shader_base,a.shader_base+launch,a.shader_base+roots,entry,meta['apple9_publication_count'],0,4 if stage else 0,1 if stage else 0,0,0]
 subprocess.run([str(a.launcher),*[str(v) for v in args]],check=True)
 payload=dest.read_bytes();assert len(payload)==256;image[launch:launch+256]=payload
 header=66;encoded=int.from_bytes(payload[header+2:header+5],'little');assert encoded==2*entry+0x2a
 decoded_disp=int.from_bytes(branch[3:9],'little',signed=True);assert a.shader_base+entry+decoded_disp==a.shader_base+body
 stages[name]={'block_offset':block,'entry_offset':entry,'body_offset':body,'roots_offset':roots,'launch_offset':launch,'body_bytes':len(binary),'body_sha256':hashlib.sha256(binary).hexdigest(),'launch_sha256':hashlib.sha256(payload).hexdigest(),'entry_branch_hex':branch.hex(),'metadata':meta}
assert stages['vertex']['metadata']['varying_mask']==stages['fragment']['metadata']['varying_mask']
(a.output/'usc-candidate.bin').write_bytes(image)
report={'shader_base':hex(a.shader_base),'image_bytes':len(image),'image_sha256':hashlib.sha256(image).hexdigest(),'stages':stages,'qualification':'Offline candidate byte image using Gravity layout and synthetic USC base. Body references, launch targets and matching varying masks checked. Root tables zero only because canonical shaders have no resource bindings; runtime validity not proved. No UAT allocation, GPU mapping, cache sync, coefficients, PPP/PBE, target/tile storage, VDM/firmware command or completion. Do not submit as a complete job.'}
(a.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print('Prepared candidate stage image; branch/launch links and varying masks checked; no GPU access')
