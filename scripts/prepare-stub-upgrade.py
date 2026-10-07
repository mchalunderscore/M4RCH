#!/usr/bin/env python3
"""Prepare an isolated 25G83 Apple stub; never install or personalize it."""
import argparse
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import plistlib
import re
import shutil
import stat
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
from common import download, sha256, write_json
import firmware
import stub_payload as stub

URL = ('https://updates.cdn-apple.com/2026SummerFCS/fullrestores/140-75212/'
       'A2A24B94-1FC1-45A3-93F7-C51B02AF1F4D/UniversalMac_26.6.2_25G83_Restore.ipsw')
SIZE = 19772231540
BUILD, VERSION = '25G83', '26.6.2'
PROFILE = ROOT / 'profiles/stub-25G83.lock.json'


def selected_members(archive, identity):
    names = stub.restore_members(identity)
    names.update(('SystemVersion.plist', 'RestoreVersion.plist',
                  'PlatformSupport.plist', 'usr/standalone/bootcaches.plist',
                  'BootabilityBundle/Restore/Firmware/Bootability.dmg.trustcache'))
    for member in archive.infolist():
        if not member.is_dir() and member.filename.startswith((stub.BOOTABILITY_PREFIX, stub.RESTORE_PREFIX)):
            names.add(member.filename)
    for name in names:
        stub.relative_path(name)
    return sorted(names)


