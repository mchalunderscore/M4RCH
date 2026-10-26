#!/usr/bin/env python3
from pathlib import Path
import shutil,subprocess,sys
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[1];out=ROOT/'out/aurora-audio/r13';out.mkdir(exist_ok=True)
root=Path(sys.argv[1]);d=root/'arch/arm/mach-apple'
for n in ['control.dtb','template.dtb','m1n1.bin','uboot.config','serial.Makefile']:shutil.copyfile(ROOT/'out/aurora-audio/r12'/n,out/n)
# Run the existing upstream publisher; Linux still receives the speaker-free template.
subprocess.run(['fdtput','-t','s',str(out/'control.dtb'),'/aop@510600000','status','okay'],check=True)
shutil.copyfile(KIT/'aop_standard_handoff.c',d/'aop_standard_handoff.c')
p=d/'aurora-handoff.c';s=p.read_text();anchor='#include "peripheral_handoff.c"';assert s.count(anchor)==1
s=s.replace(anchor,anchor+'\n#include "aop_standard_handoff.c"')
assert s.count('aop_error = aop_handoff(out, adt, ready);')==1
s=s.replace('aop_error = aop_handoff(out, adt, ready);','aop_error = aop_standard_handoff(out, live, ready);')
# Preserve firmware metadata for diagnosis without asking for another blind test.
anchor='\taop_error = aop_standard_handoff(out, live, ready);'
s=s.replace(anchor,'''\tint anode = adt_named(adt, "aop");
\tu32 alen;
\tconst u8 *aprop = adt_prop(adt, anode, "segment-ranges", &alen);
\tif (aprop && alen <= 1024) CHECK(fdt_setprop(out, fdt_path_offset(out, "/chosen"), "m4rch,aop-segment-ranges", aprop, alen));
\taprop = adt_prop(adt, anode, "segment-names", &alen);
\tif (aprop && alen <= 256) CHECK(fdt_setprop(out, fdt_path_offset(out, "/chosen"), "m4rch,aop-segment-names", aprop, alen));
'''+anchor)
p.write_text(s)
sys.path.insert(0,str(ROOT/'experiments/aurora-dcp'))
from prepare_uboot import refresh_template
refresh_template(root,out)
