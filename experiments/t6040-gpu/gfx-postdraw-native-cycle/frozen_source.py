"""Read the frozen v12 launcher source; never invoke its main function."""
import hashlib, runpy, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
FROZEN=HERE.parent/'gfx-native-ap-repeat-cycle'
V13=HERE.parent/'gfx-cold-render'
V13_PINS={'cold_render_contract.py': 'e53c9ee7488cf10d26d6c21eb17b99a16958793d122549a0133a67077249f89f', 'frozen_source.py': 'a3956bf489f8d30397a13bbac0c831699f2fa67265b2368cc129348b2f35d831', 'run-cold-render.py': '16bfa448d4011ccaef347c5b1ce8d08593c45dda2f4dac4f4266c56bc77694a4', 'preflight-fresh.py': '6d8837a86ebc917ce68fa95ee90792093359d0afd1a396089c3499a783fd6d61', 'analyze_cold_render.py': '29f8cf50594dbb5af352303fde6c3e4401ef3765087c6199f22ed50a9826dd7d', 'readback.py': '09c0b012ff2b85496f684c08cf4770ef935e17ec071e2e13a1cd0b2acc5d7e43', 'finalize-cold-render.py': '3c19e68f5c765d132f111cb2f54b7659c15f07681fea2241553d5735f773796b', 'test-host.py': '74717bba2f26ce752097b363f9a909253dc36ee13c70946da8064fb170d3e302'}
for v13_name,v13_hash in V13_PINS.items():
 if hashlib.sha256((V13/v13_name).read_bytes()).hexdigest()!=v13_hash:raise ValueError('Frozen v13 source changed: '+v13_name)
V14=HERE.parent/'gfx-cold-render-pause-release'
V14_PINS={'cold_render_contract.py': '8b18bf86579b4ae98a5adc50b8771e70a1ddd74c07ed5c38bffc46cde3761286', 'frozen_source.py': 'be93cfcd6798f996424520c0a8a89615779198460f4c0ade55743c60aaaba623', 'run-cold-render.py': 'd27a43cda23c120c8ea267613b6926c0ca9eae385091e131b624d7b8a7e7df42', 'preflight-fresh.py': '84a5c7e714754aace9783f8f9b42f810a5ed45e869d0d935d990e8e92d6598df', 'analyze_cold_render.py': '430858d6224b6512699113753c0a7230c1c647379fe64eec19afccb7163663b8', 'readback.py': '09c0b012ff2b85496f684c08cf4770ef935e17ec071e2e13a1cd0b2acc5d7e43', 'finalize-cold-render.py': '7040fe66a621e51dbeeb722cce278d43c6af47531b5d4796be9bae4ef49de8f6', 'test-host.py': 'a95144aa0afd92ce2a716169ebc7b2862f341e4ac4ecdf871f1dcc17c047becf'}
for name,h in V14_PINS.items():
 if hashlib.sha256((V14/name).read_bytes()).hexdigest()!=h:raise ValueError('Frozen v14 source changed: '+name)
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

V15=HERE.parent/'gfx-native-dispatch-contract'
V15_PINS={'cold_render_contract.py': '9e8fc0ef44dfe6607cba4312e3bc4c7a2018b903c738304ee901d2735b4d63c5', 'frozen_source.py': '649f61f3e09f5b8c0c32104859a09ac345250bf7b37a79fa75e70246a663cd7f', 'run-cold-render.py': 'fd4f360dc262f113160290cc04e95ef64872077d977b2d3070352a3bfe4e2330', 'preflight-fresh.py': 'b80d66421fdae747107af4d7d5f5357da7222a780272eccebc5865fed8e031e3', 'analyze_cold_render.py': '4b98aaccef6f0d929b70c40621cec4215f6c6ab2c2e97216c6c88b39190354f2', 'readback.py': 'ad575cb76a0dd930f4bbda59c7f78294546250bae41a45efaede2c3d56c4581f', 'finalize-cold-render.py': 'f503ccbff8e2f7a420c71862bf24cd3030c7d5440d42a44eb19047dc18cfa8c5', 'test-host.py': 'da30d2c92ac13e8dbc31fa4b940fef3c0a99b9126c3d28c609c195793956e09c'}
for name,h in V15_PINS.items():
 if hashlib.sha256((V15/name).read_bytes()).hexdigest()!=h:raise ValueError('Frozen v15 source changed: '+name)
