#!/usr/bin/env python3
"""Analyze only a bound cold draw's new log delta and full retained captures."""
import argparse,json,runpy,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from cold_render_contract import ATTEMPT_SCHEMA,CONTRACT,require,sha,rows,log_delta,associate_logs,validate_candidate
from readback import check_full,png
def exact(record,expected,label):
 require(all(record.get(k)==v for k,v in expected.items()),label+' fields differ')
def qualify_runtime_active_row(record,phase,fender_complete):
 exact(record,dict(phase=phase,fender_complete=int(fender_complete),policy_known=1,policy='dynamic-auto' if fender_complete else 'strict-ff',accepted=1,operand_samples_atomic=0),'Runtime active predicate')
 word=record.get('word');require(isinstance(word,int) and 0<=word<2**32-1,'Runtime physical word invalid')
 require(isinstance(record.get('valid'),int) and record['valid']&1 and record.get('domain_on')==1,'Runtime fresh ON validity differs')
 actual=(word>>4)&15;target=word&15;auto=(word>>28)&1;blocked=word&0x80001c00
 exact(record,dict(actual=actual,target=target,auto=auto,auto_state=(word>>24)&15,min_state=(word>>16)&15,blocked=blocked),'Runtime physical decode')
 if fender_complete:require(target==15 and not blocked and actual in (0,4,15) and (actual==15 or auto==1),'Runtime dynamic state outside native auto policy')
 else:require(word&0x80001cff==0xff,'Runtime pre-Fender strict active state differs')
 return record

def qualify_runtime_active(delta,cycle=False):
 values=rows(delta,'gfx-runtime-active')
 require(not rows(delta,'gfx-runtime-guard-refused'),'Runtime guard refusal in qualified operation')
 lines=delta.splitlines()
 locations=[i for i,line in enumerate(lines) if 'm4rch gfx-runtime-active: ' in line]
 prefix='gfx-postdraw-native-cycle-physical' if cycle else 'gfx-cold-render-physical'
 for position,record in zip(locations,values):
  previous=[r for line in lines[:position] for r in rows(line,prefix)]
  require(previous,'Runtime predicate lacks fresh caller snapshot')
  snapshot=previous[-1];exact(snapshot,dict(phase=record.get('phase'),result=0,valid=record.get('valid'),domain_on=record.get('domain_on'),word=record.get('word'),operand_samples_atomic=0),'Runtime fresh caller snapshot')
 def only(marker):
  found=[i for i,line in enumerate(lines) if marker in line];require(len(found)==1,'Runtime ordering boundary missing/duplicate '+marker);return found[0]
 if cycle:
  require(len(values)==2 and [r.get('phase') for r in values]==['admission-before','before-off'],'Runtime cycle admission stages differ')
  for record in values:qualify_runtime_active_row(record,record['phase'],True)
  require(only('m4rch gfx-postdraw-native-cycle: phase=intent ')<locations[0]<only('m4rch gfx-postdraw-native-cycle: phase=admission-ready ') and only('m4rch gfx-postdraw-native-cycle: phase=cpu-stop-return ')<locations[1]<only('m4rch gfx-postdraw-native-cycle: phase=off-intent '),'Runtime cycle predicate chronology differs')
 else:
  require(len(values)==6 and all(r.get('phase')=='cold-guard' for r in values),'Runtime cold guard count differs')
  for i,record in enumerate(values):qualify_runtime_active_row(record,'cold-guard',i>=4)
  control_intent=only('m4rch gfx-cold-render: phase=control-intent ');control_ready=only('m4rch gfx-cold-render: phase=control-ready ')
  fender_intent=only('m4rch gfx-native-fender-enable: phase=intent ');fender_op=only('m4rch gfx-native-fender-enable-op: ');fender_done=only('m4rch gfx-native-fender-enable: phase=complete ')
  draw_intent=only('m4rch gfx-cold-render: phase=draw-intent ');draw_publish=only('m4rch gfx-cold-render: phase=draw-published ')
  require(locations[0]<control_intent<locations[1]<locations[2]<control_ready<fender_intent<locations[3]<fender_op<fender_done<locations[4]<draw_intent<locations[5]<draw_publish,'Runtime physical stages differ from selected caller order')
 return dict(qualified=True,rows=values,read_only=True,firmware_dynamic_auto_hypothesis=True,strict_OFF_unchanged=True,physical_OFF_verified=False,dma_retirement_verified=False,gpu_execution_verified=False)

