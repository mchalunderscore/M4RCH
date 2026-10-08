#!/usr/bin/env python3
"""Build offline CF/PPP/VDM candidates and compare selected pinned Mesa serializers."""
import argparse, ctypes, hashlib, json, random, struct, subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('mesa',type=Path);p.add_argument('stage_image',type=Path);p.add_argument('output',type=Path);p.add_argument('receipt',type=Path)
a=p.parse_args()
src=a.mesa/'src/gallium/drivers/asahi/agx_apple9.c';text=src.read_text()
head=subprocess.check_output(['git','-C',str(a.mesa),'rev-parse','HEAD'],text=True).strip()
if head!='87ac51d411f0e58a9433567ec2666f457be89e1d':raise ValueError('Unqualified Mesa revision')
a.output.mkdir(parents=True,exist_ok=False)
def function(name):
 start=text.index(name+'(');start=text.rfind('\n',0,start)+1
 opening=text.index('{',start);depth=1;end=opening+1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 # Extract only the signature/body; caller supplies original return type.
 return text[start:end]
cf='static unsigned\n'+function('apple9_cf_binding_count')+'\nstatic unsigned\n'+function('apple9_build_cf_bindings')
group='static void\n'+function('apple9_build_direct_bind_group')
pppdef=text[text.index('struct agx_apple9_ppp_update {'):text.index('bool\nagx_apple9_link_render_pipeline(',text.index('struct agx_apple9_ppp_update {'))]
emit='static uint8_t *\n'+function('agx_apple9_emit_draw_state')+'\nuint8_t *\n'+function('agx_apple9_emit_direct_draw')
preamble=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define DIV_ROUND_UP(a,b) (((a)+(b)-1)/(b))
#define APPLE9_CF_BINDINGS 0x203d00u
#define APPLE9_CF_BINDINGS_SIZE 0x220u
#define AGX_APPLE9_MAX_VARYING_COMPONENTS 96
struct agx_apple9_interp_mask { uint64_t lo, hi; };
static bool agx_apple9_interp_mask_test(struct agx_apple9_interp_mask m,unsigned i) {assert(i<128);return ((i<64?m.lo:m.hi)>>(i&63))&1;}
static void apple9_put_u32(void *p,uint32_t v) {memcpy(p,&v,4);}
static uint32_t apple9_get_u32(const void *p) {uint32_t v;memcpy(&v,p,4);return v;}
static void apple9_put_f32(void *p,float v) {memcpy(p,&v,4);}
static unsigned util_bitcount(unsigned v) {return __builtin_popcount(v);}
#define MAX2(a,b) ((a)>(b)?(a):(b))
#define BITFIELD_MASK(n) ((1u<<(n))-1)
#define AGX_OBJECT_TYPE_TRIANGLE 0
#define AGX_OBJECT_TYPE_LINE_FILLED_TRIANGLE 5
#define AGX_OBJECT_TYPE_POINT_FILLED_TRIANGLE 6
#define AGX_POLYGON_MODE_LINE 1
#define AGX_POLYGON_MODE_POINT 2
#define AGX_APPLE9_RENDER_CONTEXT_BASE UINT64_C(0x1000000000)
struct agx_apple9_uniform_draw {uint64_t program_id[2];uint32_t cf_count,coefficients,launch[2],ppp;uint8_t ppp_record[256];bool flatshade_first,reads_tile,uses_discard,disable_tri_merging,writes_depth;uint32_t object_type,depth_face[2],stencil[2],raster_control,visibility_mode,depth_control,occlusion_index,scissor_min[2],scissor_max[2],scissor_index,depth_bias_index;float viewport_translate[3],viewport_scale[3];};
static uint64_t agx_pool_upload_aligned(void *unused,const void *data,unsigned size,unsigned alignment) {(void)unused;(void)data;assert(size==256&&alignment==64);return AGX_APPLE9_RENDER_CONTEXT_BASE+0x1000;}
static unsigned util_logbase2(unsigned v) {assert(v);return 31-__builtin_clz(v);}
/* Adapter-only structs: field-compatible with extracted functions, NOT a host/GPU ABI. */
struct agx_apple9_varying_layout {uint8_t mask[64],group[64];};
struct stage {const uint8_t *binary;bool reads_primitive_id;unsigned varying_components,clip_distance_count;bool apple9_reads_z,writes_point_size,writes_layer_viewport;struct agx_apple9_varying_layout varyings;};
struct agx_apple9_render_pipeline {struct stage vertex,fragment;uint32_t ppp,pipeline_word,vertex_launch,vertex_state_class;uint64_t index_buffer;uint32_t index_extent;uint8_t index_size,primitive;bool primitive_restart,flatshade_first;uint32_t restart_index;};
'''
wrappers=r'''
unsigned cf_out(uint8_t *out,unsigned n,uint64_t l0,uint64_t l1,uint64_t f0,uint64_t f1,unsigned flags) {return apple9_build_cf_bindings(out,n,(struct agx_apple9_interp_mask){l0,l1},(struct agx_apple9_interp_mask){f0,f1},flags&1,flags&2,flags&4,flags&8);}
void group_out(uint8_t *out,unsigned n) {apple9_build_direct_bind_group(out,n);}
unsigned vdm_out(uint8_t *out,uint32_t ppp,uint32_t entry,uint32_t launch,uint32_t components,unsigned first) {uint8_t dummy=0;struct agx_apple9_render_pipeline p={.vertex={.binary=&dummy},.fragment={.binary=&dummy},.ppp=ppp,.pipeline_word=entry,.vertex_launch=launch,.vertex_state_class=(4+components)*0x101,.primitive=6,.flatshade_first=first};return agx_apple9_emit_direct_draw(out,&p,3,1,0)-out;}
'''
tail_start=text.index('   draw->cf_count = cf_count;',text.index('agx_apple9_prepare_draw('))
tail_end=text.index('\n}\n',tail_start)
tail=text[tail_start:tail_end]
ppp_adapter='bool prepare_tail(const struct agx_apple9_render_pipeline *pipeline, struct agx_apple9_uniform_draw *draw) {const struct agx_apple9_uniform_draw *previous=0;unsigned cf_count=2,tile_bytes=4,samples=1;void *context_pool=0;\n'+tail+'\n}\n'
ppp_adapter+=r'''
void ppp_out(uint8_t *out,uint32_t launch,uint32_t coefficients) {
 struct agx_apple9_render_pipeline p={0};p.vertex.varying_components=3;p.vertex.varyings.mask[32]=7;
 struct agx_apple9_uniform_draw d={0};d.coefficients=coefficients;d.launch[1]=launch;d.depth_control=0x10200;
 d.depth_face[0]=d.depth_face[1]=0x07200f00;d.stencil[0]=d.stencil[1]=0x0e000000;
 d.raster_control=(1u<<16)|(3u<<10);d.scissor_max[0]=d.scissor_max[1]=64;
 d.viewport_translate[0]=d.viewport_translate[1]=32;d.viewport_scale[0]=d.viewport_scale[1]=32;d.viewport_scale[2]=1;
 assert(prepare_tail(&p,&d));assert(d.ppp==0x1000);memcpy(out,d.ppp_record,256);
}
'''
cpath=a.output/'source-adapter.c';cpath.write_text(preamble+cf+'\n'+group+'\n'+ppp_adapter+'\n'+pppdef+'\n'+emit+'\n'+wrappers)
so=a.output/'source-adapter.so';subprocess.run(['cc','-Wall','-Wextra','-Werror','-O2','-shared','-fPIC',str(cpath),'-o',str(so)],check=True)
lib=ctypes.CDLL(str(so.resolve()));ptr=ctypes.POINTER(ctypes.c_ubyte)
lib.cf_out.argtypes=[ptr,ctypes.c_uint,*([ctypes.c_uint64]*4),ctypes.c_uint];lib.cf_out.restype=ctypes.c_uint
lib.ppp_out.argtypes=[ptr,ctypes.c_uint32,ctypes.c_uint32];lib.group_out.argtypes=[ptr,ctypes.c_uint];lib.vdm_out.argtypes=[ptr,*([ctypes.c_uint32]*5)];lib.vdm_out.restype=ctypes.c_uint

def put(b,o,v):struct.pack_into('<I',b,o,v)
def cf_model(n,linear,flat,flags):
 b=bytearray(0x220);first,z,point,primitive=[bool(flags&(1<<i)) for i in range(4)]
 slots=n+1+z+2*point+primitive;put(b,0,slots*0x101);put(b,4,12)
 def shade(i):return (0 if first else 2) if flat>>i&1 else 3 if linear>>i&1 else 7
 start=0;binding=1
 while start<n:
  count=1
  while count<4 and start+count<n and shade(start+count)==shade(start):count+=1
  base=start+1;put(b,4+4*binding,count-1|(shade(start)<<2)|((base+z)<<8)|(base<<16));binding+=1;start+=count
 for enabled,value,slot in [(primitive,0x60,n+1),(z,0x12c,n+1+primitive),(point,0x4d,n+1+primitive+z)]:
  if enabled:put(b,4+4*binding,value|(slot<<16));binding+=1
 return bytes(b),binding
COMMON={0:0x800000,4:0x10100,8:0xc9c0,0x10:0x1000000,0x14:0x66420,0x1c:0xc0a0000,0x20:0x10000,0x2c:6,0x30:0x10000b4,0x34:0x40200,0x38:0x7200f00,0x3c:0xe000000,0x40:0x7200f00,0x44:0xe000000,0x4c:0x2000048,0x50:0x200,0x54:0x7e00000,0x58:0x7e00000,0x5c:15,0x60:0x410000,0x68:0x80,0x6c:0x200000,0x70:0x480}
def group_model(n):
 b=bytearray(128)
 for o,v in COMMON.items():put(b,o,v)
 for o,v in {4:0,8:0,0x14:0x4e19,0x20:0,0x2c:4,0x5c:0x1ffff}.items():put(b,o,v)
 for o,v in {5:1,6:2,8:0x80,9:4,0x15:0x8c,0x22:1,0x2c:4+n}.items():b[o]=v
 put(b,4,0x100|((1+(n+3)//4)<<16));put(b,8,0x203d00);put(b,0x18,n//8)
 return b
UPDATES=[(0,0x700),(0x40,0x500),(0x5c,0x700),(0x70,0x500),(0x8c,0xa00),(0xc0,0x300),(0xa0,0x200),(0xac,0x200)]
def vdm_model(ppp,entry,launch,n,first):
 w=[0x4000002e,0,entry,launch,(4+n)*0x101,0 if first else 2,0,0x500]
 for rel,ctrl in UPDATES:w += [ppp+rel,ctrl]
 w += [ppp+0xf0,0x61c40600,3,1,0,0xc0000000]
 return struct.pack('<30I',*w)
rng=random.Random(604013);counts={'coefficient':0,'direct_group':0,'direct_vdm':0}
for i in range(256):
 n=i%97;linear=rng.getrandbits(96);flat=rng.getrandbits(96);flags=i%16
 buf=(ctypes.c_ubyte*0x220)();count=lib.cf_out(buf,n,linear&((1<<64)-1),linear>>64,flat&((1<<64)-1),flat>>64,flags)
 expected,bindings=cf_model(n,linear,flat,flags);assert bytes(buf)==expected and count==bindings;counts['coefficient']+=1
 buf=(ctypes.c_ubyte*128)();lib.group_out(buf,n);assert bytes(buf)==group_model(n);counts['direct_group']+=1
 ppp=(0x1000+i*0x100);entry=0x01000000;launch=0x30000//64;first=i&1
 buf=(ctypes.c_ubyte*120)();assert lib.vdm_out(buf,ppp,entry,launch,n,first)==120;assert bytes(buf)==vdm_model(ppp,entry,launch,n,first);counts['direct_vdm']+=1
stage=json.loads((a.stage_image/'receipt.json').read_text());v=stage['stages']['vertex'];f=stage['stages']['fragment'];vm=v['metadata'];fm=f['metadata']
assert vm['varying_mask']==fm['varying_mask'] and vm['varying_group']==fm['varying_group']
if vm['varying_components']!=3 or fm['varying_components']!=3 or any(fm['linear_mask']+fm['flat_mask']):raise ValueError('Canonical three-smooth-varying fixture only')
cf,count=cf_model(3,0,0,0);(a.output/'coefficients.bin').write_bytes(cf)
# The following is the canonical, no-depth/no-stencil/no-query prepare_draw tail,
# independently assembled here and checked against the extracted source tail.
# Earlier prepare_draw allocation/entry installation are not executed.
ppp=bytearray(256);put(ppp,0,0x10040000)
counts_by_group=[0,0,0]
for mask,group_index in zip(vm['varying_mask'],vm['varying_group']):counts_by_group[group_index]+=mask.bit_count()
put(ppp,4,sum(c<<(8*i) for i,c in enumerate(counts_by_group)))
b=group_model(3);coef_offset=0x40800
put(b,8,coef_offset);put(b,4,0x100|(count<<16));put(b,0x18,1);put(b,0x14,f['launch_offset']//64)
put(b,0x2c,7);put(b,0x70,(struct.unpack_from('<I',b,0x70)[0]&~0x30d83)|(3<<7)|(1<<16)|(3<<10))
put(b,0x48,0);put(b,0x34,0x10200)
for offset in (0x38,0x40):put(b,offset,0x07200f00)
for offset in (0x3c,0x44):put(b,offset,0x0e000000)
for offset in (0x54,0x58):put(b,offset,(struct.unpack_from('<I',b,offset)[0]&0x0f33ffff)|(3<<22))
ppp[0x40:0xc0]=b;put(ppp,0xc0,0xc00);put(ppp,0xc4,0x80000001);put(ppp,0xc8,1)
for axis,(translate,scale) in enumerate([(32,32),(32,32),(0,1)]):struct.pack_into('<ff',ppp,0xd0+axis*8,translate,scale)
put(ppp,0xf0,0x100);put(ppp,0xf4,0)
buf=(ctypes.c_ubyte*256)();lib.ppp_out(buf,f['launch_offset'],coef_offset);assert bytes(buf)==ppp;counts['canonical_ppp_tail']=1
(a.output/'ppp.bin').write_bytes(ppp)
vdm=vdm_model(0x1000,0x01000000,v['launch_offset']//64,3,False);(a.output/'vdm.bin').write_bytes(vdm)
image=bytearray((a.stage_image/'usc-candidate.bin').read_bytes());image[coef_offset:coef_offset+len(cf)]=cf
(a.output/'usc-with-coefficients.bin').write_bytes(image)
report={'shader_base':stage['shader_base'],'stage_receipt_sha256':hashlib.sha256((a.stage_image/'receipt.json').read_bytes()).hexdigest(),'mesa_commit':head,'mesa_source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'extracted_functions':{name:hashlib.sha256(function(name).encode()).hexdigest() for name in ['apple9_cf_binding_count','apple9_build_cf_bindings','apple9_build_direct_bind_group','agx_apple9_emit_draw_state','agx_apple9_emit_direct_draw']},'prepare_draw_tail_sha256':hashlib.sha256(tail.encode()).hexdigest(),'comparisons':counts,'candidate':{'width':64,'height':64,'format':'RGBA8 UNORM','samples':1,'tile_bytes':4,'cf_bindings':count,'cf_offset':hex(coef_offset),'context_base':'0x1000000000','ppp_relative':'0x1000','vertex_entry_block':hex(v['block_offset']),'vertex_launch_units64':hex(v['launch_offset']//64),'pipeline_word':'0x01000000','fragment_launch':hex(f['launch_offset']),'vertex_count':3,'instance_count':1,'primitive':6,'depth_stencil_queries':False},'files':{path.name:{'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in a.output.glob('*.bin')},'qualification':'Offline candidate only. Pinned Mesa extracted CF/default-group/direct-VDM serializers execute in CPU adapter; independently modeled full bytes compared. Adapter structs are not native driver or firmware ABI. Full canonical PPP bytes compared to extracted prepare_draw tail with synthetic upload return; earlier prepare_draw allocations/entry installation excluded. All placement synthetic; no GPU VA allocation, target/PBE/tile storage, scissor/depth-bias upload, TA/3D job/microsequence or completion. Source serializers not independently hardware-qualified on 16-core T6040; do not submit as a complete job.'}
a.receipt.write_text(json.dumps(report,indent=2)+'\n');(a.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(counts)
