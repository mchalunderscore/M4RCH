"""Bind checked ordinary3D descriptor fields to common scheduler inputs.

Queue/provider/epoch/QOS/payload mappings are explicit fixtures. Not a live job.
"""
import struct
from private_nop_body import convert_timestamp
from native_scheduler_candidate import bounded

def derive(descriptor, template):
    out=dict(template);spec=out.pop('native_3d')
    forbidden={'dependencies','rce_kind','auxiliary','alternate_kind','extra_flag','payload'}
    if forbidden.intersection(out):
        raise ValueError('Native 3D scheduler fields must derive from descriptor/provider bindings')
    epochs=spec['event_epochs']
    if not isinstance(epochs,list) or len(epochs)!=24 or any(not isinstance(pair,list) or len(pair)!=2 for pair in epochs):
        raise ValueError('24 explicit pairs of event-machine epochs required')
    epochs=[[bounded(value,64,'event epoch') for value in pair] for pair in epochs]
    if not isinstance(spec['cached'],bool):
        raise ValueError('Explicit cached-previous flag required')
    event,index=struct.unpack_from('<2I',descriptor,0x210)
    if index>=24:raise ValueError('Event backing index outside qualified0..23')
    q=dict(out['queue']);capacity=bounded(q['capacity'],32,'queue capacity');initial=bounded(q['initial'],64,'queue initial')
    if not spec['cached']:
        previous=(convert_timestamp(epochs[index][event>>31],event,capacity,initial)-1)&((1<<64)-1)
        if 'previous' in q and bounded(q['previous'],64,'previous')!=previous:
            raise ValueError('Uncached previous must derive from descriptor event')
        q['previous']=previous
    out['queue']=q
    count=struct.unpack_from('<I',descriptor,0x218)[0]
    if count>8:raise ValueError('Dependency count outside qualified0..8')
    deps=[]
    for j in range(count):
        ev,ix=struct.unpack_from('<2I',descriptor,0x21c+j*12)
        if ix>=24:raise ValueError('Dependency backing index outside qualified0..23')
        deps.append(dict(event=ev,index=ix,epoch=epochs[ix][ev>>31]))
    out['dependencies']=deps
    out['rce_kind']=struct.unpack_from('<I',descriptor,0x820)[0]&3
    auxiliary=struct.unpack_from('<Q',descriptor,0x168)[0]
    out['auxiliary']=auxiliary or bounded(spec['fallback_auxiliary'],64,'fallback auxiliary')
    out['alternate_kind']=descriptor[0xc44]==3 or bool(descriptor[0x4c]&1)
    out['extra_flag']=bool(descriptor[0xb48]&1)
    out['payload']=[struct.unpack_from('<Q',descriptor,0x448)[0],bounded(spec['channel_payload'],64,'channel payload')]
    return out
