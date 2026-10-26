#!/usr/bin/env python3
"""Run the production loader guard regression and pre-fix negative control."""
import argparse
from pathlib import Path
import subprocess

p=argparse.ArgumentParser();p.add_argument('uboot',type=Path);p.add_argument('work',type=Path);a=p.parse_args()
kit=Path(__file__).resolve().parents[1];a.work.mkdir(parents=True,exist_ok=True)
lib=a.uboot/'scripts/dtc/libfdt'
flags=['clang','-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(lib)]
def build(header,exe):
 subprocess.run(flags+['-I'+str(header),str(kit/'tests/loader_trace.c'),*[str(f) for f in sorted(lib.glob('*.c'))],'-o',str(exe)],check=True)
exe=a.work/'loader-trace-test';build(kit/'loader',exe);subprocess.run([str(exe)],check=True)
negative=a.work/'negative';negative.mkdir(exist_ok=True)
s=(kit/'loader/j614s-dcp.h').read_text();old='((u64)(ttbr & GENMASK(29, 2)) >> 2) << 14'
assert s.count(old)==1
(negative/'j614s-dcp.h').write_text(s.replace(old,'((u64)ttbr >> 2) << 14'))
exe=negative/'loader-trace-test';build(negative,exe)
r=subprocess.run([str(exe)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
assert r.returncode!=0 and b'Assertion' in r.stderr
print('TTBR negative control PASS: the original unmasked extraction fails the same register-field regression')
