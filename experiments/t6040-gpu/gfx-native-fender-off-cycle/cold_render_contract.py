"""Distinct cold application/control/draw contract, with no recovery count gate."""
import hashlib,json,re,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent),str(HERE.parent/'gfx-native-ap-repeat-cycle')]
from gfx_native_ap_repeat_cycle_contract import REFUSED_BOOTS,qualify_adt as qualify_base_adt,qualify_linux_dt
REFUSED_BOOTS=(*REFUSED_BOOTS,'1241f6b5-f2c5-4678-9078-dce0ed367d60','eff8eafa-d845-429e-b98c-9a5f053bcc46','d83451f8-42c7-4466-9983-f1b3fbea5963','5e129c21-c840-4540-b4f7-3a3b3ef2cf56','e7288eeb-bc71-46e3-a0c5-831b77bebb1d','2529a76a-a0ac-4de7-95f8-71b42181042b','f4a7b737-ed3d-4851-8fcd-cac56eb233d7')
FAMILY_KEY='gfx_native_fender_off_cycle_scope'
CONTRACT={'version':20,'compile_macro':'GFX_NATIVE_FENDER_OFF_CYCLE_TRIAL','automatic_cold_pipeline':True,
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
 'commands':['sample','gfx-snapshot','postdraw-native-cycle <capture_token>']}
CONTRACT.update(maximum_scheduler_request_writes=0,scheduler_ack_writes=0,native_reason_mutex_owned=False,native_reason_lifecycle_reproduced=False,maximum_trace_restore_writes=0,trace_mask_after_control=3,trace_mask_before_draw=3,trace_mask_retained_after_draw=3,native_config_getter_changed_bytes=4,no_extra_notification_for_trace=True,hardware_completion_device_vas=[0x10000d8000,0x10000dc000,0x10000e0000,0x10000e4000])
ATTEMPT_SCHEMA='m4rch.gfx-native-fender-off-cycle-attempt.v1'
RETAINED_SAMPLERS=(
 {'name':'data-retained.bin','module':'root-data-sample/gpu-data-sample.ko','physical_base':0x10001d44000,'bytes':0x138000,'module_sha256':'4c3bb5783f4d8164b817ee80ccb95f0e3cc8daf74d4041a03e9b03e0a708c25d'},
 {'name':'pagetables-retained.bin','module':'sample-pagetables/gpu-data-sample.ko','physical_base':0x105fff78000,'bytes':0x40000,'module_sha256':'92b1073661a3db363fa6bd46a8aa86eabd77ab8d24535f2c417be6ef6cc2d22d'})
def qualify_adt(tree):
 qualify_base_adt(tree)
 for node,name,digest in [
  ('/device-tree/arm-io/gfx-asc','reg','514e389c0c3ec047f962e839ba8af790b9ab56b905bb935425cc7aa3ecee57aa'),
  ('/device-tree/arm-io/gfx-asc','compatible','75c5bc1f4741c46209358afd33ee187d65ecc22c714189a8c4ac6778075e19f9'),
  ('/device-tree/arm-io/sgx','reg','c3fc8b848aec1e796ac7b92bed5986b726104b2f1e678940c83d28bc0f8506aa'),
  ('/device-tree/arm-io/sgx','compatible','c98e482b1162d48b0f94f6ab0b83d9f3086b5872c9843f5cca9e24d5048dd68e'),
  ('/device-tree/arm-io','ranges','c0a9d10a4a0f5adfd736b3c9286607903f4e06a0af8256c5d673405f0ecae005')]:
  raw=tree.get(node,{}).get(name)
  require(raw is not None and sha(raw)==digest,'New NMI/Gravity ADT mapping differs: '+node+'/'+name)
 props=tree['/device-tree/arm-io/gfx-asc']
 require(all(name not in props for name in ('nmi-ext-irq','ext-irq-reg-index','idle-ctrl-check','cpu-ctrl-filtered')),'Selected native FIQ/idle properties differ')

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
   try:record[key]=value if key=='capture_token' else int(value,16 if value.lower().startswith(('0x','-0x')) else 10)
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
 require(prep.get('schema')=='m4rch.gfx-native-fender-off-cycle-preparation.v1' and prep.get('candidate_receipt_sha256')==sha((candidate/'asc-root-envelope/build-receipt.json').read_bytes()),'Cold preparation differs')
 require(prep.get('owner_sha256')==sha((candidate/'asc-graph-init/asc-graph-init.ko').read_bytes()),'Owner preparation differs')
 require(prep.get('fixed_retained_RAM_samplers')==list(RETAINED_SAMPLERS) and prep.get('backing_changed_byte_count')==4,'Retained RAM/native config preparation differs')
 for pin in prep['inputs']:require(sha(Path(pin['path']).read_bytes())==pin['sha256'],'Prepared input differs: '+pin['path'])
 for pin in prep['analysis_input_pins']:require(sha((candidate/pin['relative']).read_bytes())==pin['sha256'],'Analysis input differs')
 return receipt

