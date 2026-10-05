import unittest
from sdboot.macos_usb_snapshot import select

class MacUsbSnapshotTests(unittest.TestCase):
    def test_attachment_preserves_controller_ancestry_without_private_properties(self):
        root = {'IORegistryEntryName':'Root','IOConsoleUsers':'private',
          'IORegistryEntryChildren':[{'IORegistryEntryName':'usb-drd1','IORegistryEntryID':10,
          'IORegistryEntryChildren':[{'IORegistryEntryName':'Drive','IOObjectClass':'IOUSBHostDevice',
          'idVendor':1921,'idProduct':21929,'serial-number':'private','Owner':'private'}]}]}
        result = select(root)
        device = result[-1]
        self.assertEqual([p['IORegistryEntryName'] for p in device['ancestry']],['Root','usb-drd1','Drive'])
        self.assertEqual(device['properties']['idVendor'],1921)
        self.assertNotIn('serial-number',device['properties'])
        self.assertNotIn('Owner',device['properties'])
        self.assertNotIn('IOConsoleUsers',device['ancestry'][0])
