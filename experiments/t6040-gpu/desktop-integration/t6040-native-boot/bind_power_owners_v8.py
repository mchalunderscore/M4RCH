#!/usr/bin/env python3
"""Offline ADT-to-CPU owners consumed by selected native ARM power routines.

No GPU access. Main mapped table copies execute original instructions
896e928..896eef0 in q.Native's RAM. Raw ADT parsing and auxiliary CPU owner
construction are numeric transcriptions; they are not a hardware map fixture.
"""
import struct
import qualify_power_v7 as q

PRIMARY = dict(count=0x196d0, columns=0x196d4, hz=0x196d8,
               core=0x19718, sram=0x19b18)
SECONDARY = dict(count=0x19f18, columns=0x19f1c, hz=0x19f20,
                 core=0x19f60, sram=0x1a360)
AUXILIARY = {'cs':dict(count=0x1a760, columns=0x1a764, hz=0x1a768,
                       core=0x1a7a8, sram=0x1a828),
             'afr':dict(count=0x1a8a8, columns=0x1a8ac, hz=0x1a8b0,
                        core=0x1a8f0, sram=0x1a970)}
PROVENANCE = dict(main_startup=[0x896e928,0x896eef0],
    primary_consumer=[0x89cb0f8,0x89cb240],
    secondary_consumer=[0x89cb440,0x89cb508],
    cs_consumer=[0x89cb240,0x89cb330], afr_consumer=[0x89cb330,0x89cb440],
    voltage_zero_fill=[0x896e49c,0x896e5e4], sram_zero_fill=[0x896e7a8,0x896e928],
    raw_cpu_owner=0x18d08, raw_count=0x18e88, raw_columns=0x18e8c,
    raw_hz=0x18e90, raw_core=0x18ed0, raw_sram=0x192d0,
    map_count=0x18e04, map_primary=0x18e08, map_secondary=0x18e48)


def decode_register_words(words):
    assert len(words)==8 and all(0<=v<=0xffffffff for v in words)
    return [n for v in words for n in (v&15,(v>>16)&15)]


def bind(native, properties, primary=None, secondary=None):
    """Bind exact ADT properties plus explicit 16-entry startup map inputs.

    Default identity maps are test inputs, never claimed as live register data.
    Returns numeric owner receipt and actual native mapped-copy output bytes.
    """
    primary=list(range(16)) if primary is None else list(primary)
    secondary=list(range(16)) if secondary is None else list(secondary)
    assert len(primary)==len(secondary)==16
    assert all(0<=v<16 for v in primary+secondary)
    count=struct.unpack('<I',properties['perf-state-count'])[0]
    columns=struct.unpack('<I',properties['perf-state-table-count'])[0]
    assert (count,columns)==(16,2)
    raw=properties['perf-states']; sram=properties['perf-states-sram']
    assert len(raw)==len(sram)==count*columns*8
    hz=[struct.unpack_from('<I',raw,i*8)[0] for i in range(count)]
    core=[]; sv=[]
    for i in range(count):
        c=[]; s=[]
        for col in range(columns):
            f,v=struct.unpack_from('<II',raw,(col*count+i)*8)
            sf,ss=struct.unpack_from('<II',sram,(col*count+i)*8)
            assert f==sf==hz[i]
            c.append(v); s.append(max(v,ss))
        # Native pre-map owner fills absent voltage columns from column0.
        core.append(c+[0]*14); sv.append(s+[0]*14)
    base=q.ACC+0x18d08
    native.ram.mem_write(base,bytes(0x18d8))
    native.put32(base+0x180,count); native.put32(base+0x184,columns)
    for i in range(count):
        native.put32(base+0x188+i*4,hz[i])
        native.ram.mem_write(base+0x1c8+i*64,struct.pack('<16I',*core[i]))
        native.ram.mem_write(base+0x5c8+i*64,struct.pack('<16I',*sv[i]))
    native.ram.mem_write(q.ACC+0x505,b'\1')
    native.put32(q.ACC+0x18e04,16)
    for i in range(16):
        native.put32(q.ACC+0x18e08+i*4,primary[i])
        native.put32(q.ACC+0x18e48+i*4,secondary[i])
    sp=q.STACK+0x10000
    native.ram.reg_write(q.reg.UC_ARM64_REG_SP,sp)
    native.setx(19,q.ACC); native.setx(21,base); native.setx(27,0)
    native.put64(sp+0x28,base+0x180); native.put64(sp+0x110,q.ACC+SECONDARY['count'])
    native.put64(sp+0x120,0); native.put64(sp+0x128,base)
    native.setx(20,count)
    native.ram.emu_start(q.BASE+0x896e49c,q.BASE+0x896e5e4,count=100000)
    assert native.ram.reg_read(q.reg.UC_ARM64_REG_PC)==q.BASE+0x896e5e4
    native.setx(20,count); native.setx(21,base)
    native.ram.emu_start(q.BASE+0x896e7a8,q.BASE+0x896e928,count=100000)
    assert native.ram.reg_read(q.reg.UC_ARM64_REG_PC)==q.BASE+0x896e928
    native.setx(19,q.ACC); native.setx(21,base); native.setx(27,0)
    native.ram.emu_start(q.BASE+0x896e928,q.BASE+0x896eef0,count=100000)
    assert native.ram.reg_read(q.reg.UC_ARM64_REG_PC)==q.BASE+0x896eef0
    result=dict(source_numeric=PROVENANCE, primary_map=primary,secondary_map=secondary,
                native_startup_copy_executed=True,native_voltage_zero_fill_executed=True,auxiliary={})
    for name,owner in [('primary',PRIMARY),('secondary',SECONDARY)]:
        n=struct.unpack('<I',native.ram.mem_read(q.ACC+owner['count'],4))[0]
        result[name]=dict(count=n,columns=columns,
            hz=list(struct.unpack('<16I',native.ram.mem_read(q.ACC+owner['hz'],64))),
            core_rows=[list(struct.unpack('<16I',native.ram.mem_read(q.ACC+owner['core']+i*64,64))) for i in range(16)],
            sram_rows=[list(struct.unpack('<16I',native.ram.mem_read(q.ACC+owner['sram']+i*64,64))) for i in range(16)])
    native.secondary=result['secondary']['hz']
    for key,owner in AUXILIARY.items():
        raw=properties[key+'-perf-states']
        assert len(raw)==152
        dies,n=struct.unpack_from('<QQ',raw)
        assert (dies,n)==(1,8)
        floor=struct.unpack_from('<Q',raw,144)[0]//1000
        native.ram.mem_write(q.ACC+owner['count'],bytes(0x148))
        native.put32(q.ACC+owner['count'],n); native.put32(q.ACC+owner['columns'],dies)
        values=[]
        for i in range(n):
            uv,f=struct.unpack_from('<QQ',raw,16+i*16)
            mv=uv//1000; sm=max(mv,floor)
            native.put32(q.ACC+owner['hz']+i*4,f)
            native.put32(q.ACC+owner['core']+i*8,mv)
            native.put32(q.ACC+owner['sram']+i*8,sm)
            values.append(dict(hz=f,core_mv=mv,sram_mv=sm))
        native.ram.mem_write(q.ACC+(0x509 if key=='cs' else 0x50a),b'\1')
        result['auxiliary'][key]=dict(count=n,columns=dies,rows=values,
            maximum_provider='ARM setup FW+bcc or FW+bd0; not this input binder')
    return result