def qualify_fender_enable(delta):
 primary=rows(delta,'gfx-native-fender-enable');ops=rows(delta,'gfx-native-fender-enable-op')
 require([r.get('phase') for r in primary]==['intent','complete'] and len(ops)==1,'Fender enable missing/duplicate/failed stages')
 for r in primary:
  exact(r,dict(result=0,refused_condition='none',intent=1,unknown=0,held=1,retained=1,transfer_hypothesis=1,native_addkicks=0,teardown_clear=0),'Fender enable ownership')
 exact(primary[0],dict(attempted=0,complete=0),'Fender enable intent')
 exact(primary[1],dict(attempted=1,complete=1),'Fender enable complete')
 op=ops[0]
 exact(op,dict(offset=0xd06030,write_attempted=1,verified=1,policy='preserve-clear-six',operand_samples_atomic=0),'Fender enable operation')
 require(isinstance(op.get('gpu_id'),int) and 0<op['gpu_id']<2**32-1,'Fender GPU identity invalid')
 require(isinstance(op.get('before'),int) and 0<=op['before']<2**32-1,'Fender baseline invalid')
 exact(op,dict(requested=op['before']&~6,after=op['before']&~6),'Fender enable preserves other bits')
 lines=delta.splitlines()
 def only(marker):
  found=[i for i,line in enumerate(lines) if marker in line]
  require(len(found)==1,'Fender ordering boundary missing/duplicate: '+marker)
  return found[0]
 order=[only('m4rch gfx-cold-render: phase=control-ready '),only('m4rch gfx-native-fender-enable: phase=intent '),only('m4rch gfx-native-fender-enable-op: '),only('m4rch gfx-native-fender-enable: phase=complete '),only('m4rch gfx-cold-render: phase=draw-intent ')]
 require(order==sorted(order),'Fender enable must follow control-ready and precede draw-intent')
 preasc=[r for r in rows(delta,'gfx-gravity-preasc') if r.get('phase')=='complete']
 require(len(preasc)==1 and preasc[0].get('gpu_id')==op['gpu_id'],'Fender GPU identity differs from preASC owner')
 return dict(qualified=True,operation=op,maximum_writes=1,native_enable_transfer_hypothesis=True,native_addkicks_reproduced=False,rendering_verified=False)
def qualify_trace_preserved(delta,terminal=True):
 require(not rows(delta,'gfx-native-dispatch-trace') and not rows(delta,'gfx-cold-pause-release'),'A trace restore/scheduler write is outside v19')
 controls=rows(delta,'gfx-cold-render-control')
 phases=('control-ready','draw-intent','draw-published')+(('retained-final',) if terminal else ())
 selected=[]
 for phase in phases:
  found=[r for r in controls if r.get('phase')==phase];require(len(found)==1,'Trace-preserved control missing/duplicate: '+phase)
  exact(found[0],dict(trace_attempted=0,trace_before=3,trace_after=3,cached=1,operand_samples_atomic=0),'Trace-preserved '+phase);selected.append(found[0])
 return dict(qualified=True,trace_mask_retained=3,trace_restore_writes=0,extra_notification=False,scheduler_request_intervention=False,control_rows=selected,cached_non_atomic=True,gpu_execution_verified=False,rendering_verified=False)

def qualify_gravity_preasc(delta):
 primary=rows(delta,'gfx-gravity-preasc')
 require([r.get('phase') for r in primary]==['intent','complete'],'Gravity preASC missing/duplicate/failed stages')
 final=primary[-1]
 exact(final,dict(result=0,complete=1,attempted=1,held=1,usage=1,active=1,start_clear=1,status=0x6a,rx_empty=1,resources_owned=1,unknown=0),'Gravity preASC terminal')
 require(isinstance(final.get('gpu_id'),int) and 0<final['gpu_id']<2**32-1,'Gravity GPU identity invalid')
 baselines=rows(delta,'gfx-gravity-preasc-baseline')
 require(len(baselines)==3 and [r.get('index') for r in baselines]==[0,1,2],'Gravity preASC baseline sequence differs')
 for r,offset in zip(baselines,[0x1000104,0x1000108,0xd06030]):
  exact(r,dict(offset=offset,valid=1),'Gravity preASC baseline')
  require(isinstance(r.get('value'),int) and 0<=r['value']<2**32-1,'Gravity preASC baseline invalid')
 ops=rows(delta,'gfx-gravity-preasc-op')
 require(len(ops)==3 and [r.get('index') for r in ops]==[0,1,2],'Gravity preASC operation sequence differs')
 for r,offset,policy in zip(ops,[0x1000104,0x1000108,0xd06030],['preserve-set-bit0','preserve-set-bit0','literal-six']):
  exact(r,dict(offset=offset,baseline=baselines[r['index']]['value'],policy=policy,write_attempted=1,verified=1),'Gravity preASC operation')
  require(isinstance(r.get('before'),int) and 0<=r['before']<2**32-1,'Gravity preASC before invalid')
  expected=(r['before']|1) if policy=='preserve-set-bit0' else 6
  exact(r,dict(requested=expected,after=expected),'Gravity preASC readback')
 lines=delta.splitlines()
 baseline_lines=[i for i,line in enumerate(lines) if 'm4rch gfx-gravity-preasc-baseline: ' in line]
 op_lines=[i for i,line in enumerate(lines) if 'm4rch gfx-gravity-preasc-op: ' in line]
 require(max(baseline_lines)<min(op_lines),'Gravity baseline was not saved before first write')
 complete_i=next(i for i,line in enumerate(lines) if 'm4rch gfx-gravity-preasc: phase=complete ' in line)
 starts=[i for i,line in enumerate(lines) if 'm4rch gfx-cold-render: phase=pipeline-intent ' in line]
 if starts:require(len(starts)==1 and complete_i<starts[0],'Gravity preASC after draw pipeline')
 return dict(qualified=True,operations=ops,terminal=final,source_derived_prefix=True,normal_T6040_boot_verified=False,rendering_verified=False)

