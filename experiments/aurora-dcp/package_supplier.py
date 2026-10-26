#!/usr/bin/env python3
"""Package r7's native PMP topology/readiness correction and matching modules."""
import io
import json
from pathlib import Path
import tarfile
from package import PROJECT, OUTPUT, sha
from package_bootfb import repack_cpio
from validate_initramfs import entries

RELEASE='7.3.0-m4rch-dcp006'


def main():
    out=OUTPUT/'supplier-r7';old=OUTPUT/'bootfb-r6';base=OUTPUT/'desktop-r5'
    for directory in [old,base]:
        manifest=json.loads((directory/'manifest.json').read_text())
        for name,item in manifest['files'].items():assert sha(directory/name)==item['sha256'],name
    log=(out/'supplier-tests.log').read_text()
    assert 'Supplier production tests PASS' in log and 'Supplier negative control PASS' in log
    assert (out/'kernel.release').read_text().strip()==RELEASE
    image=(out/'Image').read_bytes();assert image[56:60]==b'ARM\x64' and RELEASE.encode() in image
    before_config=(base/'kernel.config').read_text()
    assert (out/'kernel.config').read_text()==before_config.replace('-m4rch-dcp005','-m4rch-dcp006')
    for name in ['j614s-display-boot','pmp-report']:
        assert 'CC      drivers/'+('soc/apple/' if name.startswith('j614s') else 'pmdomain/apple/')+name+'.o' in (out/'build.log').read_text()
    with tarfile.open(out/'modules.tar.gz') as t:
        names=t.getnames();module_count=0
        for n in names:
            assert n=='lib/modules' or n.startswith('lib/modules/'+RELEASE),n
            assert 'snd-soc-tas2764.ko' not in n and 'snd-soc-tas2770.ko' not in n
            if n.endswith('.ko'):
                assert ('vermagic='+RELEASE+' ').encode() in t.extractfile(n).read(),n
                module_count+=1
        assert module_count==248,module_count
        for suffix in ['/appledrm.ko','/asahi.ko','/phy-apple-t6040-usb2.ko','/apple-pmp.ko']:
            assert any(n.endswith(suffix) for n in names),suffix
    before=entries(old/'initramfs.img')
    runtime=before['aurora-runtime.sh'][1]
    banner=b'AUDP001 r6 PR445 T6041 boot-framebuffer correction; speakers excluded';assert runtime.count(banner)==1
    runtime=runtime.replace(banner,b'AUDP001 r7 native PMP supplier/report readiness; speakers excluded')
    conf=before['etc/nvme-root.conf'][1];assert conf.count(b'7.3.0-m4rch-dcp005')==1
    conf=conf.replace(b'7.3.0-m4rch-dcp005',RELEASE.encode())
    profile=json.loads(before['gpu16-profile.json'][1]);profile.update({'revision':7,'kernel_release':RELEASE,
        'module_only_update':False,'native_boot_tested':False,'native_takeover_tested':False,
        'prior_native_result':'r6 framebuffer lookup succeeded; native PMP report link absent and readiness API lacks T6041'})
    profile['changes']+=['transactional native PMP supplier/report phandle completion before device population',
        'T6041 readiness uses native nonzero running status; zero-time checks are bounded']
    data=(json.dumps(profile,indent=2)+'\n').encode()
    changes={'modules.tar.gz':(out/'modules.tar.gz').read_bytes(),'aurora-runtime.sh':runtime,
        'etc/nvme-root.conf':conf,'gpu16-profile.json':data}
    (out/'initramfs.img').write_bytes(repack_cpio(old/'initramfs.img',changes))
    after=entries(out/'initramfs.img');assert before.keys()==after.keys()
    assert {n for n in before if before[n]!=after[n]}==changes.keys()
    (out/'profile.json').write_bytes(data)
    report={'revision':7,'kernel_release':RELEASE,'loader_revision':'DCP005','loader_sha256':sha(base/'boot.bin'),
        'loader':'unchanged from r5/r6','kernel_and_modules_build':'pass','matching_modules':module_count,
        'native_dt_topology_and_readiness_sanitizer_tests':'pass','original_readiness_negative_control':'fails as expected',
        'unchanged_initramfs_entries':len(before)-4,'speakers_enabled':False,'native_boot_tested':False,'reboot_performed':False}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    files=['Image','initramfs.img','modules.tar.gz','kernel.config','kernel.release','profile.json','validation.json',
        'kernel-supplier.patch','j614s-display-boot.c','j614s-display-boot.c.before','pmp-report.c','pmp-report.c.before',
        'supplier-tests.log','build.log','modules-install.log']
    manifest={'revision':7,'kernel_release':RELEASE,
        'files':{n:{'bytes':(out/n).stat().st_size,'sha256':sha(out/n)} for n in files},
        'kit_sources':{n:sha(PROJECT/n) for n in ['experiments/aurora-dcp/kernel/j614s-display-boot.c',
            'experiments/aurora-dcp/prepare_supplier.py','experiments/aurora-dcp/package_supplier.py',
            'experiments/aurora-dcp/refresh_supplier.py','experiments/aurora-dcp/tests/supplier.py']}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
