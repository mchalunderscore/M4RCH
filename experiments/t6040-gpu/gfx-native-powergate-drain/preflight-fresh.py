#!/usr/bin/env python3
"""Read-only fresh drain-owner preflight; refuses both retained owner boots."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from frozen_wrapper import execute

execute('preflight-fresh.py', '77a8ac5d2a9276c862cd81ed4474bfaf5c8f09b5b0c15d3192419f8eb5b6f110', [
    ('gfx_native_powergate_contract', 'gfx_native_powergate_drain_contract', 1),
    ('REFUSED_BOOT', 'REFUSED_BOOTS', 2),
    ('boot != REFUSED_BOOTS', 'boot not in REFUSED_BOOTS', 1),
    ('powergate-preparation.json', 'powergate-drain-preparation.json', 1),
    ('m4rch.gfx-native-powergate-preparation.v1', 'm4rch.gfx-native-powergate-drain-preparation.v1', 1),
    ('m4rch.gfx-native-powergate-fresh-preflight.v1', 'm4rch.gfx-native-powergate-drain-fresh-preflight.v1', 1),
    ('Retained 94cb owner boot refused', 'Retained old owner boot refused', 1),
], globals())
