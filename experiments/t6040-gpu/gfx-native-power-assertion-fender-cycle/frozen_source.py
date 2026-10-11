"""Compose immutable v22 host/runtime scopes without invoking any old main."""
import hashlib, runpy, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'gfx-native-idle-policy-fender-cycle'
PINS={'cold_render_contract.py': '4ff692f39758e4dc4e1cb3f5148d408a9275e616b7bdc8293b4944685a041e09', 'frozen_source.py': 'b61406e5cf62eb905cd14e904ea51aed51258d4dd2ce9f621ab2f5804742d7a7', 'run-cold-render.py': 'c4f4bf3026e4c3dc449dc82c7d6175f3b2a0bfc230f66ec3774713fb24a3e556', 'preflight-fresh.py': '74e18dfeb9e87acd67b1ce4ad2c9182e0be61666414bd2980cc4cf11a15fd90d', 'analyze_cold_render.py': '5c87d5da3f952fbcc4b0591974028a639991bd5818a4ae4c81a20ce1f91a2306', 'readback.py': 'bd4dddc8d0aebbbaf80dad46e41e12143ab5115eb585771631e1de3cb1ed5b40', 'test-host.py': '00a25762773903478639a4c031261d5ae98ed6b6952ebdc03ef510b493b65f1d', 'finalize-cold-render.py': '9139fe6c866f7bc84c8dcfa922c2012a87c0c875651723dbe3a24ca07ebebc03', 'prepare-idle-policy-owner.py': 'a465a6370008c52652284b576de2c600c849ed70a175cc4ee05cae3b8a1e55ff', 'test-idle-policy.py': '35c4bea9ee67777f8ac8c7a8aeb79abbbaca57746d2c0585e5ca825ce1f1eba0', 'gfx-native-idle-policy.h': '48b56d10cd312b09c9200637f0979ef91fdd50aa9b6475c5b1c6e80d919280cc', 'README.md': '5be875ab9673f56e8f0d5730a4d1a7a9d4f37b803584dc7738a9800b975a207e'}
for name,digest in PINS.items():
    if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=digest:
        raise ValueError('Frozen v22 source changed: '+name)
_namespace=runpy.run_path(str(BASE/'frozen_source.py'),run_name='frozen_v22_host_source')
replace_once=_namespace['replace_once']
def source(name):
    text=_namespace['source'](name)
    sys.path.insert(0,str(HERE))
    return text