CONTRACT.update(maximum_postdraw_native_cycles=1,automatic_postcapture_native_cycle=True,postdraw_capture_required=True,capture_token_algorithm='sha256-exact-pre-cycle-attempt',trace3_through_control=True,postdraw_native202=True,postdraw_management_rejoin_only=True,postdraw_application_replay=False,postdraw_work_replay=False,postdraw_backing_release=False)

CONTRACT.update(native_NMI_on_clean_202_ACK_timeout=True,maximum_native_NMI_requests=1,native_NMI_packet=0x00f0000000000000,native_NMI_FIQ_writes=[[0x1004,0x10],[0x1014,1]],ASC_reserved_bytes=0x2000,strict_idle_required_after_NMI=True,NMI_is_not_ACK=True)

CONTRACT.update(Gravity_preASC_prefix=True,Gravity_preASC_offsets=[0x1000104,0x1000108,0xd06030],Gravity_preASC_requested_policy=["preserve-set-bit0","preserve-set-bit0","literal-six"],maximum_Gravity_preASC_calls=1,Gravity_preASC_after_coordinate_ON_before_first_START=True,normal_T6040_boot_qualified=False)

CONTRACT.update(Gravity_preASC_resources=[[0x289000000,0x4000],[0x288d04000,0x4000]])

CONTRACT.update(maximum_native_Fender_enable_calls=1,native_Fender_enable_offset=0xd06030,native_Fender_enable_policy="fresh-preserve-clear-six",native_Fender_enable_after_control_before_draw=True,native_Fender_enable_transfer_hypothesis=True,native_addKicks_reproduced=False,direct_SGX_kick_writes=0,native_Fender_teardown_clear=False)

CONTRACT.update(native_runtime_active_after_Fender=True,native_runtime_active_read_only=True,native_runtime_active_policy='target-f-known-actual-auto',native_runtime_actual_states=[0,4,15],native_runtime_target=15,native_runtime_AUTO_required_for_gated_states=True,native_runtime_blocked_mask=0x80001c00,native_runtime_pre_Fender_strict_FF=True,native_runtime_dynamic_cold_guard=True,native_runtime_dynamic_postdraw_ON_phases=['admission-before','before-off'],strict_physical_OFF_unchanged=True,strict_management_rejoin_ON_unchanged=True)

CONTRACT.update(maximum_native_Fender_disable_calls=1,native_Fender_disable_before_OFF=True,native_Fender_disable_offset=0xd06030,native_Fender_disable_policy='fresh-preserve-set-bit2',native_Fender_disable_after_CPU_stop_and_coordinate_alias_before_OFF_seal=True,native_Fender_disable_transfer_hypothesis=True,native_Fender_disable_MMIO_writes=1,native_Fender_disable_PM_writes=0,native_Fender_disable_dynamic_fresh_snapshot_phase='fender-off-before')
