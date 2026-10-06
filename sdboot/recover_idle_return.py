#!/usr/bin/env python3
"""Read selected m4rch idle captures from unmounted SD ext4; never write the card."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import collect_sd_logs as reader

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--disk',required=True);args=parser.parse_args()
    if os.geteuid()!=0:raise ValueError('Run with sudo for read-only raw SD access')
    assert hashlib.sha256(reader.DEBUGFS.read_bytes()).hexdigest()==reader.DEBUGFS_SHA256
    device,whole,part=reader.validate_disk(args.disk)
    with open(device,'rb',buffering=0) as f:reader.validate_superblock(f.read(4096))
    base=reader.PROJECT/'out/native-returns';base.mkdir(exist_ok=True);reader.safe_directory(base)
    output=Path(tempfile.mkdtemp(prefix='recovered-shallow-',dir=base));output.chmod(0o700)
    reader.MAX_FILES=256;reader.MAX_COMMANDS=800;reader.MAX_TOTAL=128*reader.MIB
    capture=reader.Capture(device,output)
    safe=re.compile(r'[A-Za-z0-9_.-]+\Z')
    suffixes=('.json','.jsonl','.csv','.tsv','.txt','.log','.md','.config','.gz','.sha256')
    def walk(source,target,depth=0):
        if depth>6:return
        target.mkdir(exist_ok=True,mode=0o700)
        for name,mode in capture.listing(source):
            if name in ('.','..') or not safe.fullmatch(name):continue
            if stat.S_ISDIR(mode):walk(source+'/'+name,target/name,depth+1)
            elif stat.S_ISREG(mode) and (name.endswith(suffixes) or name in ('SHA256SUMS','kernel.config','config')):capture.dump(source+'/'+name,target/name)
    try:
        source='/home/alice/Documents/Codex/2026-10-05/he/outputs'
        walk(source+'/m4rch-idle-shallow',output/'shallow')
        capture.dump(source+'/m4rch-return-idle-shallow.tar.gz',output/'original-return.tar.gz')
    finally:
        (output/'debugfs.txt').write_text('\n'.join(capture.messages));reader.restore_ownership(output)
    print(output)
if __name__=='__main__':main()
