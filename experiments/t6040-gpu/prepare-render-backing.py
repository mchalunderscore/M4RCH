"""Prepare checked authored Apple9 candidate backing, no GPU publication."""
from pathlib import Path
import json,hashlib,argparse,struct
p=argparse.ArgumentParser();p.add_argument('draw',type=Path);p.add_argument('target',type=Path);p.add_argument('output',type=Path);p.add_argument('--storage-profile',type=Path);a=p.parse_args();a.output.mkdir(exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest();draw=json.loads((a.draw/'receipt.json').read_text());target=json.loads((a.target/'receipt.json').read_text())
assert int(draw['shader_base'],0)==int(target['shader_base'],0)==1<<40
assert target['draw_receipt_sha256']==sha((a.draw/'receipt.json').read_bytes())
def checked(root,receipt,name):
 b=(root/name).read_bytes();r=receipt['files'][name];assert len(b)==r['bytes'] and sha(b)==r['sha256'];return b
usc=checked(a.target,target,'usc-with-target-store.bin');assert len(usc)==20*16384
tgt=checked(a.target,target,'target-sentinel.bin');assert len(tgt)==16384 and tgt==bytes([165])*16384
state=bytearray(16384)
for name,root,r,off in [('vdm.bin',a.draw,draw,0),('ppp.bin',a.draw,draw,0x1000),('scissor.bin',a.target,target,0x2000),('depth-bias.bin',a.target,target,0x2040)]:
 b=checked(root,r,name);state[off:off+len(b)]=b
base=1<<40;target_va=int(target['target']['address'],0);state_va=int(draw['candidate']['context_base'],0)
assert not (target_va|state_va)&16383 and len({base>>36,target_va>>36,state_va>>36})==3
vas=[base+i*16384 for i in range(20)]+[target_va,state_va];data=usc+tgt+state
storage=[]
if a.storage_profile:
 profile=json.loads(a.storage_profile.read_text());assert profile['submission_ready'] is False
 assert (profile['width'],profile['height'],profile['samples'],profile['layers'])==(64,64,1,1)
 assert target['target']['width']==64 and target['target']['height']==64
 for name,r in profile['files'].items():
  b=(a.storage_profile.parent/name).read_bytes();assert len(b)==r['bytes'] and sha(b)==r['sha256']
 source=(a.storage_profile.parent/'render-target-source-fixture.bin').read_bytes();q=lambda off:struct.unpack_from('<Q',source,off)[0]
 ring=profile['ring'];assert ring['allocation_bytes']==q(0x268) and ring['capacity_bytes']==q(0x270)
 assert ring['entry_main_bytes']==q(0x10) and ring['entry_adjacent_bytes']==q(0x30) and ring['entry_extra_bytes']==q(0x260)
 assert ring['offsets']==[q(0x2a8),q(0x2b0),q(0x2b8)] and ring['capacity_bytes']>=16*(q(0x10)+q(0x30)+q(0x260))
 assert q(0x270)>0 and q(0x270)&(q(0x270)-1)==0
 gtp=profile['gtp'];assert gtp['sizes']==[q(0x140+8*j) for j in range(8)] and gtp['alignments']==[q(0x188+8*j) for j in range(7)]
 offsets=[0]
 for j,alignment in enumerate(gtp['alignments']):
  end=offsets[-1]+gtp['sizes'][j];offsets.append(end if alignment==0 else (end+alignment-1)&-alignment)
 assert offsets==gtp['offsets'] and gtp['allocation_bytes']==offsets[-1]+gtp['sizes'][-1]
 ring_va=int(ring['candidate_device_base'],0);gtp_va=ring_va+((q(0x268)+16383)//16384)*16384
 for name,va,size in [('native-ring-storage',ring_va,q(0x268)),('native-gtp-storage',gtp_va,gtp['allocation_bytes'])]:
  pages=(size+16383)//16384;assert 0<size<=1048576 and va&16383==0
  assert va>>25==state_va>>25 and va>>36==state_va>>36
  newvas=[va+j*16384 for j in range(pages)];assert not set(newvas)&set(vas)
  vas.extend(newvas);data+=bytes(pages*16384)
  storage.append(dict(name=name,va=hex(va),logical_bytes=size,pages=pages,initialization='zero allocation-only placeholder; native contents unqualified'))
header='#define RENDER_BACKING_PAGES '+str(len(vas))+'U\n#define RENDER_EXTRA_PAGES '+str(len(vas)+6)+'U\nstatic const unsigned int render_region_starts[]={0,20,21};\nstatic const unsigned int render_region_counts[]={20,1,'+str(len(vas)-21)+'};\nstatic const u64 render_vas[]={'+','.join(hex(x)+'ULL' for x in vas)+'};\nstatic const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n'
(a.output/'render-data.h').write_text(header);(a.output/'backing.bin').write_bytes(data)
report=dict(shader_base=hex(base),target_va=hex(target_va),state_va=hex(state_va),pages=len(vas),storage=storage,storage_profile_sha256=sha(a.storage_profile.read_bytes()) if a.storage_profile else None,extra_table_pages=6,bytes=len(data),data_sha256=sha(data),header_sha256=sha(header.encode()),target_receipt_sha256=sha((a.target/'receipt.json').read_bytes()),draw_receipt_sha256=sha((a.draw/'receipt.json').read_bytes()),objects=[dict(name=n,va=hex(va),bytes=len(b),sha256=sha(b)) for n,va,b in [('usc',base,usc),('target',target_va,tgt),('draw-state',state_va,bytes(state))]],submission_ready=False,qualification='Checked authored compiler/state candidates bound to previous receipt-linked VAs; no native descriptor relocation, GPU translation, shader execution or complete job proved.')
(a.output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n');print('Prepared',len(vas),'render/storage data pages and6 table pages')