def qualify_postdraw_cycle(delta,token):
 require(len(token)==64 and all(c in '0123456789abcdef' for c in token),'Capture token syntax differs')
 all_primary=rows(delta,'gfx-postdraw-native-cycle');primary=[r for r in all_primary if r.get('phase')!='diagnostic-cached'];require(primary,'No source postdraw cycle rows')
 runtime_active=qualify_runtime_active(delta,cycle=True)
 nmi_rows=rows(delta,'gfx-postdraw-native-nmi')
 nmi_branch=bool(nmi_rows)
 phases=('intent','admission-ready','request-published','handshake-return')+(('nmi-return',) if nmi_branch else ())+('cpu-stop-return','off-intent','off-put-intent','off-put-return','off-qualified','on-get-intent','on-get-return','on-coordinate-return','start-intent','start-return','autonomous-map-retained','boot-running-observed','retained-final')
 order=[]
 for phase in phases:
  found=[(i,r) for i,r in enumerate(primary) if r.get('phase')==phase];require(len(found)==1,'Cycle phase missing/duplicate: '+phase)
  i,r=found[0];order.append(i)
  require(r.get('result')==0 or nmi_branch and phase=='handshake-return' and r.get('result')==-110 or phase=='off-put-return' and isinstance(r.get('result'),int) and r['result']>=0,'Cycle stage result differs')
  exact(r,dict(refused_condition='none',intent=1,unknown=0,capture_token=token,token_host_verified=0,allocations_retained=174,retirement_verified=0),'Cycle '+phase)
  exact(r,dict(complete=int(phase=='retained-final'),management_rejoin_verified=int(phase=='retained-final')),'Cycle completion chronology')
 require(order==sorted(order) and len(primary)==len(phases),'Unexpected/reordered postdraw phases')
 final=primary[order[-1]];exact(final,dict(complete=1,management_rejoin_verified=1),'Cycle terminal')
 terminal_index=all_primary.index(final)
 for i,r in enumerate(all_primary):
  if r.get('phase')=='diagnostic-cached':require(i>terminal_index and r==dict(final,phase='diagnostic-cached'),'Cached cycle diagnostics differ from terminal')
 def at(prefix,phase):
  selected=[r for r in rows(delta,prefix) if r.get('phase')==phase];require(len(selected)==1,'Cycle group missing/duplicate '+prefix+'/'+phase);return selected[0]
 off=at('gfx-postdraw-native-cycle-off','off-qualified')
 exact(off,dict(request_attempted=1,ack_observed=int(not nmi_branch),idle_observed=1,clear10_attempted=1,clear20_attempted=1,cpu_stopped=1,off_attempted=1,coordinate_off_complete=1,pm_put_attempted=1,provider_off_observed=1,accounting_ok=1),'Own native OFF')
 require(isinstance(off['pm_put_result'],int) and off['pm_put_result']>=0,'OwnOFF PMput failed')
 if nmi_branch:
  exact(off,dict(ack_message=0,ack_metadata=0),'NMI is not management ACK')
  expected_nmi_phases=['eligible','request-published','fiq-published','drain-ready','return']
  require([r.get('phase') for r in nmi_rows]==expected_nmi_phases,'Native NMI chronology differs')
  for r in nmi_rows:
   exact(r,dict(result=0,eligible=1,asc_extent=0x2000,ack_observed=0),'Native NMI branch')
  nmi_final=nmi_rows[-1]
  exact(nmi_final,dict(attempted=1,ep0_published=1,fiq1004_attempted=1,fiq1014_attempted=1,drain_complete=1,idle_observed=1),'Native NMI completion')
  require(isinstance(nmi_final.get('status48'),int) and 0<=nmi_final['status48']<2**32-1 and nmi_final['status48']&3,'Native NMI fresh idle differs')
  require(isinstance(nmi_final.get('rx_status'),int) and 0<=nmi_final['rx_status']<2**32-1 and nmi_final['rx_status']&(1<<17),'Native NMI empty RX differs')
  require(0<=nmi_final.get('messages',257)<=256 and 1<=nmi_final.get('polls',252)<=251,'Native NMI drain budget differs')
  nmi_rx=rows(delta,'gfx-postdraw-native-nmi-rx')
  require(len(nmi_rx)==nmi_final['messages'] and [r.get('index') for r in nmi_rx]==list(range(1,len(nmi_rx)+1)),'Native NMI RX custody differs')
  for r in nmi_rx:
   exact(r,dict(direction='rx',raw_only=1),'Native NMI RX direction')
   require(isinstance(r.get('message'),int) and 0<=r['message']<2**64-1 and isinstance(r.get('metadata'),int) and 0<=r['metadata']<2**64-1,'Native NMI RX operands invalid')
   ep=r['metadata']&255
   require(ep==1 or ep==32 and r['message']==0x0042000000000000,'Native NMI RX type differs')
  require(sum((r['metadata']&255)==1 for r in nmi_rx)==nmi_final['crash_frames'],'Native NMI crash count differs')
 else:
  require(not rows(delta,'gfx-postdraw-native-nmi-rx'),'Unexpected NMI receive without branch')
  require((off['ack_message']>>52)&15==7 and off['ack_message']&255 in (1,2) and off['ack_metadata']&255==0,'OwnOFF ACK operands differ')
 offstate=at('gfx-postdraw-native-cycle-state','off-qualified')
 exact(offstate,dict(held=0,usage=0,runtime_error=0,active=0,suspended=1,identities_preserved=1),'OFF PM accounting')
 physical=rows(delta,'gfx-postdraw-native-cycle-physical')
 afteroff=[r for r in physical if r.get('phase')=='after-off'];require(1<=len(afteroff)<=101 and [r.get('index') for r in afteroff]==list(range(len(afteroff))),'Strict physicalOFF samples differ')
 phys=afteroff[-1]
 for r in (phys,at('gfx-postdraw-native-cycle-physical','before-get')):
  exact(r,dict(result=0,valid=1,domain_on=0,state_mask=0x90001cff,expected_on=0,operand_samples_atomic=0),'Strict physical OFF')
  require(r['word']&r['state_mask']==0,'Strict physical OFF state bits differ')
 for phase in ('after-get','rejoin-final'):
  r=at('gfx-postdraw-native-cycle-physical',phase);exact(r,dict(result=0,valid=1,domain_on=1,expected_on=1,operand_samples_atomic=0),'Strict physical ON')
  require(r['word']&0x80001cff==0xff,'Strict physical ON state bits differ')
 on=at('gfx-postdraw-native-cycle-on','retained-final')
 exact(on,dict(get_attempted=1,coordinate_on_complete=1,start_attempted=1,hello_replied=1,map_seen=3,endpoint_map=1,boot_running_observed=1,host_on_requests=0,root_publications=0,application_starts=0),'Own native management ON')
 require(isinstance(on['get_result'],int) and on['get_result']>=0,'OwnON PMget failed')
 onstate=at('gfx-postdraw-native-cycle-state','retained-final')
 exact(onstate,dict(held=1,usage=1,runtime_error=0,active=1,suspended=0,identities_preserved=1),'ON PM accounting')
 management=at('gfx-postdraw-native-cycle-management','retained-final')
 exact(management,dict(hello_replies=1,map_replies=2,advertised_appmap=3,application_bitmap_selected=0,AP_carried_known=1,AP_carried_state=0x20,application_starts=0,root_publications=0,work_replays=0),'Management rejoin')
 require(management['boot_message']==0x0070000000000020 and management['boot_metadata']&255==0,'Management Running acknowledgement differs')
 rx=rows(delta,'gfx-postdraw-native-cycle-rx')
 require(len(rx)==4 and [r.get('index') for r in rx]==[1,2,3,4] and all(r.get('epoch')==2 for r in rx),'Own management RX sequence differs')
 require([r.get('message') for r in rx]==[0x00100000000c000c,0x0080000000000003,0x0088000100000003,0x0070000000000020] and all(isinstance(r.get('metadata'),int) and 0<=r['metadata']<2**64-1 and r['metadata']&255==0 for r in rx),'Own management RX operands differ')
 tx=rows(delta,'gfx-postdraw-native-cycle-tx')
 require(len(tx)==3 and [r.get('packet') for r in tx]==[0x00200000000c000c,0x0080000000000001,0x0088000100000000],'Management-only TX selection differs')
 for r in tx:exact(r,dict(epoch=2,endpoint=0,root_publications=0,application_starts=0,host_on_requests=0,work_replays=0),'Management-only TX')
 return dict(qualified=True,native_runtime_active=runtime_active,native_NMI_fallback_used=nmi_branch,management_ACK_observed=not nmi_branch,native_NMI_rows=nmi_rows,strict_physical_OFF=True,paired_PM_accounting=True,management_rejoin_verified=True,application_rejoined=False,work_replayed=False,resources_retained=174,retirement_verified=False,rebootless_render_restart_verified=False,capture_token=token,token_host_verified_by_C=False,primary_rows=primary,off_row=off,off_state=offstate,physical_OFF_row=phys,on_row=on,on_state=onstate,management_row=management)

