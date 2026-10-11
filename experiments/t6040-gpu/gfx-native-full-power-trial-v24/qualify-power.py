#!/usr/bin/env python3
"""Compare complete native power writers with original ARM execution offline.

This composes the already bound period/QoS inputs. It neither accesses GPU
hardware nor treats test performance maps as captured hardware registers.
"""
import argparse, importlib.util, json, re, struct, subprocess
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"desktop-integration/t6040-native-boot"))
import qualify_power_v7 as q
from prepare_power_complete_v7 import FullNative
from bind_power_owners_v8 import bind

SUPPORT=0xfffffc200014f000
QOS=0xfffffc200012c000
AON=0xfffffc200014f100

def qualify(output):
    output.mkdir(parents=True,exist_ok=False)
    evidence=q.ROOT/'out/gpu-gravity-normal-boot-v6-source-evidence/native-power.json'
    adt=next(Path(r['path']) for r in json.loads(evidence.read_text())['source_pins'] if r['path'].endswith('/boot.adt'))
    parser_path=q.ROOT/'experiments/t6040-gpu/adt.py'
    spec=importlib.util.spec_from_file_location('power_complete_adt',parser_path)
    parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
    node=parser.parse(adt.read_bytes())['/device-tree/arm-io/sgx']
    component=Path(__file__).resolve().parent/'g16_t6040_power_trial_v24.rs'
    baseline_float=q.ROOT/'out/gpu-gravity-normal-boot-v6/source/linux/drivers/gpu/drm/asahi/float.rs'
    f=baseline_float.read_text();f=f[:f.index("impl<'a> TryFrom<of::Property")]
    f=re.sub(r'use kernel::\{.*?\};','',f,flags=re.S).replace('unsafe impl Zeroable for F32 {}','')
    (output/'float.rs').write_text(f)
    props=[]
    for i,(key,value) in enumerate(node.items()):
        if isinstance(value,bytes):
            path=output/f'property-{i}.bin';path.write_bytes(value)
            props.append(f'({json.dumps(key)},include_bytes!({json.dumps(str(path))}).as_slice())')
    tests=[];cases=[]
    for index,maps in enumerate([(list(range(16)),list(range(16))),
                                ([0,1,2,3,4,5,6,7,8,9,10,0,0,0,0,0],)*2]):
        case=output/f'case-{index}';case.mkdir()
        preserved=(bytes([index+1])*8,bytes((index+i)&255 for i in range(48)))
        native=FullNative(node,20000,24,preserved)
        native.put64(q.ACC+0x5b0,q.FW);native.put32(q.ACC+0x4e4,2);native.put32(q.ACC+0x4ec,1)
        native.put64(q.FW+0x960,q.FW+0x20000);native.put64(q.FW+0xc38,q.FW+0x30000)
        native.put64(q.FW+0xc30,AON);native.put64(q.FW+0x3a8,SUPPORT)
        native.ram.mem_write(q.HARDWARE,bytes(0x2718+16));native.ram.mem_write(q.REGION,bytes(0xe58+16))
        # Previously bound native period producer, composed before lifecycle.
        native.put32(q.HARDWARE+0xed8,8)
        # Execute actual QoS pointer load/store from its actual manager owner.
        native.put64(q.ACC+0x530,q.NODE+0x6000);native.put64(q.NODE+0x6028,QOS)
        native.setx(9,q.ACC);native.setx(8,q.HARDWARE)
        native.ram.emu_start(q.BASE+0x89aa428,q.BASE+0x89aa434,count=3)
        owners=bind(native,node,*maps)
        from bind_power_controller_v8 import bind_controller_predecessors as bind_controller
        bind_controller(native)
        controller=dict(native_sustained_controller_executed=True,sample_period_ms=8,gpu_clusters=2,auxiliary_soc_die_count=1)
        native.execute(0x89ea270,owner=q.ACC);native.execute(0x89e9678,owner=q.ACC)
        native.execute(0x89cf0ec);native.execute(0x89cad50)
        for name,address,size in [('power',q.POWER,0x6578),('hardware',q.HARDWARE,0x2718),('region-c',q.REGION,0xe58),('aonptd',q.FW+0x30000,0xe4)]:
            (case/(name+'-native.bin')).write_bytes(bytes(native.ram.mem_read(address,size)))
        s='let d=p::PowerData::from_adt(&['+','.join(props)+']).unwrap();\n'
        s+='let maps=p::PerfStateMaps{primary:'+str(maps[0])+',secondary:'+str(maps[1])+'};let d=d.with_perf_state_maps(&maps).unwrap();\n'
        s+='let mut power=vec![0;p::LOGICAL_BYTES];'
        s+=f'power[0x6530..0x6538].copy_from_slice(&{list(preserved[0])});power[0x2888..0x28b8].copy_from_slice(&{list(preserved[1])});\n'
        s+='let policy=p::LinuxBootPolicy::t6040_20w_24mhz(1000,16,2).unwrap();'
        s+=f'let aliases=p::PowerOwnedAliases{{support26_gpu:{SUPPORT},qos_gpu:{QOS},aonptd_gpu:{AON}}};let providers=p::LifecycleProviders::capture(&power,&policy,aliases).unwrap();\n'
        for name,var,size,expr in [('power','power',0,'d.write_lifecycle_component(&mut power,&providers)'),('hardware','hardware',0x2718,'d.write_hardware_component(&mut hardware,&providers)'),('region-c','region',0xe58,'d.write_region_c_component(&mut region,&providers)'),('aonptd','aonptd',0xe4,'d.write_aonptd_component(&mut aonptd)')]:
            if size:s+=f'let mut {var}=vec![0;{size}];\n'
            s+=expr+'.unwrap();std::fs::write('+json.dumps(str(case/(name+'-rust.bin')))+f',&{var}).unwrap();\n'
        tests.append('{'+s+'}\n');cases.append(dict(index=index,owners=owners,controller=controller,calls=native.calls))
    source=output/'power-tests.rs'
    source.write_text('#![allow(dead_code)]\n#[macro_use]\n#[path="float.rs"] mod float;\n#[path='+json.dumps(str(component))+'] mod p;\nfn main(){\n'+''.join(tests)+'}\n')
    compile_result=subprocess.run(['rustc','--edition=2021','-Dwarnings',str(source),'-o',str(output/'power-tests')],capture_output=True,text=True)
    (output/'compile.stderr').write_text(compile_result.stderr)
    assert compile_result.returncode==0,compile_result.stderr
    run=subprocess.run([str(output/'power-tests')],capture_output=True,text=True)
    (output/'run.stderr').write_text(run.stderr);assert run.returncode==0,run.stderr
    complete=True
    for case in cases:
        comparisons={}
        for name in ['power','hardware','region-c','aonptd']:
            directory=output/f'case-{case["index"]}'
            a=(directory/(name+'-rust.bin')).read_bytes();b=(directory/(name+'-native.bin')).read_bytes()
            offsets=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
            comparisons[name]=dict(bytes=len(a),different_bytes=len(offsets),different_words=[dict(offset=hex(i),rust=a[i:i+4].hex(),native=b[i:i+4].hex()) for i in range(0,len(a)-3,4) if a[i:i+4]!=b[i:i+4]])
            complete &= not offsets
        case['comparisons']=comparisons
    report=dict(schema='m4rch.native-t6040-complete-power-comparison.trial-v24',inputs=[q.pin(p) for p in [q.AGX,adt,parser_path,component,Path(__file__),q.KIT/'bind_power_owners_v8.py',q.KIT/'bind_power_controller_v8.py']],cases=cases,whole_outputs_agree=complete,rust_compile_returncode=compile_result.returncode,rust_run_returncode=run.returncode,hardware_actions=[],triangle_trial_ready=False,scope='20W/24MHz Linux policy, original raw ADT, explicit test maps, fresh zero leakage, absent optional AON dictionary; period and actual native QoS store composed before power writers')
    (output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(whole_outputs_agree=complete,cases=[{name:data['different_bytes'] for name,data in c['comparisons'].items()} for c in cases])))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);qualify(p.parse_args().output.resolve())
