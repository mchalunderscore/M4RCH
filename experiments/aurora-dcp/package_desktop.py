#!/usr/bin/env python3
"""Validate and assemble the revision-5 desktop-backend boot candidate."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
from package import PROJECT, OUTPUT, pack, sha, validate_uboot_config
from prepare_desktop_runtime import RELEASE
from validate_initramfs import entries


def main():
    out = OUTPUT / 'desktop-r5'
    old = entries(OUTPUT / 'handoff-r4/initramfs.img')
    new = entries(out / 'initramfs.img')
    allowed = {'modules.tar.gz', 'etc/nvme-root.conf', 'aurora-runtime.sh', 'gpu16-profile.json', 'collect-display.sh'}
    assert old.keys() == new.keys()
    changed = {n for n in old if old[n] != new[n]}
    assert changed == allowed, changed
    assert new['init'][0] & 0o111
    assert ("KERNEL_RELEASE='" + RELEASE + "'").encode() in new['etc/nvme-root.conf'][1]
    assert b'modprobe_test appledrm show_notch=1 t6041_dcpext=0' in new['aurora-runtime.sh'][1]
    assert b'j614s_modeset' not in new['aurora-runtime.sh'][1]
    assert b'AllowSuspend=no' in new['init'][1]
    assert new['modules.tar.gz'][1] == (out / 'modules.tar.gz').read_bytes()
    assert new['collect-display.sh'][1] == (PROJECT / 'experiments/aurora-dcp/collect-display.sh').read_bytes()
    runtime = json.loads(new['gpu16-profile.json'][1])
    assert runtime == json.loads((out / 'runtime-profile.json').read_text())
    assert runtime['loader_revision'] == 'DCP005' and not runtime['speakers_enabled']
    config = (out / 'kernel.config').read_text()
    for line in ['CONFIG_DRM_APPLE=m', 'CONFIG_DRM_APPLE_DCP_J614S=y', 'CONFIG_VMAP_PFN=y',
                 'CONFIG_APPLE_J614S_DCP_BOOT=y', 'CONFIG_APPLE_DART_J713_DCP=y', 'CONFIG_RUST=y',
                 'CONFIG_DRM_ASAHI=m']:
        assert line + '\n' in config, line
    image = (out / 'Image').read_bytes()
    assert image[56:60] == b'ARM\x64' and RELEASE.encode() in image
    module_count = 0
    with tarfile.open(fileobj=io.BytesIO(new['modules.tar.gz'][1])) as t:
        names = t.getnames()
        for n in names:
            assert n == 'lib/modules' or n.startswith('lib/modules/' + RELEASE), n
            assert 'snd-soc-tas2764.ko' not in n and 'snd-soc-tas2770.ko' not in n
            if n.endswith('.ko'):
                data = t.extractfile(n).read()
                assert ('vermagic=' + RELEASE + ' ').encode() in data, n
                module_count += 1
        drm = t.extractfile(next(n for n in names if n.endswith('/appledrm.ko'))).read()
        assert b'J614s DISP0 shared aperture differs' in drm
        assert b'T6041 display not started' in drm and b'short desktop IOMFB callback' in drm
        assert b'j614s_modeset' not in drm
        assert any(n.endswith('/asahi.ko') for n in names)
        assert any(n.endswith('/phy-apple-t6040-usb2.ko') for n in names)
    m1n1 = (out / 'm1n1.bin').read_bytes()
    control = (OUTPUT / 'control.dtb').read_bytes()
    uboot = (OUTPUT / 'handoff-r4/u-boot-nodtb.bin').read_bytes()
    assert b'DCP005' in m1n1 and b'm4rch,dcp-summary' in m1n1
    assert (OUTPUT / 'template.dtb').read_bytes() in uboot
    pack(m1n1, control, uboot)
    validate_uboot_config(OUTPUT / 'uboot.config', OUTPUT / 'serial.Makefile', internal=True)
    boot = m1n1 + control + gzip.compress(uboot, compresslevel=9, mtime=0)
    first = PROJECT / 'out/aurora-bootstrap/stage1.bin'
    assert sha(first) == 'c352def73ab145b1cb2d9f9a74785dc36641b480ff53b7f795403391f68fca0f'
    assert first.stat().st_size >= ((len(boot) + 32767) // 16384) * 16384
    (out / 'boot.bin').write_bytes(boot)
    source = json.loads((out / 'desktop-source-manifest.json').read_text())
    report = {'test': 'AUDP001', 'revision': 5, 'kernel_release': RELEASE,
        'native_boot_tested': False, 'source_replay': 'pass', 'kernel_and_modules_build': 'pass',
        'desktop_production_sanitizer_tests': 'pass', 'loader_guard_tests': 'pass',
        'flat_root_actual_dt_sanitizer_tests': 'pass', 'original_decoder_negative_control': 'fails as expected',
        'upstream_boot_host_tests': '2/2 pass',
        'upstream_rate_host_tests': {'passed': ['parser-policy', 'metadata-decoder', 'bounded-retry'],
            'not_run': {'publication-hpd': 'upstream host extractor/mocks do not support PR445 lookup-mode and VRR additions; generated fixture does not compile'}},
        'unchanged_initramfs_entries': len(old) - len(allowed), 'matching_modules': module_count,
        'mesa_sha256': hashlib.sha256(new['mesa.tar.gz'][1]).hexdigest(),
        'ucm_sha256': hashlib.sha256(new['ucm.tar.gz'][1]).hexdigest(),
        'stage2_bytes': len(boot), 'stage2_window_remaining': first.stat().st_size - len(boot),
        'speakers_enabled': False, 'reboot_performed': False}
    # Require successful log evidence rather than recording attempted checks.
    for name, marker in [('desktop-tests.log', 'Desktop production tests PASS'),
                         ('loader-tests.log', 'TTBR negative control PASS'),
                         ('flat-root-tests.log', 'Native-failure negative control PASS')]:
        assert marker in (out / name).read_text(), name
    for needle in ['ok 1 - oslog-events', 'ok 2 - syslog-policy']:
        assert needle in (out / 'upstream-boot-tests.log').read_text()
    for needle in ['ok 1 - parser-policy', 'ok 3 - metadata-decoder', 'ok 4 - bounded-retry']:
        assert needle in (out / 'upstream-rate-tests.log').read_text()
    (out / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    profile = {**runtime, 'source': source, 'stage1_changed': False,
        'stage1_sha256': sha(first), 'stage2_window_remaining': report['stage2_window_remaining'],
        'default_grub_id': 'm4rch-aurora-dcp001',
        'native_handoff_fix': 'm1n1 flat-root address decoder, proved with r4 live DT and pre-fix negative control',
        'limitations': ['J614s native takeover and refresh changes await manual boot',
            'display suspend inhibited', 'external DCP processors disabled; USB3 PHY unchanged',
            'no HDR or VRR enablement']}
    (out / 'profile.json').write_text(json.dumps(profile, indent=2) + '\n')
    files = ['Image', 'initramfs.img', 'boot.bin', 'kernel.release', 'kernel.config', 'modules.tar.gz',
             'profile.json', 'runtime-profile.json', 'validation.json', 'desktop-source-manifest.json',
             'j614s-desktop.patch', 'm1n1-flat-root.patch']
    manifest = {'test': 'AUDP001', 'revision': 5, 'kernel_release': RELEASE, 'native_boot_tested': False,
        'files': {n: {'bytes': (out / n).stat().st_size, 'sha256': sha(out / n)} for n in files},
        'kit_sources': {str(p.relative_to(PROJECT)): sha(p) for p in sorted((PROJECT / 'experiments/aurora-dcp').rglob('*'))
                        if p.is_file() and '__pycache__' not in p.parts}}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
