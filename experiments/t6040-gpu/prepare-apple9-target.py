#!/usr/bin/env python3
"""Offline linear target/PBE, EOT shader launch and pixel-readback fixtures."""
import argparse,ctypes,hashlib,json,shlex,struct,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('mesa',type=Path);p.add_argument('build',type=Path);p.add_argument('shaders',type=Path);p.add_argument('draw',type=Path);p.add_argument('launcher',type=Path);p.add_argument('output',type=Path);p.add_argument('receipt',type=Path);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
source_head=subprocess.check_output(['git','-C',str(a.mesa),'rev-parse','HEAD'],text=True).strip();assert source_head=='87ac51d411f0e58a9433567ec2666f457be89e1d'
commands=json.loads((a.build/'compile_commands.json').read_text());entry=next(e for e in commands if e['file'].endswith('/test/apple9-tiny-tool.c'))
defines=[s for s in shlex.split(entry['command']) if s.startswith('-D')]
adapter=Path(__file__).with_name('prepare-apple9-pbe-adapter.c');so=a.output/'pbe-adapter.so'
subprocess.run(['cc','-Wall','-Wextra','-O2','-shared','-fPIC',*defines,'-I',str(a.build/'src'),'-I',str(a.mesa/'src'),'-I',str(a.mesa/'include'),str(adapter),'-o',str(so)],check=True,capture_output=True,text=True)
lib=ctypes.CDLL(str(so.resolve()));lib.pack.argtypes=[ctypes.POINTER(ctypes.c_ubyte),ctypes.c_uint,ctypes.c_uint,ctypes.c_uint64,ctypes.c_uint]
def legacy(w,h,address,stride):
 assert 1<=w<=16384 and 1<=h<=16384 and address%16==0 and address<1<<40 and stride%16==0 and stride>=4*w
 # Shared PBE header XML and legacy linear packing; Apple9 replaces its address/stride later.
 value=2|(0x28<<6)|(0xe4<<16)|((w-1)<<24)|((h-1)<<38)|((address>>4)<<64)|((stride-4)<<104)
 return value.to_bytes(24,'little')
for i in range(1024):
 w=1+i%257;h=1+(i*13)%257;address=0x2000000000+i*0x10000;stride=(w*4+15)&~15
 buf=(ctypes.c_ubyte*24)();lib.pack(buf,w,h,address,stride);assert bytes(buf)==legacy(w,h,address,stride)
