#!/usr/bin/env python3
"""Package a reviewed MTP-only U-Boot trial with the installed Gravity m1n1.

Run after applying the base Gravity patch and keyboard patch and building U-Boot.
No enrollment, reboot or deployment is performed here.
"""
import argparse,gzip,hashlib,json,struct,subprocess,sys
from pathlib import Path
import libfdt

PROJECT=Path(__file__).resolve().parents[1]
NODES=('/soc/m4rch-boot-keyboard@514b34000','/soc/m4rch-boot-mtp-helper@514600000')
def sha(x):return hashlib.sha256(x).hexdigest()
def properties(f):
    result={};node=0;depth=0
    while node>=0:
        props={};off=f.first_property_offset(node,quiet=(libfdt.NOTFOUND,))
        while off>=0:
            p=f.get_property_by_offset(off);props[p.name]=bytes(p)
            off=f.next_property_offset(off,quiet=(libfdt.NOTFOUND,))
        result[f.get_path(node)]=props
        node,depth=f.next_node(node,depth,quiet=(libfdt.NOTFOUND,))
        if depth<0:break
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--uboot-tree',type=Path,required=True)
    p.add_argument('--base-bundle',type=Path,default=Path('/boot/boot.bin'))
    p.add_argument('--base-manifest',type=Path,default=Path('/boot/loader-alignment/loader-manifest.json'))
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(a.base_manifest.read_text());blob=a.base_bundle.read_bytes()
    if sha(blob)!=manifest['files']['boot.bin']['sha256']:raise ValueError('Base bundle differs from qualified loader manifest')
    lengths=manifest['files'];n=lengths['loader/m1n1.bin']['bytes'];d=lengths['loader/baseline.dtb']['bytes']
    prefix,dt,old_image=blob[:n],blob[n:n+d],gzip.decompress(blob[n+d:])
    for name,b in [('m1n1.bin',prefix),('baseline.dtb',dt),('u-boot-nodtb.bin',old_image)]:
        if sha(b)!=lengths['loader/'+name]['sha256']:raise ValueError('Base component differs: '+name)
    profile=json.loads((PROJECT/'profiles/gravity-loader.json').read_text())
    keyboard=json.loads((PROJECT/'profiles/gravity-keyboard.json').read_text())
    for file,digest in keyboard['input_files'].items():
        if sha((PROJECT/file).read_bytes())!=digest:raise ValueError('Keyboard input changed: '+file)
    expected={**profile['sources']['uboot']['result_files'],**keyboard['result_files']}
    for file,digest in expected.items():
        if sha((a.uboot_tree/file).read_bytes())!=digest:raise ValueError('U-Boot source differs: '+file)
    settings=dict(s.split('=',1) for s in (a.uboot_tree/'.config').read_text().splitlines() if s.startswith('CONFIG_') and '=' in s)
    sys.path.insert(0,str(PROJECT/'sdboot'));import loader
    loader.validate_uboot_config(a.uboot_tree/'.config',a.uboot_tree/'drivers/serial/Makefile',internal=True)
    for key in ('APPLE_NOIO','DM_KEYBOARD','APPLE_MTP_KEYB','APPLE_KEYB'):
        if settings.get('CONFIG_'+key)!='y':raise ValueError('Missing keyboard config: '+key)
    image=(a.uboot_tree/'u-boot-nodtb.bin').read_bytes()
    original=libfdt.Fdt(dt);base_properties=properties(original)
    mailbox=original.path_offset('/soc/mailbox@514608000')
    if original.getprop(mailbox,'phandle').as_uint32()!=0x5f:raise ValueError('MTP mailbox phandle changed')
    (a.output/'baseline.dtb').write_bytes(dt)
    subprocess.run(['dtc','-@','-I','dts','-O','dtb',str(PROJECT/'sdboot/t6040-boot-keyboard.dtso'),'-o',str(a.output/'keyboard.dtbo')],check=True)
    subprocess.run(['fdtoverlay','-i',str(a.output/'baseline.dtb'),'-o',str(a.output/'control.dtb'),str(a.output/'keyboard.dtbo')],check=True)
    control=libfdt.Fdt((a.output/'control.dtb').read_bytes())
    # The overlay's temporary symbol is not part of the boot or Linux contract.
    if '/__symbols__' not in base_properties:control.del_node(control.path_offset('/__symbols__'))
    else:
        control.delprop(control.path_offset('/__symbols__'),'boot_mtp_helper')
    control.pack();new_properties=properties(control)
    if set(new_properties)-set(base_properties)!=set(NODES):raise ValueError('Unexpected control DT nodes')
    if any(new_properties[path]!=props for path,props in base_properties.items()):raise ValueError('Original DT property changed')
    helper=control.getprop(control.path_offset(NODES[1]),'phandle').as_uint32()
    if control.getprop(control.path_offset(NODES[0]),'apple,helper-cpu').as_uint32()!=helper:raise ValueError('Helper phandle mismatch')
    for path in NODES:control.del_node(control.path_offset(path))
    if properties(control)!=base_properties:raise ValueError('Handoff removal fails to restore original DT')
    # Reopen the packed control DT, including boot-only nodes, for stage 2.
    control=libfdt.Fdt((a.output/'control.dtb').read_bytes())
    if '/__symbols__' not in base_properties:control.del_node(control.path_offset('/__symbols__'))
    else:control.delprop(control.path_offset('/__symbols__'),'boot_mtp_helper')
    control.pack();new_dt=bytes(control.as_bytearray())
    loader.pack(prefix,new_dt,image)
    result=prefix+new_dt+gzip.compress(image,compresslevel=9,mtime=0)
    (a.output/'control.dtb').write_bytes(new_dt)
    (a.output/'boot.bin').write_bytes(result)
    (a.output/'boot-before.bin').write_bytes(blob)
    (a.output/'u-boot-nodtb.bin').write_bytes(image)
    (a.output/'uboot.config').write_bytes((a.uboot_tree/'.config').read_bytes())
    receipt=dict(schema=1,scope='Built-in keyboard MTP-only stage-2 trial; no USB keyboard support',hardware_tested=False,
        original_bundle_sha256=sha(blob),new_bundle_sha256=sha(result),unchanged_m1n1_sha256=sha(prefix),
        original_baseline_sha256=sha(dt),control_dtb_sha256=sha(new_dt),uboot_sha256=sha(image),
        keyboard_profile=keyboard,source_revision=profile['sources']['uboot']['revision'],
        validations=['Base bundle/component hashes match qualified loader manifest','Reviewed source hashes match',
        'Required NVMe and keyboard config; USB/PCI disabled','All original DT properties preserved',
        'Boot-only nodes removed from separate handoff DT restore original properties','ARM64 Image/DT packing checks'],
        boot_only_nodes=list(NODES),rollback='Replace /boot/boot.bin with boot-before.bin; enrolled stage 1 unchanged')
    (a.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k.endswith('sha256')},indent=2))
if __name__=='__main__':main()
