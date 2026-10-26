"""Route all loader readers through a bounded G16-aware physical span bridge."""
from pathlib import Path
import re
KIT=Path(__file__).resolve().parent
def wiring(files):
    files['g16_loader_region_v16.rs']=(KIT/'g16_loader_region_v16.rs').read_text()
    files['asahi_m4.rs']=files['asahi_m4.rs'].replace('mod g16;','mod g16;\nmod g16_loader_region_v16;',1)
    pattern=r'(?P<node>(?:self\s*\.dev\s*\.as_ref\(\)\s*\.of_node\(\)\s*\.ok_or\(EINVAL\)\?|dev\s*\.of_node\(\)\s*\.ok_or\(EINVAL\)\?|node|of_node))\s*\.reserved_mem_region_to_resource_byname\((?P<arg>(?:kernel::)?c_str!\("[^"\\]+"\)|name)\)'
    counts={}
    for name in ['g16.rs','g16_runtime.rs','g16_vm.rs','mmu.rs','gpu.rs']:
        files[name],count=re.subn(pattern,lambda m:'crate::g16_loader_region_v16::resource(&'+m['node']+', '+m['arg']+')',files[name])
        counts[name]=count
        if 'reserved_mem_region_to_resource_byname' in files[name]:
            raise ValueError('Unwired loader reader in '+name)
    if counts!={'g16.rs':6,'g16_runtime.rs':1,'g16_vm.rs':1,'mmu.rs':2,'gpu.rs':1}:
        raise ValueError(str(counts))
