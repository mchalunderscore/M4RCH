# SPDX-License-Identifier: GPL-2.0-only
"""Explicit contract shared by the future reset builder and resident runner."""
import struct
from pathlib import Path
import hashlib
import json

RELEASE = '7.1.13-m4rch-gpu-reset'
PATCH_SHA = 'b08f6785ce938b20fcd1d1ededd49ffca04242263ac0e7a0bc7f6f6f3678821c'
DRIVER_SHA = '93df185e68c3e69d428460db7fc725b85ed191f75d24753a0563536a0dd1da61'
HEADER_SHA = '22392cd82cfdabcc1796166612bbb1d7b935cc34111bc1bf930e72d8e328c71e'
ROOT = Path(__file__).resolve().parents[2]
CONTRACT = {
    'version': 1,
    'provider_path': '/soc/power-management@288e80000/power-controller@110',
    'snapshot_api': 'apple_pmgr_t6040_gfx_snapshot',
    'pulse_api': 'apple_pmgr_t6040_gfx_checked_pulse',
    'pulse_us': 10,
    'maximum_reset_commands': 1,
    'runtime_pm_required': True,
    'work_submitted': False,
    'allocations_retained': True,
    'automatic_restart': False,
    'backing_release': False,
    'packet_free_stop': True,
    'commands': ['gfx-snapshot', 'gfx-reset'],
    'after_attempt': ['sample', 'gfx-snapshot', 'stop'],
}
NATIVE_RELEASE = '7.1.13-m4rch-gpu-native-reset'
NATIVE_PATCH_SHA = '5df46ea05dbf84d0245a6a74b97f309ca07c1b1d54d3848497ee7cf430bd5264'
NATIVE_DRIVER_SHA = '04910407755d029a2acd131f873359bd14983ace946a469725612883835abb61'
NATIVE_HEADER_SHA = '4fbdca1e18ed9c3ee030bad9a94f35c2f70b213d038dfb0555350f35809df9a0'
USB_PATCHED_SHA = '7ca78866b27aa670134ded04820c26b7cabfb17640c410ee5cf3b307e0aa5b0c'
USB_PATCH_SHA = 'c138588f8509a41502e22c8ddd2e62fa917b181685673edfc01313d2a27b9365'
NATIVE_CONTRACT = dict(
    CONTRACT, version=2, pulse_api='apple_pmgr_t6040_gfx_native_probe', pulse_us=1,
    disable_completion='minimum-1us-then-busy-clear',
    command_bits_latch_required=False,
    commands_forced=['disable', 'combined-reset', 'release'],
    all_command_writes_forced=True, desired_words_full_register=True,
    physical_reset_acknowledged=False,
)


def profile(native=False):
    if native:
        require(all(isinstance(h, str) and len(h) == 64 for h in
                    (NATIVE_PATCH_SHA, NATIVE_DRIVER_SHA, NATIVE_HEADER_SHA)),
                'Native command API has not been qualified')
        return dict(contract=NATIVE_CONTRACT, release=NATIVE_RELEASE,
                    patch=NATIVE_PATCH_SHA, driver=NATIVE_DRIVER_SHA,
                    header=NATIVE_HEADER_SHA,
                    schema='m4rch.gfx-native-reset-kernel-qualification.v1')
    return dict(contract=CONTRACT, release=RELEASE, patch=PATCH_SHA,
                driver=DRIVER_SHA, header=HEADER_SHA,
                schema='m4rch.gfx-reset-kernel-qualification.v1')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def elf_section(data, wanted):
    """Read a bounded little-endian ELF64 section without running the image."""
    require(len(data) >= 64 and data[:6] == b'\x7fELF\x02\x01', 'Invalid ELF64 image')
    require(struct.unpack_from('<H', data, 18)[0] == 183, 'Not an AArch64 image')
    table = struct.unpack_from('<Q', data, 40)[0]
    entry_size, count, names_index = struct.unpack_from('<HHH', data, 58)
    require(entry_size == 64 and 0 < names_index < count and
            table + count * entry_size <= len(data), 'Invalid ELF section table')

    def section(index):
        return struct.unpack_from('<IIQQQQIIQQ', data, table + index * entry_size)

    names_row = section(names_index)
    require(names_row[4] + names_row[5] <= len(data), 'Invalid ELF section names')
    names = data[names_row[4]:names_row[4] + names_row[5]]
    matches = []
    for index in range(count):
        row = section(index)
        require(row[0] < len(names), 'Invalid ELF section name index')
        end = names.find(b'\0', row[0])
        require(end >= 0, 'Unterminated ELF section name')
        if names[row[0]:end] == wanted:
            require(row[4] + row[5] <= len(data), 'Truncated ELF section')
            matches.append(data[row[4]:row[4] + row[5]])
    require(len(matches) == 1 and matches[0], 'Missing or ambiguous ELF section')
    return matches[0]


