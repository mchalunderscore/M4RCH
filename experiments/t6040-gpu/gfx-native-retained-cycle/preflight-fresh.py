#!/usr/bin/env python3
"""Read-only fresh native retained-cycle preflight; all consumed boots refused."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_retained_wrapper import source

text=source('preflight-fresh.py')
text=text.replace('gfx_retained_power_cycle_contract','gfx_native_retained_cycle_contract')
text=text.replace('retained-power-cycle-preparation.json','native-retained-cycle-preparation.json')
text=text.replace('m4rch.gfx-retained-power-cycle-preparation.v1','m4rch.gfx-native-retained-cycle-preparation.v1')
text=text.replace('m4rch.gfx-retained-power-cycle-fresh-preflight.v1','m4rch.gfx-native-retained-cycle-fresh-preflight.v1')
exec(compile(text,str(HERE/'preflight-fresh.py'),'exec'),globals())
