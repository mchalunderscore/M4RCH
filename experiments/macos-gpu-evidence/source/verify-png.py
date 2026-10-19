import pathlib,struct,zlib,json
root=pathlib.Path(__file__).resolve().parents[1]; data=(root/'render/triangle.png').read_bytes()
assert data[:8]==b'\x89PNG\r\n\x1a\n'
p=8;compressed=b''
while p<len(data):
 size=struct.unpack_from('>I',data,p)[0];kind=data[p+4:p+8];payload=data[p+8:p+8+size];crc=struct.unpack_from('>I',data,p+8+size)[0]
 assert zlib.crc32(kind+payload)&0xffffffff==crc
 if kind==b'IHDR':w,h,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',payload)
 if kind==b'IDAT':compressed+=payload
 p+=size+12
assert (w,h,depth,compression,filtering,interlace)==(64,64,8,0,0,0)
assert color in (2,6)
bpp=4 if color==6 else 3;stride=w*bpp;raw=zlib.decompress(compressed);prev=bytearray(stride);rgba=bytearray();position=0
for y in range(h):
 f=raw[position];position+=1;row=bytearray(raw[position:position+stride]);position+=stride
 for x in range(stride):
  a=row[x-bpp] if x>=bpp else 0;b=prev[x];c=prev[x-bpp] if x>=bpp else 0
  if f==0:v=0
  elif f==1:v=a
  elif f==2:v=b
  elif f==3:v=(a+b)//2
  elif f==4:
   estimate=a+b-c;pa=abs(estimate-a);pb=abs(estimate-b);pc=abs(estimate-c);v=a if pa<=pb and pa<=pc else b if pb<=pc else c
  else:raise ValueError(f)
  row[x]=(row[x]+v)&255
 for x in range(w):rgba.extend(row[x*bpp:x*bpp+3]+bytes([row[x*bpp+3] if bpp==4 else 255]))
 prev=row
assert bytes(rgba)==(root/'render/triangle.rgba').read_bytes()
assert bytes(rgba)==(root/'render/triangle-final.rgba').read_bytes()
(root/'render/png-verification.json').write_text(json.dumps({'verified':True,'png_crc_checks_passed':True,'all_4096_decoded_pixels_match_initial_and_final_raw_readbacks':True,'png_color_type':color,'width':w,'height':h},indent=2)+'\n')
print('PNG CRCs and all 4096 decoded pixels verified against both GPU readbacks')
