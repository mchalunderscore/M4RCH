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

V17=HERE.parent/'gfx-postdraw-native-nmi-cycle'
V17_PINS={'cold_render_contract.py': '7747ea05fd027e6f6207bec449b1783bf278efa328019744f3518d46381015ab', 'frozen_source.py': 'c4870d2d98bed1622ff05e1ba0fe8ce717e494169175213888f5480245c80ab5', 'run-cold-render.py': 'c4f4bf3026e4c3dc449dc82c7d6175f3b2a0bfc230f66ec3774713fb24a3e556', 'preflight-fresh.py': 'a91f60b005e4deb63da798528edbb972867fa3b6af9c43b2dfd2aa3497bcccd8', 'analyze_cold_render.py': '33f9c9090b28c92d3b7cd2ae84a75d44bdd7ecae8517cff26513f9f880bd7f59', 'readback.py': '1406319fcf128800fa973e65a641d7b0408177e40a0ade796211fb869fe5f4a5', 'test-host.py': '895a5791a07d62da2ee6fe0a44b218086792987b8bec8c3374cf4d7f625bb7cd', 'finalize-cold-render.py': 'db3d5cea82bc88719504c86176e2a53ad0a5562bed8004a8c7868347ad9287d8'}
for name,h in V17_PINS.items():
 if hashlib.sha256((V17/name).read_bytes()).hexdigest()!=h:raise ValueError('Frozen v17 source changed: '+name)

V18=HERE.parent/'gfx-native-fender-draw-cycle'
V18_PINS={'cold_render_contract.py': 'f569e2cce94701f2c6e23a18dccd3059d6a024951cc2128b3326ddd10e914454', 'frozen_source.py': '85190a7723d14e90b8b0ddb4aa4bfe80ec61a5fc4ec4a3bded2b6c28adcfc541', 'run-cold-render.py': 'c4f4bf3026e4c3dc449dc82c7d6175f3b2a0bfc230f66ec3774713fb24a3e556', 'preflight-fresh.py': 'a6715054bd72c82f000ac7e534cc29d8d6ce07fb3e3d869d6617a95fc5469846', 'analyze_cold_render.py': '1c30a606b27906756dce433dda6d610228651806c5c41272a8067e1c4f4a13c2', 'readback.py': '1406319fcf128800fa973e65a641d7b0408177e40a0ade796211fb869fe5f4a5', 'test-host.py': '20ae46ec51b5056a1b0faa3687e7c54c693bd1e2abc4e1b0abf853e1113e1d54', 'finalize-cold-render.py': 'e44a4b04c09fe6d950be055fa2660f9b581d307ce4ef368526cd62fc0b51e37c'}
for name,h in V18_PINS.items():
 if hashlib.sha256((V18/name).read_bytes()).hexdigest()!=h:raise ValueError('Frozen v18 source changed: '+name)

V19=HERE.parent/'gfx-native-fender-runtime-cycle'
V19_PINS={'cold_render_contract.py': '22bc38f7889c3da09a12b2544fc5d5f21547fd3f742726fc1b6579fcb566e4c7', 'frozen_source.py': 'aa5fc1f62376a20b204e6aacd7662a485ba396d778d1829b5c6a7bda096a352e', 'run-cold-render.py': 'c4f4bf3026e4c3dc449dc82c7d6175f3b2a0bfc230f66ec3774713fb24a3e556', 'preflight-fresh.py': 'c4a6d4973f809b8715e2f725b88fb4e1be34291811299aba6e1fa3bef02fb887', 'analyze_cold_render.py': '0f109c7c55e49afb751db29197dfce888ff8068e0014487fedbf436dc026bd7a', 'readback.py': '5ac33eccf5d68159ad51730c14b92950ee08dec23e83c3089a7c2881e229763f', 'test-host.py': '70e3daca31c9120ac4da4c576231cd8ef62735490cbe39aa481fbb2811769567', 'finalize-cold-render.py': '460b4fffbbe845ff756c6d6b549ed926e4fa457f74618179d295a6cb6df3fd4e'}
for name,h in V19_PINS.items():
 if hashlib.sha256((V19/name).read_bytes()).hexdigest()!=h:raise ValueError('Frozen v19 source changed: '+name)

V20=HERE.parent/'gfx-native-fender-off-cycle'
V20_PINS={'cold_render_contract.py': '6f84af009785951d65ca217272b37a83e8e83ffd01eb59ad153a301737635321', 'frozen_source.py': '1a611f5c2d3f76757f7ba819726d7c8c00e2cd86c8a6ded564875553ea4c20c0', 'run-cold-render.py': 'c4f4bf3026e4c3dc449dc82c7d6175f3b2a0bfc230f66ec3774713fb24a3e556', 'preflight-fresh.py': '81542854229259c2d54ee1eb89e86e75a8de17f19e8ba0012c28e98b308ad1b5', 'analyze_cold_render.py': '8cbc50f38800942e01c24a9ca359086cf54f7c2b4123fbe728920adccd734b8a', 'readback.py': '9541f79a856297ea36d1c2458912b18f867c84f70cdc3e44474ae1792ce970a0', 'test-host.py': 'b93d7f164ac3c45230aa262f2f804424de954fca5116219d122e855b5911cafc', 'finalize-cold-render.py': '2a6fc8c6e1bbf0c50b73e412a834171d3f2ad31214b1bfca011670c85e92336d'}
for name,h in V20_PINS.items():
 if hashlib.sha256((V20/name).read_bytes()).hexdigest()!=h:raise ValueError('Frozen v20 source changed: '+name)
