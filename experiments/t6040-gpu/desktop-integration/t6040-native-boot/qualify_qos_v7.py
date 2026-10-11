#!/usr/bin/env python3
"""Execute new sequential native QoS submissions and compare compiled v7 Rust."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import struct
import subprocess

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as reg

BASE=0xfffffe0000000000
AGX_SHA='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
SIZE=0xe40
GUARD=64
MASK64=(1<<64)-1


def pin(path):
    b=path.read_bytes()
    return {'path':str(path.resolve()),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}


def qualify(macho, output):
    b=macho.read_bytes()
    if hashlib.sha256(b).hexdigest()!=AGX_SHA: raise ValueError('Unmatched AGX input')
    output.mkdir(parents=True,exist_ok=False)
    here=Path(__file__).resolve().parent
    producer=here/'g16_t6040_qos_v7.rs'
    producer_pin=pin(producer)
    segments=[];p=32
    for _ in range(struct.unpack_from('<I',b,16)[0]):
        cmd,n=struct.unpack_from('<II',b,p)
        if cmd==25: segments.append(struct.unpack_from('<QQQQ',b,p+24))
        p+=n
    def source(a,n):
        va=BASE+a
        owners=[off+va-start for start,_,off,size in segments if start<=va and va+n<=start+size]
        if len(owners)!=1: raise ValueError('Unbacked primary source span')
        return b[owners[0]:owners[0]+n]
    spans=[]
    for name,start,end in [('willSubmit',0x8a09134,0x8a093a4),
                            ('resource_zero',0x8a08bc8,0x8a08bd4),
                            ('ID_capacity',0x8a08c04,0x8a08c08),
                            ('hardware_resource_GPU_pointer',0x89aa428,0x89aa434),
                            ('registerQueue_weight_policy',0x8a08fcc,0x8a09050)]:
        code=source(start,end-start)
        spans.append({'name':name,'start':hex(start),'end':hex(end),'bytes':len(code),'sha256':hashlib.sha256(code).hexdigest()})
    weight_table=list(source(0x713536b,5))
    if weight_table!=[20,15,4,1,0]: raise ValueError('Native QoS policy table differs')
    uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
    for va,vsize,off,size in segments:
        if size:
            start=va&~0xfff;end=(va+vsize+0xfff)&~0xfff
            uc.mem_map(start,end-start);uc.mem_write(va,b[off:off+size])
    manager,accel,queues,commands,allocation,stack=0x20000000,0x21000000,0x22000000,0x23000000,0x24000000,0x25010000
    for address,size in [(manager,0x4000),(accel,0x2000),(queues,0x10000),
                         (commands,0x10000),(allocation,0x2000),(0x25000000,0x20000)]: uc.mem_map(address,size)
    resource=allocation+GUARD
    def qwrite(address,value): uc.mem_write(address,struct.pack('<Q',value))
    def wwrite(address,value): uc.mem_write(address,struct.pack('<I',value))
    def qread(address): return struct.unpack('<Q',bytes(uc.mem_read(address,8)))[0]
    ops={}
    for line in Path('out/private-apple/agx-disassembly.txt').read_text().splitlines():
        match=re.match(r'([0-9a-f]{16}):\s+(?:[0-9a-f]{2} ){3}[0-9a-f]{2}\s+(\S+)\s*(.*)',line)
        if match:ops[int(match[1],16)]=(match[2],match[3])
    services={'lock':0,'unlock':0,'native_time':0,'bzero':0,'PAC_bypassed':0}
    clock=[0];locked=[False]
    def hook(uc,pc,size,_):
        op,arg=ops.get(pc,('', ''))
        if op in ('pacibsp','autibsp'):
            services['PAC_bypassed']+=1;uc.reg_write(reg.UC_ARM64_REG_PC,pc+4)
        elif op=='bl':
            if arg=='0xfffffe000b7b13c4':
                if locked[0]:raise ValueError('Native lock nested')
                if uc.reg_read(reg.UC_ARM64_REG_X0)!=manager+0x1000:raise ValueError('Native wrong queue lock')
                locked[0]=True;services['lock']+=1
            elif arg=='0xfffffe000b928a20':
                if not locked[0]:raise ValueError('Native time read outside lock')
                uc.reg_write(reg.UC_ARM64_REG_X0,clock[0]);services['native_time']+=1
            elif arg=='0xfffffe000b744da0':
                pointer,count=uc.reg_read(reg.UC_ARM64_REG_X0),uc.reg_read(reg.UC_ARM64_REG_X1)
                if pointer!=resource or count!=SIZE:raise ValueError('Native QoS zero extent differs')
                uc.mem_write(pointer,bytes(count));services['bzero']+=1
            else:raise ValueError('Unexpected native service: '+arg)
            uc.reg_write(reg.UC_ARM64_REG_PC,pc+4)
        elif op=='b' and arg=='0xfffffe000b7b27c0':
            if not locked[0]:raise ValueError('Native unlock without lock')
            if uc.reg_read(reg.UC_ARM64_REG_X0)!=manager+0x1000:raise ValueError('Native wrong unlock')
            locked[0]=False;services['unlock']+=1
            uc.reg_write(reg.UC_ARM64_REG_PC,BASE+0x8a093a4)
    uc.hook_add(UC_HOOK_CODE,hook)
    def execute(start,end,limit=600):
        uc.emu_start(BASE+start,BASE+end,count=limit)
        if uc.reg_read(reg.UC_ARM64_REG_PC)!=BASE+end:raise ValueError('Native path did not complete')
    initial_guard=bytes([0x5a])*GUARD
    uc.mem_write(allocation,initial_guard+bytes([0xa5])*SIZE+initial_guard)
    qwrite(manager+0x20,resource)
    uc.reg_write(reg.UC_ARM64_REG_X19,manager)
    execute(0x8a08bc8,0x8a08bd4,10)
    zero_image=bytes(uc.mem_read(allocation,SIZE+2*GUARD))
    if zero_image!=initial_guard+bytes(SIZE)+initial_guard:raise ValueError('Native QoS zero clobbered guards')
    execute(0x8a08c04,0x8a08c08,2)
    if uc.reg_read(reg.UC_ARM64_REG_X2)!=128:raise ValueError('Native ID capacity differs')
    # Execute actual hardware child0+26b8 pointer binding with an owned GPU VA.
    hw=allocation+0x1000
    qwrite(accel+0x530,manager);qwrite(manager+0x28,0xfffffc2080000000)
    uc.reg_write(reg.UC_ARM64_REG_X9,accel);uc.reg_write(reg.UC_ARM64_REG_X8,hw)
    # Target extends beyond the resource page; a distinct local HW backing.
    uc.mem_map(0x26000000,0x4000);hw=0x26000000
    uc.reg_write(reg.UC_ARM64_REG_X8,hw)
    execute(0x89aa428,0x89aa434,4)
    if qread(hw+0x26b8)!=0xfffffc2080000000:raise ValueError('Native hardware QoS binding differs')

    rng=random.Random(0x6040_0711)
    owner_specs=[(0,0,20,0x2000,0xfffffc2081000000),
                 (1,1,15,0x1000,0xfffffc2081000040),
                 (2,63,4,0xffffffff,0xfffffc2081000080),
                 (3,64,1,0,0xfffffc20810000c0),
                 (4,127,0,0x80000000,0xfffffc2081000100),
                 (5,126,255,0x7fffffff,0xfffffc2081000140)]
    seed=bytearray(rng.randbytes(SIZE))
    # Near-wrap seeds cover both u32 counters and every native u64 counter.
    for wid in [0,1,2,63,64,65,126,127]:struct.pack_into('<I',seed,0x400+wid*4,0xfffffffe)
    for _,hid,_,_,_ in owner_specs:struct.pack_into('<I',seed,0x600+hid*4,0xfffffffe)
    struct.pack_into('<Q',seed,0xe00,MASK64-1)
    for dm in range(3):struct.pack_into('<Q',seed,0xe20+dm*8,MASK64-1)
    manager_count=MASK64-1
    uc.mem_write(allocation,initial_guard+seed+initial_guard)
    qwrite(manager+0xc60,manager_count)
    for owner,hid,weight,ratio,slot in owner_specs:
        q=queues+owner*0x1000;c=commands+owner*0x1000
        uc.mem_write(q,bytes(0x100));uc.mem_write(c,bytes(0x900))
        wwrite(q+0x10,hid);uc.mem_write(q+0x46,bytes([weight]));wwrite(q+0x48,ratio)
        qwrite(q+0x50,manager+0x1000);qwrite(q+0x58,accel);qwrite(q+0x60,c);qwrite(c+0x8b8,slot)
    expected=[];inputs=[];equal=0;not_equal=0;wrapping32=0;wrapping64=0
    for iteration in range(96):
        owner=iteration%len(owner_specs)
        _,hid,weight,ratio,slot=owner_specs[owner]
        # Each queue crosses its two64-bit published sets and repeats every ID.
        wid=[0,1,63,64,65,126,127,2][(iteration//6+owner)%8]
        dm=(iteration//6+owner)%3
        counts=[qread(resource+0xe20+i*8) for i in range(3)]
        observed=[counts[i] if (iteration+i)%2==0 else (counts[i]+1)&MASK64 for i in range(3)]
        match=counts[dm]==observed[dm]
        equal+=int(match);not_equal+=int(not match)
        for i,v in enumerate(observed):qwrite(manager+0xc48+i*8,v)
        ticks=[0,1,MASK64,0x123456789abcdef0][iteration%4]
        clock[0]=ticks
        before=bytes(uc.mem_read(resource,SIZE))
        uc.reg_write(reg.UC_ARM64_REG_SP,stack)
        uc.reg_write(reg.UC_ARM64_REG_X0,queues+owner*0x1000)
        uc.reg_write(reg.UC_ARM64_REG_X1,wid)
        uc.reg_write(reg.UC_ARM64_REG_X2,dm)
        uc.reg_write(reg.UC_ARM64_REG_X30,BASE+0x8a093a4)
        execute(0x8a09134,0x8a093a4)
        if locked[0] or uc.reg_read(reg.UC_ARM64_REG_SP)!=stack:raise ValueError('Native lock/stack did not retire')
        image=bytes(uc.mem_read(allocation,SIZE+2*GUARD))
        if image[:GUARD]!=initial_guard or image[-GUARD:]!=initial_guard:raise ValueError('Native QoS guards changed')
        for off in [0x400+wid*4,0x600+hid*4]:wrapping32+=int(struct.unpack_from('<I',before,off)[0]==0xffffffff)
        wrapping64+=int(counts[dm]==MASK64)
        wrapping64+=int(qread(manager+0xc60)==0)
        if match:wrapping64+=int(struct.unpack_from('<Q',before,0xe00)[0]==MASK64)
        q=queues+owner*0x1000
        host={'manager_submission_count':qread(manager+0xc60),
              'published':[qread(q+0x18),qread(q+0x20)],
              'initialized':uc.mem_read(q+0x3c,1)[0]}
        expected.append((image,host))
        inputs.append({'owner':owner,'id':hid,'queue':wid,'dm':dm,'weight':weight,'ratio':ratio,
                       'slot':slot,'ticks':ticks,'observed':observed,'matched_DM_counts':match})
    if equal!=48 or not_equal!=48 or wrapping32==0 or wrapping64==0:raise ValueError('Insufficient sequential branch/wrap coverage')

    rust=output/'probe.rs';binary=output/'probe'
    case_lines=[]
    for row in inputs:
        obs=','.join(str(v)+'u64' for v in row['observed'])
        case_lines.append('('+','.join(str(row[key])+'u64' for key in ['owner','id','queue','dm','weight','ratio','slot','ticks'])+',['+obs+']),')
    rust.write_text('''#![allow(dead_code)]
#[path="PRODUCER"] mod qos;
use qos::*;
fn hex(b:&[u8])->String {use std::fmt::Write;let mut s=String::new();for x in b {write!(&mut s,"{:02x}",x).unwrap();}s}
fn input(row:&(u64,u64,u64,u64,u64,u64,u64,u64,[u64;3]))->SubmissionInputs {
 SubmissionInputs{hardware_buffer_id:row.1 as u32,work_queue_id:row.2 as u32,data_master:row.3 as u32,weight:row.4 as u8,share_ratio:row.5 as u32,scheduler_slot:row.6,native_ticks:row.7}
}
fn main(){
 let mut initial=vec![0x5a;RESOURCE_BYTES+128];initial[64..64+RESOURCE_BYTES].fill(0xa5);
 write_initial(&mut initial[64..64+RESOURCE_BYTES]).unwrap();println!("initial:{}",hex(&initial));
 let mut short=[0xa5;RESOURCE_BYTES-1];assert_eq!(write_initial(&mut short),None);assert!(short.iter().all(|&x|x==0xa5));
 let seed:[u8;RESOURCE_BYTES]=[SEED];let mut allocation=vec![0x5a;RESOURCE_BYTES+128];allocation[64..64+RESOURCE_BYTES].copy_from_slice(&seed);
 let rows:&[(u64,u64,u64,u64,u64,u64,u64,u64,[u64;3])]=&[CASES];
 let mut states:Vec<QueueState>=(0..6).map(|_|QueueState::new()).collect();let mut manager=ManagerState::new();manager.submission_count=u64::MAX-1;
 for (i,row) in rows.iter().enumerate(){manager.observed_dm_counts=row.8;let request=input(row);
  states[row.0 as usize].write_submission(&mut manager,&mut allocation[64..64+RESOURCE_BYTES],request).unwrap();
  println!("step:{}:{}:{}",i,manager.submission_count,hex(&allocation));
 }
 // Refusal is before resource and shared manager writes. Follow each refusal
 // with a valid submission compared to a separate state to expose corruption.
 let valid=SubmissionInputs{hardware_buffer_id:127,work_queue_id:127,data_master:2,scheduler_slot:0xfffffc2082000000,weight:4,share_ratio:17,native_ticks:99};
 let mut tested=QueueState::new();let mut baseline=QueueState::new();let mut tm=ManagerState::new();let mut bm=ManagerState::new();
 let mut tr=vec![0;RESOURCE_BYTES];let mut br=vec![0;RESOURCE_BYTES];
 tested.write_submission(&mut tm,&mut tr,valid).unwrap();baseline.write_submission(&mut bm,&mut br,valid).unwrap();
 let mut refusals=0;
 for mode in 0..7 {let mut bad=valid;match mode{0=>bad.hardware_buffer_id=128,1=>bad.work_queue_id=128,2=>bad.data_master=3,3=>bad.hardware_buffer_id=126,4=>bad.scheduler_slot+=64,5=>bad.weight=3,_=>bad.share_ratio=18};
  let old=tr.clone();let old_count=tm.submission_count;let old_observed=tm.observed_dm_counts;
  assert_eq!(tested.write_submission(&mut tm,&mut tr,bad),None);assert_eq!(tr,old);assert_eq!(tm.submission_count,old_count);assert_eq!(tm.observed_dm_counts,old_observed);
  tested.write_submission(&mut tm,&mut tr,valid).unwrap();baseline.write_submission(&mut bm,&mut br,valid).unwrap();assert_eq!(tr,br);assert_eq!(tm.submission_count,bm.submission_count);refusals+=1;
 }
 let old=tr.clone();let old_count=tm.submission_count;assert_eq!(tested.write_submission(&mut tm,&mut tr[..RESOURCE_BYTES-1],valid),None);assert_eq!(tr,old);assert_eq!(tm.submission_count,old_count);refusals+=1;
 println!("refusals:{}",refusals+1);
}
'''.replace('PRODUCER',str(producer)).replace('SEED',','.join(str(x) for x in seed)).replace('CASES','\n'.join(case_lines)))
    built=subprocess.run(['rustc','--edition=2021','-D','warnings',str(rust),'-o',str(binary)],text=True,capture_output=True)
    if built.returncode:raise RuntimeError(built.stderr)
    ran=subprocess.run([str(binary)],text=True,capture_output=True,check=True)
    rows=ran.stdout.splitlines()
    if bytes.fromhex(rows[0].split(':')[1])!=zero_image:raise ValueError('Compiled initial QoS resource differs')
    compared=[]
    for line,(native,host),inputs_row in zip(rows[1:97],expected,inputs):
        kind,index,count,image=line.split(':')
        if kind!='step' or bytes.fromhex(image)!=native or int(count)!=host['manager_submission_count']:
            raise ValueError('Compiled sequential QoS differs at '+index)
        compared.append({'step':int(index),'owner':inputs_row['owner'],'queue':inputs_row['queue'],
                         'id':inputs_row['id'],'dm':inputs_row['dm'],'DM_counts_equal':inputs_row['matched_DM_counts'],
                         'resource_and_guards_sha256':hashlib.sha256(native).hexdigest(),
                         'manager_submission_count':host['manager_submission_count']})
    if len(compared)!=96:raise ValueError('Missing compiled sequential cases')
    refusals=int(rows[-1].split(':')[1])
    if refusals!=9:raise ValueError('Missing refusal cases')
    if pin(producer)!=producer_pin:raise ValueError('Producer changed during qualification')
    result={'schema':'m4rch.native-t6040-qos-v7.qualification.v1','macho':pin(macho),'producer':producer_pin,
        'source_spans':spans,'native_weight_table':weight_table,
        'hardware_pointer_binding_executed':True,'hardware_pointer_offset':'0x26b8',
        'native_resource_zero_executed':True,'resource_bytes':SIZE,'guards_each_side':GUARD,
        'ID_capacity':128,'sequential_submissions_equal':96,'public_queue_owners':6,
        'shared_manager_per_resource':True,'DM_equal_cases':equal,'DM_not_equal_cases':not_equal,
        'native_u32_wrap_events':wrapping32,'native_u64_wrap_events':wrapping64,
        'refusal_cases_before_writes':refusals,'whole_resource_and_guards_compared_each_step':True,
        'steps':compared,'native_service_fixtures':services,
        'kernel_lock_clock_mapping_providers_executed':False,'pointer_authentication_executed':False,
        'Linux_policy':['immutable hardware ID/scheduler slot/weight/ratio per queue owner',
                        'reject IDs/workqueue IDs >=128 and data masters >=3 before writes'],
        'hardware_actions':[],'private_instruction_bytes_exported':False,'normal_startup_qualified':False}
    (output/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('macho',type=Path);cli.add_argument('output',type=Path)
    args=cli.parse_args();r=qualify(args.macho,args.output)
    print(json.dumps({k:r[k] for k in ('sequential_submissions_equal','DM_equal_cases','DM_not_equal_cases',
                                     'native_u32_wrap_events','native_u64_wrap_events','refusal_cases_before_writes','hardware_actions')}))
