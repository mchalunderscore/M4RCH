#!/usr/bin/env python3
"""Persist exact loader refusals into /chosen after transactional rollback."""
import argparse
import difflib
from pathlib import Path
import shutil

KIT=Path(__file__).resolve().parent

def prepare(root,output):
    p=root/'src/kboot.c';before=p.read_text()
    old='''        if (dt_set_j614s_dcp_handoff())
            printf("DCP001: live display handoff refused; keeping the boot framebuffer\\n");
        return 0;'''
    new='''        int result = dt_set_j614s_dcp_handoff();
        /* Publish AFTER the helper restored its DT snapshot on refusal. */
        if (j614s_dcp_publish_trace(result)) {
            printf("DCP004: cannot preserve handoff evidence in control tree\\n");
            return -1;
        }
        if (result)
            printf("DCP001: live display handoff refused; keeping the boot framebuffer\\n");
        return 0;'''
    assert before.count(old)==1
    after=before.replace(old,new);p.write_text(after)
    header=root/'src/j614s-dcp.h';oldheader=header.read_text()
    shutil.copyfile(KIT/'loader/j614s-dcp.h',header)
    output.mkdir(parents=True,exist_ok=True)
    patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/src/kboot.c',tofile='b/src/kboot.c'))
    patch+=''.join(difflib.unified_diff(oldheader.splitlines(True),header.read_text().splitlines(True),fromfile='a/src/j614s-dcp.h',tofile='b/src/j614s-dcp.h'))
    (output/'m1n1-handoff-trace.patch').write_text(patch)
    print('Prepared persistent DCP004 loader admission evidence')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();prepare(a.root,a.output)
