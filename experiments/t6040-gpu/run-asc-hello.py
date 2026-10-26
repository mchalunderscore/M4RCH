#!/usr/bin/env python3
"""Run the staged current-boot ASC initial-message trial; reboot afterward."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace',type=Path);p.add_argument('--run',action='store_true');a=p.parse_args()
work=a.workspace.resolve();out=work/'asc-hello';receipt=json.loads((out/'stage-receipt.json').read_text());module=out/'asc-hello.ko'
def sha(b):return hashlib.sha256(b).hexdigest()
assert os.geteuid()==0,'Run through sudo for native device access'
assert os.uname().release==receipt['release']
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==receipt['boot_id'],'Staged contract belongs to another boot'
assert sha(Path('/sys/kernel/notes').read_bytes())==receipt['kernel_notes_sha256']
assert sha(module.read_bytes())==receipt['module_sha256']
for name in ['asahi_m4','resource_overlay','gfx_power_test','asc_status','gpu_data_sample','asc_hello']:
 assert not Path('/sys/module',name).exists(),'Conflicting module: '+name
assert not Path('/sys/firmware/devicetree/base/m4rch-mailbox-tests').exists()
assert receipt['default_gate_refused'] and receipt['compiled']
if not a.run:
 print('Preflight passes. No firmware start requested. Actual run requires --run and a reboot afterward.');raise SystemExit(0)
assert not (out/'attempt.json').exists(),'One attempt per cold boot; reboot and recapture before retrying'
(out/'attempt.json').write_text(json.dumps({'boot_id':receipt['boot_id'],'stage':'about to load; firmware may start','reboot_required':True},indent=2)+'\n')
with (out/'before-start-dmesg.txt').open('w') as f:subprocess.run(['dmesg','--color=never'],stdout=f,check=True)
os.sync()
with (out/'live-dmesg.txt').open('w') as f:
 follower=subprocess.Popen(['stdbuf','-oL','dmesg','--follow','--color=never'],stdout=f,stderr=subprocess.STDOUT)
 try:
  result=subprocess.run(['insmod',str(module),'run_gate=1'],capture_output=True,text=True)
 finally:
  follower.terminate();follower.wait(timeout=10)
with (out/'after-start-dmesg.txt').open('w') as f:subprocess.run(['dmesg','--color=never'],stdout=f,check=True)
started=Path('/sys/module/asc_hello').exists()
(out/'attempt.json').write_text(json.dumps({'boot_id':receipt['boot_id'],'load_returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'module_present':started,'reboot_required':started,'interpretation':'Presence means the start path ran and resources are pinned. Inspect dmesg for message/stop results. Never force module removal.'},indent=2)+'\n')
os.sync()
print('Trial returned. Reboot required; do not force module removal.' if started else 'Load refused before startup; inspect logs. Do not retry without review.')