def validate_receipt(receipt):
    trial = receipt.get('graph_recovery_trial', {})
    if 'gfx_reset_scope' not in trial:
        return False
    native = trial['gfx_reset_scope'] == NATIVE_CONTRACT
    spec = profile(native)
    require(trial['gfx_reset_scope'] == spec['contract'], 'Unknown GFX reset command contract')
    require(receipt['kernel_release'] == spec['release'] and
            receipt.get('kernel_gfx_reset_api', {}).get('patch_sha256') == spec['patch'],
            'GFX reset API kernel binding missing')
    if native:
        require(receipt['kernel_gfx_reset_api'].get('api_profile') == 'native-command-v1' and
                receipt['kernel_gfx_reset_api'].get('legacy_checked_patch_sha256') == PATCH_SHA and
                receipt['kernel_gfx_reset_api'].get('usb_role_patch_sha256') == USB_PATCH_SHA,
                'Native command profile binding missing')
    require(receipt.get('joined_owned_pages') == 174 and
            trial.get('resident_session') is True and
            receipt.get('graph_submit_work') is False and
            receipt.get('graph_power_retirement_probe') is False and
            receipt.get('graph_release_on_shutdown') is False,
            'Unexpected reset owner lifetime')
    return True


def validate_kernel(path):
    manifest = json.loads(Path(path).read_text())
    native = manifest.get('api_profile') == 'native-command-v1'
    spec = profile(native)
    require(manifest['schema'] == spec['schema'] and
            manifest['kernel_release'] == spec['release'] and manifest['patch_sha256'] == spec['patch'],
            'Wrong checked-reset kernel manifest')
    if native:
        require(manifest.get('legacy_checked_patch_sha256') == PATCH_SHA and
                manifest.get('usb_role_patch_sha256') == USB_PATCH_SHA,
                'Legacy reset API or promoted USB correction binding missing')
    tree = Path(manifest['kernel_tree']).resolve()
    require((tree / 'include/config/kernel.release').read_text().strip() == spec['release'],
            'Kernel release changed')
    require({'vmlinux', 'arch/arm64/boot/Image', '.config', 'Module.symvers',
             'drivers/pmdomain/apple/pmgr-pwrstate.c',
             'include/linux/soc/apple/pmgr-gfx-reset.h'} <= set(manifest['artifact_manifest']),
            'Kernel artifact manifest is incomplete')
    for name, expected in manifest['artifact_manifest'].items():
        require(sha(tree / name) == expected['sha256'], 'Kernel artifact changed: ' + name)
    require(sha(tree / '.config') == manifest['config_sha256'] and
            sha(tree / 'Module.symvers') == manifest['module_symvers_sha256'],
            'Kernel configuration or exports changed')
    require(sha(tree / 'vmlinux') == manifest['vmlinux_sha256'] and
            sha(tree / 'arch/arm64/boot/Image') == manifest['image_sha256'],
            'Compiled kernel image identity differs')
    require(sha(tree / 'drivers/pmdomain/apple/pmgr-pwrstate.c') == spec['driver'] and
            sha(tree / 'include/linux/soc/apple/pmgr-gfx-reset.h') == spec['header'],
            'Checked-reset API source differs from reviewed patch')
    baseline = ROOT / 'out/gpu-gravity-contract'
    source = json.loads((baseline / 'source-receipt.json').read_text())
    require(manifest['baseline_protected_fingerprints'] == source['protected_maintained_files'],
            'Maintained-source baseline differs')
    for name, expected in source['protected_maintained_files'].items():
        require(sha(baseline / 'linux' / name) == expected, 'Original source changed: ' + name)
        if native and name == 'drivers/usb/dwc3/dwc3-apple.c':
            require(sha(tree / name) == USB_PATCHED_SHA, 'Promoted USB source correction missing')
        elif name != 'drivers/pmdomain/apple/pmgr-pwrstate.c':
            require(sha(tree / name) == expected, 'Maintained source changed: ' + name)
    base_config = (baseline / 'linux/.config').read_text()
    require(sha(baseline / 'linux/.config') == manifest['baseline_config_sha256'] and
            (tree / '.config').read_text() == base_config.replace(
                'CONFIG_LOCALVERSION=""\n',
                'CONFIG_LOCALVERSION="' + spec['release'].removeprefix('7.1.13') + '"\n'),
            'Configuration change extends beyond the release suffix')
    notes = elf_section((tree / 'vmlinux').read_bytes(), b'.notes')
    require(notes == Path(manifest['kernel_notes_path']).read_bytes() and
            hashlib.sha256(notes).hexdigest() == manifest['kernel_notes_sha256'],
            'Compiled kernel notes differ from manifest')
    exports = {line.split()[1]: line.split()[3] for line in
               (tree / 'Module.symvers').read_text().splitlines() if len(line.split()) >= 4}
    apis = [spec['contract']['snapshot_api'], spec['contract']['pulse_api']]
    if native:
        apis.append(CONTRACT['pulse_api'])
    for api in apis:
        require(exports.get(api) == 'EXPORT_SYMBOL_GPL', 'Checked-reset API not exported')
    return manifest, tree, notes
