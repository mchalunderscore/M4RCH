"""Full RGBA8 readback and conditional source-derived image comparison."""
import hashlib,json,os,struct,subprocess,sys,zlib
from pathlib import Path
RECIPE_HASHES={'prepare-apple9-shaders.py':'2c5836031e8dd370f4b242baf5449aefcbc90e6346ab8f9d6f08870970666cdb','prepare-apple9-target.py':'9586b6f853f183fc47ba4982bac940e68019992ff4ea4a93cdf08b805e20e5b1'}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def pixel_model(x,y):
 nx=(x+.5)/32-1;ny=(y+.5)/32-1
 blue=(ny+.75)/1.5;green=((nx+.75)-.75*blue)/1.5;red=1-green-blue
 near=min(abs(red),abs(green),abs(blue))<.03
 inside=min(red,green,blue)>=0
 rgba=[red*red,green+.125,blue*.5,1] if inside else [.5625,.625,.125,1]
 return bytes(round(max(0,min(1,c))*255) for c in rgba),inside,near
def check_full(receipt,data):
 for name,h in RECIPE_HASHES.items():
  if sha((Path(__file__).resolve().parent.parent/name).read_bytes())!=h:raise ValueError('Canonical source recipe changed: '+name)
 target=receipt['target']
 if (target['width'],target['height'],target['stride_bytes'],target['bytes'],target['format'],target['address'])!=(64,64,256,16384,'RGBA8 UNORM','0x2000010000') or len(data)!=16384:raise ValueError('Target layout/extent differs')
 sentinel=bytes([target['sentinel']])*16384
 counts={'interior_tested':0,'background_tested':0,'edge_excluded':0,'interior_mismatch':0,'background_mismatch':0};maximum=0;changed_pixels=0
 for y in range(64):
  for x in range(64):
   at=y*256+x*4;actual=data[at:at+4];expected,inside,near=pixel_model(x,y)
   changed_pixels+=actual!=sentinel[at:at+4]
   if near:counts['edge_excluded']+=1;continue
   kind='interior' if inside else 'background';counts[kind+'_tested']+=1
   error=max(abs(a-b) for a,b in zip(actual,expected));maximum=max(maximum,error)
   counts[kind+'_mismatch']+=error>2
 for sample in receipt['interior_reference_samples']:
  expected,inside,near=pixel_model(*sample['pixel_y_up'])
  if list(expected)!=sample['rgba8_nearest'] or not inside or near:raise ValueError('Bound shader reference differs')
 return dict(bytes=len(data),sha256=sha(data),untouched_sentinel=data==sentinel,changed_bytes=sum(a!=b for a,b in zip(data,sentinel)),changed_pixels=changed_pixels,whole_image_counts=counts,maximum_tested_channel_error=maximum,source_recipe_sha256=RECIPE_HASHES,target_recipe=target,target_owned_page=132,source_draw_receipt_sha256=receipt['draw_receipt_sha256'],
  conditional_candidate_pattern_matches=not(counts['interior_mismatch'] or counts['background_mismatch']),full_image_layout_hardware_verified=False,rendering_verified=False,
  qualification='Every pixel preserved; interior/background comparison derives from the pinned canonical shader recipe under provisional y-up linear layout, UNORM quantization and raster coverage. Edge pixels are counted but excluded from exact match. A CPU-written matching image does not prove GPU execution or completion.')
def png(data):
 if len(data)!=16384:raise ValueError('Full target required')
 def chunk(kind,payload):return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
 scan=b''.join(b'\0'+data[y*256:(y+1)*256] for y in reversed(range(64)))
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b'')

