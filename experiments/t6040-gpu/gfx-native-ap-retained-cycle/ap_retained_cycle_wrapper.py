# SPDX-License-Identifier: GPL-2.0-only
"""Read-only composition from the frozen v10 wrappers; no hardware at import."""
import hashlib
from pathlib import Path
import runpy
FROZEN=Path(__file__).resolve().parent.parent/'gfx-native-running-cycle'
EXPECTED={
 'run-root-powergate.py':'a81999a4079245f04c7bd34b2617532638c4fb1ab7fb6332486787ad4940c697',
 'run-powergate.py':'0dac8cfbcbbf140fabe5efdded5af93910414e27727030425523b7b2eec0d716',
 'preflight-fresh.py':'5cd7e436ecf8ec46c7c31cddb34de1cfd1e2f31d622ffe845133da409502d350'}
def source(name):
 path=FROZEN/name
 if hashlib.sha256(path.read_bytes()).hexdigest()!=EXPECTED[name]:
  raise ValueError('Frozen Running-cycle wrapper changed: '+name)
 namespace=runpy.run_path(str(path),run_name='frozen_native_ap_retained_source')
 return namespace['text'] if name=='preflight-fresh.py' else namespace['runner_source']()
def replace_once(text,old,new):
 if text.count(old)!=1:raise ValueError('AP retained-cycle insertion changed: '+old[:100])
 return text.replace(old,new,1)
