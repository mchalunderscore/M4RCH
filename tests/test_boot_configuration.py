"""Check the packaged boot and sleep policy for the current J614s stack."""
from pathlib import Path
import shlex
import unittest

FILES = Path(__file__).resolve().parents[1] / 'packages/asahi-scripts-m4rch/files'


class BootConfigurationTest(unittest.TestCase):
    def test_grub_keeps_current_display_sleep_and_speaker_policy(self):
        values = {}
        for line in (FILES / 'grub.cfg').read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                values[key] = shlex.split(value)[0]
        self.assertEqual(values['GRUB_DEFAULT'], '0')
        self.assertEqual(values['GRUB_TOP_LEVEL'], '/boot/vmlinuz-linux-m4rch')
        args = set(shlex.split(values['GRUB_CMDLINE_LINUX_DEFAULT']))
        self.assertTrue({'mem_sleep_default=s2idle', 'm4rch.dcp=1', 'user4k=on',
                         'appledrm.j614s_vrr=1', 'm4rch.extdisp=1',
                         'appledrm.t6041_dcpext=1', 'quiet', 'splash'} <= args)
        self.assertIn('modprobe.blacklist=snd_soc_tas2764,snd_soc_tas2770', args)
        self.assertFalse(any(x.startswith('systemd.mask=apple-silicon.service') for x in args))
        modprobe = (FILES / 'apple-silicon.conf').read_text()
        for amplifier in ('snd_soc_tas2764', 'snd_soc_tas2770'):
            self.assertIn('blacklist ' + amplifier, modprobe.splitlines())

    def test_suspend_is_enabled_and_hibernation_stays_disabled(self):
        policy = (FILES / 'sleep.conf').read_text().splitlines()
        self.assertIn('AllowSuspend=yes', policy)
        for setting in ('AllowHibernation=no', 'AllowHybridSleep=no',
                        'AllowSuspendThenHibernate=no'):
            self.assertIn(setting, policy)
        initramfs = (FILES / 'mkinitcpio.conf').read_text()
        self.assertIn('HOOKS=(base udev plymouth ', initramfs)


if __name__ == '__main__':
    unittest.main()
