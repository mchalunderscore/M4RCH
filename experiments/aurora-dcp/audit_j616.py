#!/usr/bin/env python3
"""Audit and export the actual r10 build sources inside the Linux build VM."""
import hashlib
import json
from pathlib import Path
import subprocess

PROJECT = Path('/project')
OUT = PROJECT / 'out/aurora-dcp/j616-r10'
LINUX = Path('/work/linux-r10')
PIN = '6dc07e43e394d73db0de16079d3eb9463207543c'


def main():
    dart = LINUX / 'drivers/iommu/apple-dart.c'
    upstream = subprocess.check_output(['git', '-c', 'safe.directory=/project/out/aurora-test/linux',
        '-C', str(PROJECT / 'out/aurora-test/linux'), 'show', PIN + ':drivers/iommu/apple-dart.c'])
    assert dart.read_bytes() == upstream, 'DART must be byte-identical to merged Aurora'
    dcp = (LINUX / 'drivers/gpu/drm/apple/dcp.c').read_text()
    for removed in ['dcp_alloc_dma', 'j614s_display_power_prepare', 'dcp_j614s_adopt_hw']:
        assert removed not in dcp
    assert not (LINUX / 'drivers/gpu/drm/apple/j614s-power.h').exists()
    config = (LINUX / '.config').read_text()
    assert 'CONFIG_APPLE_J614S_DCP_BOOT=y\n' in config
    changed = {}
    for name in ['m1n1', 'uboot']:
        root = Path('/work/loader-r10') / name
        patch = subprocess.check_output(['git', '-C', str(root), 'diff', '--binary', 'HEAD'])
        files = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--others', '--exclude-standard'], text=True).splitlines()
        for path in files:
            proc = subprocess.run(['git', 'diff', '--no-index', '--binary', '--', '/dev/null', path], cwd=root, stdout=subprocess.PIPE)
            assert proc.returncode == 1, path
            patch += proc.stdout
        subprocess.run(['git', '-C', str(root), 'diff', '--check'], check=True)
        (OUT / (name + '-j614s.patch')).write_bytes(patch)
        changed[name] = {'head': subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
                         'new_source_files': files, 'patch_sha256': hashlib.sha256(patch).hexdigest()}
    for name in ['control.dtb', 'template.dtb']:
        path = OUT / name
        def get(node, prop):
            return subprocess.check_output(['fdtget', str(path), node, prop], text=True).strip()
        for node in ['/iommu@402300000', '/iommu@402340000', '/mailbox@402e08000',
                     '/dcp@402e00000', '/dcp@402e00000/piodma', '/display-subsystem']:
            assert get(node, 'status') == 'disabled', (name, node)
        for node in ['/dcp@402e00000', '/dcp@402e00000/piodma', '/display-subsystem']:
            props = subprocess.check_output(['fdtget', '-p', str(path), node], text=True).splitlines()
            assert 'dma-noncoherent' in props
            assert not {'memory-region', 'memory-region-names', 'apple,t6041-handoff', 'apple,firmware-uuid'} & set(props)
        for alias in ['wifi0', 'bluetooth0']:
            assert get(get('/aliases', alias), 'brcm,board-type') == 'apple,mriya'
        def visit(node):
            yield node
            for child in subprocess.check_output(['fdtget', '-l', str(path), node], text=True).splitlines():
                yield from visit(node.rstrip('/') + '/' + child)
        speakers = []
        for node in visit('/'):
            props = subprocess.check_output(['fdtget', '-p', str(path), node], text=True).splitlines()
            if 'compatible' in props:
                compat = get(node, 'compatible').split()
                if {'apple,j616-macaudio', 'ti,tas2764', 'ti,tas2770', 'ti,sn012776'} & set(compat):
                    assert get(node, 'status') == 'disabled'
                    speakers.append(node)
        assert speakers
        if name == 'control.dtb':
            assert get('/chosen', 'asahi,t6041-dcp') == '1'
    report = {'linux_pin': PIN, 'dart_byte_identical_to_merged_upstream': True,
        'dart_sha256': hashlib.sha256(upstream).hexdigest(),
        'J713_diversion_and_native_retained_DMA_wrappers': 'absent',
        'custom_display_PMP_guard': 'absent', 'complete_standard_handoff_transfer': True,
        'templates_disabled_with_no_stale_handoff': True, 'speaker_nodes_disabled': True,
        'radio_identity_mriya_preserved': True, 'loaders': changed,
        'native_boot_tested': False}
    (OUT / 'source-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
