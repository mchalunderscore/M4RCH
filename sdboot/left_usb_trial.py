"""Compile and validate an optional both-left USB2 overlay; never deploy it."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'lib'))
from boot import read_fdt


def combined_source(board, left):
    import re
    body = left[left.index(' fragment@'):left.rindex('};')]
    body = re.sub(r'fragment@(\d+)', lambda m: 'fragment@' + str(100 + int(m[1])), body)
    return board[:board.rindex('};')] + body + '};\n'


def validate(base, merged):
    def cell(value):
        if len(value) != 4:
            raise ValueError('Invalid phandle')
        return int.from_bytes(value, 'big')
    handles = {cell(v['phandle']): p for p, v in merged.items() if 'phandle' in v}
    for side, stem, sid, power in [('rear', '382', 'c', '118'), ('front', '38a', 'a', '120')]:
        usb = '/soc/usb@' + stem + '280000'
        props = merged[usb]
        for name, expected in [('status', b'okay\0'), ('dr_mode', b'host\0'),
                               ('maximum-speed', b'high-speed\0'), ('phy-names', b'usb2-phy\0'),
                               ('arch-m4,usb-wait-for-cable', b''), ('usb-role-switch', b'')]:
            if props.get(name) != expected:
                raise ValueError(f'{side}: missing {name}')
        for name in ('reg', 'interrupts', 'iommus', 'power-domains'):
            if props.get(name) != base[usb].get(name):
                raise ValueError(f'{side}: changed inherited {name}')
        phy_handle, phy_type = struct.unpack('>II', props['phys'])
        phy = merged[handles[phy_handle]]
        if (phy.get('compatible') != b'apple,t6040-atcphy\0' or
                phy.get('status') != b'okay\0' or
                phy.get('reg-names') != b'bank0\0bank1\0' or
                phy.get('#phy-cells') != struct.pack('>I', 1)):
            raise ValueError(f'{side}: incorrect PHY provider binding')
        addresses = {'rear': (0x82a90000, 0x82800000), 'front': (0x8aa90000, 0x8a800000)}[side]
        if phy_type != 3 or phy['reg'] != struct.pack('>8I', 3, addresses[0], 0, 0x4000, 3, addresses[1], 0, 0x4000):
            raise ValueError(f'{side}: incorrect USB2 PHY banks')
        if handles[cell(phy['power-domains'])] != '/soc/power-management@508300000/power-controller@' + power:
            raise ValueError(f'{side}: incorrect PHY power domain')
        for tail in ('f00000', 'f80000'):
            path = '/soc/iommu@' + stem + tail
            if merged[path].get('status') != b'okay\0':
                raise ValueError(f'{side}: disabled DART')
            if {k: v for k, v in merged[path].items() if k != 'status'} != {k: v for k, v in base[path].items() if k != 'status'}:
                raise ValueError(f'{side}: changed DART resources')
        connector = '/soc/spmi@509188000/usb-pd@' + sid + '/connector'
        if merged[connector].get('data-role') != b'host\0' or merged[connector].get('power-role') != b'source\0':
            raise ValueError(f'{side}: connector role mismatch')
        pd = merged[connector.rsplit('/', 1)[0]]
        if pd['reg'] != struct.pack('>II', int(sid, 16), 0):
            raise ValueError(f'{side}: SPMI SID mismatch')
        ends = (usb + '/port/endpoint', connector + '/port/endpoint')
        for one, other in zip(ends, reversed(ends)):
            if handles[cell(merged[one]['remote-endpoint'])] != other:
                raise ValueError(f'{side}: broken role graph')
    spmi = merged['/soc/spmi@509188000']
    if (spmi.get('status') != b'okay\0' or
            spmi.get('compatible') != b'apple,t6040-spmi\0apple,spmi\0' or
            spmi.get('#address-cells') != struct.pack('>I', 2) or
            spmi.get('#size-cells') != struct.pack('>I', 0)):
        raise ValueError('Incorrect a0 SPMI provider binding')
    if spmi['reg'] != struct.pack('>4I', 5, 0x09188000, 0, 0x4000):
        raise ValueError('Incorrect a0 SPMI aperture')
    if handles[cell(spmi['power-domains'])] != '/soc/power-management@508300000/power-controller@68':
        raise ValueError('Incorrect a0 SPMI power domain')
    # Right port, CPU trial, NVMe and every existing property must survive.
    allowed = {'status', 'dr_mode', 'phys', 'phy-names', 'usb-role-switch', 'arch-m4,usb-wait-for-cable'}
    for path, props in base.items():
        for key, value in props.items():
            if path in ('/soc/usb@382280000', '/soc/usb@38a280000') and key in allowed:
                continue
            if path in ('/soc/iommu@382f00000', '/soc/iommu@382f80000', '/soc/iommu@38af00000', '/soc/iommu@38af80000') and key == 'status':
                continue
            if merged.get(path, {}).get(key) != value:
                raise ValueError(f'Unexpected change to {path}:{key}')
    return {'ports': {'left-front': 'usb-drd1', 'left-rear': 'usb-drd0'},
            'maximum_speed': 'high-speed', 'native_verified': False,
            'pd_socket_association': 'provisional ADT port-number mapping',
            'requires_driver_patch': 'experimental-dwc3-cable-mode-precedence.patch'}



def stage_deployment(trial, destination, hardware, update, boot_fat_uuid):
    """Publish an immutable activation kit for an already-built matching update."""
    import gzip
    import re
    import shutil
    if not re.fullmatch(r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}", boot_fat_uuid):
        raise ValueError("Invalid ESP FAT UUID")
    if not re.fullmatch(r"update-[0-9a-f]{12}", update.name):
        raise ValueError("Expected a content-addressed package update directory")
    if destination.exists():
        raise ValueError("Preserve the existing deployment kit; choose a new destination")
    manifest = json.loads((hardware / "boot/hardware-manifest.json").read_text())
    patch_name = "patches/experimental-dwc3-cable-mode-precedence.patch"
    patch_hash = hashlib.sha256((PROJECT / patch_name).read_bytes()).hexdigest()
    fixes = manifest["inputs"]["experimental"]["usb_cable_fixes"]
    if not any(fix["path"] == patch_name and fix["sha256"] == patch_hash for fix in fixes):
        raise ValueError("Built kernel lacks the matching cable-mode-precedence patch")
    image = gzip.decompress((hardware / "boot/Image.gz").read_bytes())
    receipt = {
        "schema": 1, "kernel_release": manifest["kernel_release"],
        "kernel_sha256": hashlib.sha256(image).hexdigest(),
        "modules_sha256": manifest["modules_sha256"],
        "boot_fat_uuid": boot_fat_uuid.upper(),
        "update_directory": "/boot/" + update.name,
        "capacity_overlay_sha256": hashlib.sha256((trial / "board-capacity.dtbo").read_bytes()).hexdigest(),
        "left_overlay_sha256": hashlib.sha256((trial / "board-left-usb.dtbo").read_bytes()).hexdigest(),
        "native_verified": False,
    }
    destination.mkdir(parents=True)
    for name in ("board-capacity.dtbo", "board-left-usb.dtbo", "board-left-usb.dtso", "validation.json"):
        shutil.copyfile(trial / name, destination / name)
    shutil.copyfile(PROJECT / "sdboot/left_usb_activate.py", destination / "activate.py")
    shutil.copyfile(PROJECT / patch_name, destination / Path(patch_name).name)
    shutil.copyfile(PROJECT / "docs/left-usb-trial.md", destination / "README.md")
    shutil.copyfile(hardware / "boot/hardware-manifest.json", destination / "hardware-manifest.json")
    (destination / "deployment.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (destination / "SHA256SUMS").write_text("".join(
        hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n"
        for path in sorted(destination.iterdir())))
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    board = PROJECT / 'sdboot/board.dtso'
    left = PROJECT / 'sdboot/left-usb-trial.dtso'
    source = args.out / 'board-left-usb.dtso'
    source.write_text(combined_source(board.read_text(), left.read_text()))
    baseline = args.out / 'board-capacity.dtbo'
    overlay = args.out / 'board-left-usb.dtbo'
    for src, target in [(board, baseline), (source, overlay)]:
        subprocess.run(['dtc', '-@', '-I', 'dts', '-O', 'dtb', '-o', str(target), str(src)], check=True)
    merged_paths = []
    for label, target in [('capacity', baseline), ('left', overlay)]:
        path = args.out / (label + '.dtb')
        subprocess.run(['fdtoverlay', '-i', str(args.base), '-o', str(path), str(target)], check=True)
        merged_paths.append(path)
    receipt = validate(*(read_fdt(path) for path in merged_paths))
    receipt['files'] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (source, baseline, overlay)}
    (args.out / 'validation.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
