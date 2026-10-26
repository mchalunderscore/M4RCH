"""Compose frozen v21/v20 launch scopes without invoking any old main."""
import hashlib, runpy, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'gfx-native-descriptor-fender-cycle'
PINS={'cold_render_contract.py': '189c4527eaa721c1c413da6c7e95130197ca5737650eef44ef9d0ddcca85ec35', 'frozen_source.py': '9bde688b29ed2858661efb85cbcbde1a024f0ad563f8c01ceef1626012541461', 'run-cold-render.py': 'c4f4bf3026e4c3dc449dc82c7d6175f3b2a0bfc230f66ec3774713fb24a3e556', 'preflight-fresh.py': '1de28644deaa2475c2d6184626550b91d010032508b9f08d4039b38c180a1d32', 'analyze_cold_render.py': '32fca44c30279eafe4c997298d0c762ed36aaa86b21243f0e5f6ba74a22f715f', 'readback.py': '9541f79a856297ea36d1c2458912b18f867c84f70cdc3e44474ae1792ce970a0', 'test-host.py': 'acbdaacd4bdd45559072e1723a16d064bfc2eff71a97be7fb9fdef12fe9cecae', 'finalize-cold-render.py': 'e2f991946dec518d939f72129f0b9f8a9b97be4bb2545679e1237762635f48a5', 'prepare-descriptor-owner.py': '66490bf3eacde09d5b2829dec6811160edb7b9f183f48104881fba60e22e4928', 'qualify-descriptors.py': '45d4958c9ced7ddf2ec26e962723a35ae04035da8d04cf2490ef720e5061a200', 'README.md': '95e2bf16a4220cb464802dbe3a6f22d05c90af68dec72c2a634c667989c4cc15'}
for name,digest in PINS.items():
    if hashlib.sha256((BASE/name).read_bytes()).hexdigest()!=digest:
        raise ValueError('Frozen v21 source changed: '+name)
_namespace=runpy.run_path(str(BASE/'frozen_source.py'),run_name='frozen_v21_host_source')
replace_once=_namespace['replace_once']
def source(name):
    text=_namespace['source'](name)
    # The saved source provider adds its legacy library path. Restore the
    # current kit before the generated runner imports its host contract.
    sys.path.insert(0,str(HERE))
    return text
