import subprocess,json,hashlib,re,argparse
from pathlib import Path
parser=argparse.ArgumentParser(description='Allocation-only render/storage graph trial; no GPU publication.');parser.add_argument('build',type=Path);parser.add_argument('--expected-boot',required=True);args=parser.parse_args();b=args.build.resolve()
assert subprocess.check_output(['uname','-r'],text=True).strip()=='7.1.13-m4rch-gpu-contract'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==args.expected_boot
assert not Path('/sys/module/asc_graph_init').exists()
for flag in ['GRAPH_CONTEXT_LIVE_EXPERIMENT']:
 assert flag not in (b/'graph-contract.h').read_text()
assert (b/'graph-contract.h').read_text().startswith('#define GRAPH_RENDER_BACKING_EXPERIMENT 1\n#define GRAPH_COMMAND_POOL_EXPERIMENT')
prep=json.loads((b/'preparation.json').read_text());n=prep['pages'];assert n==40 and prep['submission_ready'] is False
before=subprocess.check_output(['sudo','-n','dmesg'],text=True);(b/'dmesg-before.txt').write_text(before)
loaded=False
try:
 p=subprocess.run(['sudo','-n','insmod',str(b/'asc-graph-init.ko'),'run_gate=1'],capture_output=True,text=True)
 (b/'insmod-result.json').write_text(json.dumps({'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr},indent=2)+'\n');assert p.returncode==0,p.stderr;loaded=True
finally:
 if loaded:subprocess.run(['sudo','-n','rmmod','asc_graph_init'],check=True)
after=subprocess.check_output(['sudo','-n','dmesg'],text=True);(b/'full-dmesg.txt').write_text(after)
bl=before.splitlines();al=after.splitlines();overlap=0
for overlap_count in range(min(len(bl),len(al)),0,-1):
 if bl[-overlap_count:]==al[:overlap_count]:overlap=overlap_count;break
assert overlap>0
trial='\n'.join(al[overlap:])+'\n';(b/'trial-dmesg.txt').write_text(trial)
assert not Path('/sys/module/asc_graph_init').exists()
assert f'PASS data_pages={n} table_pages=6 regions=3 byte_comparisons={n*16384}' in trial
pages=re.findall(r'render-backing: page=(\d+) va=(0x[0-9a-f]+) physical=(0x[0-9a-f]+) bytes=16384 root_index=(\d+) publication=0',trial)
assert len(pages)==n and len({x[2] for x in pages})==n
owned=re.findall(r'owned page (\d+) physical=(0x[0-9a-f]+)',trial)
assert len(owned)==118+n and len({x[1] for x in owned})==118+n and sorted(int(x[0]) for x in owned)==list(range(118+n))
prep=json.loads((b/'preparation.json').read_text());assert prep['pages']==n and prep['submission_ready'] is False
assert [int(x[1],0) for x in pages]==[int(v,0) for v in prep['candidate_vas']]
report={'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'kernel':'7.1.13-m4rch-gpu-contract','owned_pages':118+n,'owned_physical_pages_unique':True,'render_pages':[{'index':int(i),'va':va,'physical':pa,'root_index':int(root)} for i,va,pa,root in pages],'preparation':prep,'publication':False,'module_absent':True,'qualification':'Linux-owned backing and CPU shadow-table walks for authored render data plus native-derived ring/GTP sizing fixtures. PM page-list prefix regenerated for candidate mapping; remaining allocation contents placeholders; native required contents, event/PM initialization and true topology unresolved. No GPU lookup, shader execution, job, completion or pixels.','build_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in b.iterdir() if p.name in ['asc-graph-init.c','Makefile','graph-contract.h','boot-contract.h','graph-map.h','command-pool-map.h','render-backing-map.h','render-data.h','job-data.h','asc-graph-init.ko']}}
(b/'runtime.json').write_text(json.dumps(report,indent=2)+'\n');print(trial[-7000:])
