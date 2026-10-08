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
 '0xfffffe00089ca414': '0xf9647900',
 '0xfffffe0008977ec0': '0x3958c408',
 '0xfffffe0008977ed4': '0x91052913',
 '0xfffffe0008977edc': '0x340002a1',
 '0xfffffe0008977ee0': '0x7100091f',
 '0xfffffe0008977ee8': '0xf942d800',
 '0xfffffe0008977efc': '0xd2806d11',
 '0xfffffe0008977f0c': '0x52800021',
 '0xfffffe0008977f14': '0xd73f0910',
 '0xfffffe0008977f18': '0x39000275',
 '0xfffffe0008977f30': '0x7100051f',
 '0xfffffe0008977f38': '0xf942d800',
 '0xfffffe0008977f4c': '0xd2806d11',
 '0xfffffe0008977f5c': '0x52800041',
 '0xfffffe0008977f64': '0xd73f0910',
 '0xfffffe0008977f68': '0x39000275',
 '0xfffffe000895faa4': '0xf942da60',
 '0xfffffe000895fab8': '0xd2806d11',
 '0xfffffe000895fac8': '0x52800021',
 '0xfffffe000895fad0': '0xd73f0910',
 '0xfffffe00089757c0': '0xf942da76',
 '0xfffffe00089757c4': '0x912262d4',
 '0xfffffe00089757d8': '0xf8430e08',
 '0xfffffe00089757fc': '0xf8438e08',
 '0xfffffe000897580c': '0x6b0002bf',
 '0xfffffe0008975810': '0x540004c1',
 '0xfffffe0008975828': '0xd2802811',
 '0xfffffe000897583c': '0x34000360',
 '0xfffffe0008975854': '0x7100051f',
 '0xfffffe0008975878': '0xd2806d11',
 '0xfffffe0008975888': '0x52800041',
 '0xfffffe0008975890': '0xd73f0910',
 '0xfffffe0008975894': '0x390002b6',
 '0xfffffe00089d18dc': '0x9ba80028',
 '0xfffffe00089d18e4': '0x39256109',
 '0xfffffe00089d18f0': '0x39656008',
 '0xfffffe0008974b70': '0xf942da60',
 '0xfffffe0008974b84': '0xd2810011',
 '0xfffffe0008974b94': '0xd73f0910',
 '0xfffffe0008974b9c': '0xd5033bbf',
 '0xfffffe0008974bc8': '0xf948a609',
 '0xfffffe0008974bd8': '0xd73f0931',
 '0xfffffe0008974c58': '0xf942da60',
 '0xfffffe0008974c6c': '0xd2810111',
 '0xfffffe0008974c7c': '0xd73f0910',
 '0xfffffe00089e7e98': '0x52802214',
 '0xfffffe00089e7e9c': '0x72a01d14',
 '0xfffffe00089e7ea0': '0xf942d800',
 '0xfffffe00089e7eb4': '0xd2810211',
 '0xfffffe00089e7ec4': '0xd73f0910',
 '0xfffffe00089e7ec8': '0xf941ae68',
 '0xfffffe00089e7ed0': '0xb9400108',
 '0xfffffe00089e7ed4': '0x721c0d1f',
 '0xfffffe00089bf130': '0xf9444408',
 '0xfffffe00089bf134': '0xb9401108',
 '0xfffffe00089bf170': '0xf9444408',
 '0xfffffe00089bf174': '0xb9401d08',
 '0xfffffe00089bf178': '0xb95dfc09',
 '0xfffffe00089bf180': '0x54000128',
 '0xfffffe00089bf1c4': '0xf9444408',
 '0xfffffe00089bf1c8': '0xb9401d08',
 '0xfffffe00089bf1cc': '0xb91dfc08',
 '0xfffffe00089c8888': '0x52800148',
 '0xfffffe00089c888c': '0x290107e8',
 '0xfffffe00089c8890': '0x52800068',
 '0xfffffe00089c893c': '0x97ff6d3b',
 '0xfffffe00089be64c': '0xf9419261',
 '0xfffffe00089be678': '0x9111c6a8',
 '0xfffffe00089be67c': '0xf9000100'}
for address, expected in checks.items():
    if struct.unpack('<I', read(int(address, 16), 4))[0] != int(expected, 16):
        raise ValueError('Changed instruction site ' + address)
# Constructor pins ASC address point at vtable + 16. Image-specific pointer
# target base calibrated against both named destructor symbols, not PAC stripped
# as a raw virtual address; do not generalize this decoding to other images.
vtable = 0xfffffe0007ea8668
base = 0xfffffe0007004000
slots = {
    0x140: (0xfffffe00089d18ec, 'isFirmwareColdBootDone'),
    0x148: (0xfffffe00089d18d4, 'completeFirmwareColdBoot'),
    0x190: (0xfffffe00089ca7cc, 'bootFirmware'),
    0x198: (0xfffffe00089ca784, 'stopFirmware'),
    0x368: (0xfffffe00089c89e4, 'changePowerStateTo'),
    0x380: (0xfffffe00089c8860, 'submitCmdGPUIdlePowerOff'),
    0x800: (0xfffffe00089bf1b0, 'snapshotASCPowerGeneration'),
    0x808: (0xfffffe00089bf160, 'waitForNextASCPowerGeneration'),
    0x810: (0xfffffe00089bf120, 'waitForFirmwarePowerOff'),
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
# G16X accelerator table: both named destructor anchors and lifecycle calls.
accelerator_vtable = 0xfffffe0007eae388
accelerator_slots = [(0, 18446741874830912716, '__ZN18AGXAcceleratorG16XD1Ev'), (8, 18446741874830912560, '__ZN18AGXAcceleratorG16XD0Ev'), (4408, 18446741874830901088, '__ZN18AGXAcceleratorG16X18halResetEventFlagsERK20AGFIKSMEventFlagMask'), (4424, 18446741874830900868, '__ZN18AGXAcceleratorG16X25halWaitForFenderPowerGateEv')]
accelerator_resolved = []
for slot, target, name in accelerator_slots:
    encoded = struct.unpack('<Q', read(accelerator_vtable + 16 + slot, 8))[0]
    if base + (encoded & 0xffffffff) != target:
        raise ValueError('Unexpected accelerator vtable target')
    accelerator_resolved.append(dict(slot=hex(slot), target=hex(target), method=name))
result = dict(macho_sha256=digest, apple_build='25G83', agx_version='353.14',
    instruction_site_checks=len(checks), vtable=hex(vtable),
    addresspoint_offset=16, image_specific_target_base=hex(base),
    resolved_self_slots=resolved, accelerator_vtable=hex(accelerator_vtable),
    resolved_accelerator_slots=accelerator_resolved,
    payload_slots={'initialize':'0x880', 'boot':'0x888',
                   'root_notification_send':'0x898', 'recovery_send':'0x8a8',
                   'change_power_state':'0x8c0', 'request_firmware_binary':'0x8d0'},
    qualification='Offline private static audit, not clean-room. Provider implementations are absent. No hardware actions, Apple code execution or exact status48/cause diagnosis. See companion Markdown for interpretation and limitations.')
a.output.write_text(json.dumps(result, indent=2) + '\n')
print(f'Checked {len(checks)} lifecycle sites and {len(slots)} ASC and {len(accelerator_slots)} accelerator vtable slots')
