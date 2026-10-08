#!/usr/bin/env python3
"""Build one cold integrated firmware/context trial; never load modules.

The supplied backing must be the integrated paired-command candidate. Published
context and graph remain pinned until reboot. Work channels remain empty.
"""
from pathlib import Path
import argparse,shutil,json,hashlib,subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('sampler_workspace',type=Path);p.add_argument('integrated_backing',type=Path);p.add_argument('kernel_tree',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
kit=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prep=json.loads((a.integrated_backing/'preparation.json').read_text())
if prep['pages'] not in (47,48,52) or 'integrated_pair' not in prep or prep['submission_ready'] is not False:raise ValueError('Require a staged47/48/52-page native pair backing')
a.output.mkdir(exist_ok=False,parents=True)
for tag in ['adt-current','sample-pagetables','root-text-sample','root-data-sample','arena-l2-sample','asc-root-envelope','asc-arena-preflight']:
 shutil.copytree(a.sampler_workspace/tag,a.output/tag)
g=a.output/'asc-graph-init';shutil.copytree(a.integrated_backing,g)
for name in ['asc-graph-init.c','joined-context-init.h']:shutil.copy2(kit/'asc-graph-init'/name,g/name)
for name in ['graph-before.bin','graph-receipt.json']:shutil.copy2(a.sampler_workspace/'asc-graph-init'/name,g/name)
(g/'Makefile').write_text('obj-m += asc-graph-init.o\nccflags-y += -DGRAPH_JOINED_INIT_EXPERIMENT\n')
r=json.loads((a.output/'asc-root-envelope/build-receipt.json').read_text())
if (a.kernel_tree/'include/config/kernel.release').read_text().strip()!=r['kernel_release']:raise ValueError('Matching kernel tree required')
subprocess.run(['make','-C',str(a.kernel_tree.resolve()),'LLVM=1','KERNELRELEASE='+r['kernel_release'],'LOCALVERSION=','M='+str(g.resolve()),'W=1','modules'],check=True)
r.update(graph_release_on_shutdown=False,graph_power_retirement_probe=True,joined_context_init=True,joined_owned_pages=118+prep['pages'],joined_notify_first_page=106,joined_mapping_descriptors=35)
r['artifact_sha256']['asc-graph-init/asc-graph-init.ko']=sha(g/'asc-graph-init.ko')
r['graph_source_sha256']={p.name:sha(p) for p in g.glob('*.h')};r['graph_source_sha256']['asc-graph-init.c']=sha(g/'asc-graph-init.c')
(a.output/'asc-root-envelope/build-receipt.json').write_text(json.dumps(r,indent=2)+'\n')
print('Built integrated cold INIT candidate. No module loaded, work queued or rendering established.')
