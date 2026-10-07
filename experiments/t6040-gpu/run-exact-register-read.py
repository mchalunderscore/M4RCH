#!/usr/bin/env python3
"""Fresh-ADT-gated targeted reads from GPUC002 static map; no firmware wake."""
from pathlib import Path
import subprocess,sys,struct,hashlib,json,argparse
p=argparse.ArgumentParser();p.add_argument('workspace',type=Path);a=p.parse_args();w=a.workspace.resolve()
out=w/'exact-register-read'/('boot-'+Path('/proc/sys/kernel/random/boot_id').read_text().strip());out.mkdir(exist_ok=True)
assert not (out/'intent.json').exists(),'Do not overwrite a prior trial'
assert hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest()=='ab3d4a13f2cfe6403d9a75e9d03f55202f12c200894e24dd773a8c7ec6d8663a'
assert not any(l.split()[0].startswith('asc_') or l.split()[0] in ['gfx_power_test','asahi_m4','exact_register_read'] for l in Path('/proc/modules').read_text().splitlines())
subprocess.run(['insmod',str(w/'adt-current/m4rch_gpu_adt.ko')],check=True)
try:raw=Path('/sys/kernel/m4rch_gpu_adt/adt').read_bytes()
finally:subprocess.run(['rmmod','m4rch_gpu_adt'],check=True)
(out/'boot.adt').write_bytes(raw)
sys.path.insert(0,str(Path(__file__).resolve().parent));import adt
tree=adt.parse(raw);assert list(struct.iter_unpack('<QQQ',tree['/device-tree/arm-io']['ranges']))[0]==(0,0x200000000,0x480000000)
assert list(struct.iter_unpack('<QQ',tree['/device-tree/arm-io/sgx']['reg']))==[(0x88000000,0x3758000),(0x88d00000,0x16c000)]
(out/'dmesg-before.log').write_bytes(subprocess.check_output(['dmesg']))
(out/'intent.json').write_text(json.dumps({'boot_id':out.name,'addresses':['0x288d440a0','0x288d440a4','0x288d440a8','0x288e01704','0x288e01780','0x288e1f860'],'module_sha256':hashlib.sha256((w/'exact-register-read/exact-register-read.ko').read_bytes()).hexdigest(),'power':'existing GFX genpd','writes':False},indent=2)+'\n')
subprocess.run(['insmod',str(w/'gfx-power-test/gfx-power-test.ko')],check=True)
try:
 subprocess.run(['insmod',str(w/'exact-register-read/exact-register-read.ko'),'run_gate=1'],check=True)
 subprocess.run(['rmmod','exact_register_read'],check=True)
finally:subprocess.run(['rmmod','gfx_power_test'],check=True)
(out/'dmesg-after.log').write_bytes(subprocess.check_output(['dmesg']))
print('\n'.join(l for l in (out/'dmesg-after.log').read_text().splitlines() if 'm4rch exact-read:' in l))
