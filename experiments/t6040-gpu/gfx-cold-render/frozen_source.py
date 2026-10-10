"""Read the frozen v12 launcher source; never invoke its main function."""
import hashlib, runpy, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
FROZEN=HERE.parent/'gfx-native-ap-repeat-cycle'
EXPECTED={'run-root-powergate.py':'8bc63d9176897c40220bbf935128c162677b28645b35aba1179aa59435faa8a9','preflight-fresh.py':'8f522005729550491a005a061b0ccb40c7ea51caeb66192ee1c431f81c2dfb04'}
def replace_once(text,old,new):
 if text.count(old)!=1:raise ValueError('Frozen source insertion differs: '+old[:80])
 return text.replace(old,new,1)
def source(name):
 path=FROZEN/name
 if hashlib.sha256(path.read_bytes()).hexdigest()!=EXPECTED[name]:raise ValueError('Frozen launcher changed: '+name)
 sys.path.insert(0,str(FROZEN))
 namespace=runpy.run_path(str(path),run_name='frozen_cold_render_source')
 return namespace['runner_source']() if name.startswith('run-root') else namespace['text']
