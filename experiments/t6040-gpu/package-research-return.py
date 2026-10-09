#!/usr/bin/env python3
"""Refresh a hash-qualified private return bundle, excluding captured TEXT.

No /boot writes: outputs are staged locally for a separate authorized install.
"""
import argparse,hashlib,shutil,subprocess,tarfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('previous',type=Path);p.add_argument('expected_sha256');p.add_argument('stage',type=Path);p.add_argument('output',type=Path)
p.add_argument('--handover',type=Path,required=True);p.add_argument('--artifact',action='append',default=[]);p.add_argument('--evidence',action='append',default=[])
a=p.parse_args();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(a.previous)==a.expected_sha256
if a.stage.exists():raise ValueError('Stage must be new')
a.stage.mkdir(parents=True)
with tarfile.open(a.previous) as t:t.extractall(a.stage,filter='data')
for line in (a.stage/'SHA256SUMS').read_text().splitlines():
 digest,name=line.split(None,1);name=name.lstrip('* ');item=a.stage/name
 assert item.resolve().is_relative_to(a.stage.resolve()) and sha(item)==digest,name
for dst in ['HANDOVER-root.md','HANDOVER-usb.md','LINUX-HANDOVER.md']:
 (a.stage/dst).write_text(a.handover.read_text()+(a.stage/dst).read_text())
for path in map(Path,a.artifact):
 dst=a.stage/path.name
 if dst.exists():shutil.rmtree(dst)
 shutil.copytree(path,dst,ignore=shutil.ignore_patterns('text.bin','__pycache__'))
latest=a.stage/'latest-evidence';latest.mkdir(exist_ok=True)
for path in map(Path,a.evidence):shutil.copy2(path,latest/path.name)
commit=subprocess.check_output(['git','rev-parse','--short','HEAD'],text=True).strip()
with (a.stage/('source-'+commit+'.tar.gz')).open('wb') as f:subprocess.run(['git','archive','--format=tar.gz','HEAD'],stdout=f,check=True)
files=sorted(p for p in a.stage.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
(a.stage/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(a.stage).as_posix()+'\n' for p in files))
with tarfile.open(a.output,'w:gz') as t:
 for path in sorted(a.stage.iterdir()):t.add(path,arcname=path.name)
print('Bundle',sha(a.output),'files',len(files),'source',commit)
