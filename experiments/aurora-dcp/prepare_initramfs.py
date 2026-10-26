#!/usr/bin/env python3
"""Adapt a freshly unpacked native-working AURG016 initramfs for AUDP001."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

KIT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path); parser.add_argument('output',type=Path)
    args=parser.parse_args(); root=args.root; output=args.output
    def replace(name,old,new):
        path=root/name; text=path.read_text()
        if text.count(old)!=1: raise ValueError(f'Expected native anchor in {name}: {old!r}')
        path.write_text(text.replace(old,new))
    release=(output/'kernel.release').read_text().strip()
    replace('etc/nvme-root.conf',"KERNEL_RELEASE='7.3.0-m4rch-aurora-direct1+'",f"KERNEL_RELEASE='{release}'")
    shutil.copyfile(output/'modules.tar.gz',root/'modules.tar.gz')
    replace('aurora-runtime.sh',"echo 'Aurora AURG016 full-render experiment: temporary module and Mesa mounts; speakers excluded'",
        "echo 'AUDP001 J614s internal-panel DCP + accelerated desktop candidate; speakers excluded'")
    replace('aurora-runtime.sh','# /proc/device-tree is a symlink:', '''case " $(cat /proc/cmdline) " in
    *' m4rch.dcp=1 '*)
        echo 'DCP001: starting retained internal-panel driver before GPU/desktop'
        case " $(cat /proc/cmdline) " in
            *' appledrm.j614s_modeset=1 '*) modprobe_test appledrm j614s_modeset=1 ;;
            *) modprobe_test appledrm ;;
        esac || echo 'DCP001: driver failed; inspect retained-framebuffer and return logs'
        ;;
esac
# /proc/device-tree is a symlink:''')
    replace('aurora-direct.service','TimeoutStartSec=90','TimeoutStartSec=180')
    replace('init','cp /gpu16-recorder.sh /run/aurora-direct/recorder.sh',
        'cp /collect-display.sh /run/aurora-direct/collect-display.sh\ncp /gpu16-recorder.sh /run/aurora-direct/recorder.sh')
    # Leave the GPU renderer intact but do not run the old Vulkan experiment.
    replace('init','ln -s ../gpu16-vulkan.service /run/systemd/system/multi-user.target.wants/gpu16-vulkan.service',
        '# AUDP001: desktop rendering is the integrated GPU workload.')
    replace('gpu16-collect.timer','OnBootSec=2min','OnBootSec=45s')
    replace('gpu16-collect.service','Description=Collect Aurora 16-core GPU and desktop results','Description=Collect integrated AUDP001 display and desktop results')
    replace('gpu16-recorder.service','Description=Record Aurora GPU desktop startup immediately','Description=Record AUDP001 DCP takeover and desktop startup immediately')
    replace('init','# The normal root may retain a console-only default', '''# Retained DCP power has no qualified sleep/resume boundary yet. These
# are boot-only overrides; the installed root's normal sleep policy is intact.
for unit in sleep.target suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target systemd-suspend.service; do
    mkdir -p /run/systemd/system
    ln -sf /dev/null /run/systemd/system/$unit
done
printf '[Sleep]\\nAllowSuspend=no\\nAllowHibernation=no\\nAllowHybridSleep=no\\nAllowSuspendThenHibernate=no\\n' >/run/systemd/sleep.conf.d/zzzz-aurora-dcp.conf
printf '[Login]\\nHandleLidSwitch=ignore\\nHandleLidSwitchExternalPower=ignore\\nHandleLidSwitchDocked=ignore\\nIdleAction=ignore\\n' >/run/systemd/logind.conf.d/zzzz-aurora-dcp.conf
# The normal root may retain a console-only default''')
    shutil.copyfile(KIT/'recorder.sh',root/'gpu16-recorder.sh')
    shutil.copyfile(KIT/'collect-display.sh',root/'collect-display.sh')
    # Passive collection only: do not launch additional graphics probes.
    (root/'aurora-collect.sh').write_text('''#!/bin/sh
set -eu
recorded=$(cat /run/aurora-direct/return-path 2>/dev/null || true)
[ -n "$recorded" ] || exit 1
destination=$recorded/full-$(date -u +%Y%m%dT%H%M%SZ)-$$
sh /run/aurora-direct/collect-base.sh "$destination"
sh /run/aurora-direct/collect-display.sh "$destination"
cp /run/aurora-direct/gpu16-candidate.json "$destination/candidate.json"
sync -f "$destination"
echo "AUDP001 return bundle: $destination"
''')
    profile=json.loads((root/'gpu16-profile.json').read_text())
    (output/'native-gpu-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    profile={'test':'AUDP001','revision':3,'kernel_release':release,'native_boot_tested':False,
        'display':'J614s internal panel; experimental physical SDR modes up to 120 Hz, initial scanout and DRM page flips',
        'handoff':'DCP001-v1','firmware_uuid':'6CC9349E-D30B-33FB-B12B-8D6D38F9F1B3',
        'firmware_version':'26.6.2','speakers_enabled':False,'suspend_enabled':False,
        'renderer':'native-working Aurora Mesa / Asahi 16-core / Zink',
        'native_gpu_profile':profile,'dcp_power':'retain boot power; pin existing PMP supplier; no J713 power-state commands'}
    data=json.dumps(profile,indent=2)+'\n'
    (root/'gpu16-profile.json').write_text(data); (output/'runtime-profile.json').write_text(data)
    for path in root.glob('*.sh'): subprocess.run(['/bin/sh','-n',str(path)],check=True)
    subprocess.run(['/bin/sh','-n',str(root/'init')],check=True)
    print('Prepared AUDP001 initramfs runtime with passive automatic return bundle')

if __name__=='__main__': main()
