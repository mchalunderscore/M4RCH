#!/usr/bin/env python3
"""Compose actual geometry, TA resource loaders, payload copy and TA producer."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
from private_render_setup import copy_payload
from private_ta_inputs import load_ta_render_target,load_ta_parameter_management
from private_rce_entry import encode_entry
from private_descriptor_initialization import init_3d,init_ta
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('output',type=Path);p.add_argument('--paired-output',type=Path);a=p.parse_args()
def harness(name,marker,extra=()):
    path=Path(__file__).with_name(name);ns={'__file__':str(path),'__name__':'composition'};old=sys.argv;sys.argv=[str(path),str(a.macho),*map(str,extra),str(a.output)]
    try:exec(compile(path.read_text().split(marker)[0],str(path),'exec'),ns)
    finally:sys.argv=old
    return ns
geo=harness('audit-private-render-geometry.py','rng=random.Random(604018);')
loader=harness('audit-private-ta-inputs.py','rng=random.Random(604012);')
ta=harness('audit-private-ta-generator.py',"counts={'complete_ta_producer'",[a.output])
ctor=harness('audit-private-descriptor-initialization.py','rng=random.Random(604022);')
m=ta['m'];c=ta['c'];A,C,D=[ta[k] for k in ('A','C','D')];START=ta['START'];payload_address,wrapper_address=0x238000,0x23c000
ctor['m'].mem_map(0x220000,0x30000);ctor['D']=D
COPY_START,COPY_END=0xfffffe0008998198,0xfffffe0008998504
m.mem_map(0xfffffe0008998000,4096);m.mem_write(COPY_START,ta['ns']['read'](COPY_START,COPY_END-COPY_START))
paired=None
if a.paired_output is not None:
    import importlib.util
    paired_path=Path(__file__).with_name('prepare-native-sksm-registers.py')
    spec=importlib.util.spec_from_file_location('joined_paired',paired_path)
    paired=importlib.util.module_from_spec(spec);spec.loader.exec_module(paired)
    a.paired_output.mkdir(parents=True,exist_ok=False)
counts={'native_compositions':0,'independent_intermediates':0,'checked_register_values':0,'independent_encoder_records':0};examples=[]
for i in range(64):
    w=[32,64,128,256][i%4];h=[32,64,96,128][(i//4)%4];groups=1+i%3
    obj=bytearray(0x400);accel=bytearray(0x12000)
    for off,val in [(0x3c,groups),(0x40,w),(0x44,h),(0x48,1),(0x90,32),(0x94,32),(0x98,1)]:struct.pack_into('<I',obj,off,val)
    struct.pack_into('<Q',obj,0x120,geo['A']);struct.pack_into('<I',accel,0x4e4,2);struct.pack_into('<Q',accel,0x11188,16<<30);struct.pack_into('<Q',accel,0,geo['VT']);geo['provider']=2
    geo['m'].mem_write(geo['O'],bytes(obj));geo['m'].mem_write(geo['A'],bytes(accel));geo['run'](geo['GEO'],x0=geo['O'],x2=0)
    source=bytearray(geo['m'].mem_read(geo['O'],0x400));assert source==geo['geometry'](obj,accel,0,2);counts['independent_intermediates']+=1
    struct.pack_into('<Q',source,0x130,loader['N']);struct.pack_into('<Q',source,0x1c0,loader['Q'])
    for n,off in enumerate(range(0x1d8,0x218,8)):struct.pack_into('<Q',source,off,1)
    for n,off in enumerate(range(0x218,0x258,8)):struct.pack_into('<Q',source,off,0x1000*n)
    for off,val in [(0x2a8,0),(0x2b0,0x4000),(0x2b8,0x8000)]:struct.pack_into('<Q',source,off,val)
    # Deliberately distinct synthetic FW and GPU services; each resource has a stable base.
    bases={('primary',0x160):0xffffffa000000000,('primary',0x158):0x1001000000,('support',0x160):0xffffffb000000000,('support',0x158):0x10045d0000,('retain',0x20):0}
    expected_order=[]
    def service(resource,slot):
        value=bases[resource,slot];expected_order.append((resource,slot,value));return value
    # Execute both constructors on the same descriptor address used downstream.
    initial=bytearray(0x1800);struct.pack_into('<Q',initial,0,ctor['DVT']);struct.pack_into('<Q',initial,0x60,ctor['TASK'])
    cm=ctor['m'];cm.mem_write(D,bytes(initial));cm.mem_write(ctor['DVT']+0x1e0,struct.pack('<Q',ctor['leaves'][1]));cm.mem_write(ctor['QUEUE']+0x550,bytes(8));ctor['external_calls'].clear();ctor['parent_result']=1;ctor['debug']=0;ctor['allocation']=0x850000000
    for reg in ctor['regs']:cm.reg_write(reg,0)
    for reg,val in [(c.UC_ARM64_REG_X0,D),(c.UC_ARM64_REG_X1,0xfeed0000),(c.UC_ARM64_REG_X2,ctor['QUEUE']),(c.UC_ARM64_REG_X3,ctor['TASK']),(c.UC_ARM64_REG_X4,0),(c.UC_ARM64_REG_X5,0),(c.UC_ARM64_REG_X6,0),(c.UC_ARM64_REG_SP,ctor['STACK']),(c.UC_ARM64_REG_LR,ctor['STOP'])]:cm.reg_write(reg,val)
    cm.emu_start(ctor['INITTA'],ctor['STOP'],count=4000);assert cm.reg_read(c.UC_ARM64_REG_PC)==ctor['STOP']
    initialized=bytes(cm.mem_read(D,0x1800));assert initialized==init_ta(init_3d(initial,D,0,0,0,0,ctor['ROOT']),D,ctor['allocation']);counts['independent_intermediates']+=1
    expected=load_ta_render_target(initialized,source,service)
    loader['returns']=[v for _,_,v in expected_order];loader['services'].clear();lm=loader['m'];lm.mem_write(loader['D'],initialized);lm.mem_write(loader['S'],bytes(source));loader['run'](loader['TRTM'])
    desc=bytes(lm.mem_read(loader['D'],0x1800));assert desc==expected;assert loader['services']==expected_order;counts['independent_intermediates']+=1
    pm=bytearray(0x400)
    for off,val in [(0,loader['PV']),(0x88,loader['VB']),(0xa8,loader['VA'])]:struct.pack_into('<Q',pm,off,val)
    struct.pack_into('<I',pm,0xb0,1);struct.pack_into('<Q',pm,0xb8,0x1007000000)
    va=[0x1007100000];vb=[ta['ns']['O']]
    lm.mem_write(loader['S'],bytes(pm));lm.mem_write(loader['VA'],struct.pack('<Q',*va));lm.mem_write(loader['VB'],struct.pack('<Q',*vb));loader['run'](loader['TPM'])
    expected=load_ta_parameter_management(desc,pm,va,vb,[0,0,0]);desc=bytes(lm.mem_read(loader['D'],0x1800));assert desc==expected;counts['independent_intermediates']+=1
    payload=bytearray(0x900)
    # Explicit candidate stream pointer and common shader state, still no live mapping.
    for off,val in [(0x18,0x1000003000),(0x2d0+0xa0,0xffff800000000000),(0x2d0+0xa8,(1<<40)+0x30c00),(0x2d0+0xc8,(1<<40)+0x30800)]:struct.pack_into('<Q',payload,off,val)
    struct.pack_into('<II',payload,0x2d0+0x1c8,w,h)
    desc=bytearray(desc)
    for off,val in [(0xfa0,0x830000000),(0x190,ta['ns']['O']),(0x1428,ta['ns']['R1'])]:struct.pack_into('<Q',desc,off,val)
    desc[0x1558]=i&1
    m.mem_write(D,bytes(desc));m.mem_write(payload_address,bytes(payload));wrapper=bytearray(0x300);struct.pack_into('<Q',wrapper,0x18,payload_address);m.mem_write(wrapper_address,bytes(wrapper))
    for reg in ta['ns']['regs']:m.reg_write(reg,0)
    for reg,val in [(c.UC_ARM64_REG_X25,D),(c.UC_ARM64_REG_X23,D+0x79c),(c.UC_ARM64_REG_X26,wrapper_address),(c.UC_ARM64_REG_SP,ta['ns']['STACK'])]:m.reg_write(reg,val)
    m.emu_start(COPY_START,COPY_END,count=3000);assert m.reg_read(c.UC_ARM64_REG_PC)==COPY_END
    prepared=bytes(m.mem_read(D,0x1800));assert prepared==copy_payload(desc,payload);counts['independent_intermediates']+=1
    if paired is not None:
        case=a.paired_output/('case-'+str(i));case.mkdir()
        for name,data in [('descriptor.bin',prepared),('context.bin',bytes(0x100)),
                          ('scene.bin',bytes(0x100)),('submit-context.bin',bytes(0x600)),
                          ('submit-stack.bin',bytes(0x100)),('render-target-source.bin',source),
                          ('parameter-source.bin',pm),('payload.bin',payload),('3d-frame.bin',bytes(24))]:
            (case/name).write_bytes(data)
        manifest=dict(schema='native-sksm-register-input-v1',descriptor='descriptor.bin',
            context='context.bin',scene='scene.bin',ta_command_gpu='0x830000000',
            **{'3d_command_gpu':'0x850000000'},parameter_gpu='0x840000000',gpu_bit47=False,
            ta_construction=dict(submit_context='submit-context.bin',submit_stack='submit-stack.bin',
                serial=0,firmware_translations=['0xffffffc000000000','0xffffffc000010000','0xffffffc000020000'],
                x26=0,w21=0,w22=0,completion_mapping_address='0xffffffc000030000',
                accelerator_mode=0,aperture_flags=0))
        manifest['3d_construction']=dict(body_source='render-target-source.bin',frame_data='3d-frame.bin',
            submit_stack='submit-stack.bin',serial=0,channel_counter=i,w21=0,w22=0,
            firmware_translations=['0xffffffc000000000','0xffffffc000010000','0xffffffc000020000'],
            completion_mapping_address='0xffffffc000030000')
        manifest['3d_construction']['event_control']=dict(submit_context='submit-context.bin',epochs=[0,0],capacity=16,initial=0,aperture_flags=0)
        (case/'input.json').write_text(json.dumps(manifest,indent=2)+'\n')
        joined=paired.prepare(a.macho,case/'input.json',case/'output')
        assert joined['submission_ready'] is False
        assert joined['producers']['ta']['lists'][0]['records']
        assert joined['ta_construction']['aperture_count']==0
        assert struct.unpack_from('<I', (case/'output/ta-construction-candidate.bin').read_bytes(),0)[0]==0
        assert joined['3d_construction']['scratch_payload']==(i+1)&255
        counts['prepared_descriptor_pairs']=counts.get('prepared_descriptor_pairs',0)+1

    m.mem_write(C,bytes(0x3000));m.mem_write(ta['ns']['O'],bytes(0x100));m.mem_write(A+0x6d0,bytes(8));ta['ns']['mapped']=0x840000000;ta['ns']['entries'].clear();ta['ns']['calls'].clear();ta['ns']['pending']=None
    for reg in ta['ns']['regs']:m.reg_write(reg,0)
    for reg,val in [(c.UC_ARM64_REG_X0,A),(c.UC_ARM64_REG_X1,C),(c.UC_ARM64_REG_X2,D),(c.UC_ARM64_REG_SP,ta['ns']['STACK']),(c.UC_ARM64_REG_LR,ta['ns']['STOP'])]:m.reg_write(reg,val)
    m.emu_start(START,ta['ns']['STOP'],count=100000);assert m.reg_read(c.UC_ARM64_REG_PC)==ta['ns']['STOP']
    cmd=bytes(m.mem_read(C,0x3000));final=bytes(m.mem_read(D,0x1800));n,length=struct.unpack_from('<HH',cmd,0x768);exported=struct.unpack_from('<H',final,0x1570)[0];assert length==n*12
    if paired is not None:
        assert (case/'output/ta-register-command.bin').read_bytes()==cmd[:0x9c0],(i,'joined native register bytes')
    records=[]
    for j in range(n):
        header,value=struct.unpack_from('<IQ',cmd,0x60+12*j);records.append(dict(register=hex(header&0x3fff8),flag=header&1,value=hex(value)))
    for reg,flag,val in [(0x1c038,1,bases['primary',0x160]),(0x1c9c8,0,bases['primary',0x160]),(0x1c078,1,bases['primary',0x160]+0x4000),(0x1c9d8,0,bases['primary',0x160]+0x4000)]:
        assert [int(r['value'],0) for r in records if int(r['register'],0)==reg and r['flag']==flag]==[val],(i,hex(reg));counts['checked_register_values']+=1
    for off,reg,flag,value in ta['ns']['entries']:
        assert cmd[off:off+12]==encode_entry(bytes(12),reg,flag,value);counts['independent_encoder_records']+=1
    counts['native_compositions']+=1
    if i<4:examples.append(dict(width=w,height=h,groups=groups,backing_count=n,exported_count=exported,records=records,descriptor_sha256=hashlib.sha256(final).hexdigest()))
report=dict(private_binary_sha256=ta['ns']['sha'],counts=counts,examples=examples,qualification='Actual complete TA+3D constructors -> ordinary geometry -> complete TA RT loader -> complete TA/3D PM loader -> actual payload slice/common helper -> full TA producer, with full-byte independent comparisons at every input stage. Resource FW and GPU map bases deliberately distinct, only numeric services qualified. Native encoder records independently checked; four independently expected firmware addresses checked per case. 64 positive extent/single-sample fixtures with groups1..3 and conditional initial entry. Inherited constructor/lifecycle services, PM subtype, resource map/retain services, payload caller aliases and remaining lifecycle providers are explicit synthetic fixtures. Optional paired output feeds this prepared descriptor through both verified SKSM wrappers and partial TA construction; its entire TA producer output must equal this original native producer result. Caller context/stack and translation/completion services remain explicit zero/address fixtures. No actual allocation, queue/event binding, GPU execution or submission-ready job proved.')
a.output.write_text(json.dumps(report,indent=2)+'\n');print(counts)
