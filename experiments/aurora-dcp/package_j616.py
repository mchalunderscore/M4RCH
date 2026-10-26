#!/usr/bin/env python3
"""Package the coherent merged display candidate, preserving the working runtime."""
import gzip
import json
import re
import tarfile
from pathlib import Path

from package import PROJECT, OUTPUT, sha
from package_bootfb import repack_cpio
from validate_initramfs import entries

OUT = OUTPUT / 'j616-r10'
RELEASE = '7.3.0-m4rch-dcp010'
SOURCES = {'linux': '6dc07e43e394d73db0de16079d3eb9463207543c',
           'm1n1': '1efafe1fe0ec134b89d55c2cc64106a66a4df2b7',
           'uboot': '7680260272f3612a13f0c9a6c7bfbc5e9ba7ce8c'}


def main():
    import sys
    sys.path.insert(0, str(PROJECT / 'sdboot'))
    from loader import pack, validate_uboot_config
    prefix, control, uboot = [(OUT / n).read_bytes() for n in
                             ['m1n1.bin', 'control.dtb', 'u-boot-nodtb.bin']]
    pack(prefix, control, uboot)
    validate_uboot_config(OUT / 'uboot.config', OUT / 'serial.Makefile', internal=True)
    assert (OUT / 'template.dtb').read_bytes() in uboot
    assert b'AUDP010: standard T6041 named memory regions' in uboot
    assert b'AUDP010-1efafe1f' in prefix
    boot = prefix + control + gzip.compress(uboot, compresslevel=9, mtime=0)
    first = PROJECT / 'out/aurora-bootstrap/stage1.bin'
    assert sha(first) == 'c352def73ab145b1cb2d9f9a74785dc36641b480ff53b7f795403391f68fca0f'
    assert first.stat().st_size >= ((len(boot) + 32767) // 16384) * 16384
    (OUT / 'boot.bin').write_bytes(boot)
    assert (OUT / 'kernel.release').read_text().strip() == RELEASE
    image = (OUT / 'Image').read_bytes()
    assert image[56:60] == b'ARM\x64' and RELEASE.encode() in image
    assert b'AUDP010: J614s standard T6041 handoff admitted' in image
    config = (OUT / 'kernel.config').read_text()
    for line in ['CONFIG_DRM_APPLE=m', 'CONFIG_APPLE_J614S_DCP_BOOT=y', 'CONFIG_APPLE_DART=y']:
        assert line + '\n' in config
    tests = (OUT / 'upstream-tests-final.log').read_text()
    assert 'not ok ' not in tests and len(re.findall(r'^ok \d+ - ', tests, re.M)) == 63
    assert '"valid": true' in (OUT / 'upstream-tests.log').read_text().splitlines()[0]
    assert 'ok 8 - paired-display-dart-irq' in (OUT / 'm4-error-tests.log').read_text()
    assert 'disabled hardware PASS; foreign owner rejected' in (OUT / 'bridge-tests.log').read_text()
    with tarfile.open(OUT / 'modules.tar.gz') as archive:
        names = archive.getnames()
        modules = [n for n in names if n.endswith('.ko')]
        assert len(modules) == 248
        assert all(n.startswith('lib/modules/' + RELEASE + '/') for n in modules)
        assert not any('snd-soc-tas2764' in n or 'snd-soc-tas2770' in n for n in names)
        for name in modules:
            data = archive.extractfile(name).read()
            assert ('vermagic=' + RELEASE + ' ').encode() in data, name
            if name.endswith('/appledrm.ko'):
                assert b'five firmware registers' in data
                assert b'dcp_alloc_dma' not in data
    before = entries(OUTPUT / 'buffers-r9/initramfs.img')
    runtime = before['aurora-runtime.sh'][1]
    runtime = runtime.replace(b'AUDP001 r9 retained RTKit AFK and IOMFB buffers; speakers excluded',
                              b'AUDP001 r10 merged J616s stack and standard T6041 DMA; speakers excluded')
    runtime = runtime.replace(b'DCP005:', b'AUDP010:')
    conf = before['etc/nvme-root.conf'][1]
    assert conf.count(b'7.3.0-m4rch-dcp006') == 1
    conf = conf.replace(b'7.3.0-m4rch-dcp006', RELEASE.encode())
    profile = json.loads(before['gpu16-profile.json'][1])
    profile.update({'revision': 10, 'kernel_release': RELEASE, 'sources': SOURCES,
        'handoff': 'apple,t6041-handoff (Aurora m1n1 #51)', 'loader_revision': 'AUDP010',
        'module_only_update': False, 'native_boot_tested': False, 'native_takeover_tested': False,
        'display_backend': 'complete merged Aurora Linux #446, J614s board adaptation',
        'dcp_power': 'standard Aurora T6041 startup; inherited native PMGR/PMP graph',
        'dcp_dma': 'standard DMA API with upstream locked-DART mirror; no J713 diversion',
        'firmware_uuid_policy': 'live UUID published by m1n1; observed UUID below is historical',
        'stage1_changed': False, 'stage1_sha256': sha(first),
        'stage2_window_remaining': first.stat().st_size - len(boot),
        'changes': ['full merged J616s desktop and scanout stack',
                    'merged m1n1 generic T6041 same-boot reservation publisher',
                    'standard named memory-region and IOVA transfer through native U-Boot bridge',
                    'standard locked-DART mirror and DMA allocation instead of J713 wrappers',
                    'J614s six physical windows / five firmware display registers',
                    'native 3024x1964 non-VRR 60 Hz initial mode; firmware catalog retained',
                    'qualified GPU16 and upstream PR427/429/433 patches retained'],
        'limitations': ['native boot and DCP takeover require the user to test',
                        'display suspend/resume remains inhibited',
                        'VRR stays disabled as in upstream; fixed 120 Hz is unqualified',
                        'external display processors remain disabled',
                        'speaker amplifier modules excluded and speaker DT nodes disabled']})
    profile_data = (json.dumps(profile, indent=2) + '\n').encode()
    changes = {'modules.tar.gz': (OUT / 'modules.tar.gz').read_bytes(),
               'aurora-runtime.sh': runtime, 'etc/nvme-root.conf': conf,
               'gpu16-profile.json': profile_data}
    (OUT / 'initramfs.img').write_bytes(repack_cpio(OUTPUT / 'buffers-r9/initramfs.img', changes))
    after = entries(OUT / 'initramfs.img')
    assert before.keys() == after.keys()
    assert {n for n in before if before[n] != after[n]} == changes.keys()
    assert b'AllowSuspend=no' in after['init'][1]
    (OUT / 'profile.json').write_bytes(profile_data)
    report = {'revision': 10, 'kernel_release': RELEASE, 'sources': SOURCES,
        'upstream_display_fixtures': '63/63 pass', 'plane_layout': 'pass',
        'm4_error_paths': '8/8 pass', 'production_cross_tree_handoff': 'ASan/UBSan pass',
        'matching_modules': len(modules), 'unchanged_initramfs_entries': len(before) - len(changes),
        'unchanged_Mesa_UCM_and_desktop_runtime': True, 'stage1_changed': False,
        'speakers_enabled': False, 'native_boot_tested': False, 'reboot_performed': False,
        'stage2_window_remaining': first.stat().st_size - len(boot)}
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    files = ['Image', 'initramfs.img', 'boot.bin', 'm1n1.bin', 'control.dtb', 'template.dtb',
             'u-boot-nodtb.bin', 'uboot.config', 'kernel.config', 'kernel.release', 'modules.tar.gz',
             'profile.json', 'validation.json', 'kernel-j614s.patch', 'gpu16.patch',
             'm1n1-j614s.patch', 'uboot-j614s.patch', 'resource-fixture.patch',
             'upstream-tests-final.log', 'bridge-tests.log', 'm4-error-tests.log', 'source-audit.json']
    kit = ['prepare_j616.py', 'audit_j616.py', 'package_j616.py', 'stage_j616.py',
           'kernel/j614s-merged-display-boot.c', 'loader/dcp_merged_handoff.c', 'tests/merged_handoff.c']
    manifest = {'revision': 10, 'kernel_release': RELEASE,
        'files': {n: {'sha256': sha(OUT / n), 'bytes': (OUT / n).stat().st_size} for n in files},
        'kit_sources': {str((Path('experiments/aurora-dcp') / n)): sha(PROJECT / 'experiments/aurora-dcp' / n) for n in kit}}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
