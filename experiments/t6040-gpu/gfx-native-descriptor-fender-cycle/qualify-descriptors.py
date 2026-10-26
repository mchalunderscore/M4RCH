#!/usr/bin/env python3
"""Check exact binary delta and compile the actual owner graph array, offline."""
import argparse,copy,json,runpy,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
P=runpy.run_path(str(HERE/'prepare-descriptor-owner.py'),run_name='descriptor_projection')
sha=P['sha'];pin=P['pin'];require=P['require']
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();source=a.source.resolve();output=a.output.resolve();require(not output.exists(),'Qualification output must be new')
 sr=source/P['RECEIPT'];receipt=json.loads(sr.read_bytes());base=Path(receipt['baseline_source_receipt']['path']);require(sha(base.read_bytes())==P['BASE_SHA'],'Frozen v20 source receipt differs')
 original={r['name']:(base.parent/r['name']).read_bytes() for r in receipt['input_source_pins']}
 for r in receipt['input_source_pins']:require(sha(original[r['name']])==r['sha256'],'Frozen input differs')
 for r in receipt['output_source_pins']:require(sha((source/r['name']).read_bytes())==r['sha256'],'Actual source differs')
 P['checked_inputs'](receipt['native_input_pins']);projected=P['project_source'](original)
 cases=[]
 def case(label,fn,accepted=True):
  try:ok=fn() is not False
  except (ValueError,KeyError,IndexError):ok=False
  require(ok==accepted,label);cases.append(dict(case=label,passed=True))
 case('all-actual-source-files-match-pure-projection',lambda:all((source/n).read_bytes()==b for n,b in projected.items()))
 j=receipt['descriptor_projection'];before=original['graph-before.bin'];after=(source/'graph-before.bin').read_bytes()
 delta=[dict(offset=hex(i),before=x,after=y) for i,(x,y) in enumerate(zip(before,after)) if x!=y]
 case('exact-nineteen-uploaded-arena-byte-delta',lambda:len(before)==len(after) and len(delta)==19 and [d['offset'] for d in delta]==j['changed_arena_offsets'])
 case('baseline-v20-equals-proposal-v19-whole-arena',lambda:before==Path(next(r['path'] for r in j['inputs'] if r['path'].endswith('/graph-before.bin'))).read_bytes())
 case('same-backing-shaders-work-and-mapping-headers',lambda:all(projected[n]==original[n] for n in ['backing.bin','render-data.h','render-backing-map.h','job-data.h','joined-context-init.h','graph-map.h','command-pool-map.h','boot-contract.h']))
 case('production-graph-upload-uses-compiled-array',lambda:b'memcpy(page_address(owned[2+i]),graph_bytes+i*PAGE_SIZE,PAGE_SIZE);' in original['graph-map.h'])
 for row in j['rows']:
  at=int(row['arena_record_offset'],16);case('whole-record-slot'+str(row['slot']),lambda at=at,row=row:after[at:at+40].hex()==row['after_record_hex'])
 for label,index in [('descriptor-before-guard',0x8cc8),('outside-descriptor-byte',0x4000)]:
  bad=bytearray(before);bad[index]^=1;case('reject-'+label,lambda bad=bad:P['project_arena'](bytes(bad),j),False)
 mutated=copy.deepcopy(j);mutated['rows'][0]['patch']['replacement_hex']='03000000';case('reject-unqualified-native-value',lambda:P['project_arena'](before,mutated),False)
 bad_outputs=dict(original);bad_outputs['graph-contract.h']=original['graph-contract.h'].replace(b'[0x0]=0xc0,',b'[0x0]=0xc1,',1);case('reject-compiled-array-input-mismatch',lambda:P['project_source'](bad_outputs),False)
 output.parent.mkdir(parents=True,exist_ok=True);work=output.with_name(output.stem+'.actual-C');work.mkdir(exist_ok=False)
 tester=work/'project.c';tester.write_text('#include <stdint.h>\n#include <stdbool.h>\n#include <stdio.h>\ntypedef uint8_t u8;typedef uint64_t u64;\n#include "'+str(source/'graph-contract.h')+'"\nint main(void){(void)owned_page_vas;(void)mmio_leaves;return fwrite(graph_bytes,1,sizeof(graph_bytes),stdout)==sizeof(graph_bytes)?0:1;}\n')
 binary=work/'project';commands=[]
 args=['cc','-std=c11','-Wall','-Wextra','-Werror',str(tester),'-o',str(binary)];run=subprocess.run(args,capture_output=True,text=True);commands.append(dict(command=args,returncode=run.returncode,stdout=run.stdout,stderr=run.stderr));require(run.returncode==0,'Actual C graph array did not compile')
 run=subprocess.run([str(binary)],capture_output=True);commands.append(dict(command=[str(binary)],returncode=run.returncode,stderr=run.stderr.decode()));compiled=work/'compiled-graph.bin';compiled.write_bytes(run.stdout)
 case('actual-C-compiled-whole-array-equals-uploaded-arena',lambda:run.returncode==0 and run.stdout==after)
 h0=P['array_parts'](original['graph-contract.h'])[0];h1=P['array_parts'](projected['graph-contract.h'])[0]
 case('compiled-header-outside-array-byte-identical',lambda:original['graph-contract.h'][:h0.start(3)]==projected['graph-contract.h'][:h1.start(3)] and original['graph-contract.h'][h0.end(3):]==projected['graph-contract.h'][h1.end(3):])
 meta=json.loads((source/'graph-receipt.json').read_bytes());oldmeta=json.loads(original['graph-receipt.json']);slot27=next(d for d in meta['mmio_descriptors'] if d['slot']==27)
 case('metadata-arena-hardware-hashes-match-actual-output',lambda:meta['arena_sha256']==sha(after) and next(o for o in meta['objects'] if o['name']=='hardware')['input_sha256']==j['proposed_hardware_input_sha256'])
 case('metadata-canonical-absent-and-unused-donor-PTE-retained',lambda:slot27['physical']==slot27['gpu_va']==slot27['size']=='0x0' and slot27['mapped_pages']==0 and slot27['serialized_native_flags']==2 and meta['mmio_leaves']==oldmeta['mmio_leaves'] and meta['native_descriptor_correction']['unused_donor_PTE_retained']['descriptor_references_leaf'] is False)
 case('all-other-objects-and-mapping-metadata-identical',lambda:[o for o in meta['objects'] if o['name']!='hardware']==[o for o in oldmeta['objects'] if o['name']!='hardware'] and all(meta[k]==oldmeta[k] for k in ['arena_bytes','owned_page_vas','mmio_leaves','mapped_pages','pointers','topology','afr_map_sha256','platform_map_sha256','static_map_sha256']))
 inputs=[Path(__file__),HERE/'prepare-descriptor-owner.py',sr,base,tester,compiled,*[source/r['name'] for r in receipt['output_source_pins']],*[Path(r['path']) for r in receipt['native_input_pins']]]
 result=dict(schema='m4rch.gfx-native-descriptor-fender-cycle-descriptor-qualification.v1',passed=True,hardware_access=False,hardware_actions=[],kernel_build=False,case_count=len(cases),cases=cases,source_receipt_sha256=sha(sr.read_bytes()),baseline_arena_sha256=sha(before),projected_arena_sha256=sha(after),changed_byte_count=19,changed_bytes=delta,actual_compiled_array=pin(compiled),commands=commands,inputs=[pin(p) for p in dict.fromkeys(inputs)],selection='unselected-awaiting-v20-hardware-outcome',qualification='Whole actual compiled C array equals corrected graph-before uploaded by unchanged graph-map memcpy; exact19 byte delta only. Guard negatives, five full records, same allother arena bytes/header metadata/backing/maps/shader/174 ownership. No GPU execution or teardown result proved.')
 with output.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
 print(json.dumps(dict(output=str(output),sha256=sha(output.read_bytes()),case_count=len(cases),changed_byte_count=19)))
if __name__=='__main__':main()
