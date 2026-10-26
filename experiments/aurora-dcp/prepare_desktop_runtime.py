#!/usr/bin/env python3
"""Update the r4 temporary runtime for the PR445 desktop firmware backend."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

KIT = Path(__file__).resolve().parent
RELEASE = '7.3.0-m4rch-dcp005'


def prepare(root, output):
    path = root / 'etc/nvme-root.conf'
    old = "KERNEL_RELEASE='7.3.0-m4rch-dcp003'"
    text = path.read_text(); assert text.count(old) == 1
    path.write_text(text.replace(old, "KERNEL_RELEASE='" + RELEASE + "'"))
    shutil.copyfile(output / 'modules.tar.gz', root / 'modules.tar.gz')
    path = root / 'aurora-runtime.sh'; text = path.read_text()
    old = "echo 'AUDP001 r4 handoff-corrected integrated DCP candidate; speakers excluded'"
    assert text.count(old) == 1
    text = text.replace(old, "echo 'AUDP001 r5 PR445 T6041 desktop DCP backend; speakers excluded'")
    old = '''        echo 'DCP001: starting retained internal-panel driver before GPU/desktop'
        case " $(cat /proc/cmdline) " in
            *' appledrm.j614s_modeset=1 '*) modprobe_test appledrm j614s_modeset=1 ;;
            *) modprobe_test appledrm ;;
        esac || echo 'DCP001: driver failed; inspect retained-framebuffer and return logs'
'''
    assert text.count(old) == 1
    text = text.replace(old, '''        echo 'DCP005: starting T6041 desktop backend before GPU/desktop; full panel, external processors disabled'
        modprobe_test appledrm show_notch=1 t6041_dcpext=0 || echo 'DCP005: driver failed; inspect loader/driver return logs'
''')
    assert 'j614s_modeset' not in text
    path.write_text(text)
    shutil.copyfile(KIT / 'collect-display.sh', root / 'collect-display.sh')
    profile = json.loads((root / 'gpu16-profile.json').read_text())
    profile.update({'revision': 5, 'kernel_release': RELEASE, 'loader_revision': 'DCP005',
        'display_backend': 'PR445 T6041 desktop 26.6, internal-panel commits 4-7',
        'changes': ['dedicated desktop 26.6 firmware backend', 'native J614s six-window register validation',
            'full 3024x1964 panel height', 'firmware-listed native 60 Hz initial takeover; advertised refresh modes',
            'upstream mode-info/bootstrap/timestamps', 'typed callback and envelope bounds',
            'flat-root m1n1 MMIO decoder fixes native SID23 translator refusal'],
        'display': 'J614s native internal panel; firmware-advertised SDR modes and physical backlight',
        'external_displays_enabled': False, 'speakers_enabled': False, 'suspend_enabled': False,
        'native_boot_tested': False, 'native_takeover_tested': False,
        'prior_native_result': 'r4 refused at sid23-translator; original m1n1 decoder returned zero for root-level MMIO'})
    data = json.dumps(profile, indent=2) + '\n'
    (root / 'gpu16-profile.json').write_text(data)
    (output / 'runtime-profile.json').write_text(data)
    for name in ['aurora-runtime.sh', 'collect-display.sh', 'init']:
        subprocess.run(['/bin/sh', '-n', str(root / name)], check=True)
    print('Prepared PR445 desktop runtime; prior Mesa, UCM, root contract and service policy retained')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path); p.add_argument('output', type=Path)
    a = p.parse_args(); prepare(a.root, a.output)