def qualify_pipeline(delta):
 runtime_active=qualify_runtime_active(delta)
 preasc=qualify_gravity_preasc(delta)
 fender=qualify_fender_enable(delta)
 primary=rows(delta,'gfx-cold-render')
 require(primary,'No source cold pipeline rows')
 required=['pipeline-intent','control-intent','control-ready','draw-intent','draw-published','retained-final']
 selected={}
 for phase in required:
  found=[(i,r) for i,r in enumerate(primary) if r.get('phase')==phase]
  require(len(found)==1,'Missing or duplicate pipeline phase: '+phase);selected[phase]=found[0]
 require([selected[p][0] for p in required]==sorted(selected[p][0] for p in required),'Pipeline stage order differs')
 for phase,(_,record) in selected.items():
  exact(record,dict(result=0,refused_condition='none',pipeline_intent=1,allocations_retained=174,pm_put_attempted=0,off_attempted=0,gpu_execution_verified=0,rendering_verified=0),phase)
 exact(selected['retained-final'][1],dict(sealed=1,complete=1,software_stopped=1),'Final cold pipeline')
 controls=rows(delta,'gfx-cold-render-control');draws=rows(delta,'gfx-cold-render-draw');states=rows(delta,'gfx-cold-render-state')
 def stage(values,phase):
  selected=[r for r in values if r.get('phase')==phase];require(len(selected)==1,'Structured group missing/duplicate: '+phase);return selected[0]
 control=stage(controls,'control-ready');draw=stage(draws,'draw-published');state=stage(states,'retained-final')
 # These names are joined to the actual emitted C log fixture before selection.
 exact(control,dict(control_intent=1,trace_attempted=0,producer_attempted=1,notify_attempted=1,notify_sent=1,ready=1,record_verified=1,baseline='32/32/32',current='33/33/33',ready_cursors='33/33/33',trace_before=3,trace_after=3,cached=1,operand_samples_atomic=0),'Fresh control')
 require(0<control['polls']<=5001,'Control poll bound differs')
 exact(draw,dict(draw_intent=1,notify_attempted=1,notify_sent=1,work_submitted=1,record0_attempted=1,record1_attempted=1,record0_cleaned=1,record1_cleaned=1,producer0_attempted=1,producer1_attempted=1,producer0_verified=1,producer1_verified=1),'Draw publication')
 exact(state,dict(identities_captured=1,identities_preserved=1,held=1,usage=1,runtime_error=0,active=1,suspended=0,apps_started=3,ap_known=1,journal_status=0,receive_crashed=0,running=0),'Retained PM/identity')
 application=rows(delta,'gfx-cold-render-application')
 for phase in ('control-ready','draw-intent'):
  exact(stage(application,phase),dict(counter=0,recovery_phase=0,host_stop=0,request_state=0,request_flag=0),'Original clean cold application')
 tx=rows(delta,'gfx-cold-render-tx')
 require(len(tx)==4,'Repeated or missing packet writes')
 for row,packet,sent in zip(tx,[CONTRACT['control_packet']]*2+[CONTRACT['draw_packet']]*2,[0,1,0,1]):
  exact(row,dict(endpoint=33,packet=packet,attempted=1,sent=sent),'Sole packet transaction')
 records=rows(delta,'gfx-cold-render-record')
 require(len(records)==4,'Repeated/missing draw record writes')
 for row,index,phase in zip(records,[0,0,1,1],['record-cleaned','producer-published']*2):
  exact(row,dict(index=index,phase=phase,bytes=24,copy_attempted=1,cleaned=1,producer_attempted=int(phase=='producer-published'),producer_verified=int(phase=='producer-published')),'Record/producer publication')
 samples=rows(delta,'gfx-cold-render-sample')
 completed=[r for r in samples if r.get('begin')==0 and r.get('complete')==1]
 begun=[r for r in samples if r.get('begin')==1 and r.get('complete')==0]
 require(len(completed)==6 and len(begun)==6 and len(samples)==12,'Missing/duplicate sample boundaries')
 require([r['sample_index'] for r in completed]==list(range(6)),'Completed sample sequence differs')
 for a,b in zip(begun,completed):
  require(all(a[k]==b[k] for k in ('phase','sample_index','elapsed_ms','sample_jiffies')),'Sample begin/end provenance differs')
  exact(b,dict(fault_valid=1,fault_info=0,fault_addr=0,journal_status=0),'Healthy complete sample')
 exact(completed[0],dict(phase='before-submit',sample_index=0),'Before-submit sample')
 post=completed[1:];require(all(r['phase']=='post-submit' for r in post),'Post-submit phase differs')
 elapsed=[r['elapsed_ms'] for r in post];require(elapsed==sorted(elapsed) and all(actual>=target for actual,target in zip(elapsed,[0,100,1000,5000,15000])),'Post-submit scheduled observation bounds differ')
 require(all(r.get('operand_samples_atomic')==0 for r in samples),'Snapshot atomicity differs')
 require(not replays(delta),'Recovery/restart/unbound work marker in cold operation')
 ap=rows(delta,'gfx-cold-render-ap');require(len(ap)==2,'Cold AP request/reply missing or duplicated')
 exact(ap[0],dict(phase='request',request_attempted=1,write_attempted=0,request_message=0x00b0000000000020,request_metadata=0),'Cold AP request intent')
 exact(ap[1],dict(phase='reply',request_attempted=1,write_attempted=1,request_message=0x00b0000000000020,request_metadata=0,reply_observed=1,reply_message=0x00b0000000000020,remote_known=1,remote_state=32),'Cold AP reply')
 require(isinstance(ap[1]['reply_metadata'],int) and 0<=ap[1]['reply_metadata']<2**64-1 and ap[1]['reply_metadata']&255==0,'Cold AP reply endpoint differs')
 root=rows(delta,'gfx-cold-render-root');require(len(root)==1,'Own cold root missing/duplicated')
 exact(root[0],dict(phase='root-published',message=0x00810c2000100000,endpoint=32,apps_started=3,work_submitted=0),'Own cold root')
 for endpoint in (32,33):require(delta.count(f'application endpoint {endpoint} start sent')==1,'Own application start missing/duplicated')
 positions=[delta.index('gfx-cold-render-ap: phase=request '),delta.index('gfx-cold-render-ap: phase=reply '),delta.index('application endpoint 32 start sent'),delta.index('application endpoint 33 start sent'),delta.index('gfx-cold-render-root: phase=root-published '),delta.index('gfx-cold-render: phase=pipeline-intent ')]
 require(positions==sorted(positions),'Cold AP/start/root pipeline order differs')
 trace=qualify_trace_preserved(delta)
 return dict(qualified=True,native_runtime_active=runtime_active,gravity_preASC=preasc,native_Fender_enable=fender,primary_rows=primary,control_rows=controls,draw_rows=draws,state_rows=states,samples=completed,trace_preserved=trace,fresh_application_control=True,one_draw_published=True,gpu_execution_verified=False,rendering_verified=False,nominal_post_submit_deadline_ms=15000,actual_last_sample_ms=elapsed[-1])
