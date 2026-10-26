# SPDX-License-Identifier: GPL-2.0-only
"""Read-only composition from the exact finalized v8 Python family."""
import hashlib
from pathlib import Path
import runpy

FROZEN=Path(__file__).resolve().parent.parent/'gfx-native-retained-cycle'
EXPECTED={
 'run-root-powergate.py':'d4f5c01c0665219ddea546e527f8852dba9ab34bc2b8ceee82df5de2d259d410',
 'run-powergate.py':'0d46f3f0b1e18589ea4ad2dc630dc5fae2b8e42ef179ff70d48bacdc5c3dfad5',
 'preflight-fresh.py':'b0bf9ad970acf4de0217f6b0ac01afae3c863c5fe46392021b59b7396e6f9366'}

def source(name):
 path=FROZEN/name
 if hashlib.sha256(path.read_bytes()).hexdigest()!=EXPECTED[name]:
  raise ValueError('Frozen native retained-cycle wrapper changed: '+name)
 namespace=runpy.run_path(str(path),run_name='frozen_native_idle_source')
 return namespace['text'] if name=='preflight-fresh.py' else namespace['runner_source']()

def replace_once(text,old,new):
 if text.count(old)!=1:raise ValueError('Native idle-cycle insertion changed: '+old[:100])
 return text.replace(old,new,1)
