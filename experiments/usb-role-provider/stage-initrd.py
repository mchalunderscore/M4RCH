#!/usr/bin/env python3
"""Build a separate USB role-provider trial initrd; never install or load it."""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,stat
p=argparse.ArgumentParser();p.add_argument('original',type=Path);p.add_argument('candidate',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
spec=importlib.util.spec_from_file_location('cpio',Path(__file__).resolve().parents[1]/'t6040-sme/repack-initrd.py');cpio=importlib.util.module_from_spec(spec);spec.loader.exec_module(cpio)
old=a.original.read_bytes();_,end=cpio.parse(old);z=old.find(b'\x1f\x8b\x08',end);assert z>=end and not old[end:z].strip(b'\0')
raw=gzip.decompress(old[z:]);items,used=cpio.parse(raw);assert not raw[used:].strip(b'\0')
release='7.1.13-m4rch-gpu-contract';core=Path('/usr/lib/modules')/release/'kernel/drivers/usb/dwc3/dwc3.ko'
modules={'dwc3.ko':core.read_bytes(),'dwc3-apple.ko':a.candidate.read_bytes()}
manifest=''.join(hashlib.sha256(v).hexdigest()+'  '+k+'\n' for k,v in modules.items())
injection='''# USBR001: load trial glue BEFORE root udev, preserving installed modules.
(cd /usb-role-trial && /bin/busybox sha256sum -c SHA256SUMS) || stop 'USB trial module hash mismatch'
/bin/busybox insmod /usb-role-trial/dwc3.ko || stop 'Cannot load USB trial core dependency'
/bin/busybox insmod /usb-role-trial/dwc3-apple.ko || stop 'Cannot load USB trial glue'
echo 'M4RCH USBR001: fixed-host role-provider candidate loaded before root udev'
'''
result=[];changed=0
for name,fields,body in items[:-1]:
 if name==b'init\0':
  marker=b'for directory in dev proc sys run; do'
  assert body.count(marker)==1 and release.encode() not in body # release comes from nvme-root.conf
  body=body.replace(marker,injection.encode()+marker);changed+=1
 result.append((name,fields,body))
assert changed==1
for path,mode,body in [('usb-role-trial',stat.S_IFDIR|0o755,b''),('usb-role-trial/SHA256SUMS',stat.S_IFREG|0o644,manifest.encode())]+[('usb-role-trial/'+k,stat.S_IFREG|0o644,v) for k,v in modules.items()]:
 name=path.encode()+b'\0';fields=[len(result)+1,mode,0,0,1,0,len(body),0,0,0,0,len(name),0];result.append((name,fields,body))
result.append(items[-1]);new=old[:z]+gzip.compress(cpio.encode(result),mtime=0)
assert [(n,b) for n,f,b in cpio.parse(gzip.decompress(new[z:]))[0]]==[(n,b) for n,f,b in result]
a.output.write_bytes(new)
print(json.dumps({'release':release,'original_sha256':hashlib.sha256(old).hexdigest(),'trial_sha256':hashlib.sha256(new).hexdigest(),'module_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in modules.items()},'installed_root_modules_modified':False,'injection':'After NVMe root validation, before switch_root/root udev; exact insmod of dependency and candidate'},indent=2))
