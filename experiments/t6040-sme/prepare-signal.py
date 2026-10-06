#!/usr/bin/env python3
"""Create two diagnostic SSVE handlers for SME-only CPUs (not a kernel fix)."""
from pathlib import Path
import argparse

def transform(source,streaming):
    start=source.index('function irritator_handler');end=source.index('endfunction',start)
    block=source[start:end]
    if block.count('\tptrue\tp0.d')!=1 or block.count('\tret')!=1:raise ValueError('Unexpected upstream handler')
    if streaming:
        block=block.replace('\tptrue\tp0.d','\tsmstart_sm\t// Keep NEON clobbers in SM=0; enable streaming for PTRUE.\n\tptrue\tp0.d')
        block=block.replace('\tret','\tsmstop\t\t// sigreturn restores interrupted state.\n\tret')
    else:block=block.replace('\tptrue\tp0.d','\t// Omit non-streaming SVE predicate clobber on an SME-only CPU.')
    return source[:start]+block+source[end:]
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--streaming',action='store_true');a=p.parse_args();a.output.write_text(transform(a.source.read_text(),a.streaming))
