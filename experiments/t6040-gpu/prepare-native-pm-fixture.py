#!/usr/bin/env python3
"""Export checked initialized/retained PM data and identity requirements; not submittable."""
from pathlib import Path
import sys,json,hashlib,struct
import private_render_inputs
if '--prepared-output' not in sys.argv:raise SystemExit('required: --prepared-output NEW_DIRECTORY')
arg_index=sys.argv.index('--prepared-output');prepared_output=Path(sys.argv[arg_index+1]);del sys.argv[arg_index:arg_index+2]
prepared_output.mkdir(parents=True,exist_ok=False)
base=Path(private_render_inputs.__file__).with_name('audit-private-pm-initialized-retain.py')
source=base.read_text();pm_export_source_text=source
def export_initialized_fixture():
    pm=bytes(m.mem_read(S,0x300));capacity=struct.unpack_from('<I',pm,0x148)[0]
    slot_count=struct.unpack_from('<I',pm,0xb0)[0];state_count=struct.unpack_from('<I',pm,0x60)[0]
    factor=struct.unpack_from('<Q',pm,0x1d8)[0];page_bytes=capacity*factor*4
    assert capacity>=2 and page_bytes>=16 and slot_count>0 and state_count>0
    snapshots=[('pm-host',S,0x300),('manager-host',HWM,0x100),('ta-host',D,0x1800),('block-host',BLOCK,0x100),('hw-state',STATE,0xc0),('hw-counter',COUNTER,4),('config',CPU60[1],0x80),('scene-records',CPU60[0],slot_count*0x80),('aux-records',CPU50[0],(slot_count+1)*0x80),('block-frame-indices',CPU60[2],capacity*8),('page-list',PAGE_BUFFER,page_bytes),('packed-ring-index-fixture',RING,32*16),('staged-host',STAGED,0x40)]
    for off,label in [(0xa8,'vector-a-host'),(0x88,'vector-b-host')]:snapshots.append((label,struct.unpack_from('<Q',pm,off)[0],slot_count*8))
    files={}
    for name,data in [('device-config-input-fixture.bin',bytes(device)),('queue-config-input-fixture.bin',bytes(qcfg))]:
        (prepared_output/name).write_bytes(data);files[name]={'file':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'domain':'supplied configuration input'}
    for label,address,size in snapshots:
        data=bytes(m.mem_read(address,size));name=label+'-fixture.bin';(prepared_output/name).write_bytes(data)
        files[label]={'file':name,'bytes':size,'sha256':hashlib.sha256(data).hexdigest(),'fixture_cpu_address':hex(address)}
    associations=[]
    for off,label in [(0xd78,'page mapping'),(0xd88,'HWPB kernel-resource mapping'),(0xd90,'HWPB secondary mapping'),(0xd98,'discard inner object'),(0xda8,'PM internal resource40'),(0xda0,'HWPB internal resource90'),(0xdc0,'PM internal resource30'),(0xdb0,'scene inner object'),(0xdb8,'metrics resource')]:
        value=struct.unpack('<Q',m.mem_read(D+off,8))[0];assert value!=0
        associations.append({'ta_host_offset':hex(off),'resource':label,'fixture_object':hex(value),'domain':'host object identity; not a firmware or GPU address'})
    fields=[]
    for off,width,label in [(0x910,8,'selected vector-a value, 3D tail'),(0x918,8,'selected vector-b value, 3D tail'),(0x920,8,'mTile getter'),(0x928,8,'mList getter'),(0x930,8,'vHeap getter'),(0x938,8,'aux record end'),(0x948,4,'parameter field1d4'),(0x1228,8,'selected vector-a value, TA'),(0x1230,8,'selected vector-b value, TA'),(0x1238,8,'TA mTile getter'),(0x1240,8,'TA mList getter'),(0x1248,8,'TA vHeap getter'),(0x1250,8,'TA aux record end'),(0x1258,4,'TA parameter field1d4'),(0x1268,4,'selected scene index')]:
        value=int.from_bytes(m.mem_read(D+off,width),'little');fields.append({'offset':hex(off),'bytes':width,'label':label,'value':hex(value),'qualification':'native copied value; resource-domain conversion must be resolved before publication'})
    scene_pm=bytes(pm);_,_,_,scene_stride,scene_size=scene_setup(scene_pm,gpu,bytes(0x100),bytes(0x1000),dict(block_alloc=BLOCKALLOC,scene_alloc=SCALLOC,resource=SRESOURCE,discard_resource=DISCARD),[0],scene_map,0)
    profile={'submission_ready':False,'case':i,'private_binary_sha256':sha,'source_harness_sha256':hashlib.sha256(pm_export_source_text.encode()).hexdigest(),'files':files,'configuration_fixtures':{'accelerator4e4':int.from_bytes(m.mem_read(GPU+0x4e4,4),'little'),'accelerator6d0':hex(int.from_bytes(m.mem_read(GPU+0x6d0,8),'little')),'accelerator11188':int.from_bytes(m.mem_read(GPU+0x11188,8),'little'),'memory_provider_return':memory},'capacities':{'block_capacity':capacity,'scene_records':slot_count,'state_slots':state_count,'page_factor':factor,'page_list_resource_bytes':page_bytes,'page_entries_written':4,'block_memory_bytes':0x20000,'block_alignment':0x8000,'hw_state_bytes':0xc0,'counter_bytes':4,'scene_stride':scene_stride,'scene_resource_bytes':scene_size,'discard_bytes':0x8000,'ring_indices_checked':32,'packed_ring_entry_bytes':16},'block_mapping_fixture':hex(block_address),'frame_indices':list(struct.unpack('<4I',m.mem_read(PAGE_BUFFER,16))),'native_descriptor_fields':fields,'host_resource_associations':associations,'requirements':['replace CPU object and mapping-service identities with genuine Linux objects; host resource fields are not GPU pointers','resolve firmware-visible aliases for native copied vector/scene/aux values','rebuild page entries for the real parameter-block mapping','regenerate packed hardware-ring entries from real state and addresses; 32 checked indices do not prove actual ring capacity','initialize event/counter/cache/ownership and completion lifetimes','connect the native render-target/shader/state fields and final TA/3D work serialization'],'qualification':'Snapshot after all initializer/retention/TA-window comparisons pass in actual native chain. Preserved bytes may be random input or external-service fixtures, not required initialized values. Raw snapshots are research fixtures, never a publishable job. No GPU execution or live allocation proved.'}
    (prepared_output/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
needle="joined_counts['initializer_mode_one'] += 1"
assert source.count(needle)==1
source=source.replace(needle,needle+'\n        if i == 0: export_initialized_fixture()')
__file__=str(base)
exec(compile(source,str(base),'exec'))
assert (prepared_output/'profile.json').exists()
export_report=json.loads(args.output.read_text());export_report['prepared_profile_sha256']=hashlib.sha256((prepared_output/'profile.json').read_bytes()).hexdigest();export_report['prepared_files']=len(json.loads((prepared_output/'profile.json').read_text())['files']);export_report['prepared_submission_ready']=False;args.output.write_text(json.dumps(export_report,indent=2)+'\n')
print('Exported checked PM retention fixture and explicit identity/relocation requirements')
