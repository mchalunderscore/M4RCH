#!/usr/bin/env python3
"""Fresh v12 cold owner startup; no automatic retained command."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from ap_repeat_cycle_wrapper import source,replace_once,translate

def runner_source():
 text=translate(source('run-root-powergate.py'))
 text=replace_once(text,'args = p.parse_args()',"args = p.parse_args()\n    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()\n    require(bool(boot) and boot not in REFUSED_BOOTS, 'Consumed boot refused before candidate or live reads')")
 text=replace_once(text,"    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()\n    require(boot not in REFUSED_BOOTS,",'    require(boot not in REFUSED_BOOTS,')
 return text
exec(compile(runner_source(),str(HERE/'run-root-powergate.py'),'exec'),globals())
