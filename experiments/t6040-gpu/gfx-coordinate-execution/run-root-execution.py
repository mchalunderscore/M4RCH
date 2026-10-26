#!/usr/bin/env python3
"""Cold paired coordination with conditional retained execution; no reboot."""
import hashlib
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'gfx-native-coordinate-trial/run-root-coordinate.py'
BASE_SHA = '70374782e554472e2d949b2cb0fe7ffe35e8cac5a8a159e4cf7cfc3daba18292'
sys.path.insert(0, str(HERE))


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Cold execution insertion point changed: ' + old[:80])
    return source.replace(old, new, 1)


def runner_source():
    if hashlib.sha256(BASE.read_bytes()).hexdigest() != BASE_SHA:
        raise ValueError('Frozen coordinator cold runner changed')
    source = runpy.run_path(str(BASE))['runner_source']()
    source = replace_once(source,
        'from gfx_coordinate_contract import validate_receipt, qualify_adt, qualify_linux_dt, qualify_graph_startup',
        'from gfx_execution_contract import validate_receipt, qualify_adt, qualify_linux_dt, qualify_graph_startup')
    source = replace_once(source, "parent/'run-coordinate.py'", "parent/'run-execution.py'")
    source = replace_once(source, 'from gfx_coordinate_contract import qualify_startup_retention',
                          'from gfx_execution_contract import qualify_startup_retention')
    source = replace_once(source,
        "report['interpretation']='Retained no-work GFX power-off scope. Sample/gfx-snapshot and packet-free stop precede one terminal gfx-poweroff; afterwards only PMGR/DRAM diagnostics. All backing and mappings retained; OFF does not prove DMA retirement or restart safety.'",
        "report['interpretation']='Distinct retained coordinated execution profile. Healthy recovery permits another two idle cycles, native trace-off, then one immutable triangle. Failed idle recovery permits only diagnostics, one STOP and eligible no-work OFF. Work intent closes STOP/OFF and all later publication. No retirement/restart/unload proof.'")
    source = replace_once(source,
        "print('Retained GFX power-off scope ready. Stop before one terminal gfx-poweroff. All backing and mappings pinned; no restart, work submission or unload.')",
        "print('Distinct coordinator retained. Inspect recovery result: healthy session may complete four idle cycles and trace-off before one triangle; failed recovery remains diagnostic with eligible no-work OFF. All backing pinned; no restart or unload.')")
    return source


exec(compile(runner_source(), str(BASE), 'exec'), globals())
