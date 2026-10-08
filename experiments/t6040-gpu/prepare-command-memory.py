from pathlib import Path
import argparse,importlib.util,sys,json,hashlib,shutil,subprocess
kit=Path(__file__).resolve().parent;sys.path.insert(0,str(kit))
p=argparse.ArgumentParser(description='Stage64 prepared candidate commands for a host-only owned-page module')
p.add_argument('prepared_root',type=Path);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);p.add_argument('--device-base',type=lambda x:int(x,0),default=0x850000000)
p.add_argument('--firmware-base',type=lambda x:int(x,0),default=0xfffffc2000800000)
a=p.parse_args()
for value in (a.device_base,a.firmware_base):
 if value<0 or value+573440>1<<64 or value&16383:raise ValueError('Aligned, nonwrapping alias required')
spec=importlib.util.spec_from_file_location('paired',kit/'prepare-native-sksm-registers.py');paired=importlib.util.module_from_spec(spec);spec.loader.exec_module(paired)
root=a.prepared_root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);jobs=[];receipts=[]
for name in ('gpu-command-memory.c','Makefile'):shutil.copy2(kit/'command-memory'/name,out/name)
for i in range(64):
 source=root/('case-'+str(i));case=out/('case-'+str(i));case.mkdir()
 for f in source.iterdir():
  if f.is_file():shutil.copy2(f,case/f.name)
 binding=json.loads((case/'input.json').read_text());binding['3d_command_gpu']=hex(a.device_base+i*0x2240)
 binding['ordinary3d_pool']['device_base']=hex(a.device_base);binding['ordinary3d_pool']['firmware_base']=hex(a.firmware_base)
 manifest=case/'memory-input.json';manifest.write_text(json.dumps(binding,indent=2)+'\n')
 target=case/'memory-output';receipt=paired.prepare(a.macho,manifest,target)
 assert int(receipt['ordinary3d_pool']['device'],0)==a.device_base+i*0x2240
 assert int(receipt['ordinary3d_pool']['firmware'],0)==a.firmware_base+i*0x2240
 jobs.append((target/'3d-construction-candidate.bin').read_bytes());receipts.append(receipt)
header='#define JOB_COUNT 64U\n#define COMMAND_BYTES 0x2240U\n#define POOL_BYTES 573440U\n#define POOL_PAGES 35U\n#define DEVICE_BASE {hex(a.device_base)}ULL\n#define FW_BASE {hex(a.firmware_base)}ULL\nstatic const u8 job_bytes[JOB_COUNT][COMMAND_BYTES]={\n'
header=header.replace('{hex(a.device_base)}',hex(a.device_base)).replace('{hex(a.firmware_base)}',hex(a.firmware_base))
for data in jobs:
 header+=' {'+','.join('['+hex(j)+']='+hex(b) for j,b in enumerate(data) if b)+'},\n'
header+='};\n';(out/'job-data.h').write_text(header)
report=dict(jobs=64,allocation_bytes=573440,page_bytes=16384,pages=35,capacity=65,command_bytes=0x2240,
 device_base=hex(a.device_base),firmware_base=hex(a.firmware_base),source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=kit,text=True).strip(),header_sha256=hashlib.sha256(header.encode()).hexdigest(),
 command_sha256=[hashlib.sha256(x).hexdigest() for x in jobs],submission_ready=False,
 qualification='64 checked prepared descriptor candidates regenerated at consistent shared-slot aliases. High firmware address candidate by default; address reservation/installed mapping not proved. Explicit fixture context/shader/target contents; no GPU publication.')
(out/'preparation.json').write_text(json.dumps(report,indent=2)+'\n');print('Prepared64 shared-slot candidate commands')
