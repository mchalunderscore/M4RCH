#!/usr/bin/env python3
"""Only3 typed commands, distinct schema and durable one-use terminal intent."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from frozen_wrapper import execute

execute('run-powergate.py', 'e42f774e6fa7b5434ae6172b0b462487effdc61abc3344ce68c20fe0a2bdd85e', [
    ('gfx_native_powergate_contract', 'gfx_native_powergate_drain_contract', 2),
    ('gfx_native_powergate_scope', 'gfx_native_powergate_drain_scope', 2),
    ('m4rch.gfx-native-powergate-operation.v1', 'm4rch.gfx-native-powergate-drain-operation.v1', 2),
    ("    source = runpy.run_path(str(BASE))['runner_source']()\n",
     "    source = runpy.run_path(str(BASE))['runner_source']()\n"
     "    source = replace_once(source, 'def validate(work, boot):\\n', "
     "'def validate(work, boot):\\n    from gfx_native_powergate_drain_contract import REFUSED_BOOTS\\n"
     "    require(boot not in REFUSED_BOOTS, \\\"Retained old owner boot refused\\\")\\n')\n", 1),
], globals())