def replays(delta):
 return any(marker in delta for marker in ('recovery-send: endpoint=33 packet=0x86000000000000','prepared_triangle_published=1','gfx-native-ap-repeat-cycle:','gfx-native-ap-repeat-third:'))
def qualify_publication(delta):
 runtime_active=qualify_runtime_active(delta)
 fender=qualify_fender_enable(delta)
 primary=rows(delta,'gfx-cold-render');phases=['pipeline-intent','control-intent','control-ready','draw-intent','draw-published'];selected=[]
 for phase in phases:
  found=[(i,r) for i,r in enumerate(primary) if r.get('phase')==phase];require(len(found)==1,'Own publication phase missing/duplicate: '+phase);selected.append(found[0])
  exact(found[0][1],dict(result=0,refused_condition='none',pipeline_intent=1,allocations_retained=174,pm_put_attempted=0,off_attempted=0,gpu_execution_verified=0,rendering_verified=0),'Own publication')
 require([i for i,r in selected]==sorted(i for i,r in selected),'Own publication chronology differs')
 control=[r for r in rows(delta,'gfx-cold-render-control') if r.get('phase')=='control-ready'];require(len(control)==1,'Own control proof missing')
 exact(control[0],dict(baseline='32/32/32',current='33/33/33',ready_cursors='33/33/33',ready=1,record_verified=1,notify_attempted=1,notify_sent=1),'Own fresh control')
 tx=rows(delta,'gfx-cold-render-tx');require(len(tx)==4,'Extra/missing class84/class83 publication')
 for r,packet,sent in zip(tx,[CONTRACT['control_packet']]*2+[CONTRACT['draw_packet']]*2,[0,1,0,1]):exact(r,dict(endpoint=33,packet=packet,attempted=1,sent=sent),'Own transaction')
 root=rows(delta,'gfx-cold-render-root');require(len(root)==1,'Own root publication missing/duplicate');exact(root[0],dict(message=0x00810c2000100000,endpoint=32,apps_started=3,work_submitted=0),'Own root')
 require(not replays(delta),'Recovery/restart replay differs')
 qualify_trace_preserved(delta,terminal=False)
 return dict(qualified=True,native_runtime_active=runtime_active,native_Fender_enable=fender,one_control_and_draw_published=True,gpu_execution_verified=False,rendering_verified=False)
