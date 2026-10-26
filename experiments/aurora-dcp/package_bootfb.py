#!/usr/bin/env python3
"""Package the r6 module-only correction, keeping the exact r5 kernel/loader."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
from package import PROJECT, OUTPUT, sha
from validate_initramfs import entries


def repack_cpio(source, changes):
    data = gzip.decompress(source.read_bytes()); offset = 0; result = bytearray(); used = set()
    while True:
        assert data[offset:offset+6] == b'070701'
        fields = [int(data[offset+6+i*8:offset+14+i*8],16) for i in range(13)]
        name = data[offset+110:offset+110+fields[11]]
        key = name[:-1].decode().removeprefix('./')
        start = (offset+110+fields[11]+3)&~3
        body = data[start:start+fields[6]]
        offset = (start+fields[6]+3)&~3
        if key in changes:
            body = changes[key]; fields[6] = len(body); used.add(key)
        result.extend(b'070701'+''.join(f'{n:08x}' for n in fields).encode()+name)
        result.extend(b'\0'*(-len(result)%4)); result.extend(body)
        result.extend(b'\0'*(-len(result)%4))
        if key == 'TRAILER!!!': break
    assert used == changes.keys()
    result.extend(b'\0'*(-len(result)%512))
    return gzip.compress(result,compresslevel=9,mtime=0)


def main():
    old = OUTPUT / 'desktop-r5'; out = OUTPUT / 'bootfb-r6'
    old_manifest = json.loads((old / 'manifest.json').read_text())
    for name, item in old_manifest['files'].items(): assert sha(old/name) == item['sha256'], name
    assert 'Boot framebuffer negative control PASS' in (out/'bootfb-tests.log').read_text()
    assert 'LD [M]  drivers/gpu/drm/apple/appledrm.ko' in (out/'build.log').read_text()
    module = (out/'appledrm.ko').read_bytes()
    assert b'vermagic=7.3.0-m4rch-dcp005 ' in module
    assert b'J614s DISP0 shared aperture differs' in module
    buf=io.BytesIO(); old_modules={}
    with tarfile.open(old/'modules.tar.gz') as src, tarfile.open(fileobj=buf,mode='w') as dst:
        for item in src:
            body=src.extractfile(item).read() if item.isfile() else None
            if item.isfile(): old_modules[item.name]=body
            if item.name.endswith('/appledrm.ko'): body=module; item.size=len(module)
            dst.addfile(item,io.BytesIO(body) if body is not None else None)
    modules=gzip.compress(buf.getvalue(),compresslevel=9,mtime=0)
    (out/'modules.tar.gz').write_bytes(modules)
    with tarfile.open(fileobj=io.BytesIO(modules)) as src:
        current={m.name:src.extractfile(m).read() for m in src if m.isfile()}
    assert current.keys()==old_modules.keys()
    changed_modules=[n for n in current if current[n]!=old_modules[n]]
    assert len(changed_modules)==1 and changed_modules[0].endswith('/appledrm.ko')
    assert not any('snd-soc-tas2764.ko' in n or 'snd-soc-tas2770.ko' in n for n in current)
    before=entries(old/'initramfs.img')
    runtime=before['aurora-runtime.sh'][1]
    old_banner=b'AUDP001 r5 PR445 T6041 desktop DCP backend; speakers excluded'
    assert runtime.count(old_banner)==1
    runtime=runtime.replace(old_banner,b'AUDP001 r6 PR445 T6041 boot-framebuffer correction; speakers excluded')
    profile=json.loads(before['gpu16-profile.json'][1])
    profile.update({'revision':6,'native_boot_tested':False,'native_takeover_tested':False,
        'prior_native_result':'r5 handoff and DART admission succeeded; DRM bind refused missing legacy framebuffer memory-region',
        'module_only_update':True})
    profile['changes'].append('T6041 selects the existing simple-framebuffer aperture when no framebuffer memory-region is supplied')
    profile_bytes=(json.dumps(profile,indent=2)+'\n').encode()
    changes={'modules.tar.gz':modules,'aurora-runtime.sh':runtime,'gpu16-profile.json':profile_bytes}
    (out/'initramfs.img').write_bytes(repack_cpio(old/'initramfs.img',changes))
    after=entries(out/'initramfs.img')
    assert before.keys()==after.keys()
    assert {n for n in before if before[n]!=after[n]}==changes.keys()
    (out/'profile.json').write_bytes(profile_bytes)
    report={'revision':6,'kernel_release':profile['kernel_release'],'loader_revision':'DCP005',
        'kernel_sha256':sha(old/'Image'),'boot_sha256':sha(old/'boot.bin'),
        'changed_modules':changed_modules,'unchanged_initramfs_entries':len(before)-3,
        'actual_live_dt_sanitizer_tests':'pass','original_selector_negative_control':'fails as expected',
        'kernel_and_loader':'byte-identical to r5','speakers_enabled':False,
        'native_boot_tested':False,'native_takeover_tested':False,'reboot_performed':False}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    files=['initramfs.img','modules.tar.gz','appledrm.ko','profile.json','validation.json',
        'kernel-bootfb.patch','apple_drv.before.c','apple_drv.c','bootfb-tests.log','build.log']
    manifest={'revision':6,'files':{n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in files},
        'kit_sources':{n:sha(PROJECT/n) for n in ['experiments/aurora-dcp/prepare_bootfb.py',
            'experiments/aurora-dcp/package_bootfb.py','experiments/aurora-dcp/refresh_bootfb.py',
            'experiments/aurora-dcp/tests/bootfb.py']}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
