import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('stub_diagnostics',ROOT/'scripts/diagnose-stub-upgrade.py')
diagnostic=importlib.util.module_from_spec(spec);spec.loader.exec_module(diagnostic)

class PrebootSelectionTests(unittest.TestCase):
    def setup_disk(self):
        disk=Mock()
        disk.apfs.return_value={'Containers':[
            {'APFSContainerUUID':'other','Volumes':[{'Roles':['Preboot'],'DeviceIdentifier':'disk3s1','APFSVolumeUUID':'other-volume'}]},
            {'APFSContainerUUID':'main','Volumes':[{'Roles':['Preboot'],'DeviceIdentifier':'disk4s2','APFSVolumeUUID':'main-volume'}]}]}
        disk.info.return_value={'MountPoint':'/System/Volumes/Preboot','VolumeUUID':'main-volume','DeviceIdentifier':'disk4s2'}
        return disk

    def test_system_mount_is_allowed_only_for_verified_main_preboot(self):
        disk=self.setup_disk()
        path=diagnostic.main_preboot(disk,{'container_uuid':'main','vgid':'main-group'})
        self.assertEqual(path,Path('/System/Volumes/Preboot/main-group/var/db/AdminUserRecoveryInfo.plist'))
        disk.run.assert_not_called()
        self.assertEqual(disk.info.call_args_list[0].args,('disk4s2',))

    def test_wrong_volume_at_system_mount_is_rejected(self):
        disk=self.setup_disk();disk.info.return_value['VolumeUUID']='wrong'
        with self.assertRaisesRegex(ValueError,'mount identity changed'):
            diagnostic.main_preboot(disk,{'container_uuid':'main','vgid':'main-group'})

if __name__=='__main__':unittest.main()
