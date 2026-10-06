#!/usr/bin/env python3
"""Decode captured macOS GPU metadata without hardware access or inferred voltages."""
import argparse,json,plistlib,struct
from pathlib import Path

def nodes(value):
    if isinstance(value,dict):
        if 'IORegistryEntryName' in value:yield value
        for child in value.values():yield from nodes(child)
    elif isinstance(value,list):
        for child in value:yield from nodes(child)

def uint(node,key,width=4):
    raw=node[key]
    if not isinstance(raw,bytes) or len(raw)!=width:raise ValueError('Invalid '+key)
    return int.from_bytes(raw,'little')

def tables(raw,count,number):
    if count<1 or number<1 or len(raw)!=count*number*8:raise ValueError('Invalid table geometry')
    rows=[{'frequency_hz':f,'voltage_raw':v} for f,v in struct.iter_unpack('<II',raw)]
    return [rows[i*count:(i+1)*count] for i in range(number)]

def ladder(core,sram):
    """Preserve each cluster's observed rows; no synthetic power calibration."""
    if len(core)!=len(sram):raise ValueError('Core/SRAM length differs')
    result=[];first=0
    while first<len(core):
        last=first
        while last+1<len(core) and core[last+1]['voltage_raw']==core[first]['voltage_raw']:last+=1
        if first and core[first]['voltage_raw']<=core[first-1]['voltage_raw']:raise ValueError('Unordered voltage groups')
        for row in range(first,last+1):
            if core[row]['frequency_hz']!=sram[row]['frequency_hz'] or sram[row]['voltage_raw']!=sram[first]['voltage_raw'] or core[row]['frequency_hz']%1000000:raise ValueError('Inconsistent grouped performance row')
        low=min(range(first,last+1),key=lambda i:core[i]['frequency_hz']);high=max(range(first,last+1),key=lambda i:core[i]['frequency_hz'])
        result.append({'frequency_high_mhz':core[high]['frequency_hz']//1000000,'frequency_low_mhz':core[low]['frequency_hz']//1000000,'index_high':high,'index_low':low,'core_voltage_raw':core[first]['voltage_raw'],'sram_voltage_raw':sram[first]['voltage_raw']})
        first=last+1
    return result

def audit(dt,services):
    tree=list(nodes(dt));sgx=next(n for n in tree if n['IORegistryEntryName']=='sgx')
    chosen=next(n for n in tree if n['IORegistryEntryName']=='chosen')
    accelerator=next(n for n in nodes(services) if isinstance(n.get('GPUConfigurationVariable'),dict))
    config=accelerator['GPUConfigurationVariable'];count=uint(sgx,'perf-state-count');number=uint(sgx,'perf-state-table-count')
    core=tables(sgx['perf-states'],count,number);sram=tables(sgx['perf-states-sram'],count,number)
    if any(a['frequency_hz']!=b['frequency_hz'] for x,y in zip(core,sram) for a,b in zip(x,y)):raise ValueError('Core/SRAM frequencies differ')
    masks=config['core_mask_list'];enabled=sum(int(m).bit_count() for m in masks)
    # Do not equate Apple's raw num_cores (physical slots) with enabled cores.
    windows=[]
    for group in sgx.get('IODeviceMemory',[]):
        for region in group:windows.append({'address':region['address'],'size':region['length'],'source':'macOS IODeviceMemory translation'})
    regions={}
    for name in ('gpu-region','gfx-shared-region','gfx-shared-l2-region','gfx-handoff','gfx-data','rtkit-private-vm-region'):
        if name+'-base' in sgx and name+'-size' in sgx:regions[name]={'base':uint(sgx,name+'-base',8),'size':uint(sgx,name+'-size',8)}
    groups=[1+sum(a['voltage_raw']!=b['voltage_raw'] for a,b in zip(t,t[1:])) for t in core]
    return {'schema':'m4rch.gpu-contract.v1','compatible':sgx['compatible'].rstrip(b'\0').decode(),
      'macos_boot_firmware':chosen['firmware-version'].split(b'\0')[0].decode(),
      'linux_boot_firmware':'not captured here; do not substitute current macOS firmware',
      'generation':config['gpu_gen'],'variant':config['gpu_var'],'macos_gpu_configuration':config,
      'enabled_cores_from_masks':enabled,'macos_gpu_core_count':accelerator.get('gpu-core-count'),
      'performance_rows_per_table':count,'performance_table_count':number,'contiguous_core_voltage_groups':groups,
      'core_tables':core,'sram_tables':sram,'cluster_ladders':[ladder(c,s) for c,s in zip(core,sram)],'register_windows':windows,'memory_regions':regions,
      'gravity_t8132_mismatches':{'chip':sgx['compatible'].rstrip(b'\0')!=b'gpu,t8132','variant':config['gpu_var']!='G',
        'single_cluster':number!=1,'ten_core_mask':masks!=[0x3ff],'eleven_voltage_groups':any(g!=11 for g in groups),
        'probe_window_64MiB':not windows or windows[0]['size']<0x4000000},
      'limit':'Captured metadata only. No GPU MMIO, firmware execution, calibrated power table or Linux resource validation.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--device-tree',type=Path,required=True);p.add_argument('--services',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(plistlib.loads(a.device_tree.read_bytes()),plistlib.loads(a.services.read_bytes()))
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
if __name__=='__main__':main()
