#!/usr/bin/env python3
"""Check a captured RGBA8 target against prepared interior/background references.

Readback alone never proves firmware completion, DMA visibility or execution.
Coordinates assume the candidate's y-up linear target until hardware confirms it.
"""
import argparse,hashlib,json
from pathlib import Path

def check(receipt,data):
 target=receipt['target'];expected_size=target['bytes'];fail=[];samples=[]
 if len(data)!=expected_size:
  return {'passed':False,'failures':[f'Expected exactly {expected_size} bytes, got {len(data)}'],'samples':[]}
 if data==bytes([target['sentinel']])*expected_size:
  return {'passed':False,'failures':['Target remained entirely at the pre-submission sentinel'],'samples':[]}
 width,height,stride=target['width'],target['height'],target['stride_bytes']
 refs=[]
 for r in receipt['interior_reference_samples']:
  x,y=r['pixel_y_up'];refs.append((x,y,r['rgba8_nearest'],r['tolerance_per_channel'],'interior'))
 # The constant background candidate writes these four outside corners if its
 # dispatch is accepted. Do not infer background dispatch from interior-only success.
 rgba=[round(max(0,min(1,f))*255) for f in receipt['background_candidate']['float_rgba']]
 for x,y in [(0,0),(width-1,0),(0,height-1),(width-1,height-1)]:refs.append((x,y,rgba,2,'background'))
 for x,y,expected,tolerance,kind in refs:
  offset=y*stride+x*4
  if not (0<=x<width and 0<=y<height and offset+4<=len(data)):raise ValueError('Reference outside target')
  actual=list(data[offset:offset+4]);passed=all(abs(x-y)<=tolerance for x,y in zip(actual,expected))
  samples.append({'pixel_y_up':[x,y],'kind':kind,'expected':expected,'actual':actual,'passed':passed})
  if not passed:fail.append(f'{kind} pixel ({x},{y}) differs')
 return {'passed':not fail,'failures':fail,'samples':samples,'target_sha256':hashlib.sha256(data).hexdigest(),'qualification':'Eight selected RGBA8 sample pixels under candidate y-up layout. Does not check all pixels or prove firmware completion/cache synchronization. Require separately captured queue/event/stamp and invalidation evidence.'}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('receipt',type=Path);p.add_argument('readback',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 receipt=json.loads(a.receipt.read_text());result=check(receipt,a.readback.read_bytes());result['receipt_sha256']=hashlib.sha256(a.receipt.read_bytes()).hexdigest();a.output.write_text(json.dumps(result,indent=2)+'\n');print('Sample readback PASS' if result['passed'] else 'Sample readback FAIL');return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
