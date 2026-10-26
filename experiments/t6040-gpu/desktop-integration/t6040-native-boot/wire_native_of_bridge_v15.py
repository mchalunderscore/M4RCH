#!/usr/bin/env python3
"""Apply only the provider phandle API to a staged kernel, never boot/install."""
import argparse,hashlib,json
from pathlib import Path
KIT=Path(__file__).resolve().parent
def kernel_wiring(files):
 key='drivers/of/dynamic.c'
 if 'of_m4rch_ensure_phandle' in files[key]:raise ValueError('API already present')
 files[key]+='\n'+(KIT/'native_of_phandle_v15.c.inc').read_text()
 key='include/linux/of.h';needle='extern struct device_node *of_find_node_by_phandle(phandle handle);'
 assert files[key].count(needle)==1
 files[key]=files[key].replace(needle,needle+'\nextern int of_m4rch_ensure_phandle(struct device_node *np, u32 *handle);')
def wire(kernel):
 p=kernel/'drivers/of/dynamic.c';h=kernel/'include/linux/of.h'
 files={str(x.relative_to(kernel)):x.read_text() for x in (p,h)}
 kernel_wiring(files)
 for name,text in files.items():(kernel/name).write_text(text)
 receipt={'schema':'m4rch.native-of-provider-phandle.v15','hardware_actions':[],'kernel':str(kernel),'files':[{'path':str(x),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in (p,h)]}
 (kernel.parent/'native-of-bridge-kernel-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('kernel',type=Path);wire(a.parse_args().kernel.resolve())
