#!/usr/bin/env python3
"""Read-only USB attachment topology, excluding serials and owner records."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import plistlib
import re
import subprocess

FIELDS = {'IORegistryEntryName', 'IORegistryEntryID', 'IORegistryEntryLocation',
          'IOObjectClass', 'IOClass', 'IOProviderClass', 'locationID',
          'idVendor', 'idProduct', 'bDeviceClass', 'bDeviceSubClass',
          'port-number', 'port', 'PortNum', 'UsbLinkSpeed', 'USBSpeed'}


def select(root):
    result = []
    def walk(nodes, ancestors):
        if isinstance(nodes, dict):
            nodes = [nodes]
        for node in nodes:
            identity = {k: node[k] for k in ('IORegistryEntryName', 'IORegistryEntryID',
                       'IORegistryEntryLocation', 'IOObjectClass') if k in node}
            lineage = ancestors + [identity]
            relevant = any(re.search(r'usb-drd|USBXHCI|USBHost|TypeC|hpm[0-9]|atc-phy',
                           str(p.get('IORegistryEntryName', '')) + ' ' +
                           str(p.get('IOObjectClass', '')), re.I) for p in lineage)
            if relevant:
                props = {}
                for key in sorted(FIELDS & node.keys()):
                    value = node[key]
                    if isinstance(value, bytes):
                        if len(value) > 256:
                            continue
                        value = {'hex': value.hex()}
                    elif not isinstance(value, (str, int, bool)):
                        continue
                    props[key] = value
                result.append({'ancestry': lineage, 'properties': props})
            walk(node.get('IORegistryEntryChildren', []), lineage)
    walk(root, [])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', args.label):
        parser.error('Use a short label')
    model = subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.model'], text=True).strip()
    if model != 'Mac16,8':
        parser.error('This mapping targets Mac16,8')
    data = plistlib.loads(subprocess.check_output(['/usr/sbin/ioreg', '-a', '-p', 'IOService', '-l']))
    report = {'schema': 1, 'model': model, 'label': args.label,
              'utc': datetime.now(timezone.utc).isoformat(), 'nodes': select(data)}
    with args.output.open('x') as output:
        output.write(json.dumps(report, indent=2) + '\n')
    print('Captured', len(report['nodes']), 'filtered nodes:', args.label)


if __name__ == '__main__':
    main()
