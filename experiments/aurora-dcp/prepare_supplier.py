#!/usr/bin/env python3
"""Complete the J614s PMP report topology and native supplier readiness."""
import argparse
import difflib
from pathlib import Path

KIT=Path(__file__).resolve().parent


def prepare(root, output):
    output.mkdir(parents=True,exist_ok=True)
    targets={'drivers/soc/apple/j614s-display-boot.c':(KIT/'kernel/j614s-display-boot.c').read_text()}
    rel='drivers/pmdomain/apple/pmp-report.c';text=(root/rel).read_text()
    old='\tint ret;\n\n\tif (!np || !of_device_is_compatible(np, t8132 ?\n\t\t"apple,t8132-pmp-v2-report" : "apple,j613-25g83-pmp-report")) {'
    new='''\tbool t6041 = of_machine_is_compatible("apple,j614s") &&
\t\tof_machine_is_compatible("apple,t6040") &&
\t\tof_device_is_compatible(supplier->of_node, "apple,t6041-pmp-v2");
\tint ret;

\tif (!np || !of_device_is_compatible(np, t8132 ?
\t\t"apple,t8132-pmp-v2-report" : t6041 ?
\t\t"apple,t6041-pmp-v2-report" : "apple,j613-25g83-pmp-report")) {'''
    assert text.count(old)==1;text=text.replace(old,new)
    old='''\telse
\t\tret = readq_poll_timeout(rep->base + rep->offsets->status, status,
\t\t\t\t\tt8132 ? (status & PMP_REPORT_READY) : status == PMP_REPORT_READY,
\t\t\t\t\t1000, timeout_ms * 1000);'''
    new='''\telse if (!timeout_ms) {
\t\t/* A readiness check with no wait must never poll forever. */
\t\tstatus = readq(rep->base + rep->offsets->status);
\t\tret = (t6041 ? !!status : t8132 ? !!(status & PMP_REPORT_READY) :
\t\t\tstatus == PMP_REPORT_READY) ? 0 : -EAGAIN;
\t} else
\t\tret = readq_poll_timeout(rep->base + rep->offsets->status, status,
\t\t\t\t\tt6041 ? status : t8132 ? (status & PMP_REPORT_READY) :
\t\t\t\t\tstatus == PMP_REPORT_READY,
\t\t\t\t\t1000, timeout_ms * 1000);'''
    assert text.count(old)==1;targets[rel]=text.replace(old,new)
    patch=[]
    for rel,after in targets.items():
        path=root/rel;before=path.read_text();assert before!=after
        (output/(path.name+'.before')).write_text(before)
        patch.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
        path.write_text(after);(output/path.name).write_text(after)
    (output/'kernel-supplier.patch').write_text(''.join(patch))
    print('Prepared native PMP report link and T6041 readiness; existing owner and removal locking retained')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();prepare(a.root,a.output)