def retained_owner_guard(selected,boot,receipt):
 from cold_render_contract import module_build_note,require
 selected=Path(selected);owner=Path('/sys/module/asc_graph_init')
 require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot,'Boot changed during retained RAM capture')
 require(owner.exists(),'Retained owner missing')
 require(sha(selected.read_bytes())==receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'],'Selected owner changed')
 note=(owner/'notes/.note.gnu.build-id').read_bytes()
 require(note==module_build_note(selected.read_bytes()),'Retained owner GNU note differs')
 ref=int((owner/'refcnt').read_text());require(ref==1,'Retained owner refcount differs from1')
 require(os.uname().release==receipt['kernel_release'] and sha(Path('/sys/kernel/notes').read_bytes())==receipt['kernel_notes_sha256'],'Retained kernel identity differs')
 return dict(boot_id=boot,owner_GNU_note_hex=note.hex(),owner_refcount=ref,kernel_release=receipt['kernel_release'],kernel_notes_sha256=receipt['kernel_notes_sha256'])

def retained_sampler_guard(raw_module):
 from cold_render_contract import module_build_note,require
 sampler=Path('/sys/module/gpu_data_sample')
 require(sampler.exists(),'Loaded fixed RAM sampler missing')
 note=(sampler/'notes/.note.gnu.build-id').read_bytes()
 require(note==module_build_note(raw_module),'Loaded fixed RAM sampler GNU note differs')
 ref=int((sampler/'refcnt').read_text());require(ref==0,'Loaded fixed RAM sampler refcount differs from0')
 return dict(sampler_GNU_note_hex=note.hex(),sampler_refcount=ref)

def capture_retained_ram(candidate,output,selected,boot,receipt):
 """Two disjoint fixed RAM reads; a temporary sampler is the only module touched."""
 from cold_render_contract import RETAINED_SAMPLERS,require
 candidate=Path(candidate);output=Path(output);record_path=output/'retained-ram-capture.json'
 require(not record_path.exists(),'Retained RAM capture already recorded; no retry')
 report=dict(schema='m4rch.gfx-native-dispatch-retained-ram-capture.v1',boot_id=boot,complete=False,non_atomic_snapshot=True,IOP_cache_writeback_proved=False,GPU_commands=[],GPU_register_reads=False,firmware_RAM_writes=False,owner_unload_OFF_PMput_free=False,samplers=[],errors=[])
 def save():record_path.write_text(json.dumps(report,indent=2)+'\n');os.sync()
 save()
 for spec in RETAINED_SAMPLERS:
  row=dict(spec,load_intent=False,unload_intent=False,complete=False);report['samplers'].append(row);save()
  loaded=False;custody_failed=False
  try:
   # RAM reads remain independent of log association and pipeline success.
   for name in ('objects-after.bin','owned-after.bin','notifications-after.bin','target-after.png','dmesg-after.log'):
    require((output/name).exists(),'Own raw capture missing before retained RAM: '+name)
   before=retained_owner_guard(selected,boot,receipt);row['owner_before']=before
   require(not Path('/sys/module/gpu_data_sample').exists(),'Temporary sampler already present')
   module=candidate/spec['module'];raw_module=module.read_bytes()
   require(sha(raw_module)==spec['module_sha256'],'Fixed RAM sampler module differs')
   row['load_intent']=True;save()
   result=subprocess.run(['insmod',str(module)],capture_output=True,text=True)
   row['load_returncode']=result.returncode;row['load_stdout']=result.stdout;row['load_stderr']=result.stderr
   loaded=result.returncode==0
   require(loaded,'Fixed RAM sampler load failed')
   try:row['sampler_loaded']=retained_sampler_guard(raw_module)
   except Exception:
    custody_failed=True;raise
   raw=Path('/sys/kernel/m4rch_gpu_data_sample/data').read_bytes()
   # Preserve the raw bytes even when an extent check fails.
   destination=output/spec['name'];destination.write_bytes(raw)
   row['capture']=dict(name=spec['name'],bytes=len(raw),sha256=sha(raw));save()
   require(len(raw)==spec['bytes'],'Fixed RAM sampler extent differs')
  except Exception as error:
   row['error']=str(error);report['errors'].append(spec['name']+': '+str(error))
  finally:
   if loaded:
    try:
     require(not custody_failed,'Sampler custody mismatch; leave resident and stop captures')
     row['sampler_before_unload']=retained_sampler_guard(raw_module)
     row['owner_before_unload']=retained_owner_guard(selected,boot,receipt)
     require(row['owner_before_unload']==row['owner_before'],'Retained owner changed before sampler unload')
     row['unload_intent']=True;save()
     result=subprocess.run(['rmmod','gpu_data_sample'],capture_output=True,text=True)
     row['unload_returncode']=result.returncode;row['unload_stdout']=result.stdout;row['unload_stderr']=result.stderr
     require(result.returncode==0 and not Path('/sys/module/gpu_data_sample').exists(),'Temporary sampler unload incomplete')
    except Exception as error:
     row['unload_error']=str(error);report['errors'].append(spec['name']+': '+str(error))
   try:
    after=retained_owner_guard(selected,boot,receipt);row['owner_after']=after
    require(row.get('owner_before')==after,'Retained owner identity changed')
    require(not Path('/sys/module/gpu_data_sample').exists(),'Temporary sampler remains loaded')
    row['complete']=not any(k in row for k in ('error','unload_error'))
   except Exception as error:
    row['owner_error']=str(error);report['errors'].append(spec['name']+': '+str(error))
   save()
  # Never replace a lingering sampler or continue after an owner identity change.
  if 'unload_error' in row or 'owner_error' in row:break
 report['complete']=len(report['samplers'])==2 and all(r['complete'] for r in report['samplers']) and not report['errors']
 save();return report

PRE_CYCLE_SCHEMA='m4rch.gfx-native-idle-policy-fender-cycle-pre-cycle-attempt.v1'
WRITE_ONCE_CODE='''import os,sys
fd=os.open(sys.argv[1],os.O_WRONLY)
try:
 raw=sys.argv[2].encode('ascii')
 count=os.write(fd,raw)
 if count!=len(raw):raise RuntimeError('Short command write; no retry')
finally:os.close(fd)
'''
def verify_pre_cycle(output,manifest):
 from cold_render_contract import require
 output=Path(output)
 require(manifest.get('schema')==PRE_CYCLE_SCHEMA and manifest.get('complete') is True,'Pre-cycle manifest differs')
 for p in manifest['capture_pins']:
  path=output/p['relative'];require(path.resolve().is_relative_to(output.resolve()) and not path.is_symlink(),'Pre-cycle path differs')
  raw=path.read_bytes();require(len(raw)==p['bytes'] and sha(raw)==p['sha256'],'Immutable pre-cycle input changed: '+p['relative'])
 return True

def seal_pre_cycle(candidate,output,selected,boot,receipt):
 from cold_render_contract import require
 candidate=Path(candidate);output=Path(output);selected=Path(selected)
 attempt=json.loads((output/'attempt.json').read_text())
 require(attempt.get('complete') is True and attempt.get('raw_capture_complete') is True and attempt.get('capture_errors')==[] and attempt.get('operation_uncertain') is False,'Complete bound draw capture required before cycle')
 require(attempt.get('retained_RAM_complete') is True,'Full DATA/PT capture required before cycle')
 require(all(attempt.get(name,{}).get('qualified') is True for name in ('pipeline','publication','trace_preserved')),'Own successful 15s draw pipeline required before cycle')
 require(not attempt.get('analysis_error'),'Draw analysis incomplete before cycle')
 require(attempt['boot_id']==boot and attempt['session']==str(output) and attempt['candidate']==str(candidate),'Pre-cycle session identity differs')
 guard=retained_owner_guard(selected,boot,receipt)
 require(attempt['owner_sha256']==sha(selected.read_bytes()) and attempt['loaded_owner_note_hex']==guard['owner_GNU_note_hex'],'Pre-cycle own module binding differs')
 for pin in attempt['capture_pins']:
  raw=(output/pin['name']).read_bytes();require(len(raw)==pin['bytes'] and sha(raw)==pin['sha256'],'Draw raw input changed before cycle: '+pin['name'])
 destination=output/'pre-cycle-attempt.json';require(not destination.exists(),'Pre-cycle manifest already consumed; no cycle retry')
 files=sorted(path for path in output.rglob('*') if path.is_file() and not path.name.startswith('cycle-'))
 require(files and not any(path.is_symlink() for path in files),'Pre-cycle capture inventory differs')
 pins=[dict(relative=str(path.relative_to(output)),bytes=path.stat().st_size,sha256=sha(path.read_bytes())) for path in files]
 manifest=dict(schema=PRE_CYCLE_SCHEMA,complete=True,boot_id=boot,owner_sha256=attempt['owner_sha256'],owner_GNU_note_hex=guard['owner_GNU_note_hex'],candidate_receipt_sha256=attempt['candidate_receipt_sha256'],attempt_sha256=sha((output/'attempt.json').read_bytes()),capture_pins=pins,host_verified_full_capture=True,IOP_cache_writeback_verified=False,draw_execution_verified=False,retirement_verified=False)
 raw=(json.dumps(manifest,indent=2)+'\n').encode()
 with destination.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 verify_pre_cycle(output,manifest)
 for path in [*files,destination]:
  os.chmod(path,0o444)
  with path.open('rb') as f:os.fsync(f.fileno())
 fd=os.open(output,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
 require(destination.read_bytes()==raw,'Pre-cycle manifest changed while sealing')
 return sha(raw),manifest

def attempt_postdraw_cycle(candidate,output,selected,boot,receipt):
 """One native cycle after immutable full draw capture; postcycle dmesg only."""
 from cold_render_contract import require,associate_logs,rows
 from analyze_cold_render import qualify_postdraw_cycle,observe_postdraw_cycle
 candidate=Path(candidate);output=Path(output);destination=output/'cycle-attempt.json'
 require(not destination.exists(),'Cycle attempt already exists; no retry')
 report=dict(schema='m4rch.gfx-native-idle-policy-fender-cycle-operation.v1',boot_id=boot,stage='capture-admission',command_intent=False,write_attempted=False,command_uncertain=False,command_replayed=False,postcycle_GPU_register_reads=False,postcycle_RAM_samplers=False,backing_freed=False,owner_unloaded=False,errors=[],cycle_capture_complete=False,management_rejoin_verified=False,retirement_verified=False,native_idle_policy_caller_order_reproduced=False)
 def save():
  destination.write_text(json.dumps(report,indent=2)+'\n');os.sync()
 save()
 try:
  token,manifest=seal_pre_cycle(candidate,output,selected,boot,receipt)
  report.update(capture_token=token,pre_cycle_manifest_sha256=token,pre_cycle_inputs=len(manifest['capture_pins']),stage='pre-cycle-capture-sealed')
  before=subprocess.check_output(['dmesg','--color=never'],text=True)
  (output/'cycle-dmesg-before.log').write_text(before)
  verify_pre_cycle(output,manifest)
  require(sha((output/'pre-cycle-attempt.json').read_bytes())==token,'Pre-cycle token changed')
  retained_owner_guard(selected,boot,receipt)
  command='postdraw-native-cycle '+token+'\n'
  report.update(command=command.rstrip(),command_intent=True,write_attempted=True,command_uncertain=True,stage='cycle-write-intent');save()
  # Exactly one child and one write; timeout/write errors never replay the command.
  try:
   result=subprocess.run([sys.executable,'-c',WRITE_ONCE_CODE,'/sys/kernel/m4rch_gpu_graph_trial/command',command],capture_output=True,text=True,timeout=45)
   report.update(write_returncode=result.returncode,write_stdout=result.stdout,write_stderr=result.stderr)
   if result.returncode:report['errors'].append('Cycle write failed; command may have executed and will not be retried')
  except Exception as error:report['errors'].append(str(error))
  report['stage']='cycle-write-return';save()
  # No ASC/SGX/owned sysfs or physical RAM reads after an uncertain OFF.
  after=subprocess.check_output(['dmesg','--color=never'],text=True)
  (output/'cycle-dmesg-after.log').write_text(after)
  try:
   association,delta=associate_logs(before,after);report['log_association']=association
   (output/'cycle-operation-delta.log').write_text(delta)
   report['raw_cycle_rows']={name:rows(delta,name) for name in ('gfx-postdraw-native-cycle','gfx-postdraw-native-cycle-state','gfx-postdraw-native-cycle-off','gfx-postdraw-native-cycle-on','gfx-postdraw-native-cycle-physical','gfx-postdraw-native-cycle-management','gfx-postdraw-native-nmi','gfx-postdraw-native-nmi-rx','gfx-runtime-active','gfx-runtime-guard-refused','gfx-native-fender-disable','gfx-native-fender-disable-op','gfx-native-idle-policy','gfx-native-idle-policy-state','gfx-native-idle-policy-control','gfx-native-idle-policy-power','gfx-native-idle-policy-bounds','gfx-native-idle-policy-application','gfx-native-idle-policy-record','gfx-native-idle-policy-producer','gfx-native-idle-policy-tx','gfx-native-idle-policy-rx')}
   try:report['independent_shutdown_observations']=observe_postdraw_cycle(delta,token)
   except (ValueError,KeyError,TypeError,IndexError) as error:report['independent_shutdown_observations']=dict(qualified=False,error=str(error))
   try:
    report['qualification']=qualify_postdraw_cycle(delta,token)
    report['management_rejoin_verified']=True;report['command_uncertain']=False
   except (ValueError,KeyError) as error:report['qualification']=dict(qualified=False,error=str(error))
  except ValueError as error:report['log_association']=dict(qualified=False,error=str(error))
  verify_pre_cycle(output,manifest)
  require(sha((output/'pre-cycle-attempt.json').read_bytes())==token,'Immutable pre-cycle manifest changed after cycle')
  report.update(cycle_capture_complete=True,stage='management-rejoin-qualified' if report['management_rejoin_verified'] else 'cycle-unknown-retained')
 except Exception as error:
  report['errors'].append(str(error));report['stage']='cycle-unknown-retained' if report['command_intent'] else 'cycle-not-admitted'
 report['capture_pins']=[dict(name=name,bytes=(output/name).stat().st_size,sha256=sha((output/name).read_bytes())) for name in ('pre-cycle-attempt.json','cycle-dmesg-before.log','cycle-dmesg-after.log','cycle-operation-delta.log') if (output/name).exists()]
 save();return report