def gfx_metadata(path):
    """Decode only bounded container fields and published Mach-O metadata."""
    data = path.read_bytes()
    def tlv(position, limit):
        if position + 2 > limit:
            raise ValueError('Truncated DER header')
        tag, length = data[position:position + 2]
        start = position + 2
        if length & 128:
            count = length & 127
            if not 0 < count <= 4 or start + count > limit:
                raise ValueError('Invalid DER length')
            length = int.from_bytes(data[start:start + count], 'big')
            start += count
        end = start + length
        if end > limit:
            raise ValueError('Truncated DER body')
        return tag, start, end
    tag, position, end = tlv(0, len(data))
    if tag != 0x30 or end != len(data):
        raise ValueError('Expected one IM4P sequence')
    parts = []
    while position < end:
        tag, start, following = tlv(position, end)
        parts.append((tag, data[start:following]))
        position = following
    if len(parts) < 4 or parts[0] != (22, b'IM4P') or parts[1] != (22, b'gfxf') or parts[3][0] != 4:
        raise ValueError('Unexpected GFX IM4P fields')
    spec = importlib.util.spec_from_file_location('gfx_layout', ROOT / 'experiments/t6040-gpu/firmware-layout.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.layout(parts[3][1])
    report.update(im4p_sha256=sha256(path), im4p_bytes=len(data))
    return report


def verify_candidate(output):
    output = output.resolve()
    lock = json.loads((output / 'target-inputs.lock.json').read_text())
    if lock != json.loads(PROFILE.read_text()):
        raise ValueError('Candidate lock differs from the published target profile')
    expected = {'apple_build': BUILD, 'apple_version': VERSION, 'apple_url': URL, 'apple_size': SIZE,
                'device_class': 'j614sap', 'chip_id': '0x6040', 'board_id': '0x04'}
    if any(lock.get(k) != v for k, v in expected.items()):
        raise ValueError('Candidate target identity changed')
    manifest_data = (output / 'BuildManifest.plist').read_bytes()
    if hashlib.sha256(manifest_data).hexdigest() != lock['build_manifest_sha256']:
        raise ValueError('Candidate BuildManifest changed')
    apple = plistlib.loads(manifest_data)
    identity = stub.select_identity(apple, BUILD)
    for name, record in lock['files'].items():
        stub.relative_path(name)
        if not stub.check_input(output / 'inputs' / name, record):
            raise ValueError('Candidate input changed: ' + name)
    base = output / 'inputs' / identity['Manifest']['BaseSystem']['Info']['Path']
    if base.is_symlink() or sha256(base) != lock['base_system_aea_sha256']:
        raise ValueError('Candidate AEA input changed')
    dmg = base.with_suffix('')
    if dmg.is_symlink() or sha256(dmg) != lock['base_system_dmg_sha256']:
        raise ValueError('Candidate decrypted Recovery changed')
    payload = output / 'payload'
    receipt = json.loads((payload / 'manifest.json').read_text())
    files, links, directories = stub.inventory(payload)
    if (receipt.get('input_lock_sha256') != sha256(output / 'target-inputs.lock.json')
            or (files, links, directories) != (receipt['files'], receipt['symlinks'], receipt['directories'])):
        raise ValueError('Candidate assembled payload changed')
    gfx = gfx_metadata(output / 'inputs/Firmware/agx/armfw_g16s.im4p')
    write_json(output / 'gfx-layout.json', gfx)
    write_json(output / 'verification.json', {'candidate_content_verified': True,
        'input_lock_sha256': sha256(output / 'target-inputs.lock.json'),
        'payload_manifest_sha256': sha256(payload / 'manifest.json'),
        'verifier_sha256': sha256(__file__), 'installed': False,
        'qualification': 'Local candidate integrity; no native Recovery or boot-policy qualification'})
    print('Candidate integrity verified:', payload)


def prepare(output):
    if sys.platform != 'darwin':
        raise ValueError('Preparation requires macOS for authenticated AEA decryption')
    output = output.resolve()
    if output.exists():
        raise ValueError('Output already exists; retain it and select a fresh --output directory')
    output.mkdir(parents=True)
    # Keep successful downloads after interruption, but never expose a partial payload as ready.
    inputs = output / 'inputs'
    inputs.mkdir()
    baseline = stub.load_lock()
    pinned = json.loads(PROFILE.read_text())
    write_json(output / 'baseline-inputs.lock.json', baseline)
    source_archive = download('https://codeload.github.com/AsahiLinux/asahi-installer/tar.gz/' + firmware.ASAHI_REVISION,
                              output / 'asahi-installer.tar.gz', firmware.ASAHI_SHA256)
    source = output / 'asahi'
    firmware.extract_regular(source_archive, source, 'asahi-installer-' + firmware.ASAHI_REVISION + '/')
    sys.path.insert(0, str(source / 'src'))
    try:
        from urlcache import URLCache
        with contextlib.redirect_stdout(sys.stderr):
            remote = URLCache(URL)
            try:
                if remote.size != SIZE:
                    raise ValueError('Target Apple archive size changed')
                with zipfile.ZipFile(remote) as archive:
                    manifest_data = archive.read('BuildManifest.plist')
                    if hashlib.sha256(manifest_data).hexdigest() != pinned['build_manifest_sha256']:
                        raise ValueError('Target Apple BuildManifest differs from pinned profile')
                    manifest = plistlib.loads(manifest_data)
                    if manifest.get('ProductVersion') != VERSION:
                        raise ValueError('Target Apple version changed')
                    identity = stub.select_identity(manifest, BUILD)
                    (output / 'BuildManifest.plist').write_bytes(manifest_data)
                    base_name = identity['Manifest']['BaseSystem']['Info']['Path']
                    names = selected_members(archive, identity)
                    if set(names) != set(pinned['files']):
                        raise ValueError('Target member selection differs from pinned profile')
                    records = {}
                    for name in names + [base_name]:
                        stub.relative_path(name)
                        member = archive.getinfo(name)
                        mode = member.external_attr >> 16
                        if stat.S_IFMT(mode) not in (stat.S_IFREG, stat.S_IFLNK) or mode & 0o7000:
                            raise ValueError('Unsupported Apple archive member mode')
                        target = inputs / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        print('Fetching', name, member.file_size, flush=True)
                        with archive.open(member) as src, target.open('wb') as dst:
                            shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
                        records[name] = {'bytes': member.file_size, 'mode': member.external_attr >> 16,
                                         'sha256': sha256(target)}
                        if name != base_name and records[name] != pinned['files'][name]:
                            raise ValueError('Target member differs from pinned profile: ' + name)
                        if name == base_name and records[name]['sha256'] != pinned['base_system_aea_sha256']:
                            raise ValueError('Target AEA differs from pinned profile')
            finally:
                remote.close_connection()
    finally:
        sys.path.remove(str(source / 'src'))
    arch = platform.machine()
    helper_name = f'ipsw_{firmware.IPSW_VERSION}_macOS_{arch}.tar.gz'
    helper = download(f'https://github.com/blacktop/ipsw/releases/download/v{firmware.IPSW_VERSION}/{helper_name}',
                      output / helper_name, firmware.IPSW_TOOL_HASHES[arch])
    firmware.extract_regular(helper, output / 'ipsw')
    firmware.run([output / 'ipsw/ipsw', 'fw', 'aea', inputs / base_name, '-o', inputs])
    dmg = inputs / base_name.removesuffix('.aea')
    if not dmg.is_file() or dmg.is_symlink():
        raise ValueError('AEA tool did not produce the expected BaseSystem DMG')
    if sha256(dmg) != pinned['base_system_dmg_sha256']:
        raise ValueError('Decrypted target Recovery differs from pinned profile')
    lock = {**baseline, 'apple_build': BUILD, 'apple_version': VERSION,
            'apple_url': URL, 'apple_size': SIZE,
            'build_manifest_sha256': hashlib.sha256(manifest_data).hexdigest(),
            'base_system_dmg_sha256': sha256(dmg),
            'base_system_aea_sha256': records.pop(base_name)['sha256'],
            'files': records,
            'restore_bundle_evidence': '25G83 candidate layout; native personalization and Recovery upgrade not qualified'}
    write_json(output / 'target-inputs.lock.json', lock)
    if lock != pinned:
        raise ValueError('Generated target lock differs from pinned profile')
    stage = output / 'payload.partial'
    stage.mkdir()
    stub.assemble(inputs, dmg, manifest, source, stage, lock)
    files, links, directories = stub.inventory(stage)
    receipt = {'schema': 'm4rch.stub-upgrade-preparation.v1', 'apple_build': BUILD,
               'apple_version': VERSION, 'input_lock_sha256': sha256(output / 'target-inputs.lock.json'),
               'builder_sha256': sha256(__file__), 'files': files, 'symlinks': links,
               'directories': directories, 'installed': False, 'personalized': False,
               'native_recovery_qualified': False, 'default_profile_changed': False}
    write_json(stage / 'manifest.json', receipt)
    stage.rename(output / 'payload')
    # These are public firmware metadata strings, not decoded executable instructions.
    firmware_tags = {}
    for name in records:
        if name.endswith('.im4p') and ('iBoot.' in name or '/agx/' in name):
            data = (inputs / name).read_bytes()
            firmware_tags[name] = sorted(set(x.decode('ascii') for x in re.findall(
                rb'(?:mBoot-[0-9.]+|RTKit(?:_release)?-[A-Za-z0-9_.-]+)', data)))
    write_json(output / 'firmware-strings.json', firmware_tags)
    write_json(output / 'gfx-layout.json', gfx_metadata(inputs / 'Firmware/agx/armfw_g16s.im4p'))
    print('Prepared candidate:', output / 'payload', flush=True)
    print('No internal volume, boot policy, SD file, or working default profile was changed.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify', action='store_true', help='Verify an existing candidate without installing it')
    args = parser.parse_args()
    if args.verify:
        verify_candidate(args.output)
    else:
        prepare(args.output)
