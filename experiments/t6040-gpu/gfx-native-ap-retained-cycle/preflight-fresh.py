#!/usr/bin/env python3
"""Read-only fresh native idle-cycle preflight; all consumed boots refused."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from ap_retained_cycle_wrapper import source

text=source('preflight-fresh.py')
text=text.replace('gfx_native_running_cycle_contract','gfx_native_ap_retained_cycle_contract')
text=text.replace('native-running-cycle-preparation.json','native-ap-retained-cycle-preparation.json')
text=text.replace('m4rch.gfx-native-running-cycle-preparation.v1','m4rch.gfx-native-ap-retained-cycle-preparation.v1')
text=text.replace('m4rch.gfx-native-running-cycle-fresh-preflight.v1','m4rch.gfx-native-ap-retained-cycle-fresh-preflight.v1')
exec(compile(text,str(HERE/'preflight-fresh.py'),'exec'),globals())
