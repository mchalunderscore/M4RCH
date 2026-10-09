#!/usr/bin/env python3
"""ONE fresh distinct native idle-cycle owner; no automatic power command."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from idle_cycle_wrapper import source


def runner_source():
    text=source('run-root-powergate.py')
    text=text.replace('gfx_native_retained_cycle_contract','gfx_native_idle_cycle_contract')
    text=text.replace('gfx-native-retained-cycle-startup-retained','gfx-native-idle-cycle-startup-retained')
    return text


exec(compile(runner_source(),str(HERE/'run-root-powergate.py'),'exec'),globals())