OBSERVATION_FAMILIES=('ksm-status','ksm-detail','ksm-fault','ksm-live','hw-completion-register','joined-hw-completion','joined-live-output')
def diagnostic_observations(delta):
 """Keep failed/incomplete samples; exact source tuples do not imply success."""
 lines=delta.splitlines()
 def located(name):return [(i,row) for i,line in enumerate(lines) for row in rows(line,name)]
 boundary_rows=located('gfx-cold-render-sample');primary=rows(delta,'gfx-cold-render')
 publications=[r for r in primary if r.get('phase')=='draw-published' and r.get('pipeline_intent')==1]
 publication_pos=next((i for i,line in enumerate(lines) if 'gfx-cold-render: phase=draw-published ' in line),-1)
 errors=[];groups={};keys=('phase','sample_index','elapsed_ms','sample_jiffies')
 def identity(row):
  if row.get('phase')!='post-submit' or row.get('operand_samples_atomic')!=0:return None
  if not all(isinstance(row.get(k),int) and row[k]>=0 for k in keys[1:]):return None
  if not 1<=row['sample_index']<=5:return None
  return tuple(row[k] for k in keys)
 for position,row in boundary_rows:
  if row.get('phase')!='post-submit':continue
  key=identity(row)
  if key is None:errors.append('Invalid post-submit boundary identity');continue
  groups.setdefault(key,[]).append((position,row))
 bound={};sample_reports=[]
 for key,values in groups.items():
  begun=[(i,r) for i,r in values if r.get('begin')==1 and r.get('complete')==0]
  completed=[(i,r) for i,r in values if r.get('begin')==0 and r.get('complete')==1]
  # Publication and complete health are separate. A lone begin preserves partial raw diagnostics.
  provenance=len(publications)==1 and publication_pos>=0 and len(begun)==1 and len(completed)<=1 and len(values)==len(begun)+len(completed)
  provenance=provenance and begun[0][0]>publication_pos and (not completed or completed[0][0]>begun[0][0])
  status='complete' if provenance and completed else 'incomplete' if provenance else 'unbound'
  if provenance:
   next_boundary=min([i for i,r in boundary_rows if i>begun[0][0] and r.get('begin')==1]+[len(lines)])
   bound[key]=(status,begun[0][0],completed[0][0] if completed else next_boundary)
  else:errors.append('Unbound/duplicate post-submit sample '+str(key[1]))
  sample_reports.append(dict(identity=dict(zip(keys,key)),boundary_status=status,source_rows=[r for i,r in values],health_verified=bool(status=='complete' and len(completed)==1 and completed[0][1].get('fault_valid')==1 and completed[0][1].get('fault_info')==0 and completed[0][1].get('fault_addr')==0 and completed[0][1].get('journal_status')==0)))
 associated={};unassociated={}
 for name in OBSERVATION_FAMILIES:
  associated[name]=[];unassociated[name]=[]
  for position,row in located(name):
   if row.get('phase')!='post-submit':continue
   key=identity(row)
   if key in bound and bound[key][1]<position<bound[key][2]:associated[name].append(dict(row,boundary_status=bound[key][0]))
   else:unassociated[name].append(row)
 return dict(independent_of_pipeline_success=True,draw_publication_present=len(publications)==1,samples=sample_reports,errors=errors,raw_post_submit_observations=associated,unassociated_post_submit_observations=unassociated,complete_post_submit_window=len(sample_reports)==5 and all(r['boundary_status']=='complete' for r in sample_reports))
