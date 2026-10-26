# SPDX-License-Identifier: GPL-2.0-only
"""Compose pinned v11 wrappers without invoking their entry points."""
import hashlib
from pathlib import Path
import runpy

FROZEN=Path(__file__).resolve().parent.parent/'gfx-native-ap-retained-cycle'
EXPECTED={
 'run-root-powergate.py':'e17f91fb809ae7d6bb699a803c94c67ff428e9313f203a6863d1efe15f2da045',
 'run-powergate.py':'e5f94dcabf1d340c73051efdeb1ae84b270f03cc451b84b3282cfc2de054d415',
 'preflight-fresh.py':'2fb0859dd5104eb965dc084d38289ab098d7f630aeea41910cc5fffcef99e88e'}

def namespace(name):
 path=FROZEN/name
 if hashlib.sha256(path.read_bytes()).hexdigest()!=EXPECTED[name]:
  raise ValueError('Frozen AP-retained wrapper changed: '+name)
 return runpy.run_path(str(path),run_name='frozen_native_ap_repeat_source')

def source(name):
 values=namespace(name)
 return values['text'] if name=='preflight-fresh.py' else values['runner_source']()

def replace_once(text,old,new):
 if text.count(old)!=1:raise ValueError('AP repeat insertion changed: '+old[:100])
 return text.replace(old,new,1)

def translate(text):
 return text.replace('gfx_native_ap_retained_cycle','gfx_native_ap_repeat_cycle').replace(
  'gfx-native-ap-retained','gfx-native-ap-repeat').replace('native-ap-retained','native-ap-repeat')
