#!/usr/bin/env python3
"""Validate and assemble revision 4, reusing the unchanged r3 kernel/modules."""
import gzip,hashlib,json
from pathlib import Path
from package import PROJECT,OUTPUT,sha,pack,validate_uboot_config
from validate_initramfs import entries

def main():
    o=OUTPUT/'handoff-r4';base=json.loads((OUTPUT/'manifest.json').read_text())
    assert base['revision']==3
    for name in ['Image','kernel.config','modules.tar.gz','control.dtb','template.dtb']:
        assert sha(OUTPUT/name)==base['files'][name]['sha256'],name
    assert (OUTPUT/'kernel.release').read_text().strip()=='7.3.0-m4rch-dcp003'
    old=entries(OUTPUT/'initramfs.img');new=entries(o/'initramfs.img')
    changed={'aurora-runtime.sh','collect-display.sh','gpu16-profile.json'}
    assert old.keys()==new.keys()
    for name in old:
        if name not in changed:assert old[name]==new[name],name
    assert b'm4rch,dcp-summary' in new['aurora-runtime.sh'][1]
    assert b'modprobe_test appledrm j614s_modeset=1' in new['aurora-runtime.sh'][1]
    assert new['collect-display.sh'][1]==(PROJECT/'experiments/aurora-dcp/collect-display.sh').read_bytes()
    assert json.loads(new['gpu16-profile.json'][1])==json.loads((o/'runtime-profile.json').read_text())
    m1=(o/'m1n1.bin').read_bytes();ub=(o/'u-boot-nodtb.bin').read_bytes();dt=(OUTPUT/'control.dtb').read_bytes()
    assert b'DCP004' in m1 and b'm4rch,dcp-summary' in m1
    assert b'm4rch,dcp-bridge-summary' in ub and (OUTPUT/'template.dtb').read_bytes() in ub
    pack(m1,dt,ub);validate_uboot_config(OUTPUT/'uboot.config',OUTPUT/'serial.Makefile',internal=True)
    boot=m1+dt+gzip.compress(ub,compresslevel=9,mtime=0)
    first=PROJECT/'out/aurora-bootstrap/stage1.bin'
    assert sha(first)=='c352def73ab145b1cb2d9f9a74785dc36641b480ff53b7f795403391f68fca0f'
    assert len(first.read_bytes())>=((len(boot)+32767)//16384)*16384
    (o/'boot.bin').write_bytes(boot)
    profile=json.loads((OUTPUT/'profile.json').read_text());profile.update(json.loads((o/'runtime-profile.json').read_text()))
    profile.update({'kernel_reused_from_revision':3,'stage1_changed':False,'stage1_sha256':sha(first),
        'stage2_window_remaining':first.stat().st_size-len(boot),
        'native_takeover_tested':False,'loader_refusal_checks_preserved':True,
        'ttbr_fix_native_causality_verified':False})
    (o/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    files=['boot.bin','initramfs.img','m1n1.bin','u-boot-nodtb.bin','profile.json','runtime-profile.json','m1n1-handoff-trace.patch','uboot-handoff-trace.patch']
    manifest={'test':'AUDP001','revision':4,'kernel_release':'7.3.0-m4rch-dcp003','base_revision':3,
        'native_boot_tested':False,'reused_kernel':{'esp_path':'AUDP001/r3/vmlinuz','sha256':sha(OUTPUT/'Image')},
        'files':{n:{'bytes':(o/n).stat().st_size,'sha256':sha(o/n)} for n in files},
        'kit_sources':{str(p.relative_to(PROJECT)):sha(p) for p in sorted((PROJECT/'experiments/aurora-dcp').rglob('*')) if p.is_file() and '__pycache__' not in p.parts}}
    (o/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'revision':4,'kernel':'7.3.0-m4rch-dcp003','boot_bytes':len(boot),
        'stage2_window_remaining':profile['stage2_window_remaining'],'unchanged_initramfs_entries':len(old)-len(changed),
        'native_boot_tested':False}))
if __name__=='__main__':main()
