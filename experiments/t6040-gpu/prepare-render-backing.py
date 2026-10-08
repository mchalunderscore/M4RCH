"""Prepare checked authored Apple9 candidate backing, no GPU publication."""
from pathlib import Path
import json,hashlib,argparse
p=argparse.ArgumentParser();p.add_argument('draw',type=Path);p.add_argument('target',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(exist_ok=False)
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
header='#define RENDER_BACKING_PAGES 22U\n#define RENDER_EXTRA_PAGES 28U\nstatic const u64 render_vas[]={'+','.join(hex(x)+'ULL' for x in vas)+'};\nstatic const u8 render_bytes[RENDER_BACKING_PAGES*PAGE_SIZE]={'+','.join('['+hex(i)+']='+hex(v) for i,v in enumerate(data) if v)+'};\n'
(a.output/'render-data.h').write_text(header);(a.output/'backing.bin').write_bytes(data)
report=dict(shader_base=hex(base),target_va=hex(target_va),state_va=hex(state_va),pages=22,extra_table_pages=6,bytes=len(data),data_sha256=sha(data),header_sha256=sha(header.encode()),target_receipt_sha256=sha((a.target/'receipt.json').read_bytes()),draw_receipt_sha256=sha((a.draw/'receipt.json').read_bytes()),objects=[dict(name=n,va=hex(va),bytes=len(b),sha256=sha(b)) for n,va,b in [('usc',base,usc),('target',target_va,tgt),('draw-state',state_va,bytes(state))]],submission_ready=False,qualification='Checked authored compiler/state candidates bound to previous receipt-linked VAs; no native descriptor relocation, GPU translation, shader execution or complete job proved.')
(a.output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n');print('Prepared22 render data pages and6 table pages')