def reference(properties, primary, secondary):
    """Numeric mapping model independently checked against original CPU copies.

    A disabled primary voltage terminates the loop (896eb50 -> 896eed0),
    whereas primary map0 skips that copy but can still copy secondary.
    """
    rows=properties['perf-states']; sram=properties['perf-states-sram']
    def row(i):
        hz=struct.unpack_from('<I',rows,i*8)[0]
        core=[struct.unpack_from('<I',rows,(c*16+i)*8+4)[0] for c in range(2)]
        sv=[max(core[c],struct.unpack_from('<I',sram,(c*16+i)*8+4)[0]) for c in range(2)]
        return dict(hz=hz,core=core+[core[0]]*14,sram=sv+[sv[0]]*14)
    p=[row(0)]; s=[row(0)]
    for pi,si in zip(primary[1:],secondary[1:]):
        if row(pi)['core'][0]==0: break
        if pi: p.append(row(pi))
        if si: s.append(row(si))
    result={}
    for name, selected in [('primary',p),('secondary',s)]:
        result[name]=dict(count=len(selected),columns=2,
            hz=[r['hz'] for r in selected]+[0]*(16-len(selected)),
            core_rows=[r['core'] for r in selected]+[[0]*16 for _ in range(16-len(selected))],
            sram_rows=[r['sram'] for r in selected]+[[0]*16 for _ in range(16-len(selected))])
    return result


def qualify(output):
    import json,importlib.util
    from pathlib import Path
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    saved=json.loads((q.ROOT/'out/gpu-gravity-normal-boot-v6-source-evidence/native-power.json').read_text())
    adt=next(Path(row['path']) for row in saved['source_pins'] if row['path'].endswith('/boot.adt'))
    spec=importlib.util.spec_from_file_location('bind_owner_adt',q.ROOT/'experiments/t6040-gpu/adt.py')
    parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
    node=parser.parse(adt.read_bytes())['/device-tree/arm-io/sgx']
    identity=list(range(16)); grouped=list(range(11))+[0]*5
    duplicates=[0,1,1,0,3,3,4,5,6,7,8,9,10,11,12,13]
    shifted=[0,2,0,4,4,5,6,7,8,9,10,11,12,13,14,15]
    fixture=dict(node); disabled=bytearray(node['perf-states'])
    for c in range(2): struct.pack_into('<I',disabled,(c*16+5)*8+4,0)
    fixture['perf-states']=bytes(disabled)
    cases=[]
    for name,props,pm,sm in [('identity',node,identity,identity),
                             ('grouped11',node,grouped,grouped),
                             ('duplicate_and_primary_zero_index',node,duplicates,shifted),
                             ('disabled_primary_terminates',fixture,identity,identity)]:
        native=q.Native(props,20000,24,(bytes(8),bytes(48)))
        actual=bind(native,props,pm,sm); expected=reference(props,pm,sm)
        for owner in ('primary','secondary'):
            assert actual[owner]==expected[owner],(name,owner)
        cases.append(dict(name=name,primary_count=actual['primary']['count'],
                          secondary_count=actual['secondary']['count'],all_owner_bytes_agree=True))
        (output/(name+'.json')).write_text(json.dumps(actual,indent=2)+'\n')
    report=dict(schema='m4rch.native-power-cpu-owners.v8',
        inputs=[q.pin(__file__),q.pin(q.__file__),q.pin(q.AGX),q.pin(adt)],
        source_numeric=PROVENANCE,cases=cases,hardware_actions=[],
        rust_discrepancy='with_perf_state_maps zero primary core voltage must break, not continue',
        qualification='Original native main CPU table copies agree with independent numeric owner model. Auxiliary table binding is numeric consumer transcription only.')
    (output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    args=p.parse_args();print(json.dumps(qualify(args.output)['cases']))
