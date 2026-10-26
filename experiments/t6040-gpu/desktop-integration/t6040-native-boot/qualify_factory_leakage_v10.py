#!/usr/bin/env python3
"""Compare pure decoder with unmodified native fuse arithmetic in offline RAM."""
import json, random, re, struct, subprocess
from pathlib import Path
import qualify_power_v7 as q
from trace_factory_leakage_v10 import decode

def main():
    output=q.ROOT/'out/native-factory-leakage-v10-offline';output.mkdir(exist_ok=True)
    f=(q.ROOT/'out/gpu-gravity-normal-boot-v6/source/linux/drivers/gpu/drm/asahi/float.rs').read_text()
    f=f[:f.index("impl<'a> TryFrom<of::Property")]
    f=re.sub(r'use kernel::\{.*?\};','',f,flags=re.S).replace('unsafe impl Zeroable for F32 {}','')
    (output/'float.rs').write_text(f)
    rng=random.Random(6040)
    cases=[[0]*5,[0xffffffff]*5]+[[rng.getrandbits(32) for _ in range(5)]for _ in range(16)]
    n=q.Native({'gpu-pwr-sample-period-aic-clks':(200000).to_bytes(4,'little'),'perf-states':bytes(128)},20000,24,(bytes(8),bytes(48)))
    stop=[None]
    n.ram.hook_add(q.UC_HOOK_CODE,lambda ram,a,size,data:ram.emu_stop() if a==stop[0] else None)
    scripts=[];results=[]
    for i,words in enumerate(cases):
        n.ram.mem_write(q.FW+0xae0,bytes(0xe0));n.put64(q.ACC+0x5b0,q.FW)
        n.put32(q.ACC+0x4e4,2);n.put32(q.ACC+0x4ec,1)
        for off,v in zip([0xc10,0xc1c,0xc20,0xc24,0xc28],words):n.put32(q.RAW+off,v)
        n.setx(0,q.RAW);n.setx(9,2);n.setx(20,q.ACC)
        n.setx(22,q.STACK+0x1000);n.setx(21,q.STACK+0x1100)
        stop[0]=q.BASE+0x89e9af0
        try: n.ram.emu_start(q.BASE+0x89e9974,q.BASE+0x89e9af0,count=1000)
        except Exception as exc: raise RuntimeError((i,hex(n.ram.reg_read(q.reg.UC_ARM64_REG_PC)))) from exc
        stop[0]=q.BASE+0x89e9cb0
        n.ram.emu_start(q.BASE+0x89e9af0,q.BASE+0x89e9cb0,count=1000)
        expected=decode(words)
        got={'cluster_bits':list(struct.unpack('<2I',n.ram.mem_read(q.FW+0xae0,8))),
             'core_bits':list(struct.unpack('<2I',n.ram.mem_read(q.FW+0xb60,8))),
             'afr_bits':struct.unpack('<I',n.ram.mem_read(q.FW+0xbb0,4))[0],
             'auxiliary_bits':struct.unpack('<I',n.ram.mem_read(q.FW+0xbb8,4))[0]}
        assert got==expected,(words,got,expected)
        # Invoke actual Rust write API and compare to native values without
        # requiring another kernel module or any boot-stage execution.
        expected_words=got['cluster_bits']+got['core_bits']+[got['afr_bits'],got['auxiliary_bits']]
        scripts.append('{let mut p=vec![0u8;0x6578];l::FactoryLeakage::from_words(&'+str(words)+').write_power(&mut p).unwrap();let got=[0x642c,0x6430,0x64ac,0x64b0,0x64fc,0x6504].map(|o|u32::from_le_bytes(p[o..o+4].try_into().unwrap()));assert_eq!(got,'+str(expected_words)+');}\n')
        results.append({'words':words,'native_bits':got,'python_agrees':True})
    source=output/'factory-tests.rs'
    source.write_text('#![allow(dead_code)]\n#[macro_use]\n#[path="float.rs"] mod float;\n#[path='+json.dumps(str(q.KIT/'g16_t6040_factory_leakage_v10.rs'))+'] mod l;\nfn main(){'+''.join(scripts)+'}')
    c=subprocess.run(['rustc','--edition=2021','-Dwarnings',str(source),'-o',str(output/'factory-tests')],capture_output=True,text=True)
    assert c.returncode==0,c.stderr
    r=subprocess.run([str(output/'factory-tests')],capture_output=True,text=True);assert r.returncode==0,r.stderr
    report={'schema':'m4rch.native-factory-leakage-offline-comparison.v10','hardware_actions':[],
      'cases':results,'rust_and_python_match_native':True,
      'native_span':['89e9974..89e9af0','89e9af0..89e9cb0'],
      'input_policy':'synthetic arithmetic coverage; no actual hardware fuse values',
      'source_pins':[q.pin(q.AGX),q.pin(__file__),q.pin(q.KIT/'g16_t6040_factory_leakage_v10.rs')]}
    out=q.ROOT/'docs/evidence/2026-10-11-native-factory-leakage-offline-v10.json'
    out.write_text(json.dumps(report,indent=2)+'\n');print(out)
if __name__=='__main__':main()
