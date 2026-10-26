"""Full RGBA8 readback and conditional source-derived image comparison."""
import hashlib,json,struct,zlib
from pathlib import Path
RECIPE_HASHES={'prepare-apple9-shaders.py':'2c5836031e8dd370f4b242baf5449aefcbc90e6346ab8f9d6f08870970666cdb','prepare-apple9-target.py':'9586b6f853f183fc47ba4982bac940e68019992ff4ea4a93cdf08b805e20e5b1'}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def pixel_model(x,y):
 nx=(x+.5)/32-1;ny=(y+.5)/32-1
 blue=(ny+.75)/1.5;green=((nx+.75)-.75*blue)/1.5;red=1-green-blue
 near=min(abs(red),abs(green),abs(blue))<.03
 inside=min(red,green,blue)>=0
 rgba=[red*red,green+.125,blue*.5,1] if inside else [.5625,.625,.125,1]
 return bytes(round(max(0,min(1,c))*255) for c in rgba),inside,near
def check_full(receipt,data):
 for name,h in RECIPE_HASHES.items():
  if sha((Path(__file__).resolve().parent.parent/name).read_bytes())!=h:raise ValueError('Canonical source recipe changed: '+name)
 target=receipt['target']
 if (target['width'],target['height'],target['stride_bytes'],target['bytes'],target['format'],target['address'])!=(64,64,256,16384,'RGBA8 UNORM','0x2000010000') or len(data)!=16384:raise ValueError('Target layout/extent differs')
 sentinel=bytes([target['sentinel']])*16384
 counts={'interior_tested':0,'background_tested':0,'edge_excluded':0,'interior_mismatch':0,'background_mismatch':0};maximum=0;changed_pixels=0
 for y in range(64):
  for x in range(64):
   at=y*256+x*4;actual=data[at:at+4];expected,inside,near=pixel_model(x,y)
   changed_pixels+=actual!=sentinel[at:at+4]
   if near:counts['edge_excluded']+=1;continue
   kind='interior' if inside else 'background';counts[kind+'_tested']+=1
   error=max(abs(a-b) for a,b in zip(actual,expected));maximum=max(maximum,error)
   counts[kind+'_mismatch']+=error>2
 for sample in receipt['interior_reference_samples']:
  expected,inside,near=pixel_model(*sample['pixel_y_up'])
  if list(expected)!=sample['rgba8_nearest'] or not inside or near:raise ValueError('Bound shader reference differs')
 return dict(bytes=len(data),sha256=sha(data),untouched_sentinel=data==sentinel,changed_bytes=sum(a!=b for a,b in zip(data,sentinel)),changed_pixels=changed_pixels,whole_image_counts=counts,maximum_tested_channel_error=maximum,source_recipe_sha256=RECIPE_HASHES,target_recipe=target,target_owned_page=132,source_draw_receipt_sha256=receipt['draw_receipt_sha256'],
  conditional_candidate_pattern_matches=not(counts['interior_mismatch'] or counts['background_mismatch']),full_image_layout_hardware_verified=False,rendering_verified=False,
  qualification='Every pixel preserved; interior/background comparison derives from the pinned canonical shader recipe under provisional y-up linear layout, UNORM quantization and raster coverage. Edge pixels are counted but excluded from exact match. A CPU-written matching image does not prove GPU execution or completion.')
def png(data):
 if len(data)!=16384:raise ValueError('Full target required')
 def chunk(kind,payload):return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
 scan=b''.join(b'\0'+data[y*256:(y+1)*256] for y in reversed(range(64)))
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b'')
