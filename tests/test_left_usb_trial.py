import copy
import struct
import unittest
from sdboot.left_usb_trial import combined_source, validate


class LeftUsbTrialTests(unittest.TestCase):
    def fixture(self):
        base, merged = {}, {}
        def add(path, **props):
            merged[path] = props
        handle = 1
        def tagged(path, **props):
            nonlocal handle
            props['phandle'] = struct.pack('>I', handle)
            add(path, **props)
            handle += 1
            return props['phandle']
        for side, stem, sid, address, phy_addr in [('rear','382','c','118',0x82a90000), ('front','38a','a','120',0x8aa90000)]:
            pd = tagged('/soc/power-management@508300000/power-controller@'+address)
            phy = tagged('/soc/phy@'+stem+'a90000', reg=struct.pack('>8I',3,phy_addr,0,0x4000,3,phy_addr-0x290000,0,0x4000), **{'power-domains':pd, 'compatible':b'apple,t6040-atcphy\0', 'status':b'okay\0', 'reg-names':b'bank0\0bank1\0', '#phy-cells':struct.pack('>I',1)})
            usb='/soc/usb@'+stem+'280000'
            add(usb, status=b'okay\0', dr_mode=b'host\0', **{'maximum-speed':b'high-speed\0','arch-m4,usb-wait-for-cable':b'','usb-role-switch':b'','phy-names':b'usb2-phy\0','phys':phy+struct.pack('>I',3)})
            base[usb]={'status':b'disabled\0','dr_mode':b'peripheral\0'}
            for tail in ('f00000','f80000'):
                path='/soc/iommu@'+stem+tail;add(path,status=b'okay\0');base[path]={'status':b'disabled\0'}
            connector='/soc/spmi@509188000/usb-pd@'+sid+'/connector'
            add(connector,**{'data-role':b'host\0','power-role':b'source\0'})
            add(connector.rsplit('/',1)[0],reg=struct.pack('>II',int(sid,16),0))
            first=tagged(usb+'/port/endpoint');second=tagged(connector+'/port/endpoint',**{'remote-endpoint':first})
            merged[usb+'/port/endpoint']['remote-endpoint']=second
        pd=tagged('/soc/power-management@508300000/power-controller@68')
        add('/soc/spmi@509188000',reg=struct.pack('>4I',5,0x09188000,0,0x4000),**{'power-domains':pd, 'compatible':b'apple,t6040-spmi\0apple,spmi\0', 'status':b'okay\0', '#address-cells':struct.pack('>I',2), '#size-cells':struct.pack('>I',0)})
        base['/soc/usb@392280000']={'status':b'okay\0'};merged['/soc/usb@392280000']=copy.deepcopy(base['/soc/usb@392280000'])
        return base,merged

    def test_valid_both_ports_and_inherited_resources(self):
        base,merged=self.fixture();self.assertFalse(validate(base,merged)['native_verified'])
        merged['/soc/usb@392280000']['status']=b'disabled\0'
        with self.assertRaisesRegex(ValueError,'Unexpected change'):validate(base,merged)

    def test_rejects_broken_graph_and_wrong_phy(self):
        base,merged=self.fixture();merged['/soc/usb@382280000/port/endpoint']['remote-endpoint']=merged['/soc/usb@38a280000/port/endpoint']['phandle']
        with self.assertRaisesRegex(ValueError,'broken role graph'):validate(base,merged)
        base,merged=self.fixture();merged['/soc/phy@38aa90000']['reg']=b'wrong'
        with self.assertRaisesRegex(ValueError,'incorrect USB2 PHY'):validate(base,merged)

    def test_combination_preserves_board_and_renumbers_trial(self):
        result=combined_source('/dts-v1/;\n/plugin/;\n/ { fragment@0 { }; };\n','/dts-v1/;\n/plugin/;\n/ {\n fragment@0 { };\n};\n')
        self.assertIn('fragment@0',result);self.assertIn('fragment@100',result)
        self.assertEqual(result.count('/dts-v1/;'),1)
