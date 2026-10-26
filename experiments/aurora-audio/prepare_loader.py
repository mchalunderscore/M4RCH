#!/usr/bin/env python3
from pathlib import Path
import shutil,subprocess,sys
KIT=Path(__file__).resolve().parent;ROOT=KIT.parents[1]
root=Path(sys.argv[1]);out=ROOT/'out/aurora-audio/r12';out.mkdir(exist_ok=True)
for name in ['control.dtb','template.dtb','m1n1.bin','uboot.config','serial.Makefile']:
 shutil.copyfile(ROOT/'out/aurora-audio/r11'/name,out/name)
for name in ['control.dtb','template.dtb']:
 path=out/name;node='/aop@510600000/audio'
 cells=subprocess.check_output(['fdtget','-t','x',str(path),node,'dmas'],text=True).split()
 assert len(cells)==10
 keep=cells[:2]+cells[6:]
 subprocess.run(['fdtput','-t','x',str(path),node,'dmas',*keep],check=True)
 subprocess.run(['fdtput','-t','s',str(path),node,'dma-names','dma','cout','cin'],check=True)
 textnode=subprocess.check_output(['fdtget',str(path),'/aliases','disp0_piodma'],text=True).strip()
 subprocess.run(['fdtput','-t','s',str(path),'/aliases','disp0-piodma',textnode],check=True)
directory=root/'arch/arm/mach-apple'
shutil.copyfile(KIT/'gpu_text_handoff.c',directory/'gpu_text_handoff.c')
p=directory/'aurora-handoff.c';s=p.read_text()
anchor='#include "peripheral_handoff.c"'
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'\n#include "gpu_text_handoff.c"')
anchor='\tCHECK(gpu_dependencies(dt, 1));';assert s.count(anchor)==1
s=s.replace(anchor,'\tCHECK(gpu_text_handoff(dt, adt));\n'+anchor)
p.write_text(s)
sys.path.insert(0,str(ROOT/'experiments/aurora-dcp'))
from prepare_uboot import refresh_template
refresh_template(root,out)
