#!/usr/bin/env python3
"""Offline slot14 descriptor/PTE patch; no device access or firmware execution."""
import argparse, hashlib, json, re, shutil, struct
from pathlib import Path
PAGE=0x4000
PA=0x500658000
VA=0xfffffc2001b20000
EXTENT=0x10000

def sha(b): return hashlib.sha256(b).hexdigest()
def pin(p): return dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('destination',type=Path);a=p.parse_args();src=a.source.resolve();dst=a.destination.resolve()
 if dst.exists(): raise ValueError('Fresh output required')
 original=(src/'graph-before.bin').read_bytes();r=json.loads((src/'graph-receipt.json').read_text());h=next(o for o in r['objects'] if o['name']=='hardware');offset=h['arena_offset']+0x640+14*0x28
 assert sha(original)==r['arena_sha256'] and original[offset:offset+0x28]==bytes(0x28)
 leaves=r['mmio_leaves'];assert all(int(x['gpu_va'])!=VA and int(x['physical'])!=PA for x in leaves)
 assert VA>>25==int(r['base'],16)>>25 and VA>=int(r['base'],16)+len(original)
 assert all(not int(o['gpu_va'],16)<=VA<int(o['gpu_va'],16)+o['reserved_bytes'] for o in r['objects'])
 raw=bytearray(original);struct.pack_into('<QQIIQI',raw,offset,PA,VA,EXTENT,EXTENT,0,0)
 leaves.extend(dict(physical=PA+i,gpu_va=VA+i,readonly=True) for i in range(0,EXTENT,PAGE));leaves.sort(key=lambda x:int(x['gpu_va']))
 r['mmio_descriptors'].append(dict(slot=14,physical=hex(PA),gpu_va=hex(VA),size=hex(EXTENT),readonly=True,mapped_pages=4,mapping_class='platform',effective_writable_pages=[],role_qualification='25G83 constructor exact PA/extent; captured firmware1fdfc/1fe20 fallback reads at4600/5600. Readonly leaf is explicit Linux experiment.'))
 r['mapped_pages']+=4;r['arena_sha256']=sha(raw);h['input_sha256']=sha(raw[h['arena_offset']:h['arena_offset']+h['input_bytes']]);r['slot14_patch']=dict(descriptor_offset=hex(offset),source_arena_sha256=sha(original),no_other_arena_bytes_changed=True,read_only=True)
 header=(src/'graph-contract.h').read_text();header=header.replace('#define GRAPH_MAPPED_PAGES 171U','#define GRAPH_MAPPED_PAGES 175U')
 begin=header.index('static const struct graph_mmio_leaf mmio_leaves[] = {');end=header.index('};',begin)+2
 header=header[:begin]+'static const struct graph_mmio_leaf mmio_leaves[] = {\n'+''.join(f' {{ {int(x["physical"]):#x}ULL, {int(x["gpu_va"]):#x}ULL, {int(not x["readonly"])} }},\n' for x in leaves)+'};'+header[end:]
 begin=header.index('static const u8 graph_bytes[');end=header.index('};',begin)+2
 header=header[:begin]+f'static const u8 graph_bytes[{len(raw)}]={{\n'+''.join(f'[{i:#x}]={v:#x},\n' for i,v in enumerate(raw) if v)+'};'+header[end:]
 # Preserve immutable v9 source; remove only build products from the copied stage.
 shutil.copytree(src,dst,ignore=shutil.ignore_patterns('*.o','*.ko','*.mod','*.mod.c','*.cmd','Module.symvers','modules.order'))
 (dst/'graph-before.bin').write_bytes(raw);(dst/'graph-contract.h').write_text(header);(dst/'graph-receipt.json').write_text(json.dumps(r,indent=2)+'\n')
 changed=[i for i,(x,y) in enumerate(zip(original,raw)) if x!=y];assert all(offset<=i<offset+0x24 for i in changed)
 report=dict(schema='m4rch.v24-slot14-patch.v1',hardware_actions=[],source_pins=[pin(src/n) for n in ['graph-before.bin','graph-contract.h','graph-receipt.json']],script_pin=pin(Path(__file__)),changed_graph_offsets=[hex(i) for i in changed],slot=14,physical=hex(PA),virtual=hex(VA),extent=EXTENT,readonly=True,source_mapped_pages=171,mapped_pages=175,unchanged_source_files=[],changed_source_files=[],stale_build_receipts_are_historical=True,ready=False)
 for f in src.iterdir():
  if f.is_file() and (dst/f.name).exists():
   (report['unchanged_source_files'] if f.read_bytes()==(dst/f.name).read_bytes() else report['changed_source_files']).append(f.name)
 assert report['changed_source_files']==['graph-contract.h','graph-receipt.json','graph-before.bin'] or set(report['changed_source_files'])=={'graph-contract.h','graph-receipt.json','graph-before.bin'}
 report['output_pins']=[pin(dst/n) for n in report['changed_source_files']]
 (dst/'slot14-patch.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(destination=str(dst),changed_files=report['changed_source_files'],mapped_pages=175)))
if __name__=='__main__':main()
