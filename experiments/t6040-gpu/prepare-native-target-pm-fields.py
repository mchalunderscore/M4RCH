#!/usr/bin/env python3
"""Join checked native render/GTP preparation to exported PM parameter fields offline."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import private_ta_inputs
from private_ta_inputs import load_ta_render_target
p=argparse.ArgumentParser(description=__doc__);p.add_argument('macho',type=Path);p.add_argument('render_profile',type=Path);p.add_argument('pm_profile',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(a.macho.read_bytes())=='3df1db22f1c6d47c2ddc9cf14d57dc6be62ce2fffc3cd8b61bbb423d9f643e7e'
def profile(path):
 r=json.loads(path.read_text());assert r['submission_ready'] is False
 for entry in r['files'].values():
  name=entry.get('file')
  if name:
   data=(path.parent/name).read_bytes();assert len(data)==entry['bytes'] and sha(data)==entry['sha256']
  else:raise ValueError('named profile required')
 return r
pm=profile(a.pm_profile);render=json.loads(a.render_profile.read_text());assert render['submission_ready'] is False
for name,entry in render['files'].items():
 data=(a.render_profile.parent/name).read_bytes();assert len(data)==entry['bytes'] and sha(data)==entry['sha256']
t=render['topology_fixture'];c=pm['configuration_fixtures']
assert pm['aligned_render_profile_sha256']==sha(a.render_profile.read_bytes())
assert c['accelerator4e4']==t['accelerator4e4']
assert int(c['accelerator6d0'],0)==t['flags6d0']
assert c['accelerator11188']==t['memory11188']
assert pm['capacities']['scene_records']==t['record_count']
a.output.mkdir(parents=True,exist_ok=False)
def harness(name,marker):
 path=Path(private_ta_inputs.__file__).with_name(name);text=path.read_text();assert marker in text;ns={'__file__':str(path),'__name__':'preparation'};old=sys.argv
 try:sys.argv=[str(path),str(a.macho),str(a.output/'unused-report.json')];exec(compile(text.split(marker)[0],str(path),'exec'),ns)
 finally:sys.argv=old
 return ns
pack=harness('audit-native-render-storage.py','rng=random.Random(604022);')
loader=harness('audit-private-ta-inputs.py','rng=random.Random(604012);')
source=bytearray((a.render_profile.parent/'render-target-source-fixture.bin').read_bytes());q=lambda off:struct.unpack_from('<Q',source,off)[0]
# Check complete native GTP allocator/packing success path, not hand-filled offsets.
for off,value in [(0x120,pack['A']),(0x128,pack['SH']),(0x1c0,0),(0x1c8,0)]:struct.pack_into('<Q',source,off,value)
pack['m'].mem_write(pack['A']+0x6d0,bytes(8));pack['m'].mem_write(pack['R'],struct.pack('<Q',pack['VT']));pack['m'].mem_write(pack['VT']+0x20,struct.pack('<Q',0x207200));pack['m'].mem_write(pack['R']+0x28,struct.pack('<Q',pack['DESC']));pack['m'].mem_write(pack['DESC']+0x78,struct.pack('<I',0xffffffff));pack['m'].mem_write(pack['R']+0x18,struct.pack('<Q',0x1000060000))
pack['service_mode']=True;pack['service_return']=pack['R'];pack['services'].clear();pack['m'].mem_write(pack['O'],bytes(source));value=pack['run'](0x8a0abec,x0=pack['O']);packed=bytes(pack['m'].mem_read(pack['O'],0x400));pack['service_mode']=None
expected=bytearray(source);gtp=render['gtp'];total=gtp['allocation_bytes'];struct.pack_into('<QQQ',expected,0x1c0,pack['R'],total,total)
for j,v in enumerate(gtp['sizes']):struct.pack_into('<Q',expected,0x1d8+8*j,v)
for j,v in enumerate(gtp['offsets']):struct.pack_into('<Q',expected,0x218+8*j,v)
assert packed==expected and value==0x1000060000
assert pack['services']==[('allocate',[pack['A'],pack['SH'],total,3,5]),('0x207200',[pack['R'],pack['SH']])]
source=bytearray(packed);struct.pack_into('<Q',source,0x130,loader['N']);struct.pack_into('<Q',source,0x1c0,loader['Q'])
initial=bytearray(0x1800);parent=(a.pm_profile.parent/pm['files']['ta-host']['file']).read_bytes()
for field in pm['native_descriptor_fields']:
 off=int(field['offset'],0);n=field['bytes'];assert int.from_bytes(parent[off:off+n],'little')==int(field['value'],0);initial[off:off+n]=parent[off:off+n]
# Keep the two virtual services distinct. These aliases are proposed addresses,
# not assumptions that both provider classes have identical mapping semantics.
bases={('primary',0x160):0xfffffc2000a00000,('primary',0x158):0x1000040000,('support',0x160):0xfffffc2000a20000,('support',0x158):0x1000060000,('retain',0x20):0}
order=[]
def service(resource,slot):
 v=bases[resource,slot];order.append((resource,slot,v));return v
expected=load_ta_render_target(initial,source,service);loader['returns']=[v for _,_,v in order];loader['services'].clear();loader['m'].mem_write(loader['D'],bytes(initial));loader['m'].mem_write(loader['S'],bytes(source));loader['run'](loader['TRTM'])
actual=bytes(loader['m'].mem_read(loader['D'],0x1800));assert actual==expected and loader['services']==order
assert bytes(loader['m'].mem_read(loader['S'],0x400))==source
for field in pm['native_descriptor_fields']:
 off=int(field['offset'],0);n=field['bytes'];assert actual[off:off+n]==initial[off:off+n]
fresh=harness('audit-native-render-fresh.py','rng=random.Random(604024);')
source3d=bytearray(source);struct.pack_into('<Q',source3d,0x130,fresh['N'])
initial3d=actual[:0x1000];fresh['mapped']=bases['primary',0x158];fresh['map_count']=0
fresh['m'].mem_write(fresh['DESC'],initial3d);fresh['m'].mem_write(fresh['O'],bytes(source3d))
fresh['run'](0x895d7b4,x0=fresh['DESC'],x1=fresh['O'])
actual3d=bytes(fresh['m'].mem_read(fresh['DESC'],0x1000))
assert actual3d==fresh['load_render_target'](initial3d,source3d,[bases['primary',0x158]]*3)
assert fresh['map_count']==3 and bytes(fresh['m'].mem_read(fresh['O'],0x400))==source3d
for field in pm['native_descriptor_fields']:
 off=int(field['offset'],0);n=field['bytes']
 if off+n<=len(actual3d):assert actual3d[off:off+n]==initial3d[off:off+n]
for name,data in [('combined-3d-render-pm-fields-fixture.bin',actual3d),('render-target-packed-source-fixture.bin',bytes(source)),('combined-ta-render-pm-fields-fixture.bin',actual)]: (a.output/name).write_bytes(data)
report={'submission_ready':False,'private_binary_sha256':sha(a.macho.read_bytes()),'render_profile_sha256':sha(a.render_profile.read_bytes()),'pm_profile_sha256':sha(a.pm_profile.read_bytes()),'comparisons':{'full_gtp_pack':1,'full_ta_target_loader':1,'full_3d_target_loader':1,'pm_fields_preserved':len(pm['native_descriptor_fields'])},'gtp_bytes':total,'service_order':[{'resource':r,'slot':hex(s),'value':hex(v)} for r,s,v in order],'candidate_regions':[{'name':'ring','device_va':hex(bases['primary',0x158]),'proposed_fw_va':hex(bases['primary',0x160]),'bytes':render['ring']['allocation_bytes']},{'name':'gtp','device_va':hex(bases['support',0x158]),'proposed_fw_va':hex(bases['support',0x160]),'bytes':total}],'resource_domain_requirements':pm['requirements'],'checked_common_configuration':{'render':render['topology_fixture'],'pm':pm['configuration_fixtures']},'files':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in a.output.glob('*.bin')},'qualification':'Actual complete GTP allocation/packing and native TA and3D target loaders compose render profile with15 previously checked PM fields, whole-byte comparisons and unchanged-source/PM-field checks. Addresses are supplied candidate mapping services; FW aliases not installed or class-qualified. PM and render fixtures share topology, accelerator memory/flags and16 scene records. Memory-provider budget remains a supplied policy fixture; genuine configuration still requires validation. Partial zero-base host descriptor, not complete TA/3D work or executable job. No hardware/GPU execution.'}
(a.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(report['comparisons'])
