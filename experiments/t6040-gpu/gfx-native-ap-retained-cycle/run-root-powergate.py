#!/usr/bin/env python3
"""ONE fresh distinct native idle-cycle owner; no automatic power command."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from ap_retained_cycle_wrapper import source


def runner_source():
    text=source('run-root-powergate.py')
    text=text.replace('gfx_native_running_cycle_contract','gfx_native_ap_retained_cycle_contract')
    text=text.replace('gfx-native-running-cycle-startup-retained','gfx-native-ap-retained-cycle-startup-retained')
    return text


exec(compile(runner_source(),str(HERE/'run-root-powergate.py'),'exec'),globals())
