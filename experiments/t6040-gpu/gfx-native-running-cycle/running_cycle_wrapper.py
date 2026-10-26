# SPDX-License-Identifier: GPL-2.0-only
"""Read-only composition from the exact finalized v9 Python family."""
import hashlib
from pathlib import Path
import runpy

FROZEN=Path(__file__).resolve().parent.parent/'gfx-native-idle-cycle'
EXPECTED={
 'run-root-powergate.py':'9b114ffa72ca5c0f06476ff80e9b1ff5530f6dbe735e3e893ed7b1142f13dc0d',
 'run-powergate.py':'565b5687ed981594d5e26fe984bff90b1c3c64a8da0725a820c5e95398638f6b',
 'preflight-fresh.py':'5d6c269170b169c404c7b2ed8dd504dfc07a92d3a540c32fe5111967ed063a43'}

def source(name):
 path=FROZEN/name
 if hashlib.sha256(path.read_bytes()).hexdigest()!=EXPECTED[name]:
  raise ValueError('Frozen native retained-cycle wrapper changed: '+name)
 namespace=runpy.run_path(str(path),run_name='frozen_native_running_source')
 return namespace['text'] if name=='preflight-fresh.py' else namespace['runner_source']()

def replace_once(text,old,new):
 if text.count(old)!=1:raise ValueError('Native running-cycle insertion changed: '+old[:100])
 return text.replace(old,new,1)
