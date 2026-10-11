#!/usr/bin/env python3
"""Validate exact cold firmware and establish one retained no-work OFF owner.
Requires graph mode; rejects old/reset contracts, cycles and warm restart.
Performs one bounded OFF after immutable capture; retains backing.
"""
import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import threading
import runpy
import sys
from pathlib import Path
BASE_KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_KIT))
from live_graph_observer import observe
from pathlib import Path
from adt import parse
from firmware_text_contract import qualify
from cold_render_contract import validate_receipt, validate_candidate, qualify_adt, qualify_linux_dt, REFUSED_BOOTS, ATTEMPT_SCHEMA, module_build_note, log_delta


def owner_parameters(receipt, *, graph=False, arena=False, warm_restart=False):
    require(validate_receipt(receipt) and graph and not arena and not warm_restart,'Only cold graph mode is admitted')
    return ['run_gate=2','observe_ms=5000','resident_session=1']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, explanation):
    if not condition:
        raise ValueError(explanation)


def capture(module, sysfile, output, name):
    subprocess.run(['insmod', str(module)], check=True)
    try:
        data = Path(sysfile).read_bytes()
        output.write_bytes(data)
        return data
    finally:
        subprocess.run(['rmmod', name], check=True)


def initialized_graph(seed,snapshot):
    require(len(seed)==69*16384 and len(snapshot)==39884,'Power overlay source extent differs')
    image=bytearray(seed);cursor=0
    for offset,size in [(0x30000,0x6578),(0x8000,0x2718),(0xc000,0xe58),(0x4f100,0xe4)]:
        image[offset:offset+size]=snapshot[cursor:cursor+size];cursor+=size
    require(cursor==len(snapshot),'Power overlay consumption differs')
    return bytes(image)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('workspace', type=Path)
    p.add_argument('--run', action='store_true')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--arena', action='store_true', help='Mapping/retirement only; never publish a root')
    mode.add_argument('--graph', action='store_true', help='Structural initialization; backing pins unless the qualified shutdown release succeeds')
    p.add_argument('--cycle',type=int,choices=(1,2,3),help='Separate lifecycle capture; requires validated predecessor unload after cycle1')
    p.add_argument('--warm-restart-from',type=Path,help='Experimental stopped6e HELLO replay, only after validated prior detach/unload')
    args = p.parse_args()
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    require(bool(boot) and boot not in REFUSED_BOOTS, 'Consumed boot refused before candidate or live reads')
    require(args.warm_restart_from is None or (args.graph and args.cycle is None),'Warm restart is graph-only and separate from numbered cycles')
    require(args.cycle is None or args.graph,'Cycles only apply to graph lifecycle trial')
    require(args.graph and not args.arena and args.cycle is None and args.warm_restart_from is None,"Only one fresh cold triangle is admitted")
    work = args.workspace.resolve()
    build = work/'asc-root-envelope'
    receipt = validate_candidate(work)
    power_off_scope = validate_receipt(receipt)
    require(power_off_scope, 'Only the distinct powergate contract is admitted')
    require(sha((work/'asc-graph-init/graph-before.bin').read_bytes()) == receipt['graph_fixture_sha256'], 'Prepared graph fixture changed')
    require(sha((work/'asc-graph-init/graph-receipt.json').read_bytes()) == receipt['graph_receipt_sha256'], 'Prepared graph receipt changed')
    for name, expected in receipt['graph_source_sha256'].items():
        require('/' not in name and sha((work/'asc-graph-init'/name).read_bytes()) == expected,
                'Prepared owner source changed: ' + name)
    require(not (power_off_scope and args.cycle is not None), 'Power-off scope forbids lifecycle cycles')
    parameters = owner_parameters(receipt, graph=args.graph, arena=args.arena,
                                  warm_restart=args.warm_restart_from is not None)
    require(os.geteuid() == 0, 'Native sudo required')
    require(os.uname().release == receipt['kernel_release'], 'Kernel release mismatch')
    require(sha(Path('/sys/kernel/notes').read_bytes()) == receipt['kernel_notes_sha256'], 'Kernel identity mismatch')
    linux_dt_resource_layout = qualify_linux_dt()
    for relative, digest in receipt['artifact_sha256'].items():
        require(sha((work/relative).read_bytes()) == digest, 'Artifact mismatch: '+relative)
    modules = Path('/proc/modules').read_text()
    for line in modules.splitlines():
        name = line.split()[0]
        require(not (name.startswith('asc_') or name in ['asahi_m4', 'resource_overlay', 'gfx_power_test', 'gpu_data_sample', 'm4rch_gpu_adt']), 'Conflicting module: '+name)
    require(boot not in REFUSED_BOOTS, 'Old terminal owner boot is refused; fresh normal boot required')
    out = (work/'asc-graph-init' if args.graph else work/'asc-arena-preflight' if args.arena else build)/('boot-'+boot)
    if args.cycle is not None:
        require(receipt.get('graph_release_on_shutdown',False),'Cycle requires release-enabled candidate')
        if args.cycle>1:
            previous=out/f'cycle-{args.cycle-1}'/'attempt.json'
            require(previous.exists(),'Previous lifecycle capture missing')
            prev=json.loads(previous.read_text())
            require(prev.get('post_unload_verified') and prev.get('graph_retirement_verified') and prev.get('unloaded'),'Previous lifecycle release not verified')
            require(prev['validated_build_receipt']==receipt,'Candidate changed across lifecycle cycles')
        out=out/f'cycle-{args.cycle}'
    if args.warm_restart_from is not None:
        require(receipt.get('graph_release_on_shutdown',False),'Warm restart requires release candidate')
        prev=json.loads((args.warm_restart_from/'attempt.json').read_text())
        require(prev['boot_id']==boot and prev.get('post_unload_verified') and prev.get('graph_retirement_verified') and prev.get('unloaded'),'Prior release not verified on this boot')
        require(prev['validated_build_receipt']['graph_fixture_sha256']==receipt['graph_fixture_sha256'] and prev['validated_build_receipt']['kernel_notes_sha256']==receipt['kernel_notes_sha256'],'Warm fixture/kernel changed')
        out=out/'warm-restart-1'
    require(not out.exists(), 'An existing cold session forbids another load')
    out.mkdir(parents=True,exist_ok=False)
    require(not (out/'attempt.json').exists() and not (out/'result.json').exists(), 'Attempt already recorded for this boot; do not repeat')
    raw = capture(work/'adt-current/m4rch_gpu_adt.ko', '/sys/kernel/m4rch_gpu_adt/adt', out/'boot.adt', 'm4rch_gpu_adt')
    tree = parse(raw)
    fresh_power_adt=qualify_adt(tree)
    chosen = tree['/device-tree/chosen']
    sgx = tree['/device-tree/arm-io/sgx']
    require(chosen['firmware-version'].rstrip(b'\0') == b'mBoot-18000.161.10', 'Loader firmware mismatch')
    require(int.from_bytes(chosen['chip-id'], 'little') == 0x6040, 'Chip mismatch')
    for key, expected in {'gfx-shared-region-base':0x105fff78000, 'gfx-shared-region-size':0x40000,
                          'gfx-data-base':0x10001d44000, 'gfx-data-size':0x138000,
                          'gpu-region-base':0x105fffb8000, 'gpu-region-size':0x4000,
                          'gfx-shared-l2-region-base':0x105fff74000, 'gfx-shared-l2-region-size':0x4000}.items():
        require(int.from_bytes(sgx[key], 'little') == expected, 'Fresh ADT range mismatch: '+key)
    if args.graph:
        layout = json.loads((work/'asc-graph-init/graph-receipt.json').read_text())
        from owned_gpu_layout import validate
        validate((work/'asc-graph-init/graph-before.bin').read_bytes(),layout)
        for key,digest in layout.get('voltage_input_sha256',{}).items():
            require(sha(sgx[key])==digest,'Fresh voltage input differs: '+key)
        native_init=layout.get('native_init_recovery')
        if native_init is not None:
            require(not any('no-gpc' in node for node in tree.values()),'Fresh ADT overrides native GPC policy')
            require(int.from_bytes(sgx['has-kf'],'little')==1,'Fresh auxiliary board guard differs')
            for domain in native_init['auxiliary_power']['domains']:
                key=domain['adt_property']
                require(sha(sgx[key])==domain['adt_property_sha256'],'Fresh auxiliary voltage input differs: '+key)
        if layout.get('recovery_progress_trial'):
            for key in ('gpu-idle-off-delay-ms', 'gpu-fender-idle-off-delay-ms'):
                require(not any(key in node for node in tree.values()),
                        'Fresh ADT overrides the staged native idle default: '+key)
        timing=layout.get('power_timing_trial')
        if timing is not None:
            require(int.from_bytes(sgx['gpu-pwr-sample-period-aic-clks'],'little')==timing['period_aic_clocks'],'Fresh AIC sampling period differs')
            require(int.from_bytes(sgx['gpu-power-sample-period'],'little')==timing['period_ms'],'Fresh millisecond sampling period differs')
        regs=list(struct.iter_unpack('<QQ',sgx['reg']))
        require(regs==[(0x88000000,0x3758000),(0x88d00000,0x16c000)],'SGX MMIO apertures differ')
        for leaf in layout.get('mmio_leaves',[]):
            pa,va=leaf['physical'],leaf['gpu_va']
            platform=(pa,va) in ((0x502414000,0xfffffc2001a00000),(0x5003d0000,0xfffffc2001b10000),(0x5003d8000,0xfffffc2001b18000))
            afr=0x28b000000<=pa<0x28b640000 and (pa-0x28b000000)%0x200000<0x40000 and va==0xfffffc2001c00000+(pa-0x28b000000)//0x200000*0x40000+(pa-0x28b000000)%0x200000
            sgx=0x288000000<=pa and pa+0x4000<=0x28b758000 and va==0xfffffc2000200000+pa-0x288000000
            require((platform and not leaf['readonly']) or (afr and (leaf['readonly'] or (pa-0x28b000000)%0x10000==0)) or (sgx and (leaf['readonly'] or pa in (0x288000000,0x288004000,0x288008000,0x28800c000,0x288010000,0x288014000,0x288018000,0x28801c000,0x288020000,0x288d04000,0x288d10000,0x288d40000,0x288d44000,0x288d4c000,0x288d60000,0x288e00000,0x288e1c000,0x288e40000,0x289004000))),'Unqualified MMIO leaf range')
    tables = capture(work/'sample-pagetables/gpu-data-sample.ko', '/sys/kernel/m4rch_gpu_data_sample/data', out/'pagetables.bin', 'gpu_data_sample')
    base = 0x105fff78000
    def translate(va):
        table = base
        for shift, mask in [(36,63),(25,2047),(14,2047)]:
            offset = table-base+((va>>shift)&mask)*8
            require(0 <= offset <= len(tables)-8, 'Table outside captured reservation')
            entry = struct.unpack_from('<Q', tables, offset)[0]
            if not entry&1:
                return None
            require(entry&3 == 3, 'Unexpected block descriptor')
            table = entry&0x3ffffffc000
        return table+(va&0x3fff)
    initial_tables_zero = not any(tables)
    if not initial_tables_zero:
        require(translate(0xfffffc0000000000) == 0x10000be4000, 'TEXT mapping mismatch')
        require(translate(0xfffffc0000060000) == 0x10001d44000, 'DATA mapping mismatch')
    # On a genuinely cold boot the firmware populates these tables during its
    # handshake. The native probe checks the completed path before installing.

    slot=struct.unpack_from('<Q',tables,16)[0]
    if ((args.cycle is not None and args.cycle>1) or args.warm_restart_from is not None) and slot==0x200105fff744cb:
        retained_l2=capture(work/'arena-l2-sample/gpu-data-sample.ko','/sys/kernel/m4rch_gpu_data_sample/data',out/'l2-before-restart.bin','gpu_data_sample')
        require(not any(retained_l2),'Owned loader child remains occupied before restart')
    else:
        require(slot==0,'Candidate top-level slot occupied')
    text = capture(work/'root-text-sample/gpu-data-sample.ko', '/sys/kernel/m4rch_gpu_data_sample/data', out/'text.bin', 'gpu_data_sample')
    text_contract = qualify(text)
    # Instruction and string checks qualify the intended early rejection path.
    for offset, word in {0x2f250:0xf9400109,0x2f264:0xeb0a013f,0x2f268:0x54003d61,
                         0x2f2b4:0xb9402d29,0x2f2b8:0x34003b49,0x2fa2c:0x94004f40}.items():
        require(struct.unpack_from('<I',text,offset)[0] == word, 'Parser instruction mismatch')
    require(text[0x5b768:].startswith(b'Host-mapped FW allocations are disabled'), 'Rejection string mismatch')
    report = {'boot_id':boot, 'linux_dt_resource_layout':linux_dt_resource_layout, 'adt_sha256':sha(raw), 'fresh_power_adt':fresh_power_adt, 'tables_sha256':sha(tables), 'initial_tables_zero':initial_tables_zero,
              'text_sha256':sha(text), 'text_contract':text_contract, 'validated_build_receipt':receipt, 'run_requested':args.run, 'mapping_or_publication_performed':False}
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    if not args.run:
        print('Fresh metadata, table path and exact firmware parser validated; sampler helpers unloaded. No root mapping or firmware publication.')
        return
    # Persist intent and logs before any power/MMIO/PTE change.
    (out/'attempt.json').write_text(json.dumps({'boot_id':boot,'stage':'about to load','reboot_may_be_required':True},indent=2)+'\n')
    before = capture(work/'root-data-sample/gpu-data-sample.ko', '/sys/kernel/m4rch_gpu_data_sample/data', out/'data-before.bin', 'gpu_data_sample')
    (out/'dmesg-before.log').write_text(subprocess.check_output(['dmesg','--color=never'],text=True))
    (out/'interrupts-before.txt').write_text(Path('/proc/interrupts').read_text())
    os.sync()
    selected = work/'asc-graph-init/asc-graph-init.ko' if args.graph else work/'asc-arena-preflight/asc-arena-preflight.ko' if args.arena else build/'asc-root-envelope.ko'
    if args.graph:
        require(sha((work/'asc-graph-init/graph-before.bin').read_bytes()) == receipt['graph_fixture_sha256'], 'Graph fixture changed')
        require(sha((work/'asc-graph-init/graph-receipt.json').read_bytes()) == receipt['graph_receipt_sha256'], 'Graph relocation receipt changed')
        shadow = subprocess.run(['insmod',str(selected),'run_gate=1'],capture_output=True,text=True)
        report['shadow_load'] = dict(parameters=['run_gate=1'], returncode=shadow.returncode,
                                     stdout=shadow.stdout, stderr=shadow.stderr)
        (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\n')
        os.sync()
        require(shadow.returncode == 0, 'Owned graph allocation/shadow walk failed: '+shadow.stderr)
        subprocess.run(['rmmod','asc_graph_init'],check=True)
        (out/'objects-before.bin').write_bytes((work/'asc-graph-init/graph-before.bin').read_bytes())
    observer=None;done=threading.Event()
    if args.graph and not receipt.get('graph_recovery_trial'):
        layout=json.loads((work/'asc-graph-init/graph-receipt.json').read_text())
        observer=threading.Thread(target=observe,args=(Path('/sys/kernel/m4rch_gpu_graph_trial/objects'),out/'live-objects',layout,done),daemon=True)
        observer.start()
    try:
        report.update(schema=ATTEMPT_SCHEMA, boot_id=boot, session=str(out), stage='cold-load-intent', automatic_pipeline_intent=True, complete=False, operation_uncertain=True, selected_module=str(selected), cold_parameters=parameters, owner_sha256=sha(selected.read_bytes()), candidate_receipt_sha256=sha((work/'asc-root-envelope/build-receipt.json').read_bytes()))
        (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\n')
        os.sync()
        result = subprocess.run(['insmod',str(selected)]+parameters,capture_output=True,text=True)
    finally:
        done.set()
        if observer is not None:observer.join(timeout=5)
    if args.graph and not receipt.get('graph_recovery_trial'):
        observations=out/'live-objects/observations.json'
        report['live_observation']=json.loads(observations.read_text()) if observations.exists() else {'error':'Observer did not produce a completed report'}
    logs = subprocess.check_output(['dmesg','--color=never'],text=True)
    (out/'dmesg-after.log').write_text(logs)
    (out/'interrupts-after.txt').write_text(Path('/proc/interrupts').read_text())
    if args.arena:
        module_path = Path('/sys/module/asc_arena_preflight')
        present = module_path.exists()
        count = int((module_path/'refcnt').read_text()) if present else None
        before_log = (out/'dmesg-before.log').read_text()
        delta = logs[len(before_log):] if logs.startswith(before_log) else logs
        retired = 'application-start-only retirement verified; normal unload allowed' in delta
        unloaded = False
        if present and result.returncode == 0 and count == 0 and retired:
            subprocess.run(['rmmod','asc_arena_preflight'],check=True)
            unloaded = True
        final = subprocess.check_output(['dmesg','--color=never'],text=True)
        (out/'dmesg-after-unload.log').write_text(final)
        report.update(load_returncode=result.returncode,stderr=result.stderr,
                      root_published=False,mapping_or_publication_performed=f"{receipt['arena_object_pages']} object pages mapped" in delta,
                      expected_object_pages=receipt['arena_object_pages'],
                      mapped_expected_pages=f"{receipt['arena_object_pages']} object pages mapped" in delta,
                      retirement_verified=retired,unloaded=unloaded,reboot_required=present and not unloaded,
                      interpretation='Allocation/mapping/retirement only; no root address sent or object reads established.')
        (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\n')
        if unloaded:
            table = capture(work/'sample-pagetables/gpu-data-sample.ko', '/sys/kernel/m4rch_gpu_data_sample/data', out/'tables-after-unload.bin', 'gpu_data_sample')
            l2 = capture(work/'arena-l2-sample/gpu-data-sample.ko', '/sys/kernel/m4rch_gpu_data_sample/data', out/'l2-after-unload.bin', 'gpu_data_sample')
            require(len(table)==0x40000 and len(l2)==0x4000, 'Unexpected post-unload table extent')
            owned_pages = [int(pa,16) for pa in re.findall(r'owned page \d+ physical=(0x[0-9a-f]+)',delta)]
            mask = ((1<<42)-1)&~0x3fff
            references = [hex(word) for blob in (table,l2) for (word,) in struct.iter_unpack('<Q',blob)
                          if (word & 3)==3 and (word & mask) in owned_pages]
            report.update(post_unload_tables_sha256=sha(table),post_unload_l2_sha256=sha(l2),
                          owned_page_count=len(owned_pages),owned_page_references=references,
                          reserved_l2_zero=not any(l2),
                          post_unload_verified=len(owned_pages)==receipt['arena_object_pages']+2 and not references and not any(l2))
        (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\n')
        os.sync()
        print('Arena preflight retired and unloaded; no pinned resources.' if unloaded else 'Arena preflight refused or retained resources; inspect evidence.')
        return
    present = Path('/sys/module/asc_graph_init').exists()
    before_log=(out/'dmesg-before.log').read_text()
    report.update(schema=ATTEMPT_SCHEMA,boot_id=boot,session=str(out),candidate=str(work),
      selected_module=str(selected),owner_sha256=sha(selected.read_bytes()),
      candidate_receipt_sha256=sha((work/'asc-root-envelope/build-receipt.json').read_bytes()),
      dmesg_before_sha256=sha(before_log.encode()),dmesg_after_sha256=sha(logs.encode()),
      load_returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,module_present=present,
      complete=False,operation_uncertain=True,capture_errors=[],capture_pins=[],
      allocations_retained=True,pm_retained=True,unloaded=False,commands_admitted=[],
      interpretation='Automatic cold-render attempt; retained resources and PM, no work reuse or teardown.')
    (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\n');os.sync()
    try:
        if not present:raise ValueError('Owner absent after load; outcome and retirement unknown')
        pinned=Path('/sys/module/asc_graph_init')
        note=(pinned/'notes/.note.gnu.build-id').read_bytes()
        require(note==module_build_note(selected.read_bytes()),'Loaded owner GNU note differs')
        require(int((pinned/'refcnt').read_text())==1,'Owner refcount differs from retained1')
        report['loaded_owner_note_hex']=note.hex()
        for name,sysfile,size in [('objects-after.bin','objects',receipt['graph_object_pages']*0x4000),
           ('owned-after.bin','owned',receipt['joined_owned_pages']*0x4000),
           ('notifications-after.bin','notifications',None)]:
            raw=Path('/sys/kernel/m4rch_gpu_graph_trial',sysfile).read_bytes()
            if size is not None:require(len(raw)==size,'Captured extent differs: '+name)
            (out/name).write_bytes(raw)
        initial=Path('/sys/kernel/m4rch_gpu_graph_trial/full-power-initialized').read_bytes()
        require(len(initial)==39884,'Initialized full-power snapshot extent differs')
        (out/'full-power-initialized.bin').write_bytes(initial)
        seeded=initialized_graph((work/'asc-graph-init/graph-before.bin').read_bytes(),initial)
        (out/'objects-before.bin').write_bytes(seeded)
        report['dynamic_power_initial_snapshot']=dict(bytes=len(initial),sha256=sha(initial),source='retained CPU scratch before root publication; HW refreshed after timestamp binding')
        decoded=runpy.run_path(str(BASE_KIT/'decode-receive-journal.py'))['decode']((out/'notifications-after.bin').read_bytes())
        (out/'notifications-after.json').write_text(json.dumps(decoded,indent=2)+'\n')
        owned=(out/'owned-after.bin').read_bytes()
        for name,first,count in [('target-after.bin',132,1),('completion-after.bin',159,1),('queues-after.bin',160,4),('hardware-completions-after.bin',164,4)]:
            (out/name).write_bytes(owned[first*0x4000:(first+count)*0x4000])
        from readback import png
        (out/'target-after.png').write_bytes(png((out/'target-after.bin').read_bytes()))
        from readback import capture_retained_ram
        report['retained_RAM']=capture_retained_ram(work,out,selected,boot,receipt)
        report['retained_RAM_complete']=report['retained_RAM']['complete']
        (out/'dmesg-after-samplers.log').write_text(subprocess.check_output(['dmesg','--color=never'],text=True))
        from cold_render_contract import associate_logs
        from analyze_cold_render import qualify_pipeline,qualify_trace_preserved,qualify_publication
        try:
            association,delta=associate_logs(before_log,logs)
            report['log_association']=association
            (out/'operation-delta.log').write_text(delta)
            for key,qualifier in [('pipeline',qualify_pipeline),('publication',qualify_publication),('trace_preserved',qualify_trace_preserved)]:
                try:report[key]=qualifier(delta)
                except ValueError as error:report[key]={'qualified':False,'error':str(error)}
        except ValueError as error:
            report['log_association']={'qualified':False,'error':str(error)}
            for key in ('pipeline','publication','trace_preserved'):report[key]={'qualified':False,'error':'Saved logs have no exact association'}
        report.update(complete=True,raw_capture_complete=True,operation_uncertain=not report['log_association']['qualified'],stage='capture-closed')
    except Exception as error:
        report['capture_errors'].append(str(error));report['stage']='capture-unknown-retained'
    for name in ('full-power-initialized.bin','objects-before.bin','objects-after.bin','owned-after.bin','notifications-after.bin','notifications-after.json','target-after.bin','completion-after.bin','queues-after.bin','hardware-completions-after.bin','target-after.png','dmesg-before.log','dmesg-after.log','operation-delta.log','text.bin','data-retained.bin','pagetables-retained.bin','retained-ram-capture.json','dmesg-after-samplers.log'):
        path=out/name
        if path.exists():raw=path.read_bytes();report['capture_pins'].append(dict(name=name,bytes=len(raw),sha256=sha(raw)))
    (out/'attempt.json').write_text(json.dumps(report,indent=2)+'\n');os.sync()
    if report['complete']:
        from analyze_cold_render import analyze
        try:analyze(out,work,out/'analysis')
        except Exception as error:
            report['analysis_error']=str(error);(out/'attempt.json').write_text(json.dumps(report,indent=2)+'\n');os.sync()
    from readback import attempt_postdraw_cycle
    cycle=attempt_postdraw_cycle(work,out,selected,boot,receipt)
    print('Draw capture saved; postdraw native cycle outcome: '+cycle['stage'])

if __name__ == '__main__':
    main()
