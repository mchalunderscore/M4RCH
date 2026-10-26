#!/usr/bin/env python3
"""Replace only the DCP bridge helper with its evidence-preserving revision."""
import argparse,difflib
from pathlib import Path
KIT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('uboot',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
f=a.uboot/'arch/arm/mach-apple/dcp_handoff.c';old=f.read_text();new=(KIT/'loader/dcp_handoff.c').read_text()
assert old==(a.output/'dcp_handoff.before.c').read_text()
f.write_text(new)
(a.output/'uboot-handoff-trace.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/arch/arm/mach-apple/dcp_handoff.c',tofile='b/arch/arm/mach-apple/dcp_handoff.c')))
print('Prepared persistent bridge refusal evidence')