def analyze(capture,candidate,output):
 capture=Path(capture).resolve();candidate=Path(candidate).resolve();output=Path(output).resolve()
 require(not output.exists() and output!=capture and output!=candidate,'Analysis output must be new')
 receipt=validate_candidate(candidate);attempt_bytes=(capture/'attempt.json').read_bytes();report=json.loads(attempt_bytes)
 require(report.get('schema')==ATTEMPT_SCHEMA and report.get('complete') is True and report.get('raw_capture_complete') is True and report.get('capture_errors')==[],'Raw capture is incomplete/unknown')
 require(report.get('session')==str(capture) and report.get('candidate')==str(candidate) and report.get('validated_build_receipt')==receipt,'Session/candidate identity differs')
 require(report.get('boot_id')==capture.name.removeprefix('boot-') and capture.name.startswith('boot-'),'Boot/session identity differs')
 require(report.get('owner_sha256')==receipt['artifact_sha256']['asc-graph-init/asc-graph-init.ko'] and report.get('candidate_receipt_sha256')==sha((candidate/'asc-root-envelope/build-receipt.json').read_bytes()),'Owner/receipt identity differs')
 pins=report['capture_pins'];require(len({p['name'] for p in pins})==len(pins),'Duplicate capture input pin')
 captured={}
 for pin in pins:
  name=pin['name'];require('/' not in name,'Capture filename differs');raw=(capture/name).read_bytes()
  require(len(raw)==pin['bytes'] and sha(raw)==pin['sha256'],'Capture input changed: '+name);captured[name]=raw
 require(all(name in captured for name in ('objects-after.bin','owned-after.bin','notifications-after.bin','target-after.bin','dmesg-before.log','dmesg-after.log','text.bin')),'Capture inputs missing')
 require('retained-ram-capture.json' in captured,'Retained RAM outcome missing')
 retained=json.loads(captured['retained-ram-capture.json'])
 require(report.get('retained_RAM')==retained and report.get('retained_RAM_complete')==retained.get('complete'),'Retained RAM outcome differs')
 require(retained.get('boot_id')==report.get('boot_id') and retained.get('GPU_commands')==[] and retained.get('GPU_register_reads') is False and retained.get('firmware_RAM_writes') is False and retained.get('owner_unload_OFF_PMput_free') is False,'Retained RAM scope differs')
 for sampler in retained['samplers']:
  pin=sampler.get('capture')
  if pin:
   require(pin['name'] in captured and len(captured[pin['name']])==pin['bytes'] and sha(captured[pin['name']])==pin['sha256'],'Retained RAM raw capture differs')
 require(report.get('text_sha256')==sha(captured['text.bin']) and isinstance(report.get('text_contract'),dict),'Captured runtime TEXT identity differs')
 before=captured['dmesg-before.log'].decode();after=captured['dmesg-after.log'].decode()
 try:
  association,delta=associate_logs(before,after);require(captured.get('operation-delta.log',b'').decode()==delta,'Operation delta differs')
 except ValueError as error:association=dict(qualified=False,error=str(error));delta=''
 require(report.get('log_association')==association and report.get('operation_uncertain')==(not association['qualified']),'Saved association/outcome differs')
 require(sha(before.encode())==report['dmesg_before_sha256'] and sha(after.encode())==report['dmesg_after_sha256'],'Saved log pins differ')
 try:pipeline=qualify_pipeline(delta)
 except ValueError as error:pipeline=dict(qualified=False,error=str(error))
 try:publication=qualify_publication(delta)
 except ValueError as error:publication=dict(qualified=False,error=str(error))
 try:trace_restore=qualify_trace_preserved(delta)
 except ValueError as error:trace_restore=dict(qualified=False,error=str(error),typed_rows=rows(delta,'gfx-native-dispatch-trace'))
 owned=captured['owned-after.bin'];graph=captured['objects-after.bin']
 require(len(owned)==174*16384 and len(graph)==69*16384,'Owned/object capture extent differs')
 target=owned[132*16384:133*16384];require(target==captured['target-after.bin'],'Target extraction differs')
 for name,first,count in [('completion-after.bin',159,1),('queues-after.bin',160,4),('hardware-completions-after.bin',164,4)]:require(captured.get(name)==owned[first*16384:(first+count)*16384],'Owned extraction differs: '+name)
 initial=(candidate/'asc-graph-init/backing.bin').read_bytes();require(len(initial)==56*16384,'Draw backing extent differs')
 target_receipt=json.loads((candidate/'analysis-inputs/target-receipt.json').read_text());image=check_full(target_receipt,target)
 decoded=runpy.run_path(str(HERE.parent/'decode-receive-journal.py'))['decode'](captured['notifications-after.bin'])
 root=[]
 for index,offset in [(0,344064),(1,376832),(12,737280)]:
  root.append(dict(channel=index,cursors=[struct.unpack_from('<I',graph,offset+j)[0] for j in (0,8,16)]))
 firmware_accepted=bool(publication['qualified'] and all(r['cursors']==[1,1,1] for r in root[:2]))
 changed=[]
 for i in range(56):
  old=initial[i*16384:(i+1)*16384];new=owned[(112+i)*16384:(113+i)*16384]
  n=sum(a!=b for a,b in zip(old,new))
  if n:changed.append(dict(backing_page=i,owned_page=112+i,changed_bytes=n))
 diagnostics=diagnostic_observations(delta)
 result=dict(schema='m4rch.gfx-native-fender-runtime-cycle-analysis.v1',boot_id=report['boot_id'],owner_sha256=report['owner_sha256'],candidate_receipt_sha256=report['candidate_receipt_sha256'],source_attempt_sha256=sha(attempt_bytes),log_association=association,pipeline=pipeline,publication=publication,trace_preserved=trace_restore,root_channels=root,firmware_accepted_draw=firmware_accepted,whole_image=image,changed_backing_pages=changed,retained_RAM=retained,receive_journal=dict(header=decoded['header'],authoritative_records_sha256=decoded['authoritative_records_sha256']),raw_post_submit_observations=diagnostics.pop('raw_post_submit_observations'),diagnostic_provenance=diagnostics,
  hardware_activity_decoded=False,stage_completion_verified=False,gpu_execution_verified=False,rendering_verified=False,dma_retirement_verified=False,
  qualification='Only this operation delta and exact full retained dumps are analyzed. Firmware cursor movement is acceptance; raw registers/ring changes/events remain unclassified until job/stage association is decoded. Full image comparison is conditional on the source-derived provisional layout. All resources and PM remain retained.')
 # Detect input replacement while computing the result.
 for pin in pins:require(sha((capture/pin['name']).read_bytes())==pin['sha256'],'Capture changed during analysis')
 require((capture/'attempt.json').read_bytes()==attempt_bytes and validate_candidate(candidate)==receipt,'Attempt/candidate changed during analysis')
 output.mkdir(parents=True,exist_ok=False)
 (output/'target.bin').write_bytes(target);(output/'target.png').write_bytes(png(target))
 (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 return result
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('candidate',type=Path);p.add_argument('output',type=Path);a=p.parse_args();print(json.dumps(analyze(a.capture,a.candidate,a.output)))
if __name__=='__main__':main()
