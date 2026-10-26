#!/usr/bin/env python3
"""Package the r8 display-module correction on the exact tested r7 kernel."""
import gzip
import io
import json
import tarfile
from package import PROJECT,OUTPUT,sha
from package_bootfb import repack_cpio
from validate_initramfs import entries


def main():
    out=OUTPUT/'shared-r8';old=OUTPUT/'supplier-r7'
    manifest=json.loads((old/'manifest.json').read_text())
    for n,item in manifest['files'].items():assert sha(old/n)==item['sha256'],n
    log=(out/'shared-tests.log').read_text();assert 'Shared-window production tests PASS' in log and 'Shared-window negative control PASS' in log
    rates=(out/'upstream-rate-tests.log').read_text()
    for line in ['ok 1 - parser-policy','ok 2 - publication-hpd','ok 3 - metadata-decoder','ok 4 - bounded-retry']:
        assert line in rates,line
    module=(out/'appledrm.ko').read_bytes()
    assert b'vermagic=7.3.0-m4rch-dcp006 ' in module
    assert b'five firmware registers' in module
    old_files={};buffer=io.BytesIO()
    with tarfile.open(old/'modules.tar.gz') as src,tarfile.open(fileobj=buffer,mode='w') as dst:
        for member in src:
            data=src.extractfile(member).read() if member.isfile() else None
            if member.isfile():old_files[member.name]=data
            if member.name.endswith('/appledrm.ko'):data=module;member.size=len(module)
            dst.addfile(member,io.BytesIO(data) if data is not None else None)
    modules=gzip.compress(buffer.getvalue(),compresslevel=9,mtime=0)
    (out/'modules.tar.gz').write_bytes(modules)
    with tarfile.open(fileobj=io.BytesIO(modules)) as src:
        new_files={m.name:src.extractfile(m).read() for m in src if m.isfile()}
    assert new_files.keys()==old_files.keys()
    changed=[n for n in old_files if old_files[n]!=new_files[n]]
    assert len(changed)==1 and changed[0].endswith('/appledrm.ko')
    assert not any('snd-soc-tas2764.ko' in n or 'snd-soc-tas2770.ko' in n for n in new_files)
    before=entries(old/'initramfs.img');runtime=before['aurora-runtime.sh'][1]
    banner=b'AUDP001 r7 native PMP supplier/report readiness; speakers excluded';assert runtime.count(banner)==1
    runtime=runtime.replace(banner,b'AUDP001 r8 shared DISP0 aperture and live-session adoption; speakers excluded')
    profile=json.loads(before['gpu16-profile.json'][1])
    profile.update({'revision':8,'module_only_update':True,'native_boot_tested':False,'native_takeover_tested':False,
        'prior_native_result':'r7 power ownership admitted; register builder counted shared DISP0/PMGR aperture twice'})
    profile['changes']+=['exact shared DISP0/PMGR alias at firmware register4, five firmware registers',
        'native desktop live-session adoption and DMA retention before RTKit mailbox startup']
    data=(json.dumps(profile,indent=2)+'\n').encode()
    changes={'modules.tar.gz':modules,'aurora-runtime.sh':runtime,'gpu16-profile.json':data}
    (out/'initramfs.img').write_bytes(repack_cpio(old/'initramfs.img',changes))
    after=entries(out/'initramfs.img');assert after.keys()==before.keys()
    assert {n for n in before if before[n]!=after[n]}==changes.keys()
    (out/'profile.json').write_bytes(data)
    report={'revision':8,'kernel_release':'7.3.0-m4rch-dcp006','loader_revision':'DCP005',
        'kernel_sha256':sha(old/'Image'),'loader_sha256':sha(OUTPUT/'desktop-r5/boot.bin'),
        'kernel_and_loader':'byte-identical to r7','changed_modules':changed,'unchanged_initramfs_entries':len(before)-3,
        'full_register_builder_and_firmware_replies':'production C sanitizer tests pass against actual native DT data',
        'live_session_adoption_and_retention':'production C sanitizer tests pass',
        'original_register_builder_negative_control':'fails as expected','speakers_enabled':False,
        'upstream_rate_tests':'4/4 pass; #446 host fixture update only',
        'native_boot_tested':False,'reboot_performed':False}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    old_receipt=json.loads((old/'stage-receipt.json').read_text())
    retire=['AUDP001/r3/vmlinuz','AUDP001/r4/initramfs.img']
    files=['initramfs.img','modules.tar.gz','appledrm.ko','profile.json','validation.json','kernel-shared.patch',
        'dcp.c','dcp.before.c','resource-audit.json','shared-tests.log','build.log','upstream-rate-tests.log','audit.json']
    manifest={'revision':8,'previous_revision':7,'kernel_release':'7.3.0-m4rch-dcp006',
        'kernel_path':'AUDP001/r7/vmlinuz','kernel_sha256':report['kernel_sha256'],'loader_sha256':report['loader_sha256'],
        'previous_receipt_sha256':sha(old/'stage-receipt.json'),
        'retire_entry':'m4rch-aurora-dcp004-previous',
        'retire':{n:old_receipt['protected_payloads']['/'+n] for n in retire},
        'payloads':['initramfs.img','profile.json','validation.json','kernel-shared.patch','manifest.json'],
        'files':{n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in files},
        'kit_sources':{n:sha(PROJECT/n) for n in ['experiments/aurora-dcp/prepare_shared.py','experiments/aurora-dcp/package_shared.py',
            'experiments/aurora-dcp/stage_revision.py','experiments/aurora-dcp/tests/shared.py']}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