width=height=64;stride=256;target_address=0x2000010000
header=legacy(width,height,target_address,stride)[:8]
descriptor=bytearray(32);descriptor[:8]=header
# Pinned agx_state.c image-binding conversion: retain header low24 bits,
# replace dimensions, then 40 address bits in 16-byte units plus linear pitch.
h0,h1=struct.unpack('<II',header);h0=(h0&0xffffff)|((width-1)<<24);h1=((width-1)>>8)|((height-1)<<6)|(h1&0x1000000)
struct.pack_into('<IIQ',descriptor,0,h0,h1,(target_address>>4)|(((stride>>4)-1)<<44))
assert struct.unpack_from('<Q',descriptor,8)[0]&((1<<40)-1)==target_address>>4
assert (struct.unpack_from('<Q',descriptor,8)[0]>>44)&0xffff==(stride>>4)-1
(a.output/'target-pbe.bin').write_bytes(descriptor)
(a.output/'target-sentinel.bin').write_bytes(bytes([0xa5])*16384)
(a.output/'scissor.bin').write_bytes(struct.pack('<IIff',width,height,0,1));(a.output/'depth-bias.bin').write_bytes(bytes(12))
image=bytearray((a.draw/'usc-with-coefficients.bin').read_bytes());shader_meta=json.loads((a.shaders/'tile-store.bin.json').read_text());body=(a.shaders/'tile-store.bin').read_bytes()
assert shader_meta['apple9_image_mask']==1 and shader_meta['scratch_size']==0 and shader_meta['apple9_preamble_size']==0 and shader_meta['apple9_resource_count']==0 and shader_meta['varying_components']==0
base=0x800000000;block=0x580;entry=0x600;body_offset=0x28000;launch_offset=0x30800;roots=0x40c00;texture_table=0x43000
branch=b'\x0f\x00\x54'+(body_offset-entry).to_bytes(6,'little')+b'\0'
struct.pack_into('<I',image,block,0xc0);image[entry:entry+10]=branch;image[entry+10:entry+14]=b'\x0e\0\0\0';image[body_offset:body_offset+len(body)]=body
struct.pack_into('<Q',image,roots,base+texture_table);image[texture_table:texture_table+32]=descriptor
launch=a.output/'tile-store-launch.bin';subprocess.run([str(a.launcher),*map(str,[1,launch,base,base+launch_offset,base+roots,entry,shader_meta['apple9_publication_count'],0,4,1,0,0])],check=True)
payload=launch.read_bytes();assert len(payload)==256;assert int.from_bytes(payload[68:71],'little')==2*entry+0x2a;image[launch_offset:launch_offset+256]=payload
# Separate constant background candidate; no texture or interpolation roots.
clear_body=(a.shaders/'fragment-constant.bin').read_bytes();clear_meta=json.loads((a.shaders/'fragment-constant.bin.json').read_text())
assert clear_meta['varying_components']==0 and clear_meta['apple9_image_mask']==0 and clear_meta['scratch_size']==0
clear_block=0x640;clear_entry=0x6c0;clear_body_offset=0x24000;clear_roots=0x41000;clear_launch=0x30c00
struct.pack_into('<I',image,clear_block,0xc0)
clear_branch=b'\x0f\x00\x54'+(clear_body_offset-clear_entry).to_bytes(6,'little')+b'\0'
image[clear_entry:clear_entry+10]=clear_branch;image[clear_entry+10:clear_entry+14]=b'\x0e\0\0\0';image[clear_body_offset:clear_body_offset+len(clear_body)]=clear_body
clear_dest=a.output/'background-launch.bin';subprocess.run([str(a.launcher),*map(str,[1,clear_dest,base,base+clear_launch,base+clear_roots,clear_entry,clear_meta['apple9_publication_count'],0,4,1,0,0])],check=True)
clear_payload=clear_dest.read_bytes();assert int.from_bytes(clear_payload[68:71],'little')==2*clear_entry+0x2a;image[clear_launch:clear_launch+256]=clear_payload
(a.output/'usc-with-target-store.bin').write_bytes(image)
# Sample only triangle interior. Background helper/clear is not yet available;
# outside pixels cannot yet be required to have any particular value.
samples=[]
for x,y in [(32,32),(24,24),(40,24),(32,44)]:
 nx=(x+.5)/32-1;ny=(y+.5)/32-1;blue=(ny+.75)/1.5;green=((nx+.75)-.75*blue)/1.5;red=1-green-blue
 assert min(red,green,blue)>.03
 floats=[red*red,green+.125,blue*.5,1];rgba=[round(min(1,max(0,v))*255) for v in floats]
 samples.append({'pixel_y_up':[x,y],'linear_offset':y*stride+x*4,'float_rgba':floats,'rgba8_nearest':rgba,'tolerance_per_channel':2})
report={'mesa_commit':source_head,'comparisons':{'legacy_pbe_full_bytes':1024},'source_sha256':{name:hashlib.sha256((a.mesa/name).read_bytes()).hexdigest() for name in ['src/asahi/genxml/cmdbuf.xml','src/gallium/drivers/asahi/agx_state.c','src/gallium/drivers/asahi/agx_blit.c']},'target':{'address':hex(target_address),'width':64,'height':64,'stride_bytes':256,'bytes':16384,'format':'RGBA8 UNORM','sentinel':165,'pbe_hex':descriptor.hex()},'background_candidate':{'launch_byte_offset':hex(clear_launch),'body_bytes':len(clear_body),'float_rgba':[.5625,.625,.125,1],'qualification':'Constant fragment proposed for background dispatch; not firmware-qualified'},'tile_store':{'body_bytes':len(body),'entry_offset':hex(entry),'launch_offset':hex(launch_offset),'launch_units64':hex(launch_offset//64),'roots_offset':hex(roots),'texture_table_offset':hex(texture_table),'shader_metadata':shader_meta},'interior_reference_samples':samples,'files':{path.name:{'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in a.output.glob('*.bin')},'qualification':'Offline synthetic-address candidate. Legacy header pack compared to generated Mesa C in 1024 cases. Apple9 image descriptor conversion mirrors pinned source, not independent hardware evidence. Compiled EOT tile-store helper linked to one image descriptor with branch/launch checks; no shader execution. Target and canary bytes are CPU files, not allocated/mapped GPU resources. Firmware TA/3D register integration, parameter/tile buffers, background dispatch qualification, scissor/depth-bias address integration, barriers, completion and cache invalidation still required. Actual target orientation and quantization need qualification. Do not submit as a complete job.'}
a.receipt.write_text(json.dumps(report,indent=2)+'\n');(a.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print('1024 PBE pack comparisons passed; target/EOT/scissor/readback candidates prepared without GPU access')
