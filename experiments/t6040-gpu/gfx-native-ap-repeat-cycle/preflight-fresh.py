#!/usr/bin/env python3
"""Read-only v12 preflight, refusing consumed boots before candidate reads."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from ap_repeat_cycle_wrapper import source,replace_once,translate
text=translate(source('preflight-fresh.py'))
text=replace_once(text,"    candidate = args.candidate.resolve()\n    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()",
 "    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()\n    require(bool(boot) and boot not in REFUSED_BOOTS,'Consumed boot refused before candidate or live reads')\n    candidate = args.candidate.resolve()")
exec(compile(text,str(HERE/'preflight-fresh.py'),'exec'),globals())
