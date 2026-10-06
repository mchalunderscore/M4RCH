#!/usr/bin/env python3
"""Modify upstream ZA/ZT tests only at their voluntary yield syscall."""
import argparse
from pathlib import Path

def transform(text, kind):
    old=('\tmov\tx8, #__NR_sched_yield\t// encourage preemption\n1:\n\tsvc\t#0' if kind=='za' else '\tmov\tx8, #__NR_sched_yield\t// Encourage preemption\n\tsvc\t#0')
    if text.count(old)!=1:raise ValueError('Upstream syscall checkpoint changed')
    new='''\t// m4rch: allow the selected CPU to idle with ZA/ZT live.
\tsub\tsp, sp, #16
\tstr\txzr, [sp]
\tldr\tx0, =20000000
\tstr\tx0, [sp, #8]
\tmov\tx0, sp
\tmov\tx1, xzr
\tmov\tx8, #__NR_nanosleep
\tsvc\t#0
\tadd\tsp, sp, #16'''
    return text.replace(old,new)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('kind',choices=('za','zt'));p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.write_text(transform(a.source.read_text(),a.kind))
