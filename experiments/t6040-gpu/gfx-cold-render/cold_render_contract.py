"""Distinct cold application/control/draw contract, with no recovery count gate."""
import hashlib,json,re,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent),str(HERE.parent/'gfx-native-ap-repeat-cycle')]
from gfx_native_ap_repeat_cycle_contract import REFUSED_BOOTS,qualify_adt,qualify_linux_dt
FAMILY_KEY='gfx_cold_render_scope'
CONTRACT={'version':13,'compile_macro':'GFX_COLD_RENDER_TRIAL','automatic_cold_pipeline':True,
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
ATTEMPT_SCHEMA='m4rch.gfx-cold-render-attempt.v1'
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
def log_delta(before,after):
 require(after.startswith(before),'Dmesg rotated or prior prefix changed; no cumulative-log fallback')
 return after[len(before):]
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
def validate_candidate(candidate):
 candidate=Path(candidate);receipt=json.loads((candidate/'asc-root-envelope/build-receipt.json').read_text());validate_receipt(receipt)
 for name,h in receipt['artifact_sha256'].items():
  path=(candidate/name).resolve();require(path.is_relative_to(candidate.resolve()) and sha(path.read_bytes())==h,'Artifact differs: '+name)
 for name,h in receipt['graph_source_sha256'].items():require('/' not in name and sha((candidate/'asc-graph-init'/name).read_bytes())==h,'Owner source differs: '+name)
 require(sha((candidate/'asc-graph-init/graph-before.bin').read_bytes())==receipt['graph_fixture_sha256'],'Graph fixture differs')
 require(sha((candidate/'asc-graph-init/graph-receipt.json').read_bytes())==receipt['graph_receipt_sha256'],'Graph metadata differs')
 prep=json.loads((candidate/'cold-render-preparation.json').read_text())
 require(prep.get('schema')=='m4rch.gfx-cold-render-preparation.v1' and prep.get('candidate_receipt_sha256')==sha((candidate/'asc-root-envelope/build-receipt.json').read_bytes()),'Cold preparation differs')
 require(prep.get('owner_sha256')==sha((candidate/'asc-graph-init/asc-graph-init.ko').read_bytes()),'Owner preparation differs')
 for pin in prep['inputs']:require(sha(Path(pin['path']).read_bytes())==pin['sha256'],'Prepared input differs: '+pin['path'])
 for pin in prep['analysis_input_pins']:require(sha((candidate/pin['relative']).read_bytes())==pin['sha256'],'Analysis input differs')
 return receipt
