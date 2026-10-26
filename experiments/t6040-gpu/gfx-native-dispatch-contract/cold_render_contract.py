"""Distinct cold application/control/draw contract, with no recovery count gate."""
import hashlib,json,re,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent),str(HERE.parent/'gfx-native-ap-repeat-cycle')]
from gfx_native_ap_repeat_cycle_contract import REFUSED_BOOTS,qualify_adt,qualify_linux_dt
REFUSED_BOOTS=(*REFUSED_BOOTS,'1241f6b5-f2c5-4678-9078-dce0ed367d60','eff8eafa-d845-429e-b98c-9a5f053bcc46')
FAMILY_KEY='gfx_native_dispatch_contract_scope'
CONTRACT={'version':15,'compile_macro':'GFX_NATIVE_DISPATCH_CONTRACT_TRIAL','automatic_cold_pipeline':True,
 'initial_recovery_cycles':0,'minimum_completed_idle_recovery_cycles':0,'application_restarts':0,
 'maximum_control_notifications':1,'maximum_draw_intents':1,'maximum_draw_notifications':1,
 'control_before':[32,32,32],'control_after':[33,33,33],'control_opcode':22,'control_record_index':32,
 'control_record_bytes':64,'control_record_offset':753664+32*64,'control_timeout_ms':5000,
 'control_packet':0x0084000000000000,'draw_packet':0x0083000000000000,'endpoint':33,
 'target_owned_page':132,'target_bytes':16384,'target_width':64,'target_height':64,'target_stride':256,
 'owned_pages':174,'completion_owned_page':159,'queue_owned_pages':[160,161,162,163],
 'hardware_completion_owned_pages':[164,165,166,167],'post_submit_window_ms':15000,
 'owner_parameters':['run_gate=2','observe_ms=5000','resident_session=1'],
 'retain_PM_and_backing_after_work':True,'automatic_powergate':False,'backing_release':False,
 'automatic_retry':False,'recovery_phase_writes':False,'class86_sent':False,
 'gpu_execution_verified':False,'rendering_verified':False,'dma_retirement_verified':False,
 'commands':['sample','gfx-snapshot']}
CONTRACT.update(maximum_scheduler_request_writes=0,scheduler_ack_writes=0,native_reason_mutex_owned=False,native_reason_lifecycle_reproduced=False,maximum_trace_restore_writes=1,trace_mask_after_control=0,trace_mask_before_draw=3,trace_mask_retained_after_draw=3,native_config_getter_changed_bytes=4,no_extra_notification_for_trace=True,hardware_completion_device_vas=[0x10000d8000,0x10000dc000,0x10000e0000,0x10000e4000])
ATTEMPT_SCHEMA='m4rch.gfx-native-dispatch-contract-attempt.v1'
RETAINED_SAMPLERS=(
 {'name':'data-retained.bin','module':'root-data-sample/gpu-data-sample.ko','physical_base':0x10001d44000,'bytes':0x138000,'module_sha256':'4c3bb5783f4d8164b817ee80ccb95f0e3cc8daf74d4041a03e9b03e0a708c25d'},
 {'name':'pagetables-retained.bin','module':'sample-pagetables/gpu-data-sample.ko','physical_base':0x105fff78000,'bytes':0x40000,'module_sha256':'92b1073661a3db363fa6bd46a8aa86eabd77ab8d24535f2c417be6ef6cc2d22d'})
def require(condition,message):
 if not condition:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def validate_receipt(receipt):
 trial=receipt.get('graph_recovery_trial',{})
 require(trial.get(FAMILY_KEY)==CONTRACT and not any(k.endswith('_scope') and k!=FAMILY_KEY for k in trial),'Distinct cold-render contract differs')
 require(receipt.get('joined_owned_pages')==174 and receipt.get('graph_object_pages')==69,'Owned graph extent differs')
 require(receipt.get('graph_submit_work') is False and receipt.get('graph_release_on_shutdown') is False,'Generic startup work/release is forbidden')
 require(trial.get('cycles')==0 and trial.get('work_submitted') is False,'Old recovery/work profile differs')
 return True
def module_build_note(raw):
 require(raw[:7]==b'\x7fELF\x02\x01\x01','Expected little-endian ELF64 owner')
 h=struct.unpack_from('<HHIQQQIHHHHHH',raw,16);require(h[0]==1 and h[1]==183,'Expected AArch64 module')
 entries=[struct.unpack_from('<IIQQQQIIQQ',raw,h[5]+i*h[10]) for i in range(h[11])]
 st=entries[h[12]];names=raw[st[4]:st[4]+st[5]]
 matches=[raw[x[4]:x[4]+x[5]] for x in entries if names[x[0]:].split(b'\0',1)[0]==b'.note.gnu.build-id']
 require(len(matches)==1 and len(matches[0])==36,'Exact GNU owner note missing');return matches[0]
