from pathlib import Path
import subprocess,sys,struct,hashlib,json,re
import argparse
p=argparse.ArgumentParser(description='Fresh-ADT-gated powered exact MMU register snapshot; no writes')
p.add_argument('reader_build',type=Path);p.add_argument('--power-module',type=Path,required=True);args=p.parse_args()
repo=Path(__file__).resolve().parents[2];out=args.reader_build.resolve();power=args.power_module.resolve();reader=out/'gpu-mmu-state-read.ko'
assert not (out/'intent.json').exists()
assert hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest()=='ab3d4a13f2cfe6403d9a75e9d03f55202f12c200894e24dd773a8c7ec6d8663a'
assert not any(x.split()[0].startswith('asc_') or x.split()[0] in ['gfx_power_test','asahi','asahi_m4','gpu_mmu_state_read','exact_register_read'] for x in Path('/proc/modules').read_text().splitlines())
def call(*args):subprocess.run(args,check=True)
call('insmod',str(repo/'out/gpu-gravity-contract/adt-current/m4rch_gpu_adt.ko'))
try:raw=Path('/sys/kernel/m4rch_gpu_adt/adt').read_bytes()
finally:call('rmmod','m4rch_gpu_adt')
(out/'boot.adt').write_bytes(raw);sys.path.insert(0,str(repo/'experiments/t6040-gpu'));import adt
tree=adt.parse(raw);assert list(struct.iter_unpack('<QQQ',tree['/device-tree/arm-io']['ranges']))[0]==(0,0x200000000,0x480000000)
assert list(struct.iter_unpack('<QQ',tree['/device-tree/arm-io/sgx']['reg']))==[(0x88000000,0x3758000),(0x88d00000,0x16c000)]
expected=[hex(0x288d08000+i) for i in range(0,0x34,4)]
before=subprocess.check_output(['dmesg']);(out/'dmesg-before.txt').write_bytes(before)
intent=dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel='7.1.13-m4rch-gpu-contract',adt_sha256=hashlib.sha256(raw).hexdigest(),expected=expected,writes=False,firmware_start=False,power='Existing GFX genpd runtime hold, restored on unload',module_sha256=hashlib.sha256(reader.read_bytes()).hexdigest())
(out/'intent.json').write_text(json.dumps(intent,indent=2)+'\n')
call('insmod',str(power))
try:
 call('insmod',str(reader),'run_gate=1')
 call('rmmod','gpu_mmu_state_read')
finally:call('rmmod','gfx_power_test')
after=subprocess.check_output(['dmesg']);(out/'dmesg-after.txt').write_bytes(after)
before_lines=before.decode().splitlines();after_lines=after.decode().splitlines()
anchor=before_lines[-32:];matches=[i for i in range(len(after_lines)-len(anchor)+1) if after_lines[i:i+len(anchor)]==anchor];assert len(matches)==1
delta='\n'.join(after_lines[matches[0]+len(anchor):])+'\n';(out/'trial-dmesg.txt').write_text(delta)
reads=re.findall(r'm4rch mmu-read: physical=(0x[0-9a-f]+) value=(0x[0-9a-f]+)',delta)
assert [addr for addr,v in reads]==expected and not any(Path('/sys/module/'+n).exists() for n in ['gfx_power_test','gpu_mmu_state_read','m4rch_gpu_adt'])
result=dict(intent,reads=dict(reads),control=dict(reads)['0x288d08000'],base_encoded=dict(reads)['0x288d0802c'],candidate_table_physical=hex(int(dict(reads)['0x288d0802c'],16)<<14),modules_absent=True,qualification='Powered read-only exact register snapshot. Native primary-base translation corroborated by fresh ADT, not independently reconstructed macOS service index ordering. No register writes, firmware start or context publication. Register values alone do not prove table ownership or valid translations.')
(out/'runtime.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
