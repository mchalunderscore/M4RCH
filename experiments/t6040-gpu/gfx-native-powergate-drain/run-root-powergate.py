#!/usr/bin/env python3
"""ONE fresh cold drain owner, retaining all backing; no automatic control."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from frozen_wrapper import execute

execute('run-root-powergate.py', 'a30decfbc6f9a155a1232f26bd61c548815b3e5023044133927c5d8051fe45b5', [
    ('gfx_native_powergate_contract', 'gfx_native_powergate_drain_contract', 1),
    ('REFUSED_BOOT', 'REFUSED_BOOTS', 2),
    ('boot != REFUSED_BOOTS', 'boot not in REFUSED_BOOTS', 1),
    ('gfx-native-powergate-startup-retained', 'gfx-native-powergate-drain-startup-retained', 1),
], globals())
