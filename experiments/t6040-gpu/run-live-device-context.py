from pathlib import Path
import subprocess,hashlib,json
import argparse
p=argparse.ArgumentParser(description='One powered native context insert/remove trial with retain-on-failure')
p.add_argument('build',type=Path);p.add_argument('--power-module',type=Path,required=True);p.add_argument('--expected-boot',required=True);a=p.parse_args()
w=a.build.resolve();power=a.power_module.resolve();module=w/'asc-graph-init.ko'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==a.expected_boot
assert hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest()=='ab3d4a13f2cfe6403d9a75e9d03f55202f12c200894e24dd773a8c7ec6d8663a'
assert not (w/'intent.json').exists()
assert not any(x.split()[0].startswith('asc_') or x.split()[0] in ['gfx_power_test','asahi','asahi_m4'] for x in Path('/proc/modules').read_text().splitlines())
intent=dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel='7.1.13-m4rch-gpu-contract',module_sha256=hashlib.sha256(module.read_bytes()).hexdigest(),context=1,table_physical='0x105fffb8000',register_write='0x288d08030: context<<8 on removal',firmware_start=False,base_configuration_writes=False)
(w/'intent.json').write_text(json.dumps(intent,indent=2)+'\n');(w/'dmesg-before.txt').write_bytes(subprocess.check_output(['dmesg']))
subprocess.run(['insmod',str(power)],check=True)
try:
 run=subprocess.run(['insmod',str(module),'run_gate=1'],capture_output=True,text=True)
 (w/'insmod-result.json').write_text(json.dumps(dict(returncode=run.returncode,stdout=run.stdout,stderr=run.stderr),indent=2)+'\n')
 pinned=Path('/sys/module/asc_graph_init/refcnt').exists() and int(Path('/sys/module/asc_graph_init/refcnt').read_text())>0
 if pinned:print('Restoration unverified: module and GFX power helper retained')
 elif Path('/sys/module/asc_graph_init').exists():subprocess.run(['rmmod','asc_graph_init'],check=True)
finally:
 if not Path('/sys/module/asc_graph_init').exists():subprocess.run(['rmmod','gfx_power_test'],check=True)
 (w/'dmesg-after.txt').write_bytes(subprocess.check_output(['dmesg']))
print('insmod returned',run.returncode,'module_present',Path('/sys/module/asc_graph_init').exists())