def associate_logs(before,after):
 if after.startswith(before):return dict(qualified=True,method='strict-prefix',before_discarded_bytes=0,exact_overlap_bytes=len(before.encode()),delta_bytes=len(after[len(before):].encode()),delta_sha256=sha(after[len(before):].encode())),after[len(before):]
 first=after.splitlines(keepends=True)[0] if after else '';offset=0;matches=[]
 for line in before.splitlines(keepends=True):
  if first and line==first and after.startswith(before[offset:]):matches.append(offset)
  offset+=len(line)
 require(len(matches)==1,'No uniquely exact line-boundary saved-log suffix overlap; raw buffers remain diagnostic')
 at=matches[0];overlap=len(before)-at;delta=after[overlap:]
 return dict(qualified=True,method='unique-exact-suffix',before_discarded_bytes=len(before[:at].encode()),exact_overlap_bytes=len(before[at:].encode()),delta_bytes=len(delta.encode()),delta_sha256=sha(delta.encode())),delta
def log_delta(before,after):return associate_logs(before,after)[1]
def rows(delta,prefix):
 result=[]
 for line in delta.splitlines():
  marker='m4rch '+prefix+': '
  if marker not in line:continue
  payload=line.split(marker,1)[1];record={}
  require(len(line.encode())+1<=511,'Truncated/unbounded structured row')
  for token in payload.split():
   require('=' in token,'Malformed structured token');key,value=token.split('=',1)
   require(key not in record,'Duplicate structured field')
   try:record[key]=int(value,16 if value.lower().startswith(('0x','-0x')) else 10)
   except ValueError:record[key]=value
  result.append(record)
 return result
def validate_recipe_backing(source,recipe_path):
 recipe_path=Path(recipe_path)
 require(sha(recipe_path.read_bytes())=='2f66948af31aa7803f6298a97d8eba4412590b9e72e6876a64c3383886731ee8','Selected native dispatch recipe changed')
 receipt=json.loads(recipe_path.read_text());recipe=receipt['recipe']
 old=Path(recipe['source_candidate'],'backing.bin').read_bytes();new=Path(source,'backing.bin').read_bytes()
 require(len(old)==len(new)==56*0x4000 and sha(old)==recipe['source_backing_sha256'],'Native dispatch backing extent/source differs')
 changed=[dict(offset=hex(i),before=x,after=y) for i,(x,y) in enumerate(zip(old,new)) if x!=y]
 require(changed==recipe['changed_bytes'] and recipe['changed_byte_count']==4,'Native dispatch recipe is not exactly the four selected bytes')
 require(sha(Path(source,'graph-before.bin').read_bytes())==sha(Path(recipe['source_candidate'],'graph-before.bin').read_bytes()),'Native dispatch graph fixture changed')
 return recipe
def validate_candidate(candidate):
 candidate=Path(candidate);receipt=json.loads((candidate/'asc-root-envelope/build-receipt.json').read_text());validate_receipt(receipt)
 for name,h in receipt['artifact_sha256'].items():
  path=(candidate/name).resolve();require(path.is_relative_to(candidate.resolve()) and sha(path.read_bytes())==h,'Artifact differs: '+name)
 for name,h in receipt['graph_source_sha256'].items():require('/' not in name and sha((candidate/'asc-graph-init'/name).read_bytes())==h,'Owner source differs: '+name)
 require(sha((candidate/'asc-graph-init/graph-before.bin').read_bytes())==receipt['graph_fixture_sha256'],'Graph fixture differs')
 require(sha((candidate/'asc-graph-init/graph-receipt.json').read_bytes())==receipt['graph_receipt_sha256'],'Graph metadata differs')
 prep=json.loads((candidate/'cold-render-preparation.json').read_text())
 require(prep.get('schema')=='m4rch.gfx-native-dispatch-contract-preparation.v1' and prep.get('candidate_receipt_sha256')==sha((candidate/'asc-root-envelope/build-receipt.json').read_bytes()),'Cold preparation differs')
 require(prep.get('owner_sha256')==sha((candidate/'asc-graph-init/asc-graph-init.ko').read_bytes()),'Owner preparation differs')
 require(prep.get('fixed_retained_RAM_samplers')==list(RETAINED_SAMPLERS) and prep.get('backing_changed_byte_count')==4,'Retained RAM/native config preparation differs')
 for pin in prep['inputs']:require(sha(Path(pin['path']).read_bytes())==pin['sha256'],'Prepared input differs: '+pin['path'])
 for pin in prep['analysis_input_pins']:require(sha((candidate/pin['relative']).read_bytes())==pin['sha256'],'Analysis input differs')
 return receipt
