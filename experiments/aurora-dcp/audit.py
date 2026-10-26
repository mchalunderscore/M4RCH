#!/usr/bin/env python3
"""Identify the actual Arch-stub DCP image without starting a controller."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import subprocess
import uuid

PROJECT = Path(__file__).resolve().parents[2]
OUTPUT = PROJECT / 'out/aurora-dcp'
PIN = '420a1c8f5492daeaa59ffba565aac610f5218d27'
QUALIFIED_UUID = '81BAF476-679D-3CC0-8C6A-E6B6FA659D5E'
VGID = '05F89AF0-EFD8-44CB-ABEB-D805D7B34F63'


def tlv(data, offset):
    if offset + 2 > len(data):
        raise ValueError('Truncated DER header')
    tag, length = data[offset:offset + 2]
    start = offset + 2
    if length & 128:
        count = length & 127
        if not 1 <= count <= 4 or start + count > len(data):
            raise ValueError('Invalid DER length')
        length = int.from_bytes(data[start:start + count], 'big')
        start += count
    end = start + length
    if end > len(data):
        raise ValueError('Truncated DER body')
    return tag, start, end


def decode(data):
    tag, offset, end = tlv(data, 0)
    if tag != 0x30 or end != len(data):
        raise ValueError('Expected one IM4P sequence')
    fields = []
    while offset < end:
        tag, start, stop = tlv(data, offset)
        fields.append((tag, data[start:stop]))
        offset = stop
    if fields[:2] != [(0x16, b'IM4P'), (0x16, b'dcpf')] or fields[3][0] != 4:
        raise ValueError('Not a DCP IM4P image')
    payload = fields[3][1]
    library = ctypes.CDLL('/usr/lib/libcompression.dylib')
    library.compression_decode_buffer.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                                                  ctypes.c_size_t, ctypes.c_void_p, ctypes.c_int]
    library.compression_decode_buffer.restype = ctypes.c_size_t
    buffer = ctypes.create_string_buffer(64 * 1024 * 1024)
    size = library.compression_decode_buffer(buffer, len(buffer), payload, len(payload), None, 0x801)
    if not size or size == len(buffer):
        raise ValueError('LZFSE decoding failed or exceeded its bound')
    return buffer.raw[:size]


def image_uuid(image):
    if len(image) < 32 or image[:4] != b'\xcf\xfa\xed\xfe':
        raise ValueError('Expected a 64-bit Mach-O firmware image')
    count, extent = struct.unpack_from('<II', image, 16)
    offset, result = 32, []
    if extent > len(image) - offset or count > 4096:
        raise ValueError('Invalid load-command bounds')
    for _ in range(count):
        if offset + 8 > 32 + extent:
            raise ValueError('Truncated Mach-O command')
        command, size = struct.unpack_from('<II', image, offset)
        if size < 8 or offset + size > 32 + extent:
            raise ValueError('Invalid Mach-O command size')
        if command == 0x1b:
            if size != 24:
                raise ValueError('Invalid LC_UUID size')
            result.append(str(uuid.UUID(bytes=image[offset + 8:offset + 24])).upper())
        offset += size
    if len(result) != 1:
        raise ValueError('Expected one firmware UUID')
    return result[0]


def main(preboot):
    firmware = preboot / VGID / 'restore/Firmware/dcp/t604xdcp.im4p'
    version = plistlib.loads(Path('/Volumes/M4RCH/System/Library/CoreServices/SystemVersion.plist').read_bytes())
    if (version['ProductVersion'], version['ProductBuildVersion']) != ('26.6.2', '25G83'):
        raise ValueError('Arch-stub firmware profile changed; re-audit its backend')
    info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', str(preboot)]))
    if info['VolumeUUID'] != 'B428BBA0-7EE5-4D57-A895-8104C1165A73':
        raise ValueError('Not the existing Arch Preboot volume')
    data = firmware.read_bytes()
    image = decode(data)
    actual_uuid = image_uuid(image)
    private = OUTPUT / 'private'
    private.mkdir(parents=True, exist_ok=True)
    (private / 't604xdcp.macho').write_bytes(image)
    sources = {}
    for path in ['drivers/gpu/drm/apple/iomfb_m4.c', 'drivers/gpu/drm/apple/dcp-m4-profile.h',
                 'drivers/iommu/apple-dart.c', 'drivers/soc/apple/pmp-display.c']:
        source = subprocess.check_output(['git', '-C', str(PROJECT / 'out/aurora-test/linux'), 'show', PIN + ':' + path])
        sources[path] = hashlib.sha256(source).hexdigest()
    result = {'board': 'J614s / T6040', 'kernel_base': PIN,
              'stub_os': version['ProductVersion'], 'stub_build': version['ProductBuildVersion'],
              'firmware': {'source': str(firmware), 'im4p_sha256': hashlib.sha256(data).hexdigest(),
                           'decoded_sha256': hashlib.sha256(image).hexdigest(), 'decoded_bytes': len(image),
                           'macho_uuid': actual_uuid},
              'aurora_qualified_profile': {'board': 'J713 / T8132', 'firmware_uuid': QUALIFIED_UUID,
                                           'panel': [2560, 1664], 'coprocessor_base': '0x30ae00000'},
              'firmware_uuid_matches': actual_uuid == QUALIFIED_UUID,
              'j614s_coprocessor_base': '0x402e00000',
              'source_sha256': sources, 'native_dcp_started': False,
              'takeover_build_ready': False,
              'required_port': ['J614s firmware RPC/panel profile', 'Live DCP/DISP/PIODMA reservation handoff',
                                'T6041 retained DART ownership support', 'T6041 display power-vote support'],
              'boot_selection_changed': False}
    (OUTPUT / 'firmware-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preboot', type=Path, default=Path('/Volumes/Arch M4 Boot Preboot'))
    main(parser.parse_args().preboot)
