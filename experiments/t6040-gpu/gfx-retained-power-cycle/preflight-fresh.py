#!/usr/bin/env python3
"""Read-only fresh owner preflight; refuse every prior consumed boot first."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from retained_wrapper import source

text=source('preflight-fresh.py')
text=text.replace('gfx_native_powergate_drain_contract','gfx_retained_power_cycle_contract')
text=text.replace('powergate-drain-preparation.json','retained-power-cycle-preparation.json')
text=text.replace('m4rch.gfx-native-powergate-drain-preparation.v1','m4rch.gfx-retained-power-cycle-preparation.v1')
text=text.replace('m4rch.gfx-native-powergate-drain-fresh-preflight.v1','m4rch.gfx-retained-power-cycle-fresh-preflight.v1')
exec(compile(text,str(HERE/'preflight-fresh.py'),'exec'),globals())
