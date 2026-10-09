#!/usr/bin/env python3
"""ONE fresh retained-cycle cold owner; never performs an automatic power operation."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from retained_wrapper import source,replace_once


def runner_source():
    text=source('run-root-powergate.py')
    text=text.replace('gfx_native_powergate_drain_contract','gfx_retained_power_cycle_contract')
    text=text.replace('gfx-native-powergate-drain-startup-retained','gfx-retained-power-cycle-startup-retained')
    return text


exec(compile(runner_source(),str(HERE/'run-root-powergate.py'),'exec'),globals())
