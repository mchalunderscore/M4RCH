#!/usr/bin/env python3
"""Validate and assemble the AUDP001 second-stage and matching kernel kit."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tarfile

PROJECT=Path(__file__).resolve().parents[2]
OUTPUT=PROJECT/'out/aurora-dcp'
sys.path.insert(0,str(PROJECT/'sdboot'))
from loader import pack,validate_uboot_config

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    o=OUTPUT
    prefix=(o/'m1n1.bin').read_bytes(); control=(o/'control.dtb').read_bytes(); uboot=(o/'u-boot-nodtb.bin').read_bytes()
    pack(prefix,control,uboot)
    validate_uboot_config(o/'uboot.config',o/'serial.Makefile',internal=True)
    assert (o/'template.dtb').read_bytes() in uboot, 'Embedded Linux template differs'
    assert b'DCP001: live display reservations transferred' in uboot
    assert b'DCP001: native J614s firmware' in prefix
    assert b'apple,mriya\0' in control and b'apple,hostomel\0' not in control
    first=PROJECT/'out/aurora-bootstrap/stage1.bin'
    assert sha(first)=='c352def73ab145b1cb2d9f9a74785dc36641b480ff53b7f795403391f68fca0f'
    payload=prefix+control+gzip.compress(uboot,compresslevel=9,mtime=0)
    assert len(first.read_bytes()) >= ((len(payload)+32767)//16384)*16384, 'First-stage window too small'
    (o/'boot.bin').write_bytes(payload)
    release=(o/'kernel.release').read_text().strip()
    assert release=='7.3.0-m4rch-dcp003'
    image=(o/'Image').read_bytes(); assert image[56:60]==b'ARM\x64' and release.encode() in image
    config=(o/'kernel.config').read_text()
    for setting in ['CONFIG_DRM_APPLE=m','CONFIG_DRM_APPLE_DCP_J614S=y','CONFIG_APPLE_J614S_DCP_BOOT=y','CONFIG_APPLE_DART_J713_DCP=y','CONFIG_APPLE_PMP_REPORT=y']:
        assert setting+'\n' in config,setting
    with tarfile.open(o/'modules.tar.gz') as archive:
        names=archive.getnames()
        assert any(n.endswith('/appledrm.ko') for n in names)
        display=archive.extractfile(next(n for n in names if n.endswith('/appledrm.ko'))).read()
        assert b'j614s_modeset' in display and b'J614s experimental A413' in display
        assert any(n.endswith('/asahi.ko') for n in names)
        assert not any('snd-soc-tas2764.ko' in n or 'snd-soc-tas2770.ko' in n for n in names)
        assert all(n.startswith('lib/modules/'+release) for n in names if n!='lib/modules')
    profile=json.loads((o/'runtime-profile.json').read_text())
    upstream=json.loads((o/'upstream-manifest.json').read_text())
    assert [p['pr'] for p in upstream]==[429,427,433]
    profile.update({'sources':{'linux':'420a1c8f5492daeaa59ffba565aac610f5218d27',
       'linux_integrated_tree':'d6b171e95516b1683968d220800acee244c01869',
       'm1n1':'9f7cdfbd0623d96f21965434c3a7dda799ffcff4',
       'uboot':'7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c'},
       'upstream_prs':upstream,
       'stage1_changed':False,'stage1_sha256':sha(first),'stage2_window_remaining':first.stat().st_size-len(payload),
       'default_grub_id':'m4rch-aurora-dcp001','wallace_source_inputs':[],
       'abi_basis':'T604x image RPC identity, swap size and key offsets corroborated offline; strict live UUID/RPC checks; native takeover untested',
       'limitations':['experimental physical SDR modes up to 120 Hz; firmware acceptance and ProMotion timestamps unqualified','no qualified display suspend/resume','no HDR/VRR/external-display enablement']})
    (o/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    files=['Image','initramfs.img','boot.bin','control.dtb','template.dtb','profile.json','kernel.config','kernel.release',
           'modules.tar.gz','kernel-multimode.patch','modeset-abi-audit.json','kernel-dcp001.patch','m1n1-dcp001.patch','uboot-dcp001.patch','upstream-manifest.json']
    manifest={'test':'AUDP001','revision':3,'native_boot_tested':False,
      'files':{n:{'bytes':(o/n).stat().st_size,'sha256':sha(o/n)} for n in files},
      'kit_sources':{str(p.relative_to(PROJECT)):sha(p) for p in sorted((PROJECT/'experiments/aurora-dcp').rglob('*')) if p.is_file() and '__pycache__' not in p.parts}}
    (o/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'test':'AUDP001','kernel':release,'boot_bytes':len(payload),'stage2_window_remaining':profile['stage2_window_remaining'],'native_boot_tested':False}))

if __name__=='__main__': main()
