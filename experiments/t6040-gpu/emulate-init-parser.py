#!/usr/bin/env python3
"""Bounded offline execution model for a captured G16S root parser.

Only captured instructions, captured firmware DATA and explicit model buffers
exist in the emulator. No devices, host physical memory or live firmware access.
RTKit receive is substituted; pointer authentication is intentionally omitted.
Unknown code paths and unmapped memory stop the model, never receive auto maps.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unicorn as u
from unicorn import arm64_const as c
from firmware_text_contract import qualify

FW = 0xfffffc0000000000
ROOT = 0xfffffc2000100000
STACK = 0x4000000


def graph_fixture(enabled):
    # Zero templates are explicit MODEL FIXTURES ONLY. They are never emitted
    # as hardware-ready objects; unknown target size is deliberately provisional.
    spec = importlib.util.spec_from_file_location('assembler',Path(__file__).with_name('assemble-init-graph.py'))
    a = importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
    templates = {o['name']:bytes(o['extent'] or 0x100) for o in a.graph_plan.plan()['objects']}
    root=bytearray(templates['root'])
    struct.pack_into('<Q',root,0,0x0c8aa322039604c0)
    struct.pack_into('<I',root,0x2c,int(enabled))
    # Page-table geometry from the matching donor serializer; native trial
    # uses these candidate fields with our owned mapping, not donor addresses.
    struct.pack_into('<HBB',root,0x30,0x4000,14,3)
    for i,(shift,entries) in enumerate([(36,64),(25,2048),(14,2048)]):
        off=0x34+i*0x20
        struct.pack_into('<4BHHQQQ',root,off,8,14,14,shift,entries,0x4000,
                         1,0x3ffffffc000,(entries-1)<<shift)
    templates['root']=bytes(root)
    hardware=bytearray(templates['hardware'])
    struct.pack_into('<I',hardware,0xe90,0x6040)
    templates['hardware']=bytes(hardware)
    for name in ['status_a','status_b']:
        status=bytearray(templates[name]);struct.pack_into('<I',status,4,1)
        templates[name]=bytes(status)
    return a.assemble(templates,ROOT)


def run(text,data,enabled=False,instruction_limit=20000):
    contract=qualify(text)
    if len(data)!=0x138000:
        raise ValueError('Wrong DATA extent')
    arena,graph=graph_fixture(enabled)
    machine=u.Uc(u.UC_ARCH_ARM64,u.UC_MODE_ARM)
    machine.mem_map(FW,0x60000,u.UC_PROT_READ|u.UC_PROT_EXEC)
    machine.mem_write(FW,text)
    machine.mem_map(FW+0x60000,len(data),u.UC_PROT_READ|u.UC_PROT_WRITE)
    machine.mem_write(FW+0x60000,data)
    machine.mem_map(ROOT,len(arena),u.UC_PROT_READ|u.UC_PROT_WRITE)
    machine.mem_write(ROOT,arena)
    machine.mem_map(STACK,0x10000,u.UC_PROT_READ|u.UC_PROT_WRITE)
    machine.reg_write(c.UC_ARM64_REG_SP,STACK+0xf000)
    machine.reg_write(c.UC_ARM64_REG_CPACR_EL1,3<<20)
    events=[];accesses=[];steps=0;outcome='instruction-limit';stop_pc=None
    objects=graph['objects']
    def stop(reason,pc):
        nonlocal outcome,stop_pc
        outcome=reason;stop_pc=hex(pc);machine.emu_stop()
    def read_string(address):
        value=bytearray()
        for i in range(512):
            b=machine.mem_read(address+i,1)
            if b==b'\0':return value.decode('utf-8',errors='replace')
            value.extend(b)
        raise ValueError('Unterminated diagnostic format')
    def code_hook(mu,address,size,opaque):
        nonlocal steps
        steps+=1
        offset=address-FW
        if offset==0x46fe4:
            if mu.reg_read(c.UC_ARM64_REG_W0)!=32 or mu.reg_read(c.UC_ARM64_REG_W2)!=0xffffffff:
                stop('unexpected-receive-arguments',address);return
            destination=mu.reg_read(c.UC_ARM64_REG_X1)
            packet=0x0081000000000000|(ROOT&0x00000fffffffffff)
            mu.mem_write(destination,struct.pack('<Q',packet))
            mu.reg_write(c.UC_ARM64_REG_W0,0)
            events.append(dict(kind='substituted-RTKit-receive',packet=hex(packet)))
            mu.reg_write(c.UC_ARM64_REG_PC,mu.reg_read(c.UC_ARM64_REG_LR));return
        if offset==0x4372c:
            fmt=read_string(mu.reg_read(c.UC_ARM64_REG_X0))
            events.append(dict(kind='fatal-diagnostic',format=fmt,
                               caller=hex(mu.reg_read(c.UC_ARM64_REG_LR))))
            stop('firmware-fatal-path',address);return
        if offset==0x2fa04:
            stop('root-parser-return',address);return
        # Only explicitly reviewed parser/helper functions are executable.
        if not (0x2f204<=offset<0x2fa30 or 0x2ab0<=offset<0x2ef0 or 0x30a8<=offset<0x3390):
            stop('unreviewed-code-target',address);return
        word=struct.unpack('<I',mu.mem_read(address,4))[0]
        if word==0xd503237f: # PACIBSP
            events.append(dict(kind='omitted-pointer-authentication',pc=hex(address)))
            mu.reg_write(c.UC_ARM64_REG_PC,address+4)
        elif word==0xd65f0fff: # RETAB in a helper
            events.append(dict(kind='omitted-authenticated-return',pc=hex(address)))
            mu.reg_write(c.UC_ARM64_REG_PC,mu.reg_read(c.UC_ARM64_REG_LR))
    def memory_hook(mu,kind,address,size,value,opaque):
        if ROOT<=address<ROOT+len(arena):
            for obj in objects:
                start=ROOT+obj['arena_offset']
                if start<=address<start+obj['reserved_bytes']:
                    offset=address-start
                    accesses.append(dict(pc=hex(mu.reg_read(c.UC_ARM64_REG_PC)),object=obj['name'],
                                         offset=hex(offset),bytes=size,mode='write' if kind==u.UC_MEM_WRITE else 'read',
                                         within_explicit_template=offset+size<=obj['input_bytes']))
                    if offset+size>obj['input_bytes']:
                        stop('access-beyond-explicit-template',mu.reg_read(c.UC_ARM64_REG_PC))
                    break
    def invalid_hook(mu,kind,address,size,value,opaque):
        events.append(dict(kind='unmapped-memory',access_kind=kind,address=hex(address),bytes=size))
        stop('unmapped-memory',mu.reg_read(c.UC_ARM64_REG_PC));return False
    machine.hook_add(u.UC_HOOK_CODE,code_hook)
    machine.hook_add(u.UC_HOOK_MEM_READ|u.UC_HOOK_MEM_WRITE,memory_hook)
    machine.hook_add(u.UC_HOOK_MEM_INVALID,invalid_hook)
    error=None
    try:
        machine.emu_start(FW+0x2f204,0,count=instruction_limit,timeout=5_000_000)
    except u.UcError as exc:
        error=str(exc)
        if outcome=='instruction-limit':outcome='emulator-error'
    return dict(emulator='Unicorn '+u.__version__,text_contract=contract,
                data_sha256=hashlib.sha256(data).hexdigest(),enabled_allocation_model=enabled,
                explicit_zero_templates=True,graph_receipt=graph,instructions_observed=steps,
                outcome=outcome,stop_pc=stop_pc,emulator_error=error,
                substituted_or_omitted_operations=events,object_accesses=accesses,
                qualification='Offline bounded parser model only. RTKit receive substituted; pointer authentication omitted. Cold captured DATA and explicit zero object fixtures are not a complete running-firmware environment. No hardware acceptance, initialization, mapping, timing or rendering established.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture',type=Path)
    p.add_argument('--enabled-model',action='store_true')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=run((a.capture/'text.bin').read_bytes(),(a.capture/'data-before.bin').read_bytes(),a.enabled_model)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(result['outcome'],result['stop_pc'],result['instructions_observed'],'instructions,',len(result['object_accesses']),'object accesses')


if __name__=='__main__':main()
