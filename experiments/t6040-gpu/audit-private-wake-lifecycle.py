#!/usr/bin/env python3
"""Read-only numeric checks of matched private AGX lifecycle sites; no execution.

Not clean-room. Does not include driver instructions/disassembly in the report.
The pinned sites support the manually reviewed interpretation in the companion
Markdown; matching words alone does not prove that interpretation or causality.
"""
import argparse, hashlib, json, struct
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('macho', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
raw = a.macho.read_bytes()
digest = hashlib.sha256(raw).hexdigest()
if digest != '3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e':
    raise ValueError('Expected matched AGX353.14 / Apple25G83')
pos = 32
segments = []
for _ in range(struct.unpack_from('<I', raw, 16)[0]):
    cmd, size = struct.unpack_from('<II', raw, pos)
    if cmd == 0x19:
        segments.append(struct.unpack_from('<QQQQ', raw, pos + 24))
    pos += size
def read(address, size):
    for vm, _, offset, length in segments:
        if vm <= address and address + size <= vm + length:
            return raw[offset + address - vm:offset + address - vm + size]
    raise ValueError('Address not wholly file-backed')
checks = {'0xfffffe00089d30c4': '0xb0ffa6b0',
 '0xfffffe00089d30c8': '0x9119a210',
 '0xfffffe00089d30cc': '0x91004210',
 '0xfffffe00089d30dc': '0xf9000270',
 '0xfffffe00089d9f70': '0x91406808',
 '0xfffffe00089d9f74': '0x913d8108',
 '0xfffffe00089d9f80': '0xb0ff3b0a',
 '0xfffffe00089d9f84': '0x9131ed4a',
 '0xfffffe00089d9f88': '0xb0ff3b0b',
 '0xfffffe00089d9f8c': '0x9132556b',
 '0xfffffe00089d9f90': '0xa9002d0a',
 '0xfffffe00089ca48c': '0xd2811011',
 '0xfffffe00089ca4a4': '0xd73f0910',
 '0xfffffe00089ca7ec': '0x391a429f',
 '0xfffffe00089ca7f0': '0x391c569f',
 '0xfffffe00089ca7f4': '0xf94b3400',
 '0xfffffe00089ca7f8': '0xf94b4661',
 '0xfffffe00089ca80c': '0xd2811111',
 '0xfffffe00089ca81c': '0xd73f0910',
 '0xfffffe00089ca820': '0x34000b00',
 '0xfffffe00089ca8c4': '0x395c5688',
 '0xfffffe00089ca8ec': '0x390aa274',
 '0xfffffe00089d1650': '0xd503245f',
 '0xfffffe00089d1654': '0xd65f03c0',
 '0xfffffe00089c89e8': '0xf94b3400',
 '0xfffffe00089c89fc': '0xd2811811',
 '0xfffffe00089c8a18': '0xd71f0a11',
 '0xfffffe00089c7ea0': '0xf94b3408',
 '0xfffffe00089c7ea4': '0x39462508',
 '0xfffffe00089c7eac': '0xa280120',
 '0xfffffe00089ca5c4': '0xf9434515',
 '0xfffffe00089ca5cc': '0xd2e010c1',
 '0xfffffe00089ca5d0': '0xb340aea1',
 '0xfffffe00089ca5e4': '0xd2811511',
 '0xfffffe00089ca5f8': '0xd73f0910',
 '0xfffffe00089ca60c': '0x910006b6',
 '0xfffffe00089ca628': '0xd2803b11',
 '0xfffffe00089ca640': '0xeb0002df',
 '0xfffffe00089ca3f0': '0xf944b008',
 '0xfffffe00089ca3f4': '0x52892209',
 '0xfffffe00089ca3fc': '0xb9400108',
 '0xfffffe00089ca410': '0xf944b008',
 '0xfffffe00089ca414': '0xf9647900'}
for address, expected in checks.items():
    if struct.unpack('<I', read(int(address, 16), 4))[0] != int(expected, 16):
        raise ValueError('Changed instruction site ' + address)
# Constructor pins ASC address point at vtable + 16. Image-specific pointer
# target base calibrated against both named destructor symbols, not PAC stripped
# as a raw virtual address; do not generalize this decoding to other images.
vtable = 0xfffffe0007ea8668
base = 0xfffffe0007004000
slots = {
    0: (0xfffffe00089d2074, 'AGXArmFirmwareASC::~AGXArmFirmwareASC D1'),
    8: (0xfffffe00089d190c, 'AGXArmFirmwareASC::~AGXArmFirmwareASC D0'),
    0x1d8: (0xfffffe00089ca40c, 'getNumDeviceRecoveries'),
    0x1e0: (0xfffffe00089ca3ec, 'isFirmwareStoppedForHostRecovery'),
    0x480: (0xfffffe00089c27e8, 'isFirmwareStoppedForPreRecovery'),
    0x488: (0xfffffe00089c27c8, 'isFirmwareStoppedForPostRecovery'),
    0x700: (0xfffffe00089d15d0, 'isSystemSleepNotificationInProgress'),
    0x2d8: (0xfffffe00089c8ff8, 'convertGPUVAToFWVA'),
}
resolved = []
for slot, (expected, name) in slots.items():
    encoded = struct.unpack('<Q', read(vtable + 16 + slot, 8))[0]
    target = base + (encoded & 0xffffffff)
    if target != expected:
        raise ValueError('Unexpected ASC vtable target')
    resolved.append(dict(slot=hex(slot), target=hex(target), method=name))
for address, value in [(0xfffffe000713ac7b, b'AGXFirmwareKextG16RTBuddy'),
                       (0xfffffe000713ac95, b'AGXFirmwareKextRTBuddy')]:
    if read(address, len(value)) != value:
        raise ValueError('Changed provider selector string')
result = dict(macho_sha256=digest, apple_build='25G83', agx_version='353.14',
    instruction_site_checks=len(checks), vtable=hex(vtable),
    addresspoint_offset=16, image_specific_target_base=hex(base),
    resolved_self_slots=resolved,
    payload_slots={'initialize':'0x880', 'boot':'0x888',
                   'root_notification_send':'0x898', 'recovery_send':'0x8a8',
                   'change_power_state':'0x8c0', 'request_firmware_binary':'0x8d0'},
    qualification='Offline private static audit, not clean-room. Provider implementations are absent. No hardware actions, Apple code execution or exact status48/cause diagnosis. See companion Markdown for interpretation and limitations.')
a.output.write_text(json.dumps(result, indent=2) + '\n')
print(f'Checked {len(checks)} lifecycle sites and {len(slots)} ASC vtable slots')
