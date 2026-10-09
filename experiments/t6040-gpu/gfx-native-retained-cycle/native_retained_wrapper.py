# SPDX-License-Identifier: GPL-2.0-only
"""Read-only source composition from the exact finalized prior Python family."""
import hashlib
from pathlib import Path
import runpy

FROZEN=Path(__file__).resolve().parent.parent/'gfx-retained-power-cycle'
EXPECTED={
 'run-root-powergate.py':'dd0ea64980de5f195fb16d9ba2dd1e8c13ae5d94a690f28ecc7257f7ef054029',
 'run-powergate.py':'08660f6def60a6d37b43acb692b04dee1b412e86b8211f20883f58f8d3f5735f',
 'preflight-fresh.py':'e7d28ee5229d7a1e94135db59ffc2ca7d214379f22d9bc1acc4bfa52b600c901'}

def source(name):
    path=FROZEN/name
    if hashlib.sha256(path.read_bytes()).hexdigest()!=EXPECTED[name]:
        raise ValueError('Frozen retained-cycle wrapper changed: '+name)
    namespace=runpy.run_path(str(path),run_name='frozen_native_retained_source')
    return namespace['text'] if name=='preflight-fresh.py' else namespace['runner_source']()


def replace_once(text,old,new):
    if text.count(old)!=1:raise ValueError('Native retained-cycle insertion changed: '+old[:100])
    return text.replace(old,new,1)
