# SPDX-License-Identifier: GPL-2.0-only
"""Read frozen drain wrapper source; never edit or execute its main entry point."""
import hashlib
from pathlib import Path
import runpy

FROZEN=Path(__file__).resolve().parent.parent/'gfx-native-powergate-drain'
EXPECTED={
    'run-root-powergate.py':'714727da88a230a35bbee49adfcacb89f7dbd0267688358602c4e73fa28e20c6',
    'run-powergate.py':'5a639cb079b19715b5f1748033e6958a4abcb2fd24ee6e8798e3d39c270e735e',
    'preflight-fresh.py':'b3df956f8f9d794df4855b048a0f05a9cccb7dbc8f72bdec69af7dfafa45a368'}

def source(name):
    path=FROZEN/name
    if hashlib.sha256(path.read_bytes()).hexdigest()!=EXPECTED[name]:
        raise ValueError('Frozen drain wrapper changed: '+name)
    if name=='preflight-fresh.py':
        # Its thin wrapper binds and transforms the exact old preflight source.
        raw=path.read_text()
        import sys
        sys.path.insert(0,str(FROZEN))
        import frozen_wrapper
        namespace={}
        # Parse the literal execute call without evaluating any CLI entry point.
        import ast
        tree=ast.parse(raw)
        call=next(node.value for node in tree.body if isinstance(node,ast.Expr)
                  and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name)
                  and node.value.func.id=='execute')
        args=[ast.literal_eval(value) for value in call.args[:3]]
        return frozen_wrapper.source(*args)
    return runpy.run_path(str(path),run_name='frozen_retained_source')['runner_source']()


def replace_once(text,old,new):
    if text.count(old)!=1:raise ValueError('Retained wrapper insertion changed: '+old[:100])
    return text.replace(old,new,1)
